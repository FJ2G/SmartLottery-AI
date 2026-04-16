"""双色球高级分析：共现分析、聚类、号码组合评分。"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

import numpy as np

from core.data.models import SSQRecord


# ─── 1. 号码共现分析 ───────────────────────────────────────


@dataclass
class CoOccurrenceItem:
    """单个号码的共现信息。"""

    ball: int
    co_balls: List[Tuple[int, int]] = field(
        default_factory=list
    )  # [(共现号码, 共现次数], ...] 按共现次数降序


@dataclass
class CoOccurrenceStats:
    """共现分析结果。"""

    records: List[SSQRecord] = field(default_factory=list)
    total: int = 0
    # 共现矩阵: (ball_a, ball_b) -> 共现次数
    co_matrix: Dict[Tuple[int, int], int] = field(default_factory=dict)
    # 每个号码的共现伙伴
    co_by_ball: Dict[int, CoOccurrenceItem] = field(default_factory=dict)

    def get_top_co(self, ball: int, top: int = 5) -> List[Tuple[int, int]]:
        """获取某号码最常一起出现的 top 个号码。"""
        item = self.co_by_ball.get(ball)
        if not item:
            return []
        return item.co_balls[:top]

    def get_co_count(self, a: int, b: int) -> int:
        """获取两个号码共现次数。"""
        key = (min(a, b), max(a, b))
        return self.co_matrix.get(key, 0)


class SSQCoOccurrence:
    """双色球号码共现分析（关联规则挖掘简化版）。"""

    @classmethod
    def compute(cls, records: List[SSQRecord]) -> CoOccurrenceStats:
        """
        计算所有红球的共现矩阵。

        支持度 sup(A,B) = 共现次数 / 总期数
        置信度 conf(A->B) = 共现次数 / A出现次数
        """
        n = len(records)
        if n == 0:
            return CoOccurrenceStats()

        co_matrix: Dict[Tuple[int, int], int] = defaultdict(int)

        for r in records:
            balls = sorted(r.red_balls)
            for i in range(len(balls)):
                for j in range(i + 1, len(balls)):
                    a, b = balls[i], balls[j]
                    key = (a, b)
                    co_matrix[key] += 1

        # 构建每个号码的共现列表
        co_by_ball: Dict[int, CoOccurrenceItem] = {}
        for ball in range(1, 34):
            co_list = []
            for (a, b), cnt in co_matrix.items():
                if a == ball:
                    co_list.append((b, cnt))
                elif b == ball:
                    co_list.append((a, cnt))
            co_list.sort(key=lambda x: x[1], reverse=True)
            co_by_ball[ball] = CoOccurrenceItem(ball=ball, co_balls=co_list)

        return CoOccurrenceStats(
            records=records,
            total=n,
            co_matrix=dict(co_matrix),
            co_by_ball=co_by_ball,
        )

    @classmethod
    def top_co_pairs(cls, co: CoOccurrenceStats, top: int = 20) -> List[Tuple[Tuple[int, int], int]]:
        """找出共现次数最高的号码对。"""
        pairs = sorted(co.co_matrix.items(), key=lambda x: x[1], reverse=True)
        return [(k, v) for k, v in pairs[:top]]


# ─── 2. 聚类分析 ──────────────────────────────────────────


@dataclass
class ClusterResult:
    """聚类结果。"""

    labels: np.ndarray  # 每期的簇标签
    centers: np.ndarray  # 簇中心特征
    n_clusters: int
    inertia: float  # 簇内平方和
    feature_names: List[str]


@dataclass
class PeriodCluster:
    """单个簇的统计信息。"""

    cluster_id: int
    size: int
    period_range: str  # 期号范围
    # 各维特征均值
    odd_rate: float
    size_rate: float
    zone1_rate: float
    zone2_rate: float
    zone3_rate: float
    avg_sum: float  # 红球号码和均值


class SSQClustering:
    """双色球开奖期次聚类分析（K-Means）。"""

    FEATURE_NAMES = [
        "odd_rate",
        "size_rate",
        "zone1_rate",
        "zone2_rate",
        "zone3_rate",
        "sum",
        "consecutive_count",
    ]

    @classmethod
    def _extract_features(cls, records: List[SSQRecord]) -> np.ndarray:
        """从记录列表提取特征矩阵。"""
        features = []
        for r in records:
            f = []
            # 奇数率
            odd_cnt = sum(1 for b in r.red_balls if b % 2 == 1)
            f.append(odd_cnt / 6.0)
            # 大号率 (17-33)
            large_cnt = sum(1 for b in r.red_balls if b > 16)
            f.append(large_cnt / 6.0)
            # 三区比例
            z1 = sum(1 for b in r.red_balls if b <= 11)
            z2 = sum(1 for b in r.red_balls if 12 <= b <= 22)
            z3 = sum(1 for b in r.red_balls if b >= 23)
            f.append(z1 / 6.0)
            f.append(z2 / 6.0)
            f.append(z3 / 6.0)
            # 号码和
            f.append(sum(r.red_balls) / 183.0)  # 归一化
            # 连号数
            sorted_balls = sorted(r.red_balls)
            consec = sum(
                1 for i in range(len(sorted_balls) - 1)
                if sorted_balls[i + 1] - sorted_balls[i] == 1
            )
            f.append(consec / 5.0)  # 归一化
            features.append(f)
        return np.array(features)

    @classmethod
    def _extract_cluster_info(
        cls,
        records: List[SSQRecord],
        labels: np.ndarray,
        centers: np.ndarray,
        n_clusters: int,
        inertia: float,
    ) -> List[PeriodCluster]:
        """从聚类结果提取每个簇的统计摘要。"""
        clusters = []
        for k in range(n_clusters):
            indices = np.where(labels == k)[0]
            cluster_records = [records[i] for i in indices]
            cluster_features = cls._extract_features(np.array(cluster_records))
            mean_feat = cluster_features.mean(axis=0)

            periods = [r.period for r in cluster_records]
            sum_vals = [sum(r.red_balls) for r in cluster_records]

            clusters.append(
                PeriodCluster(
                    cluster_id=k,
                    size=len(cluster_records),
                    period_range=f"{min(periods)}~{max(periods)}",
                    odd_rate=mean_feat[0],
                    size_rate=mean_feat[1],
                    zone1_rate=mean_feat[2],
                    zone2_rate=mean_feat[3],
                    zone3_rate=mean_feat[4],
                    avg_sum=mean_feat[5] * 183.0,
                )
            )
        return clusters

    @classmethod
    def compute(
        cls,
        records: List[SSQRecord],
        n_clusters: int = 5,
    ) -> Tuple[ClusterResult, List[PeriodCluster]]:
        """
        对开奖期次进行 K-Means 聚类。

        特征: 奇偶率、大小率、三区比例、号码和、连号数

        Args:
            records: 开奖记录列表
            n_clusters: 聚类数（默认5）

        Returns:
            (ClusterResult, List[PeriodCluster]) 原始结果和统计摘要
        """
        if len(records) < n_clusters:
            n_clusters = max(2, len(records))

        features = cls._extract_features(records)

        # 标准化
        mean = features.mean(axis=0)
        std = features.std(axis=0) + 1e-8
        features_norm = (features - mean) / std

        # K-Means
        from sklearn.cluster import KMeans

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(features_norm)
        inertia = float(kmeans.inertia_)

        result = ClusterResult(
            labels=labels,
            centers=kmeans.cluster_centers_,
            n_clusters=n_clusters,
            inertia=inertia,
            feature_names=cls.FEATURE_NAMES,
        )
        cluster_info = cls._extract_cluster_info(
            records, labels, kmeans.cluster_centers_, n_clusters, inertia
        )
        return result, cluster_info

    @classmethod
    def find_similar_periods(
        cls,
        target: SSQRecord,
        records: List[SSQRecord],
        top_k: int = 5,
    ) -> List[Tuple[SSQRecord, float]]:
        """
        找到与目标期次模式最相似的 top_k 个历史期次。
        使用欧氏距离计算相似度。
        """
        features = cls._extract_features(records)
        target_feat = cls._extract_features([target])[0]

        mean = features.mean(axis=0)
        std = features.std(axis=0) + 1e-8
        features_norm = (features - mean) / std
        target_norm = (target_feat - mean) / std

        distances = np.linalg.norm(features_norm - target_norm, axis=1)
        top_indices = np.argsort(distances)[:top_k]
        return [(records[i], float(distances[i])) for i in top_indices]


# ─── 3. 号码组合评分模型 ──────────────────────────────────


@dataclass
class ScoreBreakdown:
    """评分明细。"""

    frequency_score: float = 0.0  # 频率得分
    missing_score: float = 0.0    # 遗漏得分
    co_occurrence_score: float = 0.0  # 共现得分
    pattern_score: float = 0.0    # 模式匹配得分
    total: float = 0.0


@dataclass
class ScoredCombination:
    """带评分的号码组合。"""

    red_balls: List[int]
    blue_ball: int
    score: float
    breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)


class SSQScorer:
    """
    双色球号码组合评分模型。

    对候选号码组合从多维度打分（0-100）：
      - 频率得分：各号码历史出现频率（越高越好）
      - 遗漏得分：号码当前遗漏是否"合理"（接近平均遗漏为佳）
      - 共现得分：各号码之间是否经常一起出现（过于分散或过于集中都不好）
      - 模式得分：奇偶比、区间分布是否接近历史均值

    使用示例::

        scorer = SSQScorer()
        scorer.fit(records)  # 用历史数据训练

        # 打分一个候选组合
        result = scorer.score([2, 10, 13, 22, 25, 33], 8)
        print(result.score)
        print(result.breakdown)
    """

    def __init__(self):
        self.records: List[SSQRecord] = []
        self._fitted = False

        # 统计量
        self._red_freq: Dict[int, int] = {}
        self._blue_freq: Dict[int, int] = {}
        self._red_miss: Dict[int, int] = {}
        self._blue_miss: Dict[int, int] = {}
        self._red_avg_miss: Dict[int, float] = {}
        self._blue_avg_miss: Dict[int, float] = {}
        self._co_stats: CoOccurrenceStats | None = None
        self._avg_odd_rate: float = 0.0
        self._avg_size_rate: float = 0.0
        self._avg_zone_rates: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._total: int = 0

    def fit(self, records: List[SSQRecord]) -> "SSQScorer":
        """用历史数据训练评分模型。"""
        self.records = records
        self._total = len(records)
        if self._total == 0:
            return self

        from core.analysis.trend import SSQTrend
        from core.analysis.stats import SSQStats

        trend = SSQTrend.compute(records)
        stats = SSQStats.compute(records)

        # 频率
        self._red_freq = dict(stats.freq.red_freq)
        self._blue_freq = dict(stats.freq.blue_freq)

        # 遗漏
        self._red_miss = dict(trend.missing.red_miss)
        self._blue_miss = dict(trend.missing.blue_miss)
        self._red_avg_miss = dict(trend.missing.red_avg_miss)
        self._blue_avg_miss = dict(trend.missing.blue_avg_miss)

        # 共现
        self._co_stats = SSQCoOccurrence.compute(records)

        # 模式统计
        odd_total = sum(1 for r in records for b in r.red_balls if b % 2 == 1)
        large_total = sum(1 for r in records for b in r.red_balls if b > 16)
        z1_total = sum(1 for r in records for b in r.red_balls if b <= 11)
        z2_total = sum(1 for r in records for b in r.red_balls if 12 <= b <= 22)
        ball_total = self._total * 6

        self._avg_odd_rate = odd_total / ball_total
        self._avg_size_rate = large_total / ball_total
        self._avg_zone_rates = (
            z1_total / ball_total,
            z2_total / ball_total,
            (ball_total - z1_total - z2_total) / ball_total,
        )

        self._fitted = True
        return self

    def score(
        self,
        red_balls: List[int],
        blue_ball: int,
        weights: Tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.25),
    ) -> ScoredCombination:
        """
        对候选号码组合打分（0-100）。

        Args:
            red_balls: 6个红球
            blue_ball: 1个蓝球
            weights: (频率权重, 遗漏权重, 共现权重, 模式权重)

        Returns:
            ScoredCombination 含总分和明细
        """
        if not self._fitted:
            raise ValueError("请先调用 fit() 方法")

        bd = ScoreBreakdown()

        # ── 频率得分 (0-100) ─────────────────────────
        # 各号码频率归一化到0-1，与历史均值对比
        red_freqs = [self._red_freq.get(b, 0) / self._total for b in red_balls]
        avg_red_freq = sum(red_freqs) / len(red_freqs)
        blue_freq = self._blue_freq.get(blue_ball, 0) / self._total

        # 理想频率：接近理论概率 6/33≈0.182
        theoretical = 6.0 / 33.0
        red_freq_score = max(
            0, 1 - abs(avg_red_freq - theoretical) / theoretical
        ) * 50 + 50 * (1 - abs(blue_freq - 1 / 16) / (1 / 16))
        bd.frequency_score = red_freq_score * 0.7 + blue_freq * 100 * 0.3

        # ── 遗漏得分 (0-100) ─────────────────────────
        # 遗漏越接近平均值越好，偏离越大扣分
        red_miss_scores = []
        for b in red_balls:
            cur = self._red_miss.get(b, self._total)
            avg = self._red_avg_miss.get(b, 0)
            if avg > 0:
                # 遗漏/平均值，越接近1越好
                ratio = cur / avg
                # ratio=1 得100分, ratio=0 得50分, ratio>2 得30分
                score = max(0, 100 - abs(ratio - 1.0) * 50)
                red_miss_scores.append(score)
            else:
                red_miss_scores.append(50)
        bd.missing_score = (
            sum(red_miss_scores) / len(red_miss_scores) * 0.85
            + max(0, 100 - abs(self._blue_miss.get(blue_ball, 0) /
                                (self._blue_avg_miss.get(blue_ball, 0) + 1e-8) - 1.0) * 50) * 0.15
        )

        # ── 共现得分 (0-100) ─────────────────────────
        if self._co_stats and self._co_stats.total > 0:
            co_scores = []
            for a in red_balls:
                for b in red_balls:
                    if a != b:
                        cnt = self._co_stats.get_co_count(a, b)
                        # 期望共现率: (6/33)^2 * 总期数
                        expected = (6.0 / 33) ** 2 * self._total
                        ratio = cnt / (expected + 1e-8)
                        co_scores.append(min(100, ratio * 50))
            bd.co_occurrence_score = sum(co_scores) / len(co_scores) if co_scores else 50
        else:
            bd.co_occurrence_score = 50

        # ── 模式得分 (0-100) ─────────────────────────
        # 奇偶率
        odd_cnt = sum(1 for b in red_balls if b % 2 == 1)
        odd_rate = odd_cnt / 6.0
        odd_score = max(0, 100 - abs(odd_rate - self._avg_odd_rate) * 200)

        # 大小率
        large_cnt = sum(1 for b in red_balls if b > 16)
        size_rate = large_cnt / 6.0
        size_score = max(0, 100 - abs(size_rate - self._avg_size_rate) * 200)

        # 三区分布
        z1 = sum(1 for b in red_balls if b <= 11) / 6.0
        z2 = sum(1 for b in red_balls if 12 <= b <= 22) / 6.0
        z3 = 1.0 - z1 - z2
        zone_score = 100 - (
            abs(z1 - self._avg_zone_rates[0])
            + abs(z2 - self._avg_zone_rates[1])
            + abs(z3 - self._avg_zone_rates[2])
        ) * 150

        bd.pattern_score = (odd_score + size_score + zone_score) / 3.0

        # ── 综合得分 ─────────────────────────────────
        w_freq, w_miss, w_co, w_pat = weights
        bd.total = (
            bd.frequency_score * w_freq
            + bd.missing_score * w_miss
            + bd.co_occurrence_score * w_co
            + bd.pattern_score * w_pat
        )

        return ScoredCombination(
            red_balls=red_balls,
            blue_ball=blue_ball,
            score=bd.total,
            breakdown=bd,
        )

    def score_random(self, n: int = 10) -> List[ScoredCombination]:
        """
        生成 n 个随机号码组合并打分，返回排序结果（高分在前）。
        """
        import random

        results = []
        for _ in range(n):
            reds = sorted(random.sample(range(1, 34), 6))
            blue = random.randint(1, 16)
            results.append(self.score(reds, blue))
        results.sort(key=lambda x: x.score, reverse=True)
        return results
