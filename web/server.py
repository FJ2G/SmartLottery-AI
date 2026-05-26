"""FastAPI 主服务。"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# 项目根目录
BASE_DIR = Path(__file__).parent.parent.resolve()

# ─── FastAPI 应用 ────────────────────────────────────────────

app = FastAPI(
    title="SmartLottery-AI",
    description="双色球号码趋势分析工具 — 查看历史数据、统计分析、选号推荐",
    version="0.1.0",
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# 静态文件（CSS/JS）
web_static = BASE_DIR / "web" / "static"
web_static.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(web_static)), name="static")

# Jinja2 模板（禁用缓存避免 request 对象导致 hash 错误）
_tpl_dir = str(BASE_DIR / "web" / "templates")
templates = Jinja2Templates(directory=_tpl_dir)
# 禁用 Jinja2 内部模板缓存，防止 request 等不可哈希对象污染缓存 key
templates.env.cache = {}  # type: ignore[assignment]

# ─── 注册路由 ───────────────────────────────────────────────

from web.routes import home, records, stats, recommend, about, verify

app.include_router(home.router)
app.include_router(records.router)
app.include_router(stats.router)
app.include_router(recommend.router)
app.include_router(about.router)
app.include_router(verify.router)
