"""数据导出器：支持 CSV / JSON 格式。"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import fields, is_dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from core.data.models import SSQRecord


# ─── 通用序列化工具 ────────────────────────────────────────────


def _dataclass_to_dict(obj: Any) -> Any:
    """
    将 dataclass 对象递归转换为 dict。
    适用于 SSQStats, SSQTrend, RecommendedPlan 等。
    """
    if isinstance(obj, dict):
        return {k: _dataclass_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_dataclass_to_dict(item) for item in obj]
    if isinstance(obj, set):
        return [_dataclass_to_dict(item) for item in obj]
    if is_dataclass(obj):
        result = {}
        for f in fields(obj):
            val = getattr(obj, f.name)
            # 跳过 records 列表（太大）
            if f.name == "records":
                continue
            result[f.name] = _dataclass_to_dict(val)
        return result
    if isinstance(obj, (date,)):
        return obj.isoformat()
    if hasattr(obj, "item"):  # numpy 类型
        return obj.item()
    return obj


def _flatten_stats(stats_dict: Dict) -> List[Dict]:
    """
    将 SSQStats 的嵌套 dict 展平为 CSV 行列表。
    """
    rows = []
    freq = stats_dict.get("freq", {})
    red_freq = freq.get("red_freq", {})

    # 每行一个号码
    for ball in range(1, 34):
        rows.append({
            "ball_type": "red",
            "ball": ball,
            "freq": red_freq.get(ball, 0),
            "total": freq.get("total", 0),
            "rate": red_freq.get(ball, 0) / max(freq.get("total", 1), 1),
        })
    blue_freq = freq.get("blue_freq", {})
    for ball in range(1, 17):
        rows.append({
            "ball_type": "blue",
            "ball": ball,
            "freq": blue_freq.get(ball, 0),
            "total": freq.get("total", 0),
            "rate": blue_freq.get(ball, 0) / max(freq.get("total", 1), 1),
        })

    # 也追加汇总行
    rows.append({
        "ball_type": "summary",
        "ball": 0,
        "freq": 0,
        "total": freq.get("total", 0),
        "rate": 0,
        "odd_count": stats_dict.get("odd_even", {}).get("odd_count", 0),
        "even_count": stats_dict.get("odd_even", {}).get("even_count", 0),
        "red_small": stats_dict.get("size", {}).get("red_small", 0),
        "red_large": stats_dict.get("size", {}).get("red_large", 0),
        "blue_small": stats_dict.get("size", {}).get("blue_small", 0),
        "blue_large": stats_dict.get("size", {}).get("blue_large", 0),
    })
    return rows


# ─── 导出器主类 ──────────────────────────────────────────────


class DataExporter:
    """
    数据导出器。

    使用示例::

        from ui.exporter import DataExporter
        exporter = DataExporter()
        exporter.export_records("data/export/", format="json")
        exporter.export_stats(records, "data/export/", format="csv")
        exporter.export_recommend(plans, "data/export/", format="json")
    """

    def __init__(self, out_dir: str | Path = "data/export"):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    # ─── 记录导出 ─────────────────────────────────────────────

    def export_records(
        self,
        records: List[SSQRecord],
        format: str = "json",
        filename: str | None = None,
    ) -> str:
        """
        导出开奖记录。

        Args:
            records: SSQRecord 列表
            format: "json" 或 "csv"
            filename: 自定义文件名（含扩展名）

        Returns:
            导出文件路径
        """
        if not records:
            raise ValueError("没有数据可导出")

        if format == "json":
            path = self.out_dir / (filename or "ssq_records.json")
            data = [r.to_dict() for r in records]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        elif format == "csv":
            path = self.out_dir / (filename or "ssq_records.csv")
            rows = [r.to_dict() for r in records]
            if rows:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
        else:
            raise ValueError(f"不支持的格式: {format}，仅支持 json 或 csv")

        return str(path)

    # ─── 统计导出 ─────────────────────────────────────────────

    def export_stats(self, stats_dict: Dict, format: str = "json", filename: str | None = None) -> str:
        """
        导出统计分析结果。

        Args:
            stats_dict: SSQStats.compute() 后经 dataclass_to_dict 转换的 dict
            format: "json" 或 "csv"
            filename: 自定义文件名（含扩展名）

        Returns:
            导出文件路径
        """
        path_json = self.out_dir / (filename or "ssq_stats.json")
        path_csv = self.out_dir / (filename or "ssq_stats.csv")

        if format == "json":
            with open(path_json, "w", encoding="utf-8") as f:
                json.dump(stats_dict, f, ensure_ascii=False, indent=2, default=str)
            return str(path_json)

        elif format == "csv":
            rows = _flatten_stats(stats_dict)
            if rows and "ball_type" in rows[0]:
                with open(path_csv, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
            return str(path_csv)
        else:
            raise ValueError(f"不支持的格式: {format}，仅支持 json 或 csv")

    # ─── 趋势导出 ─────────────────────────────────────────────

    def export_trend(self, trend_dict: Dict, format: str = "json", filename: str | None = None) -> str:
        """
        导出趋势分析结果。

        Args:
            trend_dict: SSQTrend.compute() 后经 dataclass_to_dict 转换的 dict
            format: 仅支持 json（嵌套结构不适合格式化csv）

        Returns:
            导出文件路径
        """
        if format != "json":
            print(f"[警告] 趋势数据仅支持 json 格式，已改为 json 导出")

        path = self.out_dir / (filename or "ssq_trend.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(trend_dict, f, ensure_ascii=False, indent=2, default=str)
        return str(path)

    # ─── 推荐导出 ─────────────────────────────────────────────

    def export_recommend(
        self,
        plans: List,
        format: str = "json",
        filename: str | None = None,
    ) -> str:
        """
        导出推荐结果。

        Args:
            plans: SSQRecommender.recommend() 返回的列表
            format: "json" 或 "csv"
            filename: 自定义文件名（含扩展名）

        Returns:
            导出文件路径
        """
        if not plans:
            raise ValueError("没有推荐数据可导出")

        plans_dicts = [_dataclass_to_dict(p) for p in plans]

        if format == "json":
            path = self.out_dir / (filename or "ssq_recommend.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(plans_dicts, f, ensure_ascii=False, indent=2, default=str)
        elif format == "csv":
            path = self.out_dir / (filename or "ssq_recommend.csv")
            rows = []
            for p in plans_dicts:
                rows.append({
                    "rank": p.get("rank", 0),
                    "red_1": p["red_balls"][0] if p.get("red_balls") else "",
                    "red_2": p["red_balls"][1] if p.get("red_balls") and len(p["red_balls"]) > 1 else "",
                    "red_3": p["red_balls"][2] if p.get("red_balls") and len(p["red_balls"]) > 2 else "",
                    "red_4": p["red_balls"][3] if p.get("red_balls") and len(p["red_balls"]) > 3 else "",
                    "red_5": p["red_balls"][4] if p.get("red_balls") and len(p["red_balls"]) > 4 else "",
                    "red_6": p["red_balls"][5] if p.get("red_balls") and len(p["red_balls"]) > 5 else "",
                    "blue_ball": p.get("blue_ball", ""),
                    "total_score": p.get("total_score", 0),
                    "strategy": p.get("strategy", ""),
                    "explanation": p.get("explanation", ""),
                })
            if rows:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
        else:
            raise ValueError(f"不支持的格式: {format}，仅支持 json 或 csv")

        return str(path)

    # ─── 共现导出 ─────────────────────────────────────────────

    def export_cooccur(self, co_stats_dict: Dict, format: str = "json", filename: str | None = None) -> str:
        """
        导出共现分析结果。

        Args:
            co_stats_dict: SSQCoOccurrence.compute() 后经 dataclass_to_dict 转换的 dict
            format: 仅支持 json

        Returns:
            导出文件路径
        """
        if format != "json":
            print(f"[警告] 共现数据仅支持 json 格式，已改为 json 导出")

        path = self.out_dir / (filename or "ssq_cooccur.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(co_stats_dict, f, ensure_ascii=False, indent=2, default=str)
        return str(path)
