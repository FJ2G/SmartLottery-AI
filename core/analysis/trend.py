"""双色球趋势分析：热温冷号、遗漏值、周期性。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from core.data.models import SSQRecord


# ─── 热温冷阈值常量 ────────────────────────────────────────────
HEAT_WINDOW = 30  # 近 N 期来判定热温冷

# 阈值：近N期出现率（出现次数/N）
# 红球：基数6/33≈18.2%，热≥30%（约9次/30期），温≥18%
# 蓝球：基数1/16=6.25%，热≥15%（约4.5次/30期），温≥8%
RED_HOT_RATE = 0.30
RED_WARM_RATE = 0.18
BLUE_HOT_RATE = 0.15
BLUE_WARM_RATE = 0.08


@dataclass
class BallHeat:
    """单个号码的热度分类。"""

    ball: int
    is_red: bool  # True=红球, False=蓝球
    freq_last_n: int = 0   # 近 N 期出现次数
    miss_count: int = 0    # 当前遗漏（距上次出现隔了多少期）
    avg_interval: float = 0.0  # 历史平均间隔
    heat_level: str = "cold"  # hot / warm / cold

    @property
    def heat_color(self) -> str:
        if self.heat_level == "hot":
            return "red" if self.is_red else "blue"
        elif self.heat_level == "warm":
            return "yellow"
        return "dim"


@dataclass
class HeatStats:
    """整体热温冷统计。"""

    hot_red: List[BallHeat] = field(default_factory=list)   # 红球热号
    warm_red: List[BallHeat] = field(default_factory=list)  # 红球温号
    cold_red: List[BallHeat] = field(default_factory=list)  # 红球冷号
    hot_blue: List[BallHeat] = field(default_factory=list)   # 蓝球热号
    warm_blue: List[BallHeat] = field(default_factory=list)  # 蓝球温号
    cold_blue: List[BallHeat] = field(default_factory=list)  # 蓝球冷号
    total_records: int = 0

    def all_red(self) -> List[BallHeat]:
        return self.hot_red + self.warm_red + self.cold_red

    def all_blue(self) -> List[BallHeat]:
        return self.hot_blue + self.warm_blue + self.cold_blue


@dataclass
class MissingStats:
    """各号码遗漏值统计。"""

    red_miss: Dict[int, int] = field(default_factory=dict)   # 红球遗漏值（当前距上次出现隔了多少期）
    blue_miss: Dict[int, int] = field(default_factory=dict)  # 蓝球遗漏值
    red_max_miss: Dict[int, int] = field(default_factory=dict)   # 红球历史最大遗漏
    blue_max_miss: Dict[int, int] = field(default_factory=dict)   # 蓝球历史最大遗漏
    red_avg_miss: Dict[int, float] = field(default_factory=dict)   # 红球历史平均遗漏
    blue_avg_miss: Dict[int, float] = field(default_factory=dict)  # 蓝球历史平均遗漏
    total: int = 0

    def red_overdue_ratio(self, ball: int) -> float:
        """遗漏倍数：当前遗漏 / 平均遗漏，超过1说明"欠出"."""
        avg = self.red_avg_miss.get(ball, 0)
        if avg <= 0:
            return 0.0
        return self.red_miss.get(ball, 0) / avg

    def blue_overdue_ratio(self, ball: int) -> float:
        avg = self.blue_avg_miss.get(ball, 0)
        if avg <= 0:
            return 0.0
        return self.blue_miss.get(ball, 0) / avg


@dataclass
class PeriodicStats:
    """周期性分析。"""

    total: int = 0
    # 红球周期信息: ball -> [各期间隔列表]
    red_intervals: Dict[int, List[int]] = field(default_factory=dict)
    blue_intervals: Dict[int, List[int]] = field(default_factory=dict)


# ─── 工具函数 ────────────────────────────────────────────────


def _classify(freq: int, n: int, hot_rate: float, warm_rate: float) -> str:
    """根据近N期出现次数分类热温冷."""
    rate = freq / n if n > 0 else 0
    if rate >= hot_rate:
        return "hot"
    elif rate >= warm_rate:
        return "warm"
    return "cold"


def _calc_avg(series: List[int]) -> float:
    if len(series) <= 1:
        return 0.0
    return sum(series) / len(series)


# ─── 主分析类 ────────────────────────────────────────────────


class SSQTrend:
    """
    双色球趋势分析类。

    使用示例::

        from core import DataManager
        from core.analysis.trend import SSQTrend

        dm = DataManager()
        records = dm.get_recent(100)  # 传入最近的记录（期号从新到旧）
        trend = SSQTrend.compute(records)

        # 热温冷号
        heat = trend.heat
        for b in heat.hot_red:
            print(f"热号: {b.ball} 近{HEAT_WINDOW}期出现{b.freq_last_n}次")

        # 遗漏值
        miss = trend.missing
        print(f"红球06当前遗漏: {miss.red_miss.get(6, 0)}期")
        print(f"红球06超过平均遗漏{miss.red_overdue_ratio(6):.1f}倍")

        # 周期性
        periodic = trend.periodic
        print(f"红球10历史平均周期: {periodic.red_intervals.get(10, [])}")
    """

    def __init__(
        self,
        records: List[SSQRecord],
        heat: HeatStats,
        missing: MissingStats,
        periodic: PeriodicStats,
    ):
        self.records = records  # 按新→旧顺序
        self.heat = heat
        self.missing = missing
        self.periodic = periodic

    @classmethod
    def compute(cls, records: List[SSQRecord]) -> "SSQTrend":
        """从记录列表计算所有趋势指标。records 应按新→旧排序（最新在前）。"""
        n = len(records)

        # ── 热温冷 ─────────────────────────────────────
        heat = cls._compute_heat(records, n)

        # ── 遗漏值 ─────────────────────────────────────
        missing = cls._compute_missing(records)

        # ── 周期性 ─────────────────────────────────────
        periodic = cls._compute_periodic(records)

        return cls(records, heat, missing, periodic)

    @classmethod
    def _compute_heat(cls, records: List[SSQRecord], n: int) -> HeatStats:
        """计算热温冷号。"""
        window = min(HEAT_WINDOW, n)
        window_records = records[:window]

        # 统计近 N 期各号码出现次数
        red_freq: Dict[int, int] = defaultdict(int)
        blue_freq: Dict[int, int] = defaultdict(int)
        for r in window_records:
            for b in r.red_balls:
                red_freq[b] += 1
            blue_freq[r.blue_ball] += 1

        # 计算当前遗漏
        red_miss: Dict[int, int] = {}
        blue_miss: Dict[int, int] = {}
        for ball in range(1, 34):
            red_miss[ball] = 0
        for ball in range(1, 17):
            blue_miss[ball] = 0

        for idx, r in enumerate(records):
            for b in r.red_balls:
                if red_miss[b] == 0:
                    red_miss[b] = idx
            if blue_miss[r.blue_ball] == 0:
                blue_miss[r.blue_ball] = idx

        # 历史平均间隔
        red_intervals = cls._build_intervals(records, is_red=True)
        blue_intervals = cls._build_intervals(records, is_red=False)
        red_avg = {b: _calc_avg(v) for b, v in red_intervals.items()}
        blue_avg = {b: _calc_avg(v) for b, v in blue_intervals.items()}

        # 分类
        hot_r, warm_r, cold_r = [], [], []
        hot_b, warm_b, cold_b = [], [], []

        for ball in range(1, 34):
            freq = red_freq.get(ball, 0)
            level = _classify(freq, window, RED_HOT_RATE, RED_WARM_RATE)
            bh = BallHeat(
                ball=ball, is_red=True,
                freq_last_n=freq,
                miss_count=red_miss.get(ball, 0),
                avg_interval=red_avg.get(ball, 0.0),
                heat_level=level,
            )
            if level == "hot":
                hot_r.append(bh)
            elif level == "warm":
                warm_r.append(bh)
            else:
                cold_r.append(bh)

        for ball in range(1, 17):
            freq = blue_freq.get(ball, 0)
            level = _classify(freq, window, BLUE_HOT_RATE, BLUE_WARM_RATE)
            bh = BallHeat(
                ball=ball, is_red=False,
                freq_last_n=freq,
                miss_count=blue_miss.get(ball, 0),
                avg_interval=blue_avg.get(ball, 0.0),
                heat_level=level,
            )
            if level == "hot":
                hot_b.append(bh)
            elif level == "warm":
                warm_b.append(bh)
            else:
                cold_b.append(bh)

        # 按近N期出现次数降序
        hot_r.sort(key=lambda x: x.freq_last_n, reverse=True)
        warm_r.sort(key=lambda x: x.freq_last_n, reverse=True)
        cold_r.sort(key=lambda x: x.miss_count, reverse=True)
        hot_b.sort(key=lambda x: x.freq_last_n, reverse=True)
        warm_b.sort(key=lambda x: x.freq_last_n, reverse=True)
        cold_b.sort(key=lambda x: x.miss_count, reverse=True)

        return HeatStats(
            hot_red=hot_r, warm_red=warm_r, cold_red=cold_r,
            hot_blue=hot_b, warm_blue=warm_b, cold_blue=cold_b,
            total_records=n,
        )

    @classmethod
    def _compute_missing(cls, records: List[SSQRecord]) -> MissingStats:
        """计算各号码当前遗漏和历史最大/平均遗漏。"""
        n = len(records)

        # 记录每个号码每次出现的索引（从新到旧）
        red_appear: Dict[int, List[int]] = defaultdict(list)
        blue_appear: Dict[int, List[int]] = defaultdict(list)

        for idx, r in enumerate(records):
            for b in r.red_balls:
                red_appear[b].append(idx)
            blue_appear[r.blue_ball].append(idx)

        # 当前遗漏
        red_cur: Dict[int, int] = {}
        blue_cur: Dict[int, int] = {}
        for ball in range(1, 34):
            appearances = red_appear.get(ball, [])
            red_cur[ball] = appearances[0] if appearances else n
        for ball in range(1, 17):
            appearances = blue_appear.get(ball, [])
            blue_cur[ball] = appearances[0] if appearances else n

        # 历史最大遗漏
        def max_miss(appearances: List[int]) -> int:
            if not appearances:
                return 0
            max_m = 0
            prev = -1
            for a in appearances:
                m = a - prev - 1
                if m > max_m:
                    max_m = m
                prev = a
            # 到今天的遗漏
            m = n - appearances[-1] - 1
            return max(max_m, m)

        red_max = {b: max_miss(red_appear.get(b, [])) for b in range(1, 34)}
        blue_max = {b: max_miss(blue_appear.get(b, [])) for b in range(1, 17)}

        # 历史平均遗漏（用各期间隔计算）
        red_intervals = cls._build_intervals(records, is_red=True)
        blue_intervals = cls._build_intervals(records, is_red=False)
        red_avg = {b: _calc_avg(v) for b, v in red_intervals.items()}
        blue_avg = {b: _calc_avg(v) for b, v in blue_intervals.items()}

        return MissingStats(
            red_miss=red_cur,
            blue_miss=blue_cur,
            red_max_miss=red_max,
            blue_max_miss=blue_max,
            red_avg_miss=red_avg,
            blue_avg_miss=blue_avg,
            total=n,
        )

    @classmethod
    def _build_intervals(cls, records: List[SSQRecord], is_red: bool) -> Dict[int, List[int]]:
        """构建每个号码的出现间隔列表（单位为期数）。"""
        n = len(records)
        appear: Dict[int, List[int]] = defaultdict(list)
        for idx, r in enumerate(records):
            if is_red:
                for b in r.red_balls:
                    appear[b].append(idx)
            else:
                appear[r.blue_ball].append(idx)

        intervals: Dict[int, List[int]] = {}
        for ball, positions in appear.items():
            if len(positions) < 2:
                intervals[ball] = []
                continue
            gaps = [positions[i] - positions[i - 1] - 1 for i in range(1, len(positions))]
            intervals[ball] = gaps

        return intervals

    @classmethod
    def _compute_periodic(cls, records: List[SSQRecord]) -> PeriodicStats:
        """计算号码出现周期信息。"""
        red_intervals = cls._build_intervals(records, is_red=True)
        blue_intervals = cls._build_intervals(records, is_red=False)
        return PeriodicStats(
            total=len(records),
            red_intervals=dict(red_intervals),
            blue_intervals=dict(blue_intervals),
        )

    # ── 便捷方法 ────────────────────────────────────────

    def hot_red_top(self, top: int = 10) -> List[BallHeat]:
        """红球热号 TOP N。"""
        return self.heat.hot_red[:top]

    def warm_red(self) -> List[BallHeat]:
        """红球温号。"""
        return self.heat.warm_red

    def cold_red_top(self, top: int = 10) -> List[BallHeat]:
        """红球冷号（按遗漏值排序）TOP N。"""
        return self.heat.cold_red[:top]

    def overdue_red(self, top: int = 5) -> List[Tuple[int, float]]:
        """红球"超遗漏"倍数 TOP N（当前遗漏超过历史平均最多的号码）。"""
        ratios = {
            b: self.missing.red_overdue_ratio(b)
            for b in range(1, 34)
        }
        return sorted(ratios.items(), key=lambda x: x[1], reverse=True)[:top]

    def red_interval_stats(self, ball: int) -> Dict[str, float]:
        """返回指定红球的周期统计。"""
        intervals = self.periodic.red_intervals.get(ball, [])
        if not intervals:
            return {"count": 0, "avg": 0.0, "min": 0, "max": 0}
        return {
            "count": len(intervals),
            "avg": sum(intervals) / len(intervals),
            "min": min(intervals),
            "max": max(intervals),
        }