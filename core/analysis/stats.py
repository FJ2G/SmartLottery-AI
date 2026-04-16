"""双色球基础统计分析。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from core.data.models import SSQRecord


@dataclass
class FrequencyStats:
    """各号码出现频率统计。"""

    red_freq: Dict[int, int] = field(default_factory=dict)  # 红球 1-33: 出现次数
    blue_freq: Dict[int, int] = field(default_factory=dict)  # 蓝球 1-16: 出现次数
    total: int = 0

    def red_rate(self, ball: int) -> float:
        """红球出现概率（0.0 ~ 1.0）。"""
        if self.total == 0:
            return 0.0
        return self.red_freq.get(ball, 0) / self.total

    def blue_rate(self, ball: int) -> float:
        """蓝球出现概率（0.0 ~ 1.0）。"""
        if self.total == 0:
            return 0.0
        return self.blue_freq.get(ball, 0) / self.total


@dataclass
class OddEvenStats:
    """奇偶比例分布。"""

    odd_count: int = 0   # 奇数个数（1,3,5...）
    even_count: int = 0  # 偶数个数（2,4,6...）

    @property
    def ratio(self) -> Tuple[int, int]:
        return (self.odd_count, self.even_count)

    @property
    def avg_odd_rate(self) -> float:
        """奇数占比（全局平均）。"""
        if self.odd_count + self.even_count == 0:
            return 0.0
        return self.odd_count / (self.odd_count + self.even_count)


@dataclass
class SizeStats:
    """大小号比例分布。

    红球: 小号 1-16, 大号 17-33
    蓝球: 小号 1-8,  大号 9-16
    """

    red_small: int = 0   # 红球小号 (1-16)
    red_large: int = 0    # 红球大号 (17-33)
    blue_small: int = 0   # 蓝球小号 (1-8)
    blue_large: int = 0    # 蓝球大号 (9-16)

    @property
    def red_ratio(self) -> Tuple[int, int]:
        return (self.red_small, self.red_large)

    @property
    def blue_ratio(self) -> Tuple[int, int]:
        return (self.blue_small, self.blue_large)


@dataclass
class ZoneStats:
    """区间分布统计。

    红球三区间:
      - 一区（01-11）
      - 二区（12-22）
      - 三区（23-33）
    """

    red_zone1: int = 0  # 01-11
    red_zone2: int = 0  # 12-22
    red_zone3: int = 0  # 23-33

    @property
    def ratio(self) -> Tuple[int, int, int]:
        return (self.red_zone1, self.red_zone2, self.red_zone3)


@dataclass
class ConsecutiveStats:
    """连号统计。"""

    has_consecutive: int = 0   # 含连号的期数
    no_consecutive: int = 0    # 不含连号的期数
    total_consecutive_pairs: int = 0  # 连号总对数（含2连、3连...）
    total: int = 0

    @property
    def consecutive_rate(self) -> float:
        """连号出现比例。"""
        if self.total == 0:
            return 0.0
        return self.has_consecutive / self.total


@dataclass
class SSQStats:
    """
    双色球基础统计汇总类。

    使用示例::

        from core import DataManager
        from core.analysis import SSQStats

        dm = DataManager()
        records = dm.get_recent(100)
        stats = SSQStats.compute(records)

        print(stats.freq.red_rate(6))         # 红球06出现概率
        print(stats.odd_even.odd_count)          # 奇数总数
        print(stats.consecutive.consecutive_rate) # 连号比例
    """

    records: List[SSQRecord] = field(default_factory=list)
    freq: FrequencyStats = field(default_factory=FrequencyStats)
    odd_even: OddEvenStats = field(default_factory=OddEvenStats)
    size: SizeStats = field(default_factory=SizeStats)
    zone: ZoneStats = field(default_factory=ZoneStats)
    consecutive: ConsecutiveStats = field(default_factory=ConsecutiveStats)

    @classmethod
    def compute(cls, records: List[SSQRecord]) -> "SSQStats":
        """
        从历史记录列表计算所有基础统计。

        Args:
            records: SSQRecord 列表（按任意顺序）

        Returns:
            SSQStats 统计结果
        """
        n = len(records)
        if n == 0:
            return cls()

        # ── 频率统计 ──────────────────────────────────────────
        red_counter: Counter = Counter()
        blue_counter: Counter = Counter()
        for r in records:
            for b in r.red_balls:
                red_counter[b] += 1
            blue_counter[r.blue_ball] += 1
        freq = FrequencyStats(
            red_freq=dict(red_counter),
            blue_freq=dict(blue_counter),
            total=n,
        )

        # ── 奇偶统计 ────────────────────────────────────────
        odd_count = 0
        even_count = 0
        for r in records:
            for b in r.red_balls:
                if b % 2 == 1:
                    odd_count += 1
                else:
                    even_count += 1
        odd_even = OddEvenStats(odd_count=odd_count, even_count=even_count)

        # ── 大小号统计 ─────────────────────────────────────
        red_small = red_large = blue_small = blue_large = 0
        for r in records:
            for b in r.red_balls:
                if b <= 16:
                    red_small += 1
                else:
                    red_large += 1
            if r.blue_ball <= 8:
                blue_small += 1
            else:
                blue_large += 1
        size = SizeStats(
            red_small=red_small,
            red_large=red_large,
            blue_small=blue_small,
            blue_large=blue_large,
        )

        # ── 区间分布 ───────────────────────────────────────
        z1 = z2 = z3 = 0
        for r in records:
            for b in r.red_balls:
                if b <= 11:
                    z1 += 1
                elif b <= 22:
                    z2 += 1
                else:
                    z3 += 1
        zone = ZoneStats(red_zone1=z1, red_zone2=z2, red_zone3=z3)

        # ── 连号统计 ───────────────────────────────────────
        has_consec = 0
        no_consec = 0
        total_pairs = 0
        for r in records:
            sorted_balls = sorted(r.red_balls)
            consec = sum(
                1 for i in range(len(sorted_balls) - 1)
                if sorted_balls[i + 1] - sorted_balls[i] == 1
            )
            if consec > 0:
                has_consec += 1
                total_pairs += consec
            else:
                no_consec += 1
        consecutive = ConsecutiveStats(
            has_consecutive=has_consec,
            no_consecutive=no_consec,
            total_consecutive_pairs=total_pairs,
            total=n,
        )

        return cls(
            records=records,
            freq=freq,
            odd_even=odd_even,
            size=size,
            zone=zone,
            consecutive=consecutive,
        )

    # ── 便捷辅助方法 ──────────────────────────────────────

    def hot_red(self, top: int = 10) -> List[Tuple[int, int]]:
        """出现频率最高的 top 个红球。返回 [(号码, 次数), ...]"""
        return sorted(self.freq.red_freq.items(), key=lambda x: x[1], reverse=True)[:top]

    def cold_red(self, bottom: int = 10) -> List[Tuple[int, int]]:
        """出现频率最低的 bottom 个红球。返回 [(号码, 次数), ...]"""
        return sorted(self.freq.red_freq.items(), key=lambda x: x[1])[:bottom]

    def hot_blue(self, top: int = 5) -> List[Tuple[int, int]]:
        """出现频率最高的 top 个蓝球。"""
        return sorted(self.freq.blue_freq.items(), key=lambda x: x[1], reverse=True)[:top]

    def cold_blue(self, bottom: int = 5) -> List[Tuple[int, int]]:
        """出现频率最低的 bottom 个蓝球。"""
        return sorted(self.freq.blue_freq.items(), key=lambda x: x[1])[:bottom]