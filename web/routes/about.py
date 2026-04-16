"""关于页面路由。"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    from web.server import templates
    return templates.TemplateResponse(request, "about.html", {"request": request})