"""历史记录路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


def _get_db_records(year: Optional[int] = None, page: int = 1, size: int = 20):
    """从数据库获取分页记录。"""
    from core import DataManager

    dm = DataManager()
    all_records = dm.get_recent(999999, year)
    total = len(all_records)
    start = (page - 1) * size
    end = start + size
    records = all_records[start:end]

    # 转换为字典列表
    items = []
    for r in records:
        items.append({
            "period": r.period,
            "draw_date": str(r.draw_date) if hasattr(r.draw_date, "isoformat") else str(r.draw_date),
            "red_balls": sorted(r.red_balls),
            "blue_ball": r.blue_ball,
        })
    return items, total


@router.get("/records", response_class=HTMLResponse)
async def list_records(
    request: Request,
    year: Optional[int] = Query(None, description="按年份筛选"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    """历史开奖记录列表（分页）。"""
    from web.server import templates

    items, total = _get_db_records(year=year, page=page, size=size)
    total_pages = (total + size - 1) // size

    # Build page range for template
    page_range = []
    if total_pages <= 7:
        page_range = list(range(1, total_pages + 1))
    else:
        page_range = [1]
        if page > 3:
            page_range.append("...")
        for p in range(max(2, page - 1), min(total_pages, page + 1) + 1):
            if p not in page_range:
                page_range.append(p)
        if page < total_pages - 2:
            page_range.append("...")
        if total_pages not in page_range:
            page_range.append(total_pages)

    return templates.TemplateResponse(request, "records.html", {
        "request": request,
        "records": items,
        "page": page,
        "size": size,
        "total": total,
        "total_pages": total_pages,
        "year": year,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if page < total_pages else None,
        "page_range": page_range,
    })
