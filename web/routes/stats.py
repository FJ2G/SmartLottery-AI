"""统计分析路由。"""

from __future__ import annotations

import io
import warnings
from typing import Optional

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse

matplotlib.use("Agg")
warnings.filterwarnings("ignore")

router = APIRouter()


def _build_chinese_font():
    """配置中文字体。"""
    import matplotlib.font_manager as fm
    import matplotlib
    import os

    cache_file = os.path.join(matplotlib.get_cachedir(), "fontlist-v330.json")
    if os.path.exists(cache_file):
        try:
            os.remove(cache_file)
        except Exception:
            pass

    _WIN_FONT = "C:\\Windows\\Fonts"
    if os.path.isdir(_WIN_FONT):
        for fname in os.listdir(_WIN_FONT):
            if fname.lower().endswith((".ttf", ".otf")):
                try:
                    fm.fontManager.addfont(os.path.join(_WIN_FONT, fname))
                except Exception:
                    pass

    _KEYS = ["Microsoft YaHei", "SimHei", "SimSun", "WenQuanYi"]
    _AVAIL = {f.name for f in fm.fontManager.ttflist}
    font = next((k for k in _KEYS if k in _AVAIL), None)
    if font:
        plt.rcParams["font.sans-serif"] = [font] + plt.rcParams["font.sans-serif"]
        plt.rcParams["axes.unicode_minus"] = False


_build_chinese_font()


def _get_stats_data(n: int = 100, year: Optional[int] = None):
    """获取统计数据。"""
    from collections import Counter
    from core import DataManager, SSQStats
    from core.analysis.stats import SSQStats as StatsCls

    dm = DataManager()
    records = dm.get_recent(n, year)
    if not records:
        return None, {}

    stats = StatsCls.compute(records)
    c_red = Counter()
    c_blue = Counter()
    for r in records:
        c_red.update(r.red_balls)
        c_blue[r.blue_ball] += 1

    # 基础数字
    total = len(records)
    latest = records[0] if records else None

    # 奇偶/大小/区间统计
    odd_cnt = sum(1 for r in records for b in r.red_balls if b % 2 == 1)
    even_cnt = total * 6 - odd_cnt
    large_cnt = sum(1 for r in records for b in r.red_balls if b > 16)
    small_cnt = total * 6 - large_cnt
    z1 = sum(1 for r in records for b in r.red_balls if b <= 11)
    z2 = sum(1 for r in records for b in r.red_balls if 12 <= b <= 22)
    z3 = total * 6 - z1 - z2

    hot_red = sorted(c_red.items(), key=lambda x: x[1], reverse=True)[:5]
    hot_blue = sorted(c_blue.items(), key=lambda x: x[1], reverse=True)[:3]

    return records, {
        "total": total,
        "hot_red": hot_red,
        "hot_blue": hot_blue,
        "latest": {
            "period": latest.period,
            "draw_date": str(latest.draw_date),
            "red_balls": sorted(latest.red_balls),
            "blue_ball": latest.blue_ball,
        } if latest else None,
        "odd_pct": odd_cnt / (total * 6) * 100,
        "even_pct": even_cnt / (total * 6) * 100,
        "small_pct": small_cnt / (total * 6) * 100,
        "large_pct": large_cnt / (total * 6) * 100,
        "z1_pct": z1 / (total * 6) * 100,
        "z2_pct": z2 / (total * 6) * 100,
        "z3_pct": z3 / (total * 6) * 100,
        "red_freq": {b: c_red.get(b, 0) for b in range(1, 34)},
        "blue_freq": {b: c_blue.get(b, 0) for b in range(1, 17)},
    }


def _fig_to_stream(fig):
    """matplotlib Figure 转 PNG 流。"""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _make_freq_chart(freq_data: dict, n_balls: int, title: str, color: str):
    """生成频率柱状图（透明背景）。"""
    fig, ax = plt.subplots(figsize=(max(8, n_balls * 0.35), 4))
    fig.patch.set_facecolor("none")
    ax.set_facecolor("none")
    balls = list(range(1, n_balls + 1))
    freqs = [freq_data.get(b, 0) for b in balls]
    bars = ax.bar(balls, freqs, color=color, alpha=0.85)
    ax.set_xlabel("号码", color="#9ca3af")
    ax.set_ylabel("出现次数", color="#9ca3af")
    ax.set_title(title, color="#e5e7eb", pad=10)
    ax.set_xticks(balls)
    ax.tick_params(axis="x", labelsize=8, colors="#9ca3af")
    ax.tick_params(axis="y", colors="#9ca3af")
    ax.spines["bottom"].set_color("#374151")
    ax.spines["left"].set_color("#374151")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.15, color="#374151")
    fig.tight_layout()
    return fig


def _make_pie_chart(sizes: list, labels: list, colors: list, title: str):
    """生成饼图（透明背景）。"""
    fig, ax = plt.subplots(figsize=(5, 4))
    fig.patch.set_facecolor("none")
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, autopct="%1.1f%%",
        startangle=90, textprops={"color": "#9ca3af", "fontsize": 9}
    )
    for at in autotexts:
        at.set_color("#e5e7eb")
        at.set_fontsize(8)
    ax.set_title(title, color="#e5e7eb", pad=10)
    fig.tight_layout()
    return fig


def _make_dist_chart(data: dict, title: str):
    """生成区间分布柱状图（透明背景）。"""
    fig, ax = plt.subplots(figsize=(5, 4))
    fig.patch.set_facecolor("none")
    ax.set_facecolor("none")
    zones = ["一区(01-11)", "二区(12-22)", "三区(23-33)"]
    values = [data.get("z1_pct", 0), data.get("z2_pct", 0), data.get("z3_pct", 0)]
    bars = ax.bar(zones, values, color=["#69db7c", "#ffd43b", "#ff8787"], alpha=0.85)
    ax.set_ylabel("百分比 (%)", color="#9ca3af")
    ax.set_title(title, color="#e5e7eb", pad=10)
    ax.tick_params(axis="x", colors="#9ca3af", labelsize=9)
    ax.tick_params(axis="y", colors="#9ca3af")
    ax.spines["bottom"].set_color("#374151")
    ax.spines["left"].set_color("#374151")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bar in bars:
        ax.annotate(f"{bar.get_height():.1f}%",
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha="center", va="bottom", fontsize=9, color="#e5e7eb")
    ax.grid(axis="y", alpha=0.15, color="#374151")
    fig.tight_layout()
    return fig


@router.get("/stats", response_class=HTMLResponse)
async def show_stats(
    request: Request,
    n: int = Query(100, ge=10, le=1000, description="分析最近 N 期"),
    year: Optional[int] = Query(None, description="按年份筛选"),
):
    """统计分析页面。"""
    from web.server import templates

    records, data = _get_stats_data(n=n, year=year)
    if data is None:
        return templates.TemplateResponse(request, "stats.html", {
            "request": request,
            "error": "数据库中暂无数据，请先运行 CLI 抓取数据：python main.py update-latest",
            "data": None,
        })

    # 生成图表（转为 base64）
    import base64

    charts = {}

    # 红球频率图
    fig = _make_freq_chart(data["red_freq"], 33, "红球出现频率", "#ff6b6b")
    buf = _fig_to_stream(fig)
    charts["red_freq"] = base64.b64encode(buf.read()).decode()

    # 蓝球频率图
    fig = _make_freq_chart(data["blue_freq"], 16, "蓝球出现频率", "#4dabf7")
    buf = _fig_to_stream(fig)
    charts["blue_freq"] = base64.b64encode(buf.read()).decode()

    # 奇偶分布饼图
    fig = _make_pie_chart(
        [data["odd_pct"], data["even_pct"]],
        [f"奇数 ({data['odd_pct']:.1f}%)", f"偶数 ({data['even_pct']:.1f}%)"],
        ["#ff6b6b", "#4dabf7"],
        "奇偶分布"
    )
    buf = _fig_to_stream(fig)
    charts["odd_even"] = base64.b64encode(buf.read()).decode()

    # 大小分布图
    fig = _make_dist_chart(
        {"z1_pct": data["small_pct"], "z2_pct": data["large_pct"], "z3_pct": 0},
        "红球大小分布"
    )
    buf = _fig_to_stream(fig)
    charts["size"] = base64.b64encode(buf.read()).decode()

    # 区间分布图
    fig = _make_dist_chart(data, "红球三区分布")
    buf = _fig_to_stream(fig)
    charts["zone"] = base64.b64encode(buf.read()).decode()

    return templates.TemplateResponse(request, "stats.html", {
        "request": request,
        "data": data,
        "charts": charts,
        "n": n,
        "year": year,
        "error": None,
    })
