"""选号推荐路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/recommend", response_class=HTMLResponse)
async def recommend_page(
    request: Request,
):
    """选号推荐页面（表单）。"""
    from web.server import templates

    return templates.TemplateResponse(request, "recommend.html", {
        "request": request,
        "results": None,
        "error": None,
        "form_data": None,
    })


@router.post("/recommend", response_class=HTMLResponse)
async def do_recommend(
    request: Request,
    n: int = Form(100, description="分析最近 N 期"),
    generate: int = Form(10, description="生成候选数量"),
    strategy: Optional[str] = Form(None, description="生成策略"),
):
    """执行选号推荐。"""
    from web.server import templates
    from core import DataManager, SSQRecommender

    dm = DataManager()
    records = dm.get_recent(n, None)
    if not records:
        return templates.TemplateResponse(request, "recommend.html", {
            "request": request,
            "results": None,
            "error": "数据库中暂无数据，请先抓取数据。",
            "form_data": {"n": n, "generate": generate, "strategy": strategy},
        })

    rec = SSQRecommender(records)
    rec.fit()
    plans = rec.recommend(n=generate, strategy=strategy)

    results = []
    for plan in plans:
        results.append({
            "rank": plan.rank,
            "red_balls": sorted(plan.red_balls),
            "blue_ball": plan.blue_ball,
            "total_score": plan.total_score,
            "strategy": plan.strategy,
            "explanation": plan.explanation,
            "freq_score": plan.score_breakdown.get("frequency", 0),
            "miss_score": plan.score_breakdown.get("missing", 0),
            "co_score": plan.score_breakdown.get("co_occurrence", 0),
            "pat_score": plan.score_breakdown.get("pattern", 0),
        })

    return templates.TemplateResponse(request, "recommend.html", {
        "request": request,
        "results": results,
        "error": None,
        "form_data": {"n": n, "generate": generate, "strategy": strategy},
    })
