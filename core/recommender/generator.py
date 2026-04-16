"""多策略号码生成器。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List

from core.data.models import SSQRecord


class GenerationStrategy(Enum):
    """号码生成策略枚举。"""

    RANDOM = "random"          # 纯随机
    HEAT = "heat"              # 冷热号策略
    OVERDUE = "overdue"        # 遗漏优先策略
    CO_OCCUR = "co_occur"      # 共现策略
    CLUSTER_MATCH = "cluster"  # 相似匹配策略
    MIXED = "mixed"            # 混合策略

    @classmethod
    def from_str(cls, s: str) -> "GenerationStrategy":
        mapping = {
            "random": cls.RANDOM,
            "heat": cls.HEAT,
            "overdue": cls.OVERDUE,
            "co_occur": cls.CO_OCCUR,
            "cluster": cls.CLUSTER_MATCH,
            "mixed": cls.MIXED,
        }
        return mapping.get(s.lower(), cls.MIXED)


@dataclass
class GeneratedPlan:
    """生成的候选号码方案。"""

    red_balls: List[int]            # 6个红球（已排序）
    blue_ball: int                  # 1个蓝球
    strategy: str                   # 使用的策略名
    score_breakdown: Dict[str, float] = field(default_factory=dict)  # 各维度打分
    explanation: str = ""            # 中文说明

    @property
    def red_str(self) -> str:
        return ",".join(f"{b:02d}" for b in self.red_balls)

    @property
    def blue_str(self) -> str:
        return f"{self.blue_ball:02d}"


class PlanGenerator:
    """
    多策略号码生成器。

    使用示例::

        from core.recommender import PlanGenerator, GenerationStrategy
        from core.data import DataManager

        dm = DataManager()
        records = dm.get_recent(100)
        gen = PlanGenerator(records)

        # 按热号策略生成
        plans = gen.generate(GenerationStrategy.HEAT, n=5)

        # 按所有策略生成
        all_plans = gen.generate_all(n=10)
    """

    def __init__(self, records: List[SSQRecord]):
        """
        Args:
            records: 历史开奖记录（按新→旧排序）
        """
        self.records = records
        self._co_cache: Dict[int, List[int]] = {}  # ball -> top co balls
        self._cluster_balls: List[List[int]] = []  # 从聚类相似期提取的候选

        # 预计算共现伙伴
        self._build_co_cache()

        # 预计算聚类相似号码
        self._build_cluster_balls()

    # ─── 预计算 ────────────────────────────────────────────────

    def _build_co_cache(self):
        """从历史数据计算每个号码的高共现伙伴。"""
        if not self.records:
            return
        from collections import Counter
        co_counter: Dict[int, Counter] = {b: Counter() for b in range(1, 34)}
        for r in self.records:
            for a in r.red_balls:
                for b in r.red_balls:
                    if a != b:
                        co_counter[a][b] += 1
        for ball in range(1, 34):
            self._co_cache[ball] = [b for b, _ in co_counter[ball].most_common(10)]

    def _build_cluster_balls(self):
        """从与最近一期最相似的历史期次中提取候选号码。"""
        if len(self.records) < 10:
            return
        try:
            from core.analysis.advanced import SSQClustering

            target = self.records[0]  # 最近一期
            similar = SSQClustering.find_similar_periods(target, self.records[1:], top_k=10)
            candidates: Dict[int, int] = {}
            for rec, dist in similar:
                for b in rec.red_balls:
                    candidates[b] = candidates.get(b, 0) + 1
            # 按出现频次排序
            self._cluster_balls = [
                sorted(candidates.keys(), key=lambda x: candidates[x], reverse=True)
            ]
        except Exception:
            self._cluster_balls = []

    # ─── 各策略生成 ─────────────────────────────────────────────

    def generate(
        self,
        strategy: GenerationStrategy,
        n: int = 5,
    ) -> List[GeneratedPlan]:
        """按指定策略生成 n 个候选方案。"""
        if strategy == GenerationStrategy.RANDOM:
            return self._gen_random(n)
        elif strategy == GenerationStrategy.HEAT:
            return self._gen_heat(n)
        elif strategy == GenerationStrategy.OVERDUE:
            return self._gen_overdue(n)
        elif strategy == GenerationStrategy.CO_OCCUR:
            return self._gen_co_occur(n)
        elif strategy == GenerationStrategy.CLUSTER_MATCH:
            return self._gen_cluster(n)
        elif strategy == GenerationStrategy.MIXED:
            return self._gen_mixed(n)
        return []

    def generate_all(self, n: int = 10) -> List[GeneratedPlan]:
        """按所有策略生成候选方案。"""
        total = []
        per_strategy = max(2, n // len(GenerationStrategy))
        for s in GenerationStrategy:
            total.extend(self.generate(s, per_strategy))
        # 去重（按红球组合）
        seen = set()
        unique = []
        for p in total:
            key = tuple(sorted(p.red_balls))
            if key not in seen:
                seen.add(key)
                unique.append(p)
        # 按红球组合多样性打散
        random.shuffle(unique)
        return unique[:n]

    # ─── 具体策略实现 ──────────────────────────────────────────

    def _gen_random(self, n: int) -> List[GeneratedPlan]:
        """纯随机策略。"""
        plans = []
        seen = set()
        attempts = 0
        while len(plans) < n and attempts < n * 10:
            attempts += 1
            reds = sorted(random.sample(range(1, 34), 6))
            blue = random.randint(1, 16)
            key = tuple(reds)
            if key in seen:
                continue
            seen.add(key)
            plans.append(GeneratedPlan(
                red_balls=reds,
                blue_ball=blue,
                strategy="随机",
                explanation="纯随机生成，不参考历史规律",
            ))
        return plans

    def _gen_heat(self, n: int) -> List[GeneratedPlan]:
        """冷热号策略：从近期高频热号和温号中选取。"""
        if not self.records:
            return self._gen_random(n)

        from collections import Counter

        # 近30期统计
        window = self.records[:min(30, len(self.records))]
        red_counter = Counter()
        blue_counter = Counter()
        for r in window:
            red_counter.update(r.red_balls)
            blue_counter[r.blue_ball] += 1

        # 频率归一化权重
        max_red = red_counter.most_common(1)[0][1] if red_counter else 1
        red_weights = {b: red_counter.get(b, 0) / max_red for b in range(1, 34)}
        max_blue = blue_counter.most_common(1)[0][1] if blue_counter else 1
        blue_weights = {b: blue_counter.get(b, 0) / max_blue for b in range(1, 17)}

        plans = []
        seen = set()
        attempts = 0
        while len(plans) < n and attempts < n * 20:
            attempts += 1
            # 选取红球：按权重随机抽取
            candidates = list(range(1, 34))
            weights = [red_weights[b] for b in candidates]
            total_w = sum(weights) + 1e-8
            probs = [w / total_w for w in weights]

            # 6个红球（不放回）
            selected = random.choices(candidates, weights=probs, k=6)
            # 调整：如果重复太多，用加权采样
            seen_red = set()
            reds = []
            remaining = list(range(1, 34))
            rem_weights = [red_weights[b] for b in remaining]
            for _ in range(6):
                total_r = sum(rem_weights) + 1e-8
                r_probs = [w / total_r for w in rem_weights]
                chosen = random.choices(remaining, weights=r_probs, k=1)[0]
                reds.append(chosen)
                remaining.remove(chosen)
                rem_weights.pop(0)

            reds = sorted(reds)
            key = tuple(reds)
            if key in seen:
                continue
            seen.add(key)

            # 蓝球：按权重
            blue_candidates = list(range(1, 17))
            blue_probs = [blue_weights[b] / (sum(blue_weights.values()) + 1e-8) for b in blue_candidates]
            blue = random.choices(blue_candidates, weights=blue_probs, k=1)[0]

            plans.append(GeneratedPlan(
                red_balls=reds,
                blue_ball=blue,
                strategy="热号策略",
                explanation=f"从近30期高频号码中加权选取，红球侧重近期热号",
            ))
        return plans

    def _gen_overdue(self, n: int) -> List[GeneratedPlan]:
        """遗漏优先策略：优先选遗漏值大（超过历史平均）的号码。"""
        if not self.records:
            return self._gen_random(n)

        from collections import defaultdict

        n_total = len(self.records)

        # 计算当前遗漏
        red_appear: Dict[int, List[int]] = defaultdict(list)
        blue_appear: Dict[int, List[int]] = defaultdict(list)
        for idx, r in enumerate(self.records):
            for b in r.red_balls:
                red_appear[b].append(idx)
            blue_appear[r.blue_ball].append(idx)

        red_cur_miss = {b: red_appear.get(b, [n_total])[0] for b in range(1, 34)}
        blue_cur_miss = {b: blue_appear.get(b, [n_total])[0] for b in range(1, 17)}

        # 计算平均遗漏
        def avg_interval(positions: List[int], n: int) -> float:
            if len(positions) < 2:
                return 0.0
            gaps = [positions[i] - positions[i - 1] - 1 for i in range(1, len(positions))]
            return sum(gaps) / len(gaps) if gaps else 0.0

        red_avg = {b: avg_interval(red_appear.get(b, []), n_total) for b in range(1, 34)}
        blue_avg = {b: avg_interval(blue_appear.get(b, []), n_total) for b in range(1, 17)}

        # 遗漏倍数 = 当前遗漏 / 平均遗漏
        red_overdue = {b: red_cur_miss[b] / (red_avg[b] + 1e-8) for b in range(1, 34)}
        blue_overdue = {b: blue_cur_miss[b] / (blue_avg[b] + 1e-8) for b in range(1, 17)}

        plans = []
        seen = set()
        attempts = 0
        while len(plans) < n and attempts < n * 20:
            attempts += 1
            # 按遗漏倍数加权选取红球
            red_candidates = list(range(1, 34))
            red_probs = [red_overdue[b] for b in red_candidates]
            total_r = sum(red_probs) + 1e-8
            red_probs = [p / total_r for p in red_probs]

            reds = []
            remaining = list(range(1, 34))
            rem_overdue = [red_overdue[b] for b in remaining]
            for _ in range(6):
                total_s = sum(rem_overdue) + 1e-8
                r_probs = [w / total_s for w in rem_overdue]
                chosen = random.choices(remaining, weights=r_probs, k=1)[0]
                reds.append(chosen)
                idx = remaining.index(chosen)
                remaining.pop(idx)
                rem_overdue.pop(idx)

            reds = sorted(reds)
            key = tuple(reds)
            if key in seen:
                continue
            seen.add(key)

            # 蓝球
            blue_candidates = list(range(1, 17))
            blue_probs = [blue_overdue[b] for b in blue_candidates]
            total_b = sum(blue_probs) + 1e-8
            blue_probs = [p / total_b for p in blue_probs]
            blue = random.choices(blue_candidates, weights=blue_probs, k=1)[0]

            top_overdue = sorted(red_overdue.items(), key=lambda x: x[1], reverse=True)[:3]
            top_str = ", ".join(f"{b}号({v:.1f}倍)" for b, v in top_overdue)
            plans.append(GeneratedPlan(
                red_balls=reds,
                blue_ball=blue,
                strategy="遗漏策略",
                explanation=f"优先选遗漏超过历史均值的号码，当前红球最大遗漏倍数: {top_str}",
            ))
        return plans

    def _gen_co_occur(self, n: int) -> List[GeneratedPlan]:
        """共现策略：从历史高频共现号码对中构建组合。"""
        if not self.records:
            return self._gen_random(n)

        plans = []
        seen = set()
        attempts = 0
        while len(plans) < n and attempts < n * 20:
            attempts += 1
            # 随机选一个起始号码
            if not self._co_cache:
                reds = sorted(random.sample(range(1, 34), 6))
            else:
                start = random.choice(list(self._co_cache.keys()))
                reds = [start]
                remaining = list(range(1, 34))
                remaining.remove(start)

                # 每次从剩余号码中选择与已选号码共现次数最高的
                for _ in range(5):
                    best = None
                    best_score = -1
                    for b in remaining:
                        score = sum(1 for r in reds for co in self._co_cache.get(r, []) if co == b)
                        if score > best_score:
                            best_score = score
                            best = b
                    if best is not None:
                        reds.append(best)
                        remaining.remove(best)

            reds = sorted(reds)
            key = tuple(reds)
            if key in seen:
                continue
            seen.add(key)

            # 蓝球随机
            blue = random.randint(1, 16)

            plans.append(GeneratedPlan(
                red_balls=reds,
                blue_ball=blue,
                strategy="共现策略",
                explanation="号码组合参考历史共现规律，优先选择历史上常一起出现的号码对",
            ))
        return plans

    def _gen_cluster(self, n: int) -> List[GeneratedPlan]:
        """相似匹配策略：从与最近一期模式最相似的历史期次中提取候选号码。"""
        if not self._cluster_balls or not self.records:
            return self._gen_random(n)

        plans = []
        seen = set()
        cluster_candidates = self._cluster_balls[0] if self._cluster_balls else list(range(1, 34))

        attempts = 0
        while len(plans) < n and attempts < n * 20:
            attempts += 1
            # 从相似期的高频号码中选取
            if len(cluster_candidates) < 6:
                reds = sorted(random.sample(range(1, 34), 6))
            else:
                # 优先从相似期选取，但也混入少量随机
                top_n = min(len(cluster_candidates), 15)
                pool = cluster_candidates[:top_n]
                if len(pool) >= 6:
                    reds = sorted(random.sample(pool, 6))
                else:
                    reds = sorted(random.sample(pool + list(range(1, 34)), 6))

            key = tuple(reds)
            if key in seen:
                continue
            seen.add(key)

            blue = random.randint(1, 16)
            plans.append(GeneratedPlan(
                red_balls=reds,
                blue_ball=blue,
                strategy="相似匹配",
                explanation="号码来自与最近一期开奖模式最相似的历史期次，参考历史相似模式",
            ))
        return plans

    def _gen_mixed(self, n: int) -> List[GeneratedPlan]:
        """混合策略：融合多种策略的结果。"""
        # 均匀分配到各策略
        parts = []
        strategies = [
            GenerationStrategy.HEAT,
            GenerationStrategy.OVERDUE,
            GenerationStrategy.CO_OCCUR,
            GenerationStrategy.CLUSTER_MATCH,
        ]
        per_strat = max(1, n // len(strategies))
        for s in strategies:
            parts.extend(self.generate(s, per_strat))

        # 不足的用随机补
        while len(parts) < n:
            parts.extend(self._gen_random(1))

        random.shuffle(parts)
        return parts[:n]
