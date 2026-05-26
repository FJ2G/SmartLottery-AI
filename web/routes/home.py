"""主页路由 — 首页仪表盘。"""

import threading

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

# ── 全量刷新后台任务状态 ─────────────────────────────────
_update_all_state = {
    "running": False,
    "inserted": 0,
    "done": False,
    "error": None,
}
_update_all_lock = threading.Lock()


def _build_context(dm):
    """Build shared context dict for homepage."""
    from core import DataManager, SSQRecommender
    from core.analysis.stats import SSQStats

    total_records = dm.count()
    latest = dm.get_latest()
    recent_records = dm.get_recent(10)

    s_records = dm.get_recent(100)
    s_data = None
    if s_records:
        stats = SSQStats.compute(s_records)
        total = stats.freq.total
        hot_red = sorted(stats.freq.red_freq.items(), key=lambda x: x[1], reverse=True)[:3]
        hot_blue = sorted(stats.freq.blue_freq.items(), key=lambda x: x[1], reverse=True)[:3]
        odd_pct = stats.odd_even.odd_pct if hasattr(stats.odd_even, 'odd_pct') else (
            stats.odd_even.odd_count / (total * 6) * 100 if total > 0 else 0
        )
        z1 = sum(1 for r in s_records for b in r.red_balls if b <= 11)
        z2 = sum(1 for r in s_records for b in r.red_balls if 12 <= b <= 22)
        s_data = {
            "total": total,
            "hot_red": hot_red,
            "hot_blue": hot_blue,
            "odd_pct": odd_pct,
            "even_pct": 100 - odd_pct,
            "z1_pct": z1 / (total * 6) * 100,
            "z2_pct": z2 / (total * 6) * 100,
            "z3_pct": 100 - z1 / (total * 6) * 100 - z2 / (total * 6) * 100,
        }

    return {
        "total_records": total_records,
        "latest": latest,
        "recent_records": recent_records,
        "s_data": s_data,
    }


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页仪表盘：展示最新开奖、近期记录、统计数据。"""
    from web.server import templates
    from core import DataManager

    dm = DataManager()
    ctx = _build_context(dm)
    ctx["request"] = request
    ctx["rec_results"] = None
    return templates.TemplateResponse(request, "index.html", ctx)


@router.post("/", response_class=HTMLResponse)
async def index_post(
    request: Request,
    n: int = Form(100),
    generate: int = Form(5),
    strategy: str = Form(""),
):
    """首页内联推荐（POST 到 /）。"""
    from web.server import templates
    from core import DataManager, SSQRecommender

    dm = DataManager()
    ctx = _build_context(dm)

    rec_results = None
    records = dm.get_recent(n, None)
    if records:
        rec = SSQRecommender(records)
        rec.fit()
        strat = strategy if strategy else None
        plans = rec.recommend(n=generate, strategy=strat)
        rec_results = []
        for plan in plans:
            rec_results.append({
                "rank": plan.rank,
                "red_balls": sorted(plan.red_balls),
                "blue_ball": plan.blue_ball,
                "total_score": plan.total_score,
                "strategy": plan.strategy,
            })

    ctx["request"] = request
    ctx["rec_results"] = rec_results
    return templates.TemplateResponse(request, "index.html", ctx)


@router.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    """关于页面。"""
    from web.server import templates
    return templates.TemplateResponse(request, "about.html", {"request": request})


@router.post("/api/update")
async def update_data():
    """智能刷新：抓取最新一期 + 补齐当前年份缺失数据。"""
    from core import DataManager
    import traceback

    dm = DataManager()
    try:
        status, latest, year_filled = dm.update_recent()
        if latest:
            msg = f"已更新到 {latest.period} 期"
            if year_filled > 0:
                msg += f"，并补齐 {year_filled} 条历史数据"
            return {
                "ok": True,
                "period": latest.period,
                "draw_date": str(latest.draw_date),
                "red_balls": sorted(latest.red_balls),
                "blue_ball": latest.blue_ball,
                "inserted": status,
                "year_filled": year_filled,
                "message": msg,
            }
        else:
            return {"ok": False, "error": "未获取到新数据，请检查网络"}
    except Exception:
        return {"ok": False, "error": traceback.format_exc()}


def _run_update_all():
    """后台线程：全量拉取历史数据。"""
    from core import DataManager
    import traceback as _tb

    dm = DataManager()
    try:
        def on_insert(record):
            with _update_all_lock:
                _update_all_state["inserted"] += 1

        dm.update_all(on_insert=on_insert)
        with _update_all_lock:
            _update_all_state["done"] = True
            _update_all_state["running"] = False
    except Exception:
        with _update_all_lock:
            _update_all_state["error"] = _tb.format_exc()
            _update_all_state["done"] = True
            _update_all_state["running"] = False


@router.post("/api/update-all")
async def update_all_data():
    """启动全量历史数据刷新（后台线程执行）。"""
    with _update_all_lock:
        if _update_all_state["running"]:
            return {"ok": False, "error": "全量刷新正在进行中"}

        _update_all_state["running"] = True
        _update_all_state["inserted"] = 0
        _update_all_state["done"] = False
        _update_all_state["error"] = None

    t = threading.Thread(target=_run_update_all, daemon=True)
    t.start()
    return {"ok": True, "message": "全量刷新已启动"}


@router.get("/api/update-all/status")
async def update_all_status():
    """查询全量刷新进度。"""
    with _update_all_lock:
        return {
            "running": _update_all_state["running"],
            "inserted": _update_all_state["inserted"],
            "done": _update_all_state["done"],
            "error": _update_all_state["error"],
        }
