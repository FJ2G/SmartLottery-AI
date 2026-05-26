# SmartLottery-AI - 号码趋势分析工具规格说明书

## 1. 项目概述

**项目名称**: SmartLottery-AI
**项目类型**: 基于机器学习的彩票号码趋势分析工具（桌面/CLI 应用）
**核心定位**: 提供历史数据分析与趋势可视化，辅助用户做出更理性的选号决策。**绝非"必中神器"，不保证任何中奖结果。**
**目标用户**: 对彩票有一定了解、希望通过数据驱动方式分析号码趋势的彩民。

---

## 2. 项目愿景

> "把每一次选号，变成一次有数据支撑的理性决策。"

我们不承诺中奖，只承诺：**把历史数据中隐藏的规律，用清晰的图表呈现给你**。

---

## 3. 支持的彩种

| 彩种    | 类型              | 说明                 |
|-------|-----------------|--------------------|
| 双色球   | 红球33选6 + 蓝球16选1 | 大乐透前区35选5 + 后区12选2 |
| 大乐透   | 快乐8             | 待定                 |
| 3D/P3 | 排列三/五           | 待定                 |

> 初期实现双色球，后续彩种模块化扩展。

---

## 3.5 快速上手

详细内容请参考 [QUICKSTART.md](QUICKSTART.md)。

---

## 4. 核心功能模块

### 4.1 数据管理模块 (`core/data/`) ✅

- **数据爬取**: 从公开数据源自动抓取历史开奖数据
- **本地存储**: SQLite 数据库存储开奖历史
- **数据更新**: 支持增量更新与全量重拉

> **实现文件**: `models.py`、`database.py`、`spider.py`、`manager.py`

### 4.2 统计分析模块 (`core/analysis/`)

- **基础统计** ✅
    - 各号码出现频率统计
    - 奇偶比例分布
    - 大小号比例分布
    - 区间分布（将号码划分为多个区间，统计分布）
    - 连号统计（是否出现连续号码）

> **实现文件**: `core/analysis/stats.py`（SSQStats 类）
> **CLI 命令**: `python main.py stat` / `python main.py freq`

- **趋势分析** ✅
    - N期内出现频率走势（热号、温号、冷号）
    - 遗漏值追踪（某号码距上次出现的间隔）
    - 周期性分析（某些号码组合的出现周期）

> **实现文件**: `core/analysis/trend.py`（SSQTrend 类）
> **CLI 命令**: `python main.py trend`

- **高级分析**（机器学习部分）✅
    - 基于历史数据的号码共现分析（关联规则挖掘）
    - 聚类分析（将历史开奖期次聚类，发现相似模式）
    - 号码组合评分模型（基于多维特征的号码组合打分）

> **实现文件**: `core/analysis/advanced.py`（SSQCoOccurrence / SSQClustering / SSQScorer 类）
> **CLI 命令**: `python main.py cooccur` / `python main.py cluster` / `python main.py recommend`

### 4.3 可视化模块 (`core/visualization/`) ✅

- 热力图：号码出现频率热力图
- 折线图：号码遗漏值/出现频率随时间变化
- 饼图/柱状图：奇偶、大小、区间分布
- 散点图：号码相关性分析（MDS 降维）

> **实现文件**: `core/visualization/charts.py`
> **CLI 命令**: `python main.py chart <类型>`，图表保存到 `data/charts/`

> **实现文件**: `core/visualization/charts.py`
> **CLI 命令**: `python main.py chart <类型>`，图表保存到 `data/charts/`

### 4.4 选号推荐模块 (`core/recommender/`) ✅

- 基于热力指数的智能选号 ✅
- 随机+策略混合选号（避免人脑偏误）✅
- 号码相似度匹配（查找与历史中奖号码"模式相似"的其他号码）✅
- **多方案生成**：生成多套候选方案，供用户挑选 ✅

> **实现文件**: `core/recommender/generator.py`（多策略生成器）、`core/recommender/recommender.py`（推荐主类）
> **CLI 命令**: `python main.py recommend -g 10 --strategy heat`（支持 heat/overdue/co_occur/cluster/mixed/random 六种策略，
`--show-detail` 显示详细理由）

### 4.5 CLI/界面模块 (`ui/`) ✅

- 命令行交互界面（核心）✅
- 基于 Rich 库的交互式 TUI ✅
- 数据导出（CSV / JSON）✅

> **实现文件**: `ui/tui.py`（交互式 TUI）、`ui/exporter.py`（数据导出器）
> **CLI 命令**: `python main.py run-tui`（启动交互菜单），`python main.py export`（数据导出，支持
> records/stats/trend/recommend 类型，json/csv 格式）

### 4.6 Web 网站 (`web/`) ✅

- 基于 FastAPI + Jinja2 的轻量级 Web 网站
- 页面：首页、历史记录（分页）、统计分析（含嵌入式图表）、选号推荐（表单）、号码验证
- 图表通过 matplotlib 生成并内嵌为 base64 图片，无需额外文件
- 首页顶部提供「刷新最新」与「全量刷新」快捷操作按钮

> **实现文件**: `web/server.py`（FastAPI 主服务）、`web/routes/`（各页面路由）、`web/templates/`（HTML 模板）
> **CLI 命令**: `python main.py serve`（默认监听 0.0.0.0:8080，局域网可访问），本机访问 `http://localhost:8080`，局域网访问 `http://<本机IP>:8080`

### 4.7 号码验证模块 (`web/routes/verify.py`) ✅

号码验证模块提供三个核心功能，用于验证用户号码与实际开奖的吻合程度：

- **中奖比对** ✅
    - 用户输入6红+1蓝号码，系统比对最新一期开奖结果
    - 自动判定奖级（一等奖 ~ 六等奖 / 未中奖）
    - 命中号码高亮显示、未命中号码灰色标记
    - 计算偏差分数（红球权重70% + 蓝球权重30%，满分100）

- **偏差概率分析** ✅
    - 用户输入号码，比对最近N期（默认30期）开奖记录
    - 计算平均红球命中数、蓝球命中率、平均偏差分数
    - 提供理论概率对比（理论红球平均 ≈1.09，蓝球命中率 ≈6.25%）
    - 统计各奖级出现频次
    - 逐期命中详情展示（前20期）

- **推荐号码验证** ✅
    - 系统自动生成推荐号码（支持 heat/overdue/mixed 等策略）
    - 将每组推荐号码与最近N期实际开奖比对
    - 计算每组推荐号码的平均红球命中、偏差分数、最佳奖级
    - 汇总所有推荐组的整体命中率与最佳奖级
    - 供用户评估推荐系统的实际命中概率

> **奖级判定规则**: `_check_prize(red_match, blue_match)` — 6红+1蓝→一等奖，6红→二等奖，5红+1蓝→三等奖，5红/4红+1蓝→四等奖，4红/3红+1蓝→五等奖，2红+1蓝/1红+1蓝/仅蓝→六等奖
>
> **偏差分数公式**: `_deviation_score(red_match, blue_match)` — `红球命中数 / 6 × 70 + (蓝球命中 ? 30 : 0)`，满分100
>
> **实现文件**: `web/routes/verify.py`（验证路由）、`web/templates/verify.html`（验证页面模板）
> **Web 路由**: `/verify`（页面）、`/verify/check`（中奖比对）、`/verify/deviation`（偏差分析）、`/verify/recommend`（推荐验证）

---

## 5. 技术架构

```
SmartLottery-AI/
├── core/
│   ├── data/           # 数据爬取、存储、管理
│   ├── analysis/       # 统计分析、机器学习模型
│   ├── visualization/  # 图表生成
│   └── recommender/    # 选号推荐算法
├── ui/
│   ├── tui.py          # 交互式 TUI 菜单
│   └── exporter.py      # 数据导出器（CSV/JSON）
├── web/                # Web 网站（FastAPI）
│   ├── server.py        # FastAPI 主服务
│   ├── routes/         # 页面路由（home/stats/records/recommend/about/verify）
│   └── templates/       # HTML 模板（含 verify.html）
├── models/             # 训练好的模型文件
├── data/               # SQLite 数据库存储
├── config/             # 配置文件
├── tests/              # 单元测试
├── SPEC.md             # 本规格文档
└── README.md           # 项目说明
```

### 关键技术选型

| 模块     | 技术栈                        |
|--------|----------------------------|
| 数据存储   | SQLite                     |
| 数据处理   | pandas, numpy              |
| 统计分析   | scipy, statsmodels         |
| 机器学习   | scikit-learn, torch (LSTM) |
| 可视化    | matplotlib, seaborn        |
| CLI UI | Rich, Click                |
| 数据爬取   | requests, BeautifulSoup    |

---

## 6. 免责声明（法律合规）

> **重要提示**: 本工具仅供数据分析与趋势研究之用，不构成任何投注建议。彩票中奖为随机事件，历史数据分析不能预测未来结果。理性购彩，量力而行。请遵守当地法律法规，未满18周岁禁止购买彩票。

此免责声明将在：

- 应用启动时显示
- README 文档中突出显示
- 每个分析报告/推荐结果页底部显示

---

## 7. 项目里程碑

| 阶段 | 内容               | 优先级 | 状态     |
|----|------------------|-----|--------|
| M1 | 项目初始化、数据库设计、数据爬取 | P0  | ✅ 已完成  |
| M2 | 基础统计分析功能         | P0  | 🔄 进行中 |
| M3 | CLI 界面 + 可视化     | P1  | ✅ 已完成  |
| M4 | 机器学习趋势预测         | P2  | ⬜ 待开始  |
| M5 | 选号推荐引擎           | P2  | ✅ 已完成  |
| M6 | 多彩种支持            | P3  | ⬜ 待开始  |
| M7 | GUI 界面（可选）       | P3  | ⬜ 待开始  |
| M8 | Web 网站           | P2  | ✅ 已完成  |
| M9 | 号码验证模块          | P1  | ✅ 已完成  |

---

## 8. 已知限制与边界

- **不提供**: 中奖保证、实时开奖查询、在线投注接口
- **数据依赖**: 历史数据来源于公开网站，需处理反爬机制
- **模型局限**: 所有 ML 模型仅反映历史统计规律，**不具预测未来能力**，结果仅供参考
- **性能**: 数据量超过10万条时，需优化查询与计算效率

---

## 9. 后续开发流程

1. 用户通过 Issue 或直接对话提出具体需求
2. 根据需求更新 SPEC.md 对应章节
3. 实现代码并补充测试
4. 更新 SPEC.md 的完成状态

---

*本工具旨在让数据说话，让选号更有依据。但最终，彩票的本质是娱乐，而非投资。*
