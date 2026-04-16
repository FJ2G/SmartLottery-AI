"""双色球 SQLite 数据库操作层。"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Generator, List, Optional

from .models import SSQRecord

# 数据库默认路径：项目根目录下的 data/ssq.db
DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DB_DIR / "ssq.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ssq_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    period      TEXT    NOT NULL UNIQUE,
    draw_date   TEXT    NOT NULL,
    red_1       INTEGER NOT NULL,
    red_2       INTEGER NOT NULL,
    red_3       INTEGER NOT NULL,
    red_4       INTEGER NOT NULL,
    red_5       INTEGER NOT NULL,
    red_6       INTEGER NOT NULL,
    blue        INTEGER NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    CONSTRAINT valid_red_1 CHECK (red_1 BETWEEN 1 AND 33),
    CONSTRAINT valid_red_2 CHECK (red_2 BETWEEN 1 AND 33),
    CONSTRAINT valid_red_3 CHECK (red_3 BETWEEN 1 AND 33),
    CONSTRAINT valid_red_4 CHECK (red_4 BETWEEN 1 AND 33),
    CONSTRAINT valid_red_5 CHECK (red_5 BETWEEN 1 AND 33),
    CONSTRAINT valid_red_6 CHECK (red_6 BETWEEN 1 AND 33),
    CONSTRAINT valid_blue  CHECK (blue  BETWEEN 1 AND 16)
);

CREATE INDEX IF NOT EXISTS idx_ssq_period ON ssq_records(period DESC);
CREATE INDEX IF NOT EXISTS idx_ssq_date   ON ssq_records(draw_date DESC);
"""


class SSQDatabase:
    """双色球数据库管理类。"""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self._ensure_dir()
        self._init_schema()

    def _ensure_dir(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _conn_ctx(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn_ctx() as conn:
            conn.executescript(SCHEMA)

    # ─────────────────────────────────────────
    # CRUD
    # ─────────────────────────────────────────

    def insert(self, record: SSQRecord) -> bool:
        """
        插入一条记录。成功返回 True；如已存在（UNIQUE 冲突）返回 False。
        """
        sql = """
        INSERT OR IGNORE INTO ssq_records
            (period, draw_date, red_1, red_2, red_3, red_4, red_5, red_6, blue)
        VALUES
            (:period, :draw_date, :red_1, :red_2, :red_3, :red_4, :red_5, :red_6, :blue)
        """
        d = record.to_dict()
        d["draw_date"] = record.draw_date.isoformat()
        with self._conn_ctx() as conn:
            cursor = conn.execute(sql, d)
            return cursor.rowcount > 0

    def insert_batch(self, records: List[SSQRecord]) -> int:
        """
        批量插入多条记录。
        返回实际成功插入的行数（排除已存在的）。
        """
        sql = """
        INSERT OR IGNORE INTO ssq_records
            (period, draw_date, red_1, red_2, red_3, red_4, red_5, red_6, blue)
        VALUES
            (:period, :draw_date, :red_1, :red_2, :red_3, :red_4, :red_5, :red_6, :blue)
        """
        rows = 0
        with self._conn_ctx() as conn:
            for r in records:
                d = r.to_dict()
                d["draw_date"] = r.draw_date.isoformat()
                cursor = conn.execute(sql, d)
                rows += cursor.rowcount
        return rows

    def exists(self, period: str) -> bool:
        """检查指定期号是否已存在。"""
        with self._conn_ctx() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM ssq_records WHERE period = ?", (period,)
            )
            return cursor.fetchone() is not None

    def get_by_date(self, draw_date: date | str) -> Optional[SSQRecord]:
        """按开奖日期查询（精确匹配），返回最新一期。"""
        if isinstance(draw_date, date):
            draw_date = draw_date.isoformat()
        with self._conn_ctx() as conn:
            cursor = conn.execute(
                "SELECT * FROM ssq_records WHERE draw_date = ? ORDER BY period DESC LIMIT 1",
                (draw_date,),
            )
            row = cursor.fetchone()
            return SSQRecord.from_row(tuple(row)) if row else None

    def get_by_period(self, period: str) -> Optional[SSQRecord]:
        """按期号查询单条记录。"""
        with self._conn_ctx() as conn:
            cursor = conn.execute(
                "SELECT * FROM ssq_records WHERE period = ?", (period,)
            )
            row = cursor.fetchone()
            return SSQRecord.from_row(tuple(row)) if row else None

    def get_latest(self) -> Optional[SSQRecord]:
        """获取最近一期开奖记录。"""
        with self._conn_ctx() as conn:
            cursor = conn.execute(
                "SELECT * FROM ssq_records ORDER BY period DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return SSQRecord.from_row(tuple(row)) if row else None

    def get_all(self) -> List[SSQRecord]:
        """获取所有记录（按期号降序，最新的在前）。"""
        with self._conn_ctx() as conn:
            cursor = conn.execute(
                "SELECT * FROM ssq_records ORDER BY period DESC"
            )
            return [SSQRecord.from_row(tuple(row)) for row in cursor.fetchall()]

    def get_range(
        self,
        start_date: date | str,
        end_date: date | str,
    ) -> List[SSQRecord]:
        """按日期范围查询记录（闭区间）。"""
        if isinstance(start_date, date):
            start_date = start_date.isoformat()
        if isinstance(end_date, date):
            end_date = end_date.isoformat()
        with self._conn_ctx() as conn:
            cursor = conn.execute(
                """SELECT * FROM ssq_records
                   WHERE draw_date BETWEEN ? AND ?
                   ORDER BY period DESC""",
                (start_date, end_date),
            )
            return [SSQRecord.from_row(tuple(row)) for row in cursor.fetchall()]

    def get_recent(self, n: int = 100, year: int | None = None) -> List[SSQRecord]:
        """获取最近 n 期记录，按日期降序排列。"""
        if year:
            with self._conn_ctx() as conn:
                cursor = conn.execute(
                    "SELECT * FROM ssq_records WHERE draw_date LIKE ? ORDER BY period DESC LIMIT ?",
                    (f"{year}-%", n),
                )
                return [SSQRecord.from_row(tuple(row)) for row in cursor.fetchall()]
        with self._conn_ctx() as conn:
            cursor = conn.execute(
                "SELECT * FROM ssq_records ORDER BY period DESC LIMIT ?",
                (n,),
            )
            return [SSQRecord.from_row(tuple(row)) for row in cursor.fetchall()]

    def count(self) -> int:
        """返回数据库中总记录数。"""
        with self._conn_ctx() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM ssq_records")
            return cursor.fetchone()[0]

    def delete_all(self) -> int:
        """清空所有记录（用于全量重拉）。返回删除行数。"""
        with self._conn_ctx() as conn:
            cursor = conn.execute("DELETE FROM ssq_records")
            return cursor.rowcount

    def get_latest_period(self) -> Optional[str]:
        """获取数据库中最新一期期号。"""
        with self._conn_ctx() as conn:
            cursor = conn.execute(
                "SELECT period FROM ssq_records ORDER BY period DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return row[0] if row else None