"""双色球数据管理器 - 整合爬虫与数据库，提供统一的数据访问接口。"""

from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional

from .database import SSQDatabase
from .models import SSQRecord
from .spider import SSQSpider

logger = logging.getLogger(__name__)


class DataManager:
    """
    数据管理入口类，负责数据拉取与持久化。

    使用示例::

        dm = DataManager()
        dm.update_latest()          # 增量更新最新一期
        dm.update_year(2024)       # 补充某年缺失数据
        records = dm.get_recent(100)  # 获取最近100期
    """

    def __init__(self, db_path: str | None = None, spider_interval: float = 1.0):
        self.db = SSQDatabase(db_path)
        self.spider = SSQSpider(interval=spider_interval)

    # ─────────────────────────────────────────
    # 数据查询
    # ─────────────────────────────────────────

    def get_all(self) -> List[SSQRecord]:
        """返回数据库中所有记录。"""
        return self.db.get_all()

    def get_recent(self, n: int = 100, year: int | None = None) -> List[SSQRecord]:
        """返回最近 n 期记录，可按年份过滤。"""
        return self.db.get_recent(n, year)

    def get_range(self, start_date: date | str, end_date: date | str) -> List[SSQRecord]:
        """按日期范围查询。"""
        return self.db.get_range(start_date, end_date)

    def get_by_period(self, period: str) -> Optional[SSQRecord]:
        """按期号查询单条记录。"""
        return self.db.get_by_period(period)

    def get_by_date(self, draw_date: date | str) -> Optional[SSQRecord]:
        """按开奖日期查询单条记录（精确匹配，返回该日最新一期）。"""
        return self.db.get_by_date(draw_date)

    def get_latest(self) -> Optional[SSQRecord]:
        """获取本地数据库中最新一期记录。"""
        return self.db.get_latest()

    def count(self) -> int:
        """返回数据库中总记录数。"""
        return self.db.count()

    # ─────────────────────────────────────────
    # 数据拉取
    # ─────────────────────────────────────────

    def update_latest(self) -> tuple[int, Optional[SSQRecord]]:
        """
        从网络抓取最新一期数据并写入数据库。

        Returns:
            (插入状态, 记录对象)
            - 插入状态: 1=新增成功, 0=已存在, -1=抓取失败
        """
        logger.info("正在抓取最新一期数据...")
        record = self.spider.fetch_latest()
        if not record:
            logger.error("抓取失败，无法获取最新数据")
            return -1, None

        if self.db.exists(record.period):
            logger.info(f"期号 {record.period} 已存在，跳过")
            return 0, record

        self.db.insert(record)
        logger.info(f"新增记录: {record}")
        return 1, record

    def update_recent(self) -> tuple[int, Optional[SSQRecord], int]:
        """
        智能刷新：抓取最新一期 + 补齐当前年份缺失数据。

        适用于日常使用场景——几天未启动后，一次点击补齐所有空档。

        Returns:
            (最新期状态, 最新记录, 当前年新增总数)
            - 最新期状态: 1=新增成功, 0=已存在, -1=抓取失败
        """
        # 1. 抓取最新一期
        status, latest = self.update_latest()

        # 2. 补齐当前年份缺失数据
        current_year = date.today().year
        year_inserted = self.update_year(
            current_year,
            progress=False,
            on_insert=None,
            on_skip=None,
        )

        if year_inserted > 0:
            logger.info(f"已补齐 {current_year} 年缺失数据 {year_inserted} 条")

        return status, latest, year_inserted

    def update_year(
        self,
        year: int,
        progress: bool = True,
        on_insert: callable | None = None,
        on_skip: callable | None = None,
    ) -> int:
        """
        补充指定年份的所有期次数据。

        Args:
            year: 要更新的年份，如 2024
            progress: 是否打印进度
            on_insert: 每新增一条记录时的回调，签名为 on_insert(record)
            on_skip: 每跳过一条记录时的回调，签名为 on_skip(record)

        Returns:
            成功新增的记录数
        """
        logger.info(f"正在抓取 {year} 年数据...")
        inserted = 0
        for record in self.spider.fetch_year(year):
            if self.db.insert(record):
                inserted += 1
                if on_insert:
                    on_insert(record)
                elif progress:
                    print(f"  [+] {record}")
            else:
                if on_skip:
                    on_skip(record)
                elif progress:
                    print(f"  [=] {record.period} 已存在")

        logger.info(f"{year} 年数据更新完成，新增 {inserted} 条")
        return inserted

    def update_range(
        self,
        start_period: str,
        end_period: str,
        on_insert: callable | None = None,
    ) -> int:
        """
        抓取指定期号范围的数据。

        Returns:
            成功新增的记录数
        """
        logger.info(f"抓取期号范围: {start_period} ~ {end_period}")
        inserted = 0
        for record in self.spider.fetch_range(start_period, end_period):
            if self.db.insert(record):
                inserted += 1
                if on_insert:
                    on_insert(record)
                else:
                    print(f"  [+] {record}")
        logger.info(f"范围更新完成，新增 {inserted} 条")
        return inserted

    def update_all(self, on_insert: callable | None = None) -> int:
        """
        全量重拉：从最早可查年份（2003年，双色球首发）到现在，逐年拉取。

        注意：此操作会保留数据库中已有记录，仅补充缺失数据。
        已存在的期号会自动跳过（INSERT OR IGNORE）。
        如需强制全量重建，请先调用 clear() 再调用本方法。

        Returns:
            新增记录总数
        """
        from datetime import date as _date

        logger.info("开始全量数据更新...")
        current_year = _date.today().year
        inserted = 0
        _no_op = lambda r: None

        for year in range(2003, current_year + 1):
            logger.info(f"正在拉取 {year} 年数据...")
            count = self.update_year(
                year,
                progress=False,
                on_insert=on_insert,
                on_skip=_no_op,
            )
            inserted += count
            logger.info(f"{year} 年完成，新增 {count} 条")

        logger.info(f"全量更新完成，共新增 {inserted} 条记录")
        return inserted

    def clear(self) -> int:
        """清空数据库（慎用！）。返回删除的记录数。"""
        count = self.db.count()
        self.db.delete_all()
        logger.warning(f"已清空数据库，删除了 {count} 条记录")
        return count