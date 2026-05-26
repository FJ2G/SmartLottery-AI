"""SmartLottery-AI - 智能彩票分析工具"""

__version__ = "0.1.0"

import logging
import sys
from datetime import date
from pathlib import Path

from rich.console import Console
from rich.text import Text

from core import DataManager
from core.analysis import SSQClustering, SSQCoOccurrence, SSQScorer, SSQStats, SSQTrend
from core.data.models import SSQRecord
from core.recommender import SSQRecommender

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
console = Console()


def _print_record(record: SSQRecord) -> None:
    """打印单条记录，红球红色，篮球蓝色。"""
    red = Text(",".join(f"{n:02d}" for n in sorted(record.red_balls)), style="red bold")
    blue = Text(f"{record.blue_ball:02d}", style="blue bold")
    line = Text(f"{record.period} ({record.draw_date}): ") + red + Text(" + ") + blue
    console.print(line)


def cmd_update_latest():
    """智能刷新：抓取最新一期 + 补齐当前年份缺失数据"""
    dm = DataManager()
    status, record, year_filled = dm.update_recent()
    if status == 1:
        console.print("[green]已保存最新一期:[/green]")
        _print_record(record)
    elif status == 0:
        console.print("[dim]当前已是最新:[/dim]")
        _print_record(record)
    else:
        console.print("[red]抓取失败，请检查网络或稍后重试。[/red]")

    if year_filled > 0:
        console.print(f"[green]并已补齐当前年份 {year_filled} 条缺失数据[/green]")


def cmd_update_year(year: int):
    """补充指定年份数据"""
    dm = DataManager()
    inserted = dm.update_year(
        year,
        on_insert=lambda r: _print_record(r),
        on_skip=lambda r: console.print(f"  [dim][=] {r.period} 已存在[/dim]"),
    )
    console.print(f"[green]新增 {inserted} 条记录。[/green]")


def cmd_update_all():
    """全量拉取历史数据（2003年至今）"""
    dm = DataManager()
    before = dm.count()
    console.print(f"[dim]当前数据库: {before} 条记录，开始全量刷新...[/dim]")
    inserted = dm.update_all(
        on_insert=lambda r: _print_record(r),
    )
    after = dm.count()
    console.print(f"[green]全量刷新完成，新增 {inserted} 条，数据库共 {after} 条记录。[/green]")


def cmd_stats():
    """打印本地数据库统计信息"""
    dm = DataManager()
    total = dm.count()
    latest = dm.get_latest()
    console.print(f"数据库共 [bold]{total}[/bold] 条记录")
    if latest:
        console.print("最新一期:")
        _print_record(latest)


def cmd_clear():
    """清空数据库"""
    dm = DataManager()
    count = dm.clear()
    console.print(f"[yellow]已清空数据库，删除了 {count} 条记录[/yellow]")


def cmd_list_recent(n: int = 10, year: int | None = None):
    """列出最近 n 期开奖记录，可按年份过滤"""
    dm = DataManager()
    records = dm.get_recent(n, year)
    for r in records:
        _print_record(r)


def cmd_query(date_str: str):
    """按开奖日期查询中奖号码"""
    dm = DataManager()
    record = dm.get_by_date(date_str)
    if record:
        _print_record(record)
    else:
        console.print(f"[yellow]未找到 {date_str} 的开奖记录[/yellow]")


def cmd_stat(n: int = 100, year: int | None = None):
    """显示基础统计分析（频率、奇偶、大小、区间、连号）"""
    dm = DataManager()
    records = dm.get_recent(n, year)
    if not records:
        console.print("[yellow]数据库中暂无数据，请先运行 update-latest 或 update-year[/yellow]")
        return

    stats = SSQStats.compute(records)
    total = len(records)

    console.rule(f"[bold]双色球基础统计（最近 {total} 期）[/bold]")

    # ── 奇偶比例 ────────────────────────────────────────
    oe = stats.odd_even
    oe_total = oe.odd_count + oe.even_count
    oe_odd_pct = f"{oe.odd_count / oe_total * 100:.1f}%" if oe_total else "0.0%"
    oe_even_pct = f"{oe.even_count / oe_total * 100:.1f}%" if oe_total else "0.0%"
    console.print(f"\n[bold]奇偶比例[/bold]  奇数 {oe.odd_count} ({oe_odd_pct})  /  偶数 {oe.even_count} ({oe_even_pct})")

    # ── 大小号 ─────────────────────────────────────────
    sz = stats.size
    r_total = sz.red_small + sz.red_large
    b_total = sz.blue_small + sz.blue_large
    console.print(
        f"[bold]红球大小[/bold]  小(01-16) {sz.red_small} ({sz.red_small/r_total*100:.1f}%)"
        f"  /  大(17-33) {sz.red_large} ({sz.red_large/r_total*100:.1f}%)"
    )
    console.print(
        f"[bold]蓝球大小[/bold]  小(01-08) {sz.blue_small} ({sz.blue_small/b_total*100:.1f}%)"
        f"  /  大(09-16) {sz.blue_large} ({sz.blue_large/b_total*100:.1f}%)"
    )

    # ── 区间分布 ───────────────────────────────────────
    zn = stats.zone
    z_total = zn.red_zone1 + zn.red_zone2 + zn.red_zone3
    console.print(
        f"[bold]红球区间[/bold]  "
        f"[red]一区(01-11)[/red] {zn.red_zone1} ({zn.red_zone1/z_total*100:.1f}%)  /  "
        f"[red]二区(12-22)[/red] {zn.red_zone2} ({zn.red_zone2/z_total*100:.1f}%)  /  "
        f"[red]三区(23-33)[/red] {zn.red_zone3} ({zn.red_zone3/z_total*100:.1f}%)"
    )

    # ── 连号统计 ───────────────────────────────────────
    cs = stats.consecutive
    console.print(
        f"[bold]连号统计[/bold]  "
        f"含连号 {cs.has_consecutive} 期 ({cs.consecutive_rate*100:.1f}%)  /  "
        f"无连号 {cs.no_consecutive} 期 ({(cs.no_consecutive/cs.total)*100:.1f}%)  /  "
        f"连号总对数 {cs.total_consecutive_pairs}"
    )


def cmd_freq(n: int = 100, top: int = 10, year: int | None = None):
    """显示冷热号统计"""
    dm = DataManager()
    records = dm.get_recent(n, year)
    if not records:
        console.print("[yellow]数据库中暂无数据[/yellow]")
        return

    stats = SSQStats.compute(records)
    total = len(records)

    console.rule(f"[bold]号码冷热分析（最近 {total} 期）[/bold]")

    # 红球热号
    from rich.table import Table
    hot_red_table = Table(title="[red bold]红球热号 TOP {}[/red bold]".format(top), show_header=True)
    hot_red_table.add_column("号码", justify="center")
    hot_red_table.add_column("出现次数", justify="center")
    hot_red_table.add_column("出现率", justify="center")
    for ball, cnt in stats.hot_red(top):
        rate = stats.freq.red_rate(ball) * 100
        hot_red_table.add_row(
            f"[red]{ball:02d}[/red]",
            str(cnt),
            f"{rate:.1f}%",
        )

    cold_red_table = Table(title="[red bold]红球冷号 BOTTOM {}[/red bold]".format(top), show_header=True)
    cold_red_table.add_column("号码", justify="center")
    cold_red_table.add_column("出现次数", justify="center")
    cold_red_table.add_column("出现率", justify="center")
    for ball, cnt in stats.cold_red(top):
        rate = stats.freq.red_rate(ball) * 100
        cold_red_table.add_row(
            f"[red]{ball:02d}[/red]",
            str(cnt),
            f"{rate:.1f}%",
        )

    # 蓝球
    blue_table = Table(title="[blue bold]蓝球频率[/blue bold]", show_header=True)
    blue_table.add_column("号码", justify="center")
    blue_table.add_column("出现次数", justify="center")
    blue_table.add_column("出现率", justify="center")
    all_blue = sorted(stats.freq.blue_freq.items(), key=lambda x: x[1], reverse=True)
    for ball, cnt in all_blue:
        rate = stats.freq.blue_rate(ball) * 100
        blue_table.add_row(f"[blue]{ball:02d}[/blue]", str(cnt), f"{rate:.1f}%")

    console.print(hot_red_table)
    console.print(cold_red_table)
    console.print(blue_table)


def cmd_trend(n: int = 100, year: int | None = None):
    """趋势分析：热温冷号、遗漏值追踪、周期性"""
    from rich.table import Table

    dm = DataManager()
    records = dm.get_recent(n, year)
    if not records:
        console.print("[yellow]数据库中暂无数据[/yellow]")
        return

    trend = SSQTrend.compute(records)
    total = len(records)

    console.rule(f"[bold]趋势分析（最近 {total} 期）[/bold]")

    # ── 热温冷号 ───────────────────────────────────
    console.print()
    console.print("[bold]热温冷号（近 30 期）[/bold]")

    def _make_heat_table(title, balls, is_red):
        color = "red" if is_red else "blue"
        t = Table(title=f"[{color} bold]{title}[/{color} bold]", show_header=True)
        t.add_column("号码", justify="center")
        t.add_column("近30期出现", justify="center")
        t.add_column("当前遗漏", justify="center")
        t.add_column("历史平均周期", justify="center")
        for b in balls:
            miss = b.miss_count
            avg = b.avg_interval
            miss_str = f"[red]{miss}[/red]" if miss > 10 else str(miss)
            t.add_row(
                f"[{color}]{b.ball:02d}[/{color}]",
                str(b.freq_last_n),
                miss_str,
                f"{avg:.1f}" if avg > 0 else "-",
            )
        return t

    # 红球热温冷
    console.print("[red bold]红球[/red bold]")
    console.print(_make_heat_table("热号（≥30%）", trend.heat.hot_red[:8], True))
    console.print(_make_heat_table("温号（18%-30%）", trend.heat.warm_red[:8], True))
    console.print(_make_heat_table("冷号（<18%）", trend.heat.cold_red[:8], True))

    console.print()
    console.print("[blue bold]蓝球[/blue bold]")
    console.print(_make_heat_table("热号", trend.heat.hot_blue, False))
    console.print(_make_heat_table("温号", trend.heat.warm_blue, False))
    console.print(_make_heat_table("冷号", trend.heat.cold_blue, False))

    # ── 遗漏值追踪 ──────────────────────────────────
    console.print()
    console.print('[bold]遗漏值追踪（超过历史平均越多越"欠出"）[/bold]')

    miss_table = Table(show_header=True)
    miss_table.add_column("类型", justify="center")
    miss_table.add_column("号码", justify="center")
    miss_table.add_column("当前遗漏", justify="center")
    miss_table.add_column("历史最大", justify="center")
    miss_table.add_column("历史平均", justify="center")
    miss_table.add_column("遗漏倍数", justify="center")

    overdue_r = trend.overdue_red(10)
    for ball, ratio in overdue_r:
        cur = trend.missing.red_miss.get(ball, 0)
        max_m = trend.missing.red_max_miss.get(ball, 0)
        avg_m = trend.missing.red_avg_miss.get(ball, 0)
        ratio_str = f"[red]{ratio:.1f}x[/red]" if ratio > 1.0 else f"{ratio:.1f}x"
        miss_table.add_row(
            "[red]红球[/red]", f"[red]{ball:02d}[/red]",
            str(cur), str(max_m), f"{avg_m:.1f}" if avg_m else "-", ratio_str
        )

    overdue_b = sorted(
        [(b, trend.missing.blue_overdue_ratio(b)) for b in range(1, 17)],
        key=lambda x: x[1], reverse=True
    )[:5]
    for ball, ratio in overdue_b:
        cur = trend.missing.blue_miss.get(ball, 0)
        max_m = trend.missing.blue_max_miss.get(ball, 0)
        avg_m = trend.missing.blue_avg_miss.get(ball, 0)
        ratio_str = f"[blue]{ratio:.1f}x[/blue]" if ratio > 1.0 else f"{ratio:.1f}x"
        miss_table.add_row(
            "[blue]蓝球[/blue]", f"[blue]{ball:02d}[/blue]",
            str(cur), str(max_m), f"{avg_m:.1f}" if avg_m else "-", ratio_str
        )

    console.print(miss_table)

    # ── 周期统计（展示几个代表性号码）───────────────
    console.print()
    console.print("[bold]周期统计（历史平均间隔 / 最小 / 最大）[/bold]")

    # 取热号和冷号各几个展示
    sample_balls = [b.ball for b in (trend.heat.hot_red[:3] + trend.heat.cold_red[:3])]
    periodic_table = Table(show_header=True)
    periodic_table.add_column("类型", justify="center")
    periodic_table.add_column("号码", justify="center")
    periodic_table.add_column("出现次数", justify="center")
    periodic_table.add_column("平均周期", justify="center")
    periodic_table.add_column("最短", justify="center")
    periodic_table.add_column("最长", justify="center")

    for ball in sample_balls:
        st = trend.red_interval_stats(ball)
        heat = next((b for b in trend.heat.all_red() if b.ball == ball), None)
        level_tag = ""
        if heat:
            color_map = {"hot": "red", "warm": "yellow", "cold": "dim"}
            color = color_map[heat.heat_level]
            level_tag = f"[{color}]{heat.heat_level}[/{color}]"
        periodic_table.add_row(
            level_tag,
            f"[red]{ball:02d}[/red]",
            str(st["count"]),
            f"{st['avg']:.1f}" if st["avg"] else "-",
            str(st["min"]) if st["min"] else "-",
            str(st["max"]) if st["max"] else "-",
        )

    console.print(periodic_table)


def cmd_cooccur(n: int = 100, top_ball: int = 10, year: int | None = None):
    """号码共现分析"""
    dm = DataManager()
    records = dm.get_recent(n, year)
    if not records:
        console.print("[yellow]数据库中暂无数据[/yellow]")
        return

    co = SSQCoOccurrence.compute(records)
    total = len(records)

    console.rule(f"[bold]号码共现分析（最近 {total} 期）[/bold]")

    # 共现次数最高的号码对
    console.print()
    console.print("[bold]共现次数最高的号码对 TOP 20[/bold]")
    from rich.table import Table
    pair_table = Table(show_header=True)
    pair_table.add_column("号码对", justify="center")
    pair_table.add_column("共现次数", justify="center")
    pair_table.add_column("共现率", justify="center")

    for (a, b), cnt in SSQCoOccurrence.top_co_pairs(co, 20):
        rate = cnt / total * 100
        pair_table.add_row(
            f"[red]{a:02d}[/red] + [red]{b:02d}[/red]",
            str(cnt),
            f"{rate:.1f}%",
        )
    console.print(pair_table)

    # 指定号码的共现伙伴
    console.print()
    console.print(f"[bold]热号共现伙伴（显示前 {top_ball} 个）[/bold]")
    # 取近30期热号作为代表
    from core.analysis.trend import SSQTrend as TrendAnalyzer
    heat_trend = TrendAnalyzer.compute(records)
    hot_balls = [b.ball for b in heat_trend.heat.hot_red[:8]]

    co_table = Table(show_header=True)
    co_table.add_column("号码", justify="center")
    for i in range(1, 7):
        co_table.add_column(f"共现 #{i}", justify="center")

    for ball in hot_balls:
        top_co = co.get_top_co(ball, 6)
        row = [f"[red]{ball:02d}[/red]"]
        for co_ball, cnt in top_co:
            row.append(f"[red]{co_ball:02d}[/red]({cnt})")
        while len(row) < 7:
            row.append("-")
        co_table.add_row(*row)
    console.print(co_table)


def cmd_cluster(n: int = 100, k: int = 5, year: int | None = None):
    """聚类分析：将开奖期次分群"""
    dm = DataManager()
    records = dm.get_recent(n, year)
    if len(records) < 3:
        console.print("[yellow]数据量太少，至少需要3期[/yellow]")
        return

    result, clusters = SSQClustering.compute(records, n_clusters=k)

    console.rule(f"[bold]期次聚类分析（K={result.n_clusters}，共 {len(records)} 期）[/bold]")

    from rich.table import Table
    t = Table(show_header=True)
    t.add_column("簇", justify="center")
    t.add_column("期数", justify="center")
    t.add_column("奇数率", justify="center")
    t.add_column("大号率", justify="center")
    t.add_column("一区", justify="center")
    t.add_column("二区", justify="center")
    t.add_column("三区", justify="center")
    t.add_column("号码和", justify="center")

    for c in clusters:
        t.add_row(
            f"簇{c.cluster_id}",
            str(c.size),
            f"{c.odd_rate:.1%}",
            f"{c.size_rate:.1%}",
            f"{c.zone1_rate:.1%}",
            f"{c.zone2_rate:.1%}",
            f"{c.zone3_rate:.1%}",
            f"{c.avg_sum:.0f}",
        )
    console.print(t)

    console.print()
    console.print("[bold]模式解读[/bold]")
    for c in clusters:
        odd_desc = "奇多" if c.odd_rate > 0.5 else "偶多"
        size_desc = "大号多" if c.size_rate > 0.5 else "小号多"
        zone_desc = f"一区{int(c.zone1_rate*3)}个/二区{int(c.zone2_rate*3)}个/三区{int(c.zone3_rate*3)}个"
        console.print(
            f"  [bold]簇{c.cluster_id}[/bold]（{c.size}期）: "
            f"{odd_desc}, {size_desc}, {zone_desc}, "
            f"均值和 {c.avg_sum:.0f}"
        )


def cmd_recommend(
    n: int = 100,
    generate: int = 10,
    year: int | None = None,
    strategy: str | None = None,
    show_detail: bool = False,
):
    """
    多策略号码推荐。

    支持策略: heat(热号) / overdue(遗漏) / co_occur(共现) / cluster(相似) / mixed(混合) / random(随机)
    默认使用 mixed 混合策略，综合多种规律生成候选。
    """
    dm = DataManager()
    records = dm.get_recent(n, year)
    if not records:
        console.print("[yellow]数据库中暂无数据[/yellow]")
        return

    strat_display = f"[dim]策略: {strategy or 'mixed'}[/dim] " if strategy else ""
    console.print(f"[dim]正在训练推荐模型（基于 {len(records)} 期数据）{strat_display}...[/dim]")

    rec = SSQRecommender(records)
    rec.fit()

    console.print()
    strat_title = strategy or "全部策略"
    console.rule(f"[bold]号码组合推荐（{generate} 组候选，策略: {strat_title}）[/bold]")

    from rich.table import Table
    from rich.panel import Panel

    plans = rec.recommend(n=generate, strategy=strategy)

    t = Table(show_header=True, show_lines=True)
    t.add_column("排名", justify="center", style="bold")
    t.add_column("红球", justify="center")
    t.add_column("蓝球", justify="center")
    t.add_column("总分", justify="center", style="green bold")
    t.add_column("策略", justify="center", style="cyan")
    if show_detail:
        t.add_column("频率", justify="center")
        t.add_column("遗漏", justify="center")
        t.add_column("共现", justify="center")
        t.add_column("模式", justify="center")

    for plan in plans:
        red_str = ",".join(f"{b:02d}" for b in sorted(plan.red_balls))
        row = [
            str(plan.rank),
            f"[red]{red_str}[/red]",
            f"[blue]{plan.blue_ball:02d}[/blue]",
            f"[green]{plan.total_score:.1f}[/green]",
            f"[cyan]{plan.strategy}[/cyan]",
        ]
        if show_detail:
            bd = plan.score_breakdown
            row.extend([
                f"{bd.get('frequency', 0):.1f}",
                f"{bd.get('missing', 0):.1f}",
                f"{bd.get('co_occurrence', 0):.1f}",
                f"{bd.get('pattern', 0):.1f}",
            ])
        t.add_row(*row)
    console.print(t)

    if show_detail:
        console.print()
        console.rule("[bold]推荐理由说明[/bold]")
        for plan in plans[:min(5, len(plans))]:
            red_str = ",".join(f"{b:02d}" for b in sorted(plan.red_balls))
            console.print(
                f"[bold][{plan.rank}][/bold] "
                f"[red]{red_str}[/red] + [blue]{plan.blue_ball:02d}[/blue] "
                f"({plan.strategy}): {plan.explanation}"
            )

    console.print()
    console.print(
        "[dim]评分说明: 总分100分，由频率(25%)、遗漏(25%)、共现(25%)、模式(25%)加权得到。"
        "高分组合模式更接近历史规律，仅供参考。[/dim]"
    )


def _ensure_data(dm: DataManager, min_records: int = 100, year: int | None = None) -> bool:
    """
    确保数据库有足够数据，不足则自动补充。
    - 优先抓取最新一期
    - 如果数据不足，按年份倒序逐年补充，直到够用为止
    返回是否进行了数据更新。
    """
    from datetime import date

    today = date.today()
    updated = False

    # 1. 抓取最新一期
    status, _ = dm.update_latest()
    if status == 1:
        console.print(f"[dim]已抓取最新一期[/dim]")
        updated = True
    elif status == 0:
        console.print(f"[dim]已是最新[/dim]")

    # 2. 逐年补充，直到数据够用
    if dm.count() < min_records:
        console.print(f"[dim]数据不足，正在自动补充...[/dim]")
        for y in range(today.year, today.year - 10, -1):
            if dm.count() >= min_records:
                break
            # 如果指定了年份，只补充该年
            if year is not None and y != year:
                continue
            count_before = dm.count()
            dm.update_year(
                y,
                progress=False,
                on_insert=None,
                on_skip=None,
            )
            added = dm.count() - count_before
            if added > 0:
                console.print(f"[dim]  已补充 {y} 年 +{added} 条[/dim]")
                updated = True

    final_total = dm.count()
    if updated:
        console.print(f"[green]数据就绪，共 {final_total} 条记录[/green]")
    return updated


def cmd_serve(host: str = "0.0.0.0", port: int = 8080):
    """启动 Web 网站服务。"""
    import uvicorn
    from web import app

    console.print(f"[green]启动 Web 服务: http://{host}:{port}[/green]")
    if host == "0.0.0.0":
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "<本机局域网IP>"
        console.print(f"[cyan]局域网访问: http://{local_ip}:{port}[/cyan]")
    console.print(f"[dim]按 Ctrl+C 停止服务[/dim]")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


def cmd_export(
    export_type: str = "records",
    format: str = "json",
    out_dir: str = "data/export",
    n: int = 100,
    generate: int = 10,
    year: int | None = None,
):
    """
    数据导出命令。

    支持导出:
    - records: 开奖历史记录
    - stats: 基础统计分析
    - trend: 趋势分析
    - recommend: 推荐结果
    """
    from ui.exporter import DataExporter, _dataclass_to_dict

    exporter = DataExporter(out_dir)

    dm = DataManager()
    records = dm.get_recent(n if export_type != "records" else 999999, year)
    if not records:
        console.print("[yellow]数据库中暂无数据[/yellow]")
        return

    try:
        if export_type == "records":
            path = exporter.export_records(records, format=format)
            console.print(f"[green]已导出 {len(records)} 条开奖记录: {path}[/green]")

        elif export_type == "stats":
            stats = SSQStats.compute(records[:n])
            stats_dict = _dataclass_to_dict(stats)
            path = exporter.export_stats(stats_dict, format=format)
            console.print(f"[green]已导出统计数据: {path}[/green]")

        elif export_type == "trend":
            trend = SSQTrend.compute(records[:n])
            trend_dict = _dataclass_to_dict(trend)
            path = exporter.export_trend(trend_dict, format="json")
            console.print(f"[green]已导出趋势数据: {path}[/green]")

        elif export_type == "recommend":
            rec = SSQRecommender(records[:n])
            rec.fit()
            plans = rec.recommend(n=generate)
            path = exporter.export_recommend(plans, format=format)
            console.print(f"[green]已导出 {len(plans)} 条推荐结果: {path}[/green]")

    except Exception as e:
        console.print(f"[red]导出失败: {e}[/red]")


def cmd_chart(chart_type: str, n: int = 100, year: int | None = None, out_dir: str | None = None):
    """生成可视化图表（数据不足时自动补全）"""
    dm = DataManager()

    # 自动检查并补充数据
    need_fetch = dm.count() < n
    if need_fetch:
        console.print(f"[dim]数据不足 {dm.count()}/{n} 条，自动补充中...[/dim]")
        _ensure_data(dm, min_records=n, year=year)

    records = dm.get_recent(n, year)
    if not records:
        console.print("[yellow]数据库中暂无数据[/yellow]")
        return

    from core.visualization import (
        chart_all,
        chart_distribution,
        chart_freq_heatmap,
        chart_freq_trend,
        chart_scatter,
    )

    from core.visualization.charts import OUT_DIR as default_out

    out = Path(out_dir) if out_dir else default_out
    out.mkdir(parents=True, exist_ok=True)

    console.print(f"[dim]图表将保存到: {out}[/dim]")

    if chart_type == "all":
        paths = chart_all(records, out_dir=str(out))
        console.print()
        console.print("[bold green]已生成图表:[/bold green]")
        for name, path in paths.items():
            console.print(f"  {name}: {path}")
        return

    fig = None
    fname = ""
    try:
        if chart_type == "heatmap":
            fname = "freq_heatmap_red.png"
            fig = chart_freq_heatmap(records, kind="red", save_path=str(out / fname))
        elif chart_type == "heatmap-blue":
            fname = "freq_heatmap_blue.png"
            fig = chart_freq_heatmap(records, kind="blue", save_path=str(out / fname))
        elif chart_type == "trend":
            fname = "freq_trend_red.png"
            fig = chart_freq_trend(records, kind="red", save_path=str(out / fname))
        elif chart_type == "trend-blue":
            fname = "freq_trend_blue.png"
            fig = chart_freq_trend(records, kind="blue", save_path=str(out / fname))
        elif chart_type == "distribution":
            fname = "distribution.png"
            fig = chart_distribution(records, save_path=str(out / fname))
        elif chart_type == "scatter":
            fname = "scatter_red.png"
            fig = chart_scatter(records, kind="red", save_path=str(out / fname))
        else:
            console.print(f"[yellow]未知图表类型: {chart_type}[/yellow]")
            console.print("[dim]可用类型: all / heatmap / heatmap-blue / trend / trend-blue / distribution / scatter[/dim]")
            return

        if fig:
            import matplotlib.pyplot as _plt
            _plt.close(fig)
            full_path = out / fname
            console.print(f"[green]图表已保存: {full_path}[/green]")
    except Exception as e:
        console.print(f"[red]生成图表失败: {e}[/red]")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SmartLottery-AI 数据管理工具")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("update-latest", help="抓取最新一期")
    sub.add_parser("stats", help="显示数据库统计")
    sub.add_parser("clear", help="清空数据库")
    p_list = sub.add_parser("list", help="列出最近 n 期")
    p_list.add_argument("-n", type=int, default=10)
    p_list.add_argument("--year", type=int, default=None, help="按年份过滤，如 --year 2026")
    p_query = sub.add_parser("query", help="按开奖日期查询")
    p_query.add_argument("date", help="开奖日期，格式 YYYY-MM-DD，如 2026-04-02")
    p_year = sub.add_parser("update-year", help="补充某年数据")
    p_year.add_argument("year", type=int)
    sub.add_parser("update-all", help="全量刷新历史数据（2003年至今）")
    p_stat = sub.add_parser("stat", help="基础统计分析（频率/奇偶/大小/区间/连号）")
    p_stat.add_argument("-n", type=int, default=100, help="分析最近 N 期，默认 100")
    p_stat.add_argument("--year", type=int, default=None, help="按年份过滤")
    p_freq = sub.add_parser("freq", help="显示冷热号分析")
    p_freq.add_argument("-n", type=int, default=100, help="分析最近 N 期，默认 100")
    p_freq.add_argument("--top", type=int, default=10, help="热/冷号显示数量，默认 10")
    p_freq.add_argument("--year", type=int, default=None, help="按年份过滤")
    p_trend = sub.add_parser("trend", help="趋势分析（热温冷/遗漏值/周期性）")
    p_trend.add_argument("-n", type=int, default=100, help="分析最近 N 期，默认 100")
    p_trend.add_argument("--year", type=int, default=None, help="按年份过滤")
    p_cooccur = sub.add_parser("cooccur", help="号码共现分析（关联规则挖掘）")
    p_cooccur.add_argument("-n", type=int, default=100, help="分析最近 N 期，默认 100")
    p_cooccur.add_argument("--top", type=int, default=10, help="每个号码显示共现伙伴数，默认 10")
    p_cooccur.add_argument("--year", type=int, default=None, help="按年份过滤")
    p_cluster = sub.add_parser("cluster", help="聚类分析（K-Means分群）")
    p_cluster.add_argument("-n", type=int, default=100, help="分析最近 N 期，默认 100")
    p_cluster.add_argument("-k", type=int, default=5, help="聚类数，默认 5")
    p_cluster.add_argument("--year", type=int, default=None, help="按年份过滤")
    p_recommend = sub.add_parser("recommend", help="号码组合推荐（多策略）")
    p_recommend.add_argument("-n", type=int, default=100, help="基于最近 N 期，默认 100")
    p_recommend.add_argument("-g", "--generate", type=int, default=10, help="生成候选组数，默认 10")
    p_recommend.add_argument("--year", type=int, default=None, help="按年份过滤")
    p_recommend.add_argument("-s", "--strategy", type=str, default=None,
                             choices=["heat", "overdue", "co_occur", "cluster", "mixed", "random"],
                             help="生成策略: heat=热号, overdue=遗漏, co_occur=共现, cluster=相似, mixed=混合, random=随机")
    p_recommend.add_argument("--show-detail", action="store_true", help="显示详细打分和推荐理由")
    p_chart = sub.add_parser("chart", help="生成可视化图表")
    p_chart.add_argument("type", nargs="?", default="all",
                         choices=["all", "heatmap", "heatmap-blue", "trend", "trend-blue", "distribution", "scatter"],
                         help="图表类型: all=全部, heatmap=红球热力图, trend=频率趋势, distribution=分布图, scatter=相关性散点")
    p_chart.add_argument("-n", type=int, default=100, help="分析最近 N 期，默认 100")
    p_chart.add_argument("--year", type=int, default=None, help="按年份过滤")
    p_chart.add_argument("--out", type=str, default=None, help="图表输出目录")
    sub.add_parser("run-tui", help="启动交互式 TUI 菜单")
    p_export = sub.add_parser("export", help="数据导出（CSV/JSON）")
    p_export.add_argument("--type", "-t", type=str, default="records",
                          choices=["records", "stats", "trend", "recommend"],
                          help="导出类型: records=历史记录, stats=统计数据, trend=趋势数据, recommend=推荐结果")
    p_export.add_argument("--format", "-f", type=str, default="json",
                          choices=["json", "csv"],
                          help="导出格式: json 或 csv")
    p_export.add_argument("--out", "-o", type=str, default="data/export",
                          help="输出目录，默认 data/export")
    p_export.add_argument("-n", type=int, default=100, help="分析最近 N 期（用于 stats/trend/recommend）")
    p_export.add_argument("-g", "--generate", type=int, default=10, help="生成推荐组数（用于 recommend）")
    p_export.add_argument("--year", type=int, default=None, help="按年份过滤")
    p_serve = sub.add_parser("serve", help="启动 Web 网站")
    p_serve.add_argument("--host", type=str, default="0.0.0.0", help="监听地址，默认 0.0.0.0（局域网可访问）")
    p_serve.add_argument("--port", "-p", type=int, default=8080, help="监听端口，默认 8080")

    args = parser.parse_args()

    if args.cmd == "update-latest":
        cmd_update_latest()
    elif args.cmd == "stats":
        cmd_stats()
    elif args.cmd == "clear":
        cmd_clear()
    elif args.cmd == "list":
        cmd_list_recent(args.n, args.year)
    elif args.cmd == "query":
        cmd_query(args.date)
    elif args.cmd == "update-year":
        cmd_update_year(args.year)
    elif args.cmd == "update-all":
        cmd_update_all()
    elif args.cmd == "stat":
        cmd_stat(args.n, args.year)
    elif args.cmd == "freq":
        cmd_freq(args.n, args.top, args.year)
    elif args.cmd == "trend":
        cmd_trend(args.n, args.year)
    elif args.cmd == "cooccur":
        cmd_cooccur(args.n, args.top, args.year)
    elif args.cmd == "cluster":
        cmd_cluster(args.n, args.k, args.year)
    elif args.cmd == "recommend":
        cmd_recommend(args.n, args.generate, args.year, args.strategy, args.show_detail)
    elif args.cmd == "chart":
        cmd_chart(args.type, args.n, args.year, args.out)
    elif args.cmd == "run-tui":
        from ui import run_tui
        run_tui()
    elif args.cmd == "export":
        cmd_export(args.type, args.format, args.out, args.n, args.generate, args.year)
    elif args.cmd == "serve":
        cmd_serve(args.host, args.port)
    else:
        parser.print_help()
