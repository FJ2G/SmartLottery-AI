"""双色球数据模型定义。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class SSQRecord:
    """双色球开奖记录。"""

    period: str          # 期号，如 "2025001"
    draw_date: date      # 开奖日期
    red_balls: List[int] = field(default_factory=list)  # 6个红球 [1-33]
    blue_ball: int = 0   # 1个蓝球 [1-16]
    id: Optional[int] = None  # 数据库自增ID

    def __post_init__(self):
        if isinstance(self.draw_date, str):
            self.draw_date = date.fromisoformat(self.draw_date)
        if len(self.red_balls) != 6:
            raise ValueError(f"红球数量必须为6个，当前: {self.red_balls}")

    @property
    def red_str(self) -> str:
        """返回红球字符串，如 '01,05,12,18,25,33'"""
        return ",".join(f"{n:02d}" for n in sorted(self.red_balls))

    @property
    def blue_str(self) -> str:
        """返回蓝球字符串，如 '08'"""
        return f"{self.blue_ball:02d}"

    @property
    def display(self) -> str:
        """用于展示的完整字符串，如 '2025001: 01,05,12,18,25,33 + 08'"""
        return f"{self.period}: {self.red_str} + {self.blue_str}"

    def to_dict(self) -> dict:
        return {
            "period": self.period,
            "draw_date": self.draw_date.isoformat(),
            "red_1": self.red_balls[0],
            "red_2": self.red_balls[1],
            "red_3": self.red_balls[2],
            "red_4": self.red_balls[3],
            "red_5": self.red_balls[4],
            "red_6": self.red_balls[5],
            "blue": self.blue_ball,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SSQRecord:
        """从字典（通常是数据库行）构建实例。"""
        red_balls = [d["red_1"], d["red_2"], d["red_3"],
                     d["red_4"], d["red_5"], d["red_6"]]
        return cls(
            id=d.get("id"),
            period=str(d["period"]),
            draw_date=date.fromisoformat(str(d["draw_date"])),
            red_balls=red_balls,
            blue_ball=int(d["blue"]),
        )

    @classmethod
    def from_row(cls, row: tuple) -> SSQRecord:
        """从数据库游标行元组构建实例。"""
        return cls(
            id=row[0],
            period=row[1],
            draw_date=date.fromisoformat(row[2]),
            red_balls=list(row[3:9]),
            blue_ball=row[9],
        )

    def __repr__(self) -> str:
        return f"SSQRecord({self.period}, {self.red_str}, {self.blue_str})"