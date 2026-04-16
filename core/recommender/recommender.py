"""双色球推荐主类。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.data.models import SSQRecord
from core.recommender.generator import GenerationStrategy, GeneratedPlan, PlanGenerator


@dataclass
class RecommendedPlan:
    """推荐方案（含排名和详细说明）。"""

    rank: int                           # 推荐排名
    red_balls: List[int]                 # 6个红球
    blue_ball: int                       # 1个蓝球
    strategy: str                        # 主要策略
    explanation: str                     # 预测理由
    score_breakdown: Dict[str, float]   # 各维度打分
    total_score: float = 0.0             # 综合评分

    @property
    def red_str(self) -> str:
        return ",".join(f"{b:02d}" for b in sorted(self.red_balls))

    @property
    def blue_str(self) -> str:
        return f"{self.blue_ball:02d}"


class SSQRecommender:
    """
    双色球选号推荐引擎。

    结合多种策略生成候选方案，统一打分排序，输出多样化推荐。

    使用示例::

        from core.recommender import SSQRecommender
        from core.data import DataManager

        dm = DataManager()
        records = dm.get_recent(100)
        rec = SSQRecommender(records)
        rec.fit()

        # 生成 10 个推荐方案
        plans = rec.recommend(n=10)

        # 指定策略生成
        plans = rec.recommend_by_strategy("heat", n=5)
    """

    def __init__(self, records: List[SSQRecord]):
        """
        Args:
            records: 历史开奖记录（按新→旧排序）
        """
        self.records = records
        self._generator: Optional[PlanGenerator] = None
        self._scorer: Optional["SSQScorer"] = None
        self._fitted = False

    def fit(self) -> "SSQRecommender":
        """训练推荐模型：初始化各策略生成器和评分器。"""
        if not self.records:
            return self

        self._generator = PlanGenerator(self.records)

        # 训练评分器
        from core.analysis.advanced import SSQScorer

        self._scorer = SSQScorer()
        self._scorer.fit(self.records)

        self._fitted = True
        return self

    def recommend(
        self,
        n: int = 10,
        strategy: Optional[str] = None,
    ) -> List[RecommendedPlan]:
        """
        生成 n 个推荐方案。

        Args:
            n: 生成数量
            strategy: 指定策略（heat/overdue/co_occur/cluster/mixed/random），
                      默认 None 表示使用所有策略

        Returns:
            排序后的推荐方案列表
        """
        if not self._fitted:
            self.fit()

        if not self._generator:
            return []

        # 生成候选
        if strategy:
            strat = GenerationStrategy.from_str(strategy)
            raw = self._generator.generate(strat, n)
        else:
            raw = self._generator.generate_all(n)

        if not raw:
            return []

        # 统一打分
        scored = []
        for plan in raw:
            if self._scorer:
                result = self._scorer.score(plan.red_balls, plan.blue_ball)
                bd = result.breakdown
                score_breakdown = {
                    "frequency": bd.frequency_score,
                    "missing": bd.missing_score,
                    "co_occurrence": bd.co_occurrence_score,
                    "pattern": bd.pattern_score,
                }
                total = result.score
            else:
                score_breakdown = {}
                total = 50.0

            scored.append(RecommendedPlan(
                rank=0,
                red_balls=plan.red_balls,
                blue_ball=plan.blue_ball,
                strategy=plan.strategy,
                explanation=plan.explanation,
                score_breakdown=score_breakdown,
                total_score=total,
            ))

        # 按分数排序
        scored.sort(key=lambda x: x.total_score, reverse=True)

        # 赋值排名
        for i, plan in enumerate(scored, 1):
            plan.rank = i

        return scored[:n]

    def recommend_by_strategy(
        self,
        strategy: str,
        n: int = 5,
    ) -> List[RecommendedPlan]:
        """按指定策略生成推荐方案。"""
        return self.recommend(n=n, strategy=strategy)