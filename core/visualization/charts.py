"""双色球可视化图表生成。"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure

# 非交互后端，支持无显示器环境
matplotlib.use("Agg")

# ─── 中文字体配置 ────────────────────────────────────────────
import matplotlib.font_manager as fm
import os
import matplotlib

# 清除字体缓存，强制重新扫描
_cache_file = os.path.join(matplotlib.get_cachedir(), "fontlist-v330.json")
if os.path.exists(_cache_file):
    try:
        os.remove(_cache_file)
    except Exception:
        pass

# Windows 系统字体目录
_WINDOWS_FONT_DIR = "C:\\Windows\\Fonts"

# 尝试从系统字体目录加载中文字体
def _load_system_fonts():
    """从系统字体目录加载字体文件到 matplotlib。"""
    if not os.path.isdir(_WINDOWS_FONT_DIR):
        return
    for fname in os.listdir(_WINDOWS_FONT_DIR):
        if fname.lower().endswith((".ttf", ".otf")):
            try:
                fm.fontManager.addfont(os.path.join(_WINDOWS_FONT_DIR, fname))
            except Exception:
                pass

_load_system_fonts()

# 查找系统中可用的中文字体
_CHINESE_KEYWORDS = [
    "Microsoft YaHei",  # 微软雅黑 (Windows 通用)
    "SimHei",           # 黑体
    "SimSun",           # 宋体
    "KaiTi",            # 楷体
    "FangSong",         # 仿宋
    "PingFang",         # 苹方 (macOS)
    "Heiti",            # 黑体 (macOS)
    "WenQuanYi",        # 文泉驿
    "Noto Sans CJK",    # Noto
]
_AVAILABLE_FONTS = {f.name for f in fm.fontManager.ttflist}
_CHINESE_FONT = next(
    (kw for kw in _CHINESE_KEYWORDS if kw in _AVAILABLE_FONTS),
    None,
)
if _CHINESE_FONT:
    plt.rcParams["font.sans-serif"] = [_CHINESE_FONT] + plt.rcParams["font.sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
else:
    plt.rcParams["axes.unicode_minus"] = False

# 抑制 sklearn 定期告警
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")

from core.data.models import SSQRecord

# 输出目录
OUT_DIR = Path(__file__).parent.parent.parent / "data" / "charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── 配色方案 ───────────────────────────────────────────────
RED_CMAP = LinearSegmentedColormap.from_list(
    "red_balls",
    ["#fff5f5", "#ff0000"],
    N=256,
)
BLUE_CMAP = LinearSegmentedColormap.from_list(
    "blue_balls",
    ["#f0f5ff", "#0066ff"],
    N=256,
)
GREEN_CMAP = LinearSegmentedColormap.from_list(
    "green_balls",
    ["#f0fff0", "#00aa44"],
    N=256,
)


# ─── 工具函数 ────────────────────────────────────────────────


def _build_co_matrix(records: List[SSQRecord]) -> np.ndarray:
    """构建红球共现矩阵 (33x33)。"""
    mat = np.zeros((33, 33), dtype=int)
    for r in records:
        balls = sorted(r.red_balls)
        for i in range(len(balls)):
            for j in range(i + 1, len(balls)):
                a, b = balls[i] - 1, balls[j] - 1
                mat[a, b] += 1
                mat[b, a] += 1
    return mat


def _build_freq_matrix(
    records: List[SSQRecord],
) -> Tuple[np.ndarray, List[str], List[str]]:
    """
    构建频率矩阵：行=期次（从上到下新→旧），列=号码。
    返回 (matrix, row_labels, col_labels)。
    """
    n = len(records)
    red_mat = np.zeros((n, 33), dtype=int)
    blue_mat = np.zeros((n, 16), dtype=int)
    row_labels = []

    for idx, r in enumerate(records):
        row_labels.append(r.period)
        for b in r.red_balls:
            red_mat[idx, b - 1] = 1
        blue_mat[idx, r.blue_ball - 1] = 1

    return red_mat, blue_mat, row_labels


def _build_odd_even_trend(
    records: List[SSQRecord],
) -> Tuple[List[int], List[int], List[int], List[int]]:
    """构建奇偶趋势数据。"""
    periods, odd_counts, size_counts, zone1_counts = [], [], [], []
    for r in records:
        periods.append(r.period)
        odd_counts.append(sum(1 for b in r.red_balls if b % 2 == 1))
        size_counts.append(sum(1 for b in r.red_balls if b > 16))
        zone1_counts.append(sum(1 for b in r.red_balls if b <= 11))
    return periods, odd_counts, size_counts, zone1_counts


# ─── 图表 1: 号码频率热力图 ─────────────────────────────────


def chart_freq_heatmap(
    records: List[SSQRecord],
    kind: str = "red",
    window: int = 50,
    save_path: Optional[str] = None,
) -> Figure:
    """
    绘制号码出现频率热力图。

    Args:
        records: 开奖记录列表
        kind: "red" 或 "blue"
        window: 滑动窗口大小
        save_path: 保存路径，默认 data/charts/freq_heatmap_{kind}.png

    Returns:
        matplotlib Figure
    """
    n = len(records)
    if kind == "red":
        n_balls = 33
        cmap = RED_CMAP
        title = "红球频率热力图"
        color = "Reds"
    else:
        n_balls = 16
        cmap = BLUE_CMAP
        title = "蓝球频率热力图"
        color = "Blues"

    # 构建频率矩阵
    mat = np.zeros((n, n_balls), dtype=int)
    for idx, r in enumerate(records):
        if kind == "red":
            for b in r.red_balls:
                mat[idx, b - 1] = 1
        else:
            mat[idx, r.blue_ball - 1] = 1

    # 滑动窗口统计
    w = min(window, n)
    rows = n - w + 1
    smooth = np.zeros((rows, n_balls), dtype=float)
    for i in range(w):
        smooth += mat[i : i + rows]
    smooth /= w

    # 绘制
    fig, ax = plt.subplots(figsize=(14, max(4, rows * 0.12)))
    im = ax.imshow(
        smooth,
        cmap=cmap,
        aspect="auto",
        origin="lower",
        interpolation="nearest",
    )
    ax.set_xticks(range(1, n_balls + 1))
    ax.set_xlabel("红球号码" if kind == "red" else "蓝球号码")
    ax.set_ylabel(f"期次 (最早→最近, 窗口={w})")
    ax.set_title(title)
    ax.set_xticks(range(0, n_balls, 3))
    ax.set_xticklabels([str(t + 1) for t in range(0, n_balls, 3)], fontsize=8)
    ax.set_yticks(range(0, rows, max(1, rows // 8)))
    y_labels = [records[min(i + w - 1, len(records) - 1)].period for i in range(0, rows, max(1, rows // 8))]
    ax.set_yticklabels(y_labels, fontsize=7)

    plt.colorbar(im, ax=ax, label=f"平均频率 (每{w}期)")

    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


# ─── 图表 2: 折线图（遗漏值/频率趋势）────────────────────────


def chart_freq_trend(
    records: List[SSQRecord],
    balls: Optional[List[int]] = None,
    kind: str = "red",
    window: int = 30,
    save_path: Optional[str] = None,
) -> Figure:
    """
    绘制指定号码的出现频率或遗漏值随时间变化的折线图。

    Args:
        records: 开奖记录列表
        balls: 要跟踪的号码列表，默认取热号
        kind: "red" 或 "blue"
        window: 滑动窗口大小
        save_path: 保存路径

    Returns:
        matplotlib Figure
    """
    n = len(records)
    if balls is None:
        # 默认取近30期出现最多的3个
        from collections import Counter
        c = Counter()
        for r in records[:30]:
            if kind == "red":
                c.update(r.red_balls)
            else:
                c.update([r.blue_ball])
        balls = [b for b, _ in c.most_common(5)]

    if kind == "red":
        n_balls = 33
        colors = plt.cm.Reds(np.linspace(0.4, 0.9, len(balls)))
    else:
        n_balls = 16
        colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(balls)))

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # 构建频率矩阵
    mat = np.zeros((n, n_balls), dtype=int)
    for idx, r in enumerate(records):
        if kind == "red":
            for b in r.red_balls:
                mat[idx, b - 1] = 1
        else:
            mat[idx, r.blue_ball - 1] = 1

    # 滑动窗口频率
    w = min(window, n)
    smooth = np.zeros((n - w + 1, n_balls), dtype=float)
    for i in range(w):
        smooth += mat[i : i + n - w + 1]
    smooth /= w

    periods = [records[i + w - 1].period for i in range(n - w + 1)]
    x = range(len(periods))

    # 上图: 频率趋势
    ax = axes[0]
    for idx, ball in enumerate(balls):
        ax.plot(x, smooth[:, ball - 1], label=f"#{ball:02d}", color=colors[idx], lw=1.8)
    ax.set_ylabel(f"频率 (窗口={w})")
    ax.set_title(f"{'红球' if kind=='red' else '蓝球'}频率趋势")
    ax.legend(loc="upper right", ncol=min(6, len(balls)), fontsize=8)
    ax.grid(True, alpha=0.3)

    # 下图: 遗漏值趋势
    ax = axes[1]
    miss_smooth = np.zeros((n - w + 1, n_balls), dtype=float)
    for i in range(n - w + 1):
        window_mat = mat[i : i + w]
        for b in range(n_balls):
            # 从窗口底部往上找最近出现位置
            col = window_mat[:, b]
            last_appear = np.where(col == 1)[0]
            if len(last_appear) > 0:
                miss_smooth[i, b] = w - 1 - last_appear[0]
            else:
                miss_smooth[i, b] = w

    for idx, ball in enumerate(balls):
        ax.plot(x, miss_smooth[:, ball - 1], label=f"#{ball:02d}", color=colors[idx], lw=1.8)
    ax.set_ylabel(f"遗漏值 (窗口={w})")
    ax.set_xlabel("期次")
    ax.set_title(f"{'红球' if kind=='red' else '蓝球'}遗漏值趋势")
    ax.legend(loc="upper right", ncol=min(6, len(balls)), fontsize=8)
    ax.grid(True, alpha=0.3)

    # x轴标签（每10个显示一个）
    step = max(1, (n - w + 1) // 15)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(periods[::step], rotation=45, fontsize=7)
    axes[1].set_xticks(x[::step])
    axes[1].set_xticklabels(periods[::step], rotation=45, fontsize=7)

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


# ─── 图表 3: 饼图/柱状图（分布）──────────────────────────────


def chart_distribution(
    records: List[SSQRecord],
    kind: str = "all",
    save_path: Optional[str] = None,
) -> Figure:
    """
    绘制奇偶、大小、区间分布的饼图/柱状图。

    Args:
        records: 开奖记录列表
        kind: "odd_even" / "size" / "zone" / "all"
        save_path: 保存路径

    Returns:
        matplotlib Figure
    """
    from core.analysis import SSQStats

    stats = SSQStats.compute(records)
    n = len(records)

    if kind in ("odd_even", "all"):
        oe = stats.odd_even
        total_balls = oe.odd_count + oe.even_count
        odd_pct = oe.odd_count / total_balls * 100
        even_pct = oe.even_count / total_balls * 100

    if kind in ("size", "all"):
        sz = stats.size
        r_total = sz.red_small + sz.red_large
        b_total = sz.blue_small + sz.blue_large

    if kind in ("zone", "all"):
        zn = stats.zone
        z_total = zn.red_zone1 + zn.red_zone2 + zn.red_zone3

    # 确定子图数量
    if kind == "all":
        n_cols = 3
    elif kind == "size":
        n_cols = 2
    else:
        n_cols = 1

    fig, axes = plt.subplots(1, n_cols, figsize=(5 * n_cols, 5))
    if n_cols == 1:
        axes = [axes]

    idx = 0

    if kind in ("odd_even", "all"):
        ax = axes[idx]
        ax.pie(
            [oe.odd_count, oe.even_count],
            labels=[f"奇数 ({odd_pct:.1f}%)", f"偶数 ({even_pct:.1f}%)"],
            colors=["#ff6b6b", "#4dabf7"],
            autopct="%1.1f%%",
            startangle=90,
        )
        ax.set_title(f"奇偶分布 (n={n})")
        idx += 1

    if kind in ("size", "all"):
        ax = axes[idx]
        x = np.arange(2)
        width = 0.35
        red_vals = [sz.red_small / r_total * 100, sz.red_large / r_total * 100]
        blue_vals = [sz.blue_small / b_total * 100, sz.blue_large / b_total * 100]
        bars1 = ax.bar(x - width / 2, red_vals, width, label="红球", color="#ff6b6b", alpha=0.8)
        bars2 = ax.bar(x + width / 2, blue_vals, width, label="蓝球", color="#4dabf7", alpha=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(["小号 (1-16/1-8)", "大号 (17-33/9-16)"])
        ax.set_ylabel("百分比 (%)")
        ax.set_title(f"大小分布 (n={n})")
        ax.legend()
        for bar in bars1:
            ax.annotate(f"{bar.get_height():.1f}%", xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        ha="center", va="bottom", fontsize=8)
        for bar in bars2:
            ax.annotate(f"{bar.get_height():.1f}%", xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        ha="center", va="bottom", fontsize=8)
        idx += 1

    if kind in ("zone", "all"):
        ax = axes[idx]
        zone_vals = [zn.red_zone1 / z_total * 100, zn.red_zone2 / z_total * 100, zn.red_zone3 / z_total * 100]
        bars = ax.bar(
            ["区间1 (01-11)", "区间2 (12-22)", "区间3 (23-33)"],
            zone_vals,
            color=["#69db7c", "#ffd43b", "#ff8787"],
            alpha=0.85,
        )
        ax.set_ylabel("百分比 (%)")
        ax.set_title(f"红球区间分布 (n={n})")
        for bar in bars:
            ax.annotate(f"{bar.get_height():.1f}%", xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        ha="center", va="bottom", fontsize=9)

    fig.suptitle(f"分布分析 (共{n}期)", fontsize=12, fontweight="bold")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


# ─── 图表 4: 散点图（号码相关性）──────────────────────────────


def chart_scatter(
    records: List[SSQRecord],
    kind: str = "red",
    save_path: Optional[str] | None = None,
) -> Figure:
    """
    绘制号码相关性散点图。

    使用共现矩阵做降维可视化：每两个号码之间的共现次数作为相似度，
    用 MDS 降维后在二维平面上展示相关性（距离越近=共现越多）。

    Args:
        records: 开奖记录列表
        kind: "red" 或 "blue"
        save_path: 保存路径

    Returns:
        matplotlib Figure
    """
    try:
        from sklearn.manifold import MDS
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        # fallback: 用共现矩阵直接做热力图
        return _chart_scatter_fallback(records, kind, save_path)

    n_balls = 33 if kind == "red" else 16
    co_mat = _build_co_matrix(records) if kind == "red" else _build_co_matrix_blue(records)

    # 相似度矩阵（用余弦相似度）
    sim = cosine_similarity(co_mat)
    # MDS 降维
    mds = MDS(n_components=2, dissimilarity="precomputed", random_state=42, normalized_stress="auto")
    dist = 1 - sim
    np.fill_diagonal(dist, 0)
    coords = mds.fit_transform(dist)

    fig, ax = plt.subplots(figsize=(10, 10))
    colors_map = plt.cm.Reds if kind == "red" else plt.cm.Blues
    norm_vals = co_mat.sum(axis=1) / co_mat.sum()
    norm_vals = norm_vals / norm_vals.max()

    scatter = ax.scatter(
        coords[:, 0],
        coords[:, 1],
        c=norm_vals,
        cmap=colors_map,
        s=120,
        alpha=0.85,
        edgecolors="white",
        linewidths=0.5,
    )
    for i in range(n_balls):
        ax.annotate(
            str(i + 1),
            (coords[i, 0], coords[i, 1]),
            fontsize=8,
            ha="center",
            va="center",
            color="white" if norm_vals[i] > 0.5 else "black",
            fontweight="bold",
        )
    plt.colorbar(scatter, ax=ax, label="共现频率 (标准化)")
    ax.set_title(f"号码相关性 (MDS降维, {'红球' if kind=='red' else '蓝球'})")
    ax.axis("off")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


def _build_co_matrix_blue(records: List[SSQRecord]) -> np.ndarray:
    """蓝球共现矩阵（16x16，实际上蓝球每期只出1个，共现恒为0，这里用出现次数做散点）。"""
    mat = np.zeros((16, 16), dtype=int)
    for r in records:
        b = r.blue_ball - 1
        mat[b, b] += 1
    return mat


def _chart_scatter_fallback(
    records: List[SSQRecord],
    kind: str,
    save_path: Optional[str],
) -> Figure:
    """无 sklearn 时的 fallback：直接显示共现热力图。"""
    fig, ax = plt.subplots(figsize=(10, 8))
    co_mat = _build_co_matrix(records) if kind == "red" else _build_co_matrix_blue(records)
    cmap = RED_CMAP if kind == "red" else BLUE_CMAP
    im = ax.imshow(co_mat, cmap=cmap, aspect="equal")
    ax.set_xticks(range(0, co_mat.shape[1], 3))
    ax.set_yticks(range(0, co_mat.shape[0], 3))
    ax.set_xticklabels(range(1, co_mat.shape[1] + 1, 3))
    ax.set_yticklabels(range(1, co_mat.shape[0] + 1, 3))
    ax.set_xlabel("号码")
    ax.set_ylabel("号码")
    ax.set_title(f"共现矩阵 ({'红球' if kind=='red' else '蓝球'})")
    plt.colorbar(im, ax=ax, label="共现次数")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


# ─── 图表 5: 一键生成全部图表 ────────────────────────────────


def chart_all(
    records: List[SSQRecord],
    out_dir: Optional[str] = None,
) -> dict[str, str]:
    """
    生成全部可视化图表，保存到指定目录。

    Returns:
        dict: {chart_name: file_path}
    """
    if out_dir:
        out = Path(out_dir)
    else:
        out = OUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    paths = {}

    import matplotlib.pyplot as plt

    # 热力图
    try:
        fig = chart_freq_heatmap(records, kind="red", save_path=str(out / "freq_heatmap_red.png"))
        plt.close(fig)
        paths["freq_heatmap_red"] = str(out / "freq_heatmap_red.png")
    except Exception:
        pass

    # 折线图
    try:
        fig = chart_freq_trend(records, kind="red", save_path=str(out / "freq_trend_red.png"))
        plt.close(fig)
        paths["freq_trend_red"] = str(out / "freq_trend_red.png")
    except Exception:
        pass

    # 分布图
    try:
        fig = chart_distribution(records, save_path=str(out / "distribution.png"))
        plt.close(fig)
        paths["distribution"] = str(out / "distribution.png")
    except Exception:
        pass

    # 相关性散点图
    try:
        fig = chart_scatter(records, kind="red", save_path=str(out / "scatter_red.png"))
        plt.close(fig)
        paths["scatter_red"] = str(out / "scatter_red.png")
    except Exception:
        pass

    return paths