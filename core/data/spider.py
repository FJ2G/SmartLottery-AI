"""双色球历史数据爬虫 - 从 500彩票网 抓取开奖数据。"""

from __future__ import annotations

import re
import time
import logging
from datetime import date, datetime
from typing import Iterator, List, Optional

import requests
from bs4 import BeautifulSoup

from .models import SSQRecord

logger = logging.getLogger(__name__)

# 500彩票网 - 双色球历史数据页面
BASE_URL = "https://datachart.500.com/ssq/history/newinc/history.php"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://datachart.500.com/",
}

# 请求间隔（秒），避免被封
REQUEST_INTERVAL = 1.0
MAX_RETRIES = 3


class SSQSpider:
    """双色球数据爬虫。"""

    def __init__(self, interval: float = REQUEST_INTERVAL):
        self.interval = interval
        self._session = requests.Session()
        self._session.headers.update(HEADERS)

    def _fetch_page(self, url: str) -> Optional[str]:
        """带重试的页面抓取。"""
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._session.get(url, timeout=15)
                resp.raise_for_status()
                resp.encoding = "utf-8"
                return resp.text
            except requests.RequestException as e:
                logger.warning(f"[{attempt + 1}/{MAX_RETRIES}] 请求失败: {url} — {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
        return None

    def _parse_period(self, period_str: str) -> Optional[str]:
        """
        标准化期号格式，统一转为5位短格式 YYNNN。
        输入如 '2025001'、'25001'、'2025-001' -> 返回 '25001'
        """
        digits = re.sub(r"\D", "", period_str)
        if len(digits) >= 6:
            # 完整格式: 2025001 -> 取后6位再取后5位 -> 25001
            return digits[-6:][-5:]
        elif len(digits) == 5:
            # 已经是短格式: 25001
            return digits
        return None

    def _parse_row(self, tr: BeautifulSoup) -> Optional[SSQRecord]:
        """解析单个表格行 <tr> 为 SSQRecord。"""
        try:
            tds = tr.find_all("td")
            if len(tds) < 2:
                return None

            # 期号在第一个 td
            period_raw = tds[0].get_text(strip=True)
            period = self._parse_period(period_raw)
            if not period:
                return None

            red_balls: List[int] = []
            blue_ball = 0

            # 新格式: 每个球单独一个 td (td[1]-td[6] 红球, td[7] 蓝球)
            # 例如: td[1]=06, td[2]=10, td[3]=12, td[4]=15, td[5]=22, td[6]=28, td[7]=08
            if len(tds) >= 8:
                red_texts = [tds[i].get_text(strip=True) for i in range(1, 7)]
                if all(re.match(r"^\d{1,2}$", t) for t in red_texts):
                    red_balls = [int(t) for t in red_texts]
                    blue_text = tds[7].get_text(strip=True)
                    if re.match(r"^\d{1,2}$", blue_text):
                        blue_ball = int(blue_text)

            # 旧格式 fallback: 红蓝球在同一 td (格式如 "01 05 12 18 25 33 08")
            if not red_balls or blue_ball == 0:
                balls_text = tds[1].get_text(strip=True)
                balls = re.findall(r"\d+", balls_text)
                if len(balls) == 7:
                    red_balls = [int(b) for b in balls[:6]]
                    blue_ball = int(balls[6])

            if len(red_balls) != 6 or blue_ball == 0:
                return None

            # 日期在 td[15] (新格式) 或 td[2] (旧格式)
            date_text = ""
            if len(tds) > 15:
                candidate = tds[15].get_text(strip=True)
                if re.match(r"\d{4}-\d{2}-\d{2}", candidate):
                    date_text = candidate
            if not date_text and len(tds) > 2:
                date_text = tds[2].get_text(strip=True)
            draw_date = self._parse_date(date_text)

            return SSQRecord(
                period=period,
                draw_date=draw_date,
                red_balls=red_balls,
                blue_ball=blue_ball,
            )
        except Exception as e:
            logger.debug(f"解析行失败: {e}")
            return None

    def _parse_date(self, date_str: str) -> date:
        """解析日期字符串。"""
        date_str = date_str.strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日", "%m/%d/%Y"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                pass
        # 回退到当天（日期解析失败时）
        return date.today()

    def fetch_range(self, start_period: str, end_period: str) -> Iterator[SSQRecord]:
        """
        抓取指定期号范围 [start_period, end_period] 内的所有开奖记录。
        500彩票网期号格式为 YYNNN（5位，如 24001）。
        """
        # 规范化：转成5位短格式用于URL和比较
        def to_short(p: str) -> str:
            parsed = self._parse_period(p)
            if parsed and len(parsed) == 7:
                # 完整格式 2026036 -> 26036
                return parsed[2:]
            return p

        period_start = to_short(start_period)
        period_end = to_short(end_period)

        url = f"{BASE_URL}?start={period_start}&end={period_end}"
        logger.info(f"抓取期号范围: {period_start} ~ {period_end}")

        html = self._fetch_page(url)
        if not html:
            logger.error("页面抓取失败")
            return

        soup = BeautifulSoup(html, "html.parser")
        # 目标数据在 <tbody id="tdata"> 内的 <tr> 标签中
        tbody = soup.find("tbody", id="tdata")
        rows = tbody.find_all("tr") if tbody else soup.find_all("tr")

        for tr in rows:
            record = self._parse_row(tr)
            if record and period_start <= record.period <= period_end:
                yield record
                time.sleep(self.interval)

    def fetch_latest(self) -> Optional[SSQRecord]:
        """
        仅抓取最新一期开奖记录。
        """
        # 500彩票网默认返回最新约100条，直接取第一条即可
        url = BASE_URL
        html = self._fetch_page(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        tbody = soup.find("tbody", id="tdata")
        rows = tbody.find_all("tr") if tbody else soup.find_all("tr")

        for tr in rows:
            record = self._parse_row(tr)
            if record:
                return record
        return None

    def fetch_year(self, year: int) -> Iterator[SSQRecord]:
        """
        抓取指定年份的所有期次数据。
        结束期号根据当前时间动态计算（每年约52周，最多约154期）。
        """
        import datetime
        year_code = year - 2000  # 2024 -> 24
        start = f"{year_code:02d}001"
        # 今年：期号上限 = 当前周数 * 3（约）
        today = datetime.date.today()
        if year == today.year:
            # 粗估：一年约52周，每周约3期
            weeks = today.isocalendar()[1]
            end_seq = min(weeks * 3, 154)
        else:
            end_seq = 154
        end = f"{year_code:02d}{end_seq:03d}"
        yield from self.fetch_range(start, end)