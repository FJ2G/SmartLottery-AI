"""Lottery data analyzer."""

from typing import List

from core.analysis import SSQStats
from core.data.models import SSQRecord


class LotteryAnalyzer:
    """分析彩票历史数据，提取统计特征"""

    def __init__(self, records: List[SSQRecord] | None = None):
        self.records: List[SSQRecord] = records or []

    def add_record(self, record: SSQRecord):
        """添加一条历史记录"""
        self.records.append(record)

    def get_statistics(self) -> SSQStats:
        """返回统计结果"""
        return SSQStats.compute(self.records)
