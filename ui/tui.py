"""交互式 TUI 菜单。"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text

console = Console()


# ─── 菜单项定义 ──────────────────────────────────────────────


class MenuItem:
    def __init__(self, key: str, label: str, action: Callable[[], None] | None = None,
                 children: "List[MenuItem]" | None = None):
        self.key = key        # 菜单键，如 "1", "1.1", "back"
        self.label = label    # 显示文本
        self.action = action   # 执行函数
        self.children = children  # 子菜单


def _run_submenu(title: str, items: List[MenuItem], parent_menu: Callable) -> None:
    """渲染并处理子菜单。"""
    while True:
        console.rule(f"[bold cyan]{title}[/bold cyan]")

        for item in items:
            console.print(f"  [yellow]{item.key}[/yellow]  {item.label}")

        console.print()
        console.print("  [dim]0.[/dim]  返回上级菜单")
        choice = console.input("\n请输入选项编号: ").strip()

        if choice == "0":
            break

        matched = [item for item in items if item.key == choice]
        if not matched:
            console.print("[red]无效选项，请重新输入[/red]\n")
            continue

        item = matched[0]
        if item.action:
            try:
                item.action()
            except Exception as e:
                console.print(f"[red]执行出错: {e}[/red]")
        console.print()


# ─── 各功能菜单动作 ──────────────────────────────────────────


def _do_update_latest():
    from main import cmd_update_latest
    cmd_update_latest()


def _do_update_year():
    try:
        year = int(console.input("请输入年份（如 2024）: ").strip())
        from main import cmd_update_year
        cmd_update_year(year)
    except ValueError:
        console.print("[red]请输入有效年份[/red]")


def _do_stats():
    from main import cmd_stats
    cmd_stats()


def _do_clear():
    confirm = console.input("确定要清空数据库吗？此操作不可恢复！(y/N): ").strip().lower()
    if confirm == "y":
        from main import cmd_clear
        cmd_clear()
    else:
        console.print("[dim]已取消[/dim]")


def _do_list_recent():
    try:
        n = int(console.input("请输入期数（默认 10）: ").strip() or "10")
        from main import cmd_list_recent
        cmd_list_recent(n, None)
    except ValueError:
        console.print("[red]请输入有效数字[/red]")


def _do_query():
    date_str = console.input("请输入日期（格式 YYYY-MM-DD）: ").strip()
    if date_str:
        from main import cmd_query
        cmd_query(date_str)
    else:
        console.print("[red]请输入日期[/red]")


def _do_stat():
    try:
        n = int(console.input("请输入分析最近多少期（默认 100）: ").strip() or "100")
        from main import cmd_stat
        cmd_stat(n, None)
    except ValueError:
        console.print("[red]请输入有效数字[/red]")


def _do_freq():
    try:
        n = int(console.input("请输入分析最近多少期（默认 100）: ").strip() or "100")
        from main import cmd_freq
        cmd_freq(n, 10, None)
    except ValueError:
        console.print("[red]请输入有效数字[/red]")


def _do_trend():
    try:
        n = int(console.input("请输入分析最近多少期（默认 100）: ").strip() or "100")
        from main import cmd_trend
        cmd_trend(n, None)
    except ValueError:
        console.print("[red]请输入有效数字[/red]")


def _do_cooccur():
    try:
        n = int(console.input("请输入分析最近多少期（默认 100）: ").strip() or "100")
        from main import cmd_cooccur
        cmd_cooccur(n, 10, None)
    except ValueError:
        console.print("[red]请输入有效数字[/red]")


def _do_cluster():
    try:
        n = int(console.input("请输入分析最近多少期（默认 100）: ").strip() or "100")
        k = int(console.input("请输入聚类数（默认 5）: ").strip() or "5")
        from main import cmd_cluster
        cmd_cluster(n, k, None)
    except ValueError:
        console.print("[red]请输入有效数字[/red]")


def _do_recommend():
    try:
        n = int(console.input("请输入基于最近多少期（默认 100）: ").strip() or "100")
        g = int(console.input("请输入生成候选组数（默认 10）: ").strip() or "10")
        console.print("策略选项: [cyan]heat[/cyan] / [cyan]overdue[/cyan] / "
                      "[cyan]co_occur[/cyan] / [cyan]cluster[/cyan] / "
                      "[cyan]mixed[/cyan] / [cyan]random[/cyan]（直接回车默认 mixed）")
        strat = console.input("请选择策略: ").strip() or None
        from main import cmd_recommend
        cmd_recommend(n, g, None, strat, True)
    except ValueError:
        console.print("[red]请输入有效数字[/red]")


def _do_chart_all():
    try:
        n = int(console.input("请输入基于最近多少期（默认 100）: ").strip() or "100")
        from main import cmd_chart
        console.print("[dim]正在生成全部图表...[/dim]")
        cmd_chart("all", n, None, None)
        console.print("[green]图表已保存到 data/charts/ 目录[/green]")
    except ValueError:
        console.print("[red]请输入有效数字[/red]")


def _do_chart_heatmap():
    try:
        n = int(console.input("请输入基于最近多少期（默认 100）: ").strip() or "100")
        from main import cmd_chart
        cmd_chart("heatmap", n, None, None)
    except ValueError:
        console.print("[red]请输入有效数字[/red]")


def _do_chart_trend():
    try:
        n = int(console.input("请输入基于最近多少期（默认 100）: ").strip() or "100")
        from main import cmd_chart
        cmd_chart("trend", n, None, None)
    except ValueError:
        console.print("[red]请输入有效数字[/red]")


def _do_chart_distribution():
    try:
        n = int(console.input("请输入基于最近多少期（默认 100）: ").strip() or "100")
        from main import cmd_chart
        cmd_chart("distribution", n, None, None)
    except ValueError:
        console.print("[red]请输入有效数字[/red]")


def _do_export_records():
    try:
        fmt = console.input("导出格式 [cyan]json[/cyan]/csv（直接回车默认 json）: ").strip() or "json"
        from core import DataManager
        from ui.exporter import DataExporter
        dm = DataManager()
        records = dm.get_recent(10000, None)
        if not records:
            console.print("[yellow]数据库中暂无数据[/yellow]")
            return
        exporter = DataExporter()
        path = exporter.export_records(records, format=fmt if fmt in ("json", "csv") else "json")
        console.print(f"[green]已导出: {path}[/green]")
    except Exception as e:
        console.print(f"[red]导出失败: {e}[/red]")


def _do_export_stats():
    try:
        n = int(console.input("请输入分析最近多少期（默认 100）: ").strip() or "100")
        fmt = console.input("导出格式 [cyan]json[/cyan]/csv（直接回车默认 json）: ").strip() or "json"
        from core import DataManager, SSQStats
        from core.analysis.stats import SSQStats as StatsCls
        from ui.exporter import DataExporter, _dataclass_to_dict
        dm = DataManager()
        records = dm.get_recent(n, None)
        if not records:
            console.print("[yellow]数据库中暂无数据[/yellow]")
            return
        stats = StatsCls.compute(records)
        stats_dict = _dataclass_to_dict(stats)
        exporter = DataExporter()
        path = exporter.export_stats(stats_dict, format=fmt if fmt in ("json", "csv") else "json")
        console.print(f"[green]已导出: {path}[/green]")
    except Exception as e:
        console.print(f"[red]导出失败: {e}[/red]")


def _do_export_recommend():
    try:
        n = int(console.input("请输入基于最近多少期（默认 100）: ").strip() or "100")
        g = int(console.input("请输入生成候选组数（默认 10）: ").strip() or "10")
        fmt = console.input("导出格式 [cyan]json[/cyan]/csv（直接回车默认 json）: ").strip() or "json"
        from core import DataManager, SSQRecommender
        from ui.exporter import DataExporter
        dm = DataManager()
        records = dm.get_recent(n, None)
        if not records:
            console.print("[yellow]数据库中暂无数据[/yellow]")
            return
        rec = SSQRecommender(records)
        rec.fit()
        plans = rec.recommend(n=g)
        exporter = DataExporter()
        path = exporter.export_recommend(plans, format=fmt if fmt in ("json", "csv") else "json")
        console.print(f"[green]已导出: {path}[/green]")
    except Exception as e:
        console.print(f"[red]导出失败: {e}[/red]")


# ─── 主菜单 ──────────────────────────────────────────────────


MENU_ITEMS: List[MenuItem] = [
    MenuItem(
        key="1", label="数据管理",
        children=[
            MenuItem(key="1.1", label="更新最新一期", action=_do_update_latest),
            MenuItem(key="1.2", label="补充某年数据", action=_do_update_year),
            MenuItem(key="1.3", label="查看数据库统计", action=_do_stats),
            MenuItem(key="1.4", label="清空数据库", action=_do_clear),
        ],
    ),
    MenuItem(
        key="2", label="查询记录",
        children=[
            MenuItem(key="2.1", label="列出最近 N 期", action=_do_list_recent),
            MenuItem(key="2.2", label="按日期查询", action=_do_query),
        ],
    ),
    MenuItem(
        key="3", label="统计分析",
        children=[
            MenuItem(key="3.1", label="基础统计", action=_do_stat),
            MenuItem(key="3.2", label="冷热号分析", action=_do_freq),
            MenuItem(key="3.3", label="趋势分析", action=_do_trend),
            MenuItem(key="3.4", label="共现分析", action=_do_cooccur),
            MenuItem(key="3.5", label="聚类分析", action=_do_cluster),
        ],
    ),
    MenuItem(
        key="4", label="选号推荐",
        children=[
            MenuItem(key="4.1", label="智能推荐（多策略）", action=_do_recommend),
        ],
    ),
    MenuItem(
        key="5", label="可视化图表",
        children=[
            MenuItem(key="5.1", label="生成全部图表", action=_do_chart_all),
            MenuItem(key="5.2", label="红球频率热力图", action=_do_chart_heatmap),
            MenuItem(key="5.3", label="频率/遗漏趋势图", action=_do_chart_trend),
            MenuItem(key="5.4", label="分布图（奇偶/大小/区间）", action=_do_chart_distribution),
        ],
    ),
    MenuItem(
        key="6", label="数据导出",
        children=[
            MenuItem(key="6.1", label="导出历史记录 (CSV/JSON)", action=_do_export_records),
            MenuItem(key="6.2", label="导出统计分析 (CSV/JSON)", action=_do_export_stats),
            MenuItem(key="6.3", label="导出推荐结果 (CSV/JSON)", action=_do_export_recommend),
        ],
    ),
]


def _show_main_menu():
    """显示主菜单。"""
    console.rule("[bold bright_blue]SmartLottery-AI 交互式菜单[/bold bright_blue]")
    console.print()

    for item in MENU_ITEMS:
        console.print(f"  [yellow]{item.key}[/yellow]  {item.label}")

    console.print()
    console.print("  [yellow]0[/yellow]  退出程序")


def _show_disclaimer():
    """显示免责声明。"""
    console.print(Panel(
        "[bold red]⚠ 免责声明[/bold red]\n\n"
        "本工具仅供数据分析与趋势研究之用，不构成任何投注建议。\n"
        "彩票中奖为随机事件，历史数据分析不能预测未来结果。\n"
        "理性购彩，量力而行。请遵守当地法律法规。",
        title="重要提示",
        border_style="red",
    ))
    console.print()


def run_tui():
    """
    启动交互式 TUI 菜单。

    使用示例::

        python main.py run-tui
    """
    console.clear()
    _show_disclaimer()

    console.print("[dim]欢迎使用 SmartLottery-AI[/dim]\n")
    console.input("按 [green]回车键[/green] 进入主菜单...")
    console.clear()

    while True:
        _show_main_menu()
        choice = console.input("\n请输入选项编号: ").strip()

        if choice == "0":
            console.print("\n[green]感谢使用，再见！[/green]\n")
            break

        matched = [item for item in MENU_ITEMS if item.key == choice]
        if not matched:
            console.print("[red]无效选项，请重新输入[/red]\n")
            console.input("按回车继续...")
            console.clear()
            continue

        item = matched[0]
        if item.children:
            console.clear()
            _run_submenu(item.label, item.children, _show_main_menu)
            console.clear()
        else:
            console.clear()
            if item.action:
                try:
                    item.action()
                except Exception as e:
                    console.print(f"[red]执行出错: {e}[/red]")
            console.print()
            console.input("按回车返回主菜单...")
            console.clear()
