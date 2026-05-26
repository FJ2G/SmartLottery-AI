"""号码验证路由 — 中奖比对、偏差分析、推荐验证。"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


# ── 双色球奖级规则 ──────────────────────────────────────────
def _check_prize(red_match: int, blue_match: bool) -> dict:
    """根据红球命中数和蓝球是否命中，判断奖级。"""
    if red_match == 6 and blue_match:
        return {"level": 1, "name": "一等奖", "desc": "6红+1蓝全中"}
    if red_match == 6 and not blue_match:
        return {"level": 2, "name": "二等奖", "desc": "6红全中，蓝球未中"}
    if red_match == 5 and blue_match:
        return {"level": 3, "name": "三等奖", "desc": "5红+1蓝"}
    if red_match == 5 and not blue_match:
        return {"level": 4, "name": "四等奖", "desc": "5红中"}
    if red_match == 4 and blue_match:
        return {"level": 4, "name": "四等奖", "desc": "4红+1蓝"}
    if red_match == 4 and not blue_match:
        return {"level": 5, "name": "五等奖", "desc": "4红中"}
    if red_match == 3 and blue_match:
        return {"level": 5, "name": "五等奖", "desc": "3红+1蓝"}
    if red_match == 2 and blue_match:
        return {"level": 6, "name": "六等奖", "desc": "2红+1蓝"}
    if red_match == 1 and blue_match:
        return {"level": 6, "name": "六等奖", "desc": "1红+1蓝"}
    if red_match == 0 and blue_match:
        return {"level": 6, "name": "六等奖", "desc": "仅蓝球命中"}
    return {"level": 0, "name": "未中奖", "desc": f"{red_match}红命中，蓝球未中"}


def _deviation_score(red_match: int, blue_match: bool, total_red: int = 6) -> float:
    """计算偏差概率分数（0-100）。满分100=全部命中。"""
    red_pct = red_match / total_red * 70  # 红球权重70%
    blue_pct = 30 if blue_match else 0    # 蓝球权重30%
    return round(red_pct + blue_pct, 1)


def _parse_balls(red_str: str, blue_str: str) -> tuple:
    """解析用户输入的红球和蓝球字符串，返回 (red_list, blue_int)。"""
    red_balls = sorted([int(x.strip()) for x in red_str.replace(" ", ",").split(",") if x.strip()])
    blue_ball = int(blue_str.strip())
    return red_balls, blue_ball


# ── 功能1: 单期中奖比对 ──────────────────────────────────────
@router.get("/verify", response_class=HTMLResponse)
async def verify_page(request: Request):
    """号码验证页面。"""
    from web.server import templates
    from core import DataManager

    dm = DataManager()
    latest = dm.get_latest()
    latest_info = None
    if latest:
        latest_info = {
            "period": latest.period,
            "draw_date": str(latest.draw_date),
            "red_balls": sorted(latest.red_balls),
            "blue_ball": latest.blue_ball,
        }

    return templates.TemplateResponse(request, "verify.html", {
        "request": request,
        "latest": latest_info,
        "result": None,
        "deviation": None,
        "rec_verify": None,
        "error": None,
    })


@router.post("/verify/check", response_class=HTMLResponse)
async def verify_check(
    request: Request,
    red_input: str = Form(..., description="用户输入的红球"),
    blue_input: str = Form(..., description="用户输入的蓝球"),
):
    """功能1：比对最新一期是否中奖。"""
    from web.server import templates
    from core import DataManager

    dm = DataManager()
    latest = dm.get_latest()

    if not latest:
        return templates.TemplateResponse(request, "verify.html", {
            "request": request,
            "latest": None, "result": None, "deviation": None,
            "rec_verify": None, "error": "数据库中暂无开奖数据，请先抓取数据。",
        })

    try:
        user_red, user_blue = _parse_balls(red_input, blue_input)
    except (ValueError, IndexError):
        return templates.TemplateResponse(request, "verify.html", {
            "request": request,
            "latest": {"period": latest.period, "draw_date": str(latest.draw_date),
                       "red_balls": sorted(latest.red_balls), "blue_ball": latest.blue_ball},
            "result": None, "deviation": None, "rec_verify": None,
            "error": "号码格式错误，红球请输入6个1-33的数字（逗号分隔），蓝球输入1个1-16的数字。",
        })

    if len(user_red) != 6 or any(b < 1 or b > 33 for b in user_red) or user_blue < 1 or user_blue > 16:
        return templates.TemplateResponse(request, "verify.html", {
            "request": request,
            "latest": {"period": latest.period, "draw_date": str(latest.draw_date),
                       "red_balls": sorted(latest.red_balls), "blue_ball": latest.blue_ball},
            "result": None, "deviation": None, "rec_verify": None,
            "error": "红球需要6个（范围1-33），蓝球1个（范围1-16）。",
        })

    draw_red = set(sorted(latest.red_balls))
    draw_blue = latest.blue_ball
    user_red_set = set(user_red)

    red_match = len(user_red_set & draw_red)
    blue_match = (user_blue == draw_blue)
    prize = _check_prize(red_match, blue_match)
    dev_score = _deviation_score(red_match, blue_match)

    matched_red = sorted(user_red_set & draw_red)
    missed_red = sorted(user_red_set - draw_red)

    result = {
        "period": latest.period,
        "draw_date": str(latest.draw_date),
        "draw_red": sorted(latest.red_balls),
        "draw_blue": latest.blue_ball,
        "user_red": user_red,
        "user_blue": user_blue,
        "red_match": red_match,
        "blue_match": blue_match,
        "matched_red": matched_red,
        "missed_red": missed_red,
        "prize": prize,
        "dev_score": dev_score,
    }

    latest_info = {"period": latest.period, "draw_date": str(latest.draw_date),
                   "red_balls": sorted(latest.red_balls), "blue_ball": latest.blue_ball}

    return templates.TemplateResponse(request, "verify.html", {
        "request": request,
        "latest": latest_info,
        "result": result,
        "deviation": None,
        "rec_verify": None,
        "error": None,
    })


# ── 功能2: 偏差概率分析（比对最近N期）──────────────────────────
@router.post("/verify/deviation", response_class=HTMLResponse)
async def verify_deviation(
    request: Request,
    red_input: str = Form(..., description="用户输入的红球"),
    blue_input: str = Form(..., description="用户输入的蓝球"),
    n: int = Form(30, description="比对最近N期"),
):
    """功能2：偏差概率分析 — 看输入号码在最近N期中的命中情况。"""
    from web.server import templates
    from core import DataManager

    dm = DataManager()
    records = dm.get_recent(n, None)

    if not records:
        return templates.TemplateResponse(request, "verify.html", {
            "request": request,
            "latest": None, "result": None, "deviation": None,
            "rec_verify": None, "error": "数据库中暂无数据。",
        })

    try:
        user_red, user_blue = _parse_balls(red_input, blue_input)
    except (ValueError, IndexError):
        return templates.TemplateResponse(request, "verify.html", {
            "request": request,
            "latest": None, "result": None, "deviation": None,
            "rec_verify": None, "error": "号码格式错误。",
        })

    if len(user_red) != 6 or any(b < 1 or b > 33 for b in user_red) or user_blue < 1 or user_blue > 16:
        return templates.TemplateResponse(request, "verify.html", {
            "request": request,
            "latest": None, "result": None, "deviation": None,
            "rec_verify": None, "error": "红球需要6个（1-33），蓝球1个（1-16）。",
        })

    user_red_set = set(user_red)
    match_list = []
    total_red_hits = 0
    total_blue_hits = 0
    prize_counts = {}

    for r in records:
        draw_red = set(sorted(r.red_balls))
        rm = len(user_red_set & draw_red)
        bm = (user_blue == r.blue_ball)
        p = _check_prize(rm, bm)
        ds = _deviation_score(rm, bm)
        total_red_hits += rm
        total_blue_hits += 1 if bm else 0
        prize_counts[p["name"]] = prize_counts.get(p["name"], 0) + 1

        match_list.append({
            "period": r.period,
            "draw_date": str(r.draw_date),
            "draw_red": sorted(r.red_balls),
            "draw_blue": r.blue_ball,
            "red_match": rm,
            "blue_match": bm,
            "matched_red": sorted(user_red_set & draw_red),
            "prize": p,
            "dev_score": ds,
        })

    avg_red = round(total_red_hits / len(records), 2)
    avg_blue_pct = round(total_blue_hits / len(records) * 100, 1)
    avg_dev = round(sum(m["dev_score"] for m in match_list) / len(match_list), 1)

    # 理论概率（双色球）
    theo_red_avg = round(6 * 6 / 33, 2)   # ≈ 1.09
    theo_blue_pct = round(1 / 16 * 100, 1)  # = 6.25%

    deviation = {
        "n": len(records),
        "avg_red_match": avg_red,
        "avg_blue_pct": avg_blue_pct,
        "avg_dev_score": avg_dev,
        "theo_red_avg": theo_red_avg,
        "theo_blue_pct": theo_blue_pct,
        "prize_counts": prize_counts,
        "match_list": match_list[:20],  # 只显示最近20期
        "total_match_list": len(match_list),
    }

    latest_info = None
    latest = dm.get_latest()
    if latest:
        latest_info = {"period": latest.period, "draw_date": str(latest.draw_date),
                       "red_balls": sorted(latest.red_balls), "blue_ball": latest.blue_ball}

    return templates.TemplateResponse(request, "verify.html", {
        "request": request,
        "latest": latest_info,
        "result": None,
        "deviation": deviation,
        "rec_verify": None,
        "error": None,
    })


# ── 功能3: 推荐号码验证 ──────────────────────────────────────
@router.post("/verify/recommend", response_class=HTMLResponse)
async def verify_recommend(
    request: Request,
    n: int = Form(100, description="分析期数"),
    generate: int = Form(5, description="生成推荐组数"),
    strategy: Optional[str] = Form(None, description="策略"),
    compare_n: int = Form(30, description="比对最近N期"),
):
    """功能3：生成推荐号码，然后与最近N期实际开奖比对，验证命中率。"""
    from web.server import templates
    from core import DataManager, SSQRecommender

    dm = DataManager()
    rec_records = dm.get_recent(n, None)
    compare_records = dm.get_recent(compare_n, None)

    if not rec_records or not compare_records:
        return templates.TemplateResponse(request, "verify.html", {
            "request": request,
            "latest": None, "result": None, "deviation": None,
            "rec_verify": None, "error": "数据库中暂无数据，请先抓取数据。",
        })

    rec = SSQRecommender(rec_records)
    rec.fit()
    strat = strategy if strategy else None
    plans = rec.recommend(n=generate, strategy=strat)

    # 对每组推荐号码，比对最近N期
    verify_results = []
    for plan in plans:
        plan_red_set = set(sorted(plan.red_balls))
        plan_blue = plan.blue_ball

        hits = []
        total_red = 0
        total_blue = 0
        best_prize = {"level": 0, "name": "未中奖"}

        for r in compare_records:
            draw_red = set(sorted(r.red_balls))
            rm = len(plan_red_set & draw_red)
            bm = (plan_blue == r.blue_ball)
            p = _check_prize(rm, bm)
            ds = _deviation_score(rm, bm)
            total_red += rm
            total_blue += 1 if bm else 0
            if p["level"] > 0 and (best_prize["level"] == 0 or p["level"] < best_prize["level"]):
                best_prize = p
            hits.append({
                "period": r.period,
                "red_match": rm,
                "blue_match": bm,
                "prize": p,
                "dev_score": ds,
            })

        avg_red = round(total_red / len(compare_records), 2)
        avg_blue_pct = round(total_blue / len(compare_records) * 100, 1)
        avg_dev = round(sum(h["dev_score"] for h in hits) / len(hits), 1)

        # 统计该组号码在各奖级的频次
        prize_counts = {}
        for h in hits:
            name = h["prize"]["name"]
            prize_counts[name] = prize_counts.get(name, 0) + 1

        verify_results.append({
            "rank": plan.rank,
            "red_balls": sorted(plan.red_balls),
            "blue_ball": plan.blue_ball,
            "strategy": plan.strategy,
            "total_score": round(plan.total_score, 1),
            "avg_red_match": avg_red,
            "avg_blue_pct": avg_blue_pct,
            "avg_dev_score": avg_dev,
            "best_prize": best_prize,
            "prize_counts": prize_counts,
            "hits_detail": hits[:10],
        })

    # 统计总体命中率
    overall_avg_red = round(sum(v["avg_red_match"] for v in verify_results) / len(verify_results), 2)
    overall_avg_dev = round(sum(v["avg_dev_score"] for v in verify_results) / len(verify_results), 1)
    best_prize_level = min(v["best_prize"]["level"] for v in verify_results if v["best_prize"]["level"] > 0) if any(v["best_prize"]["level"] > 0 for v in verify_results) else 0

    rec_verify = {
        "compare_n": len(compare_records),
        "strategy": strat or "默认混合",
        "verify_results": verify_results,
        "overall_avg_red": overall_avg_red,
        "overall_avg_dev": overall_avg_dev,
        "best_prize_level": best_prize_level,
    }

    latest_info = None
    latest = dm.get_latest()
    if latest:
        latest_info = {"period": latest.period, "draw_date": str(latest.draw_date),
                       "red_balls": sorted(latest.red_balls), "blue_ball": latest.blue_ball}

    return templates.TemplateResponse(request, "verify.html", {
        "request": request,
        "latest": latest_info,
        "result": None,
        "deviation": None,
        "rec_verify": rec_verify,
        "error": None,
    })