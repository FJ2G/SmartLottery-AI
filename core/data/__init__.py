"""core.data - 双色球数据管理模块。

主要导出:

- SSQRecord  : 单条开奖记录数据模型
- SSQDatabase: SQLite 数据库操作层
- SSQSpider  : 数据爬虫
- DataManager: 统一数据管理入口
"""

from .database import SSQDatabase
from .manager import DataManager
from .models import SSQRecord
from .spider import SSQSpider

__all__ = [
    "SSQRecord",
    "SSQDatabase",
    "SSQSpider",
    "DataManager",
]