# SmartLottery-AI 快速上手指南

## 环境要求

| 依赖 | 版本要求 | 说明 |
|------|---------|------|
| Python | >= 3.10 | 建议 3.10 ~ 3.12 |
| Git | 任意版本 | 用于克隆代码仓库 |
| pip / pip3 | 最新版 | Python 包管理器 |

> **Tip**: 可通过 `python --version` 或 `python3 --version` 检查当前 Python 版本。

---

## 第一步：克隆代码

```bash
# 方式一：HTTPS（推荐新手）
git clone https://github.com/YOUR_USERNAME/SmartLottery-AI.git
cd SmartLottery-AI

# 方式二：SSH（需配置 SSH Key）
git clone git@github.com:YOUR_USERNAME/SmartLottery-AI.git
cd SmartLottery-AI
```

> 如果你是从 fork 来的项目，建议先关联上游仓库：
> ```bash
> git remote add upstream https://github.com/ORIGINAL_OWNER/SmartLottery-AI.git
> ```

---

## 第二步：创建虚拟环境（推荐）

为避免与全局 Python 包冲突，建议使用虚拟环境：

```bash
# 创建虚拟环境（项目根目录下）
python -m venv .venv

# 激活虚拟环境
# Windows (PowerShell / CMD):
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate
```

> 激活后，命令行前面会出现 `(.venv)` 标识，表示已进入虚拟环境。

---

## 第三步：安装依赖

```bash
pip install -r requirements.txt
```

> 如果遇到网络问题导致安装失败，可以换国内镜像源：
> ```bash
> pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
> ```

---

## 第四步：验证安装

```bash
# 查看数据模块统计信息
python main.py stats
```

预期输出示例：
```
数据库共 0 条记录
```

（初始为空数据库属正常现象，下一步拉取数据）

---

## 第五步：拉取双色球历史数据

```bash
# 抓取最新一期开奖数据
python main.py update-latest

# 补充某一年的历史数据（以 2024 为例）
python main.py update-year 2024

# 查看数据库统计，确认数据已入库
python main.py stats
```

---

## 第六步：查看开奖记录

```bash
# 列出最近 10 期（红球红色，篮球蓝色）
python main.py list -n 10

# 列出最近 30 期
python main.py list -n 30
```

---

## 常用命令一览

| 命令 | 说明 |
|------|------|
| `python main.py stats` | 查看数据库记录总数与最新一期 |
| `python main.py update-latest` | 抓取最新一期开奖数据 |
| `python main.py update-year <年份>` | 补充指定年份所有期次数据 |
| `python main.py list -n <数量>` | 列出最近 N 期开奖记录（彩色显示） |
| `python main.py list -n 10 --year 2026` | 列出 2026 年最近 10 期 |
| `python main.py query <日期>` | 按开奖日期查询，如 `python main.py query 2026-04-02` |
| `python main.py stat -n 100` | 基础统计分析（奇偶/大小/区间/连号） |
| `python main.py stat -n 100 --year 2026` | 分析 2026 年数据 |
| `python main.py freq -n 100 --top 10` | 冷热号分析（热号/冷号/蓝球频率） |
| `python main.py trend -n 100` | 趋势分析（热温冷/遗漏值/周期性） |
| `python main.py trend -n 100 --year 2026` | 趋势分析指定年份 |
| `python main.py cooccur -n 100` | 号码共现分析（哪些号码经常一起出现） |
| `python main.py cluster -n 100 -k 5` | 聚类分析（K-Means 期次分群） |
| `python main.py recommend -n 100 -g 10` | 号码组合推荐（生成候选并多维评分） |
| `python main.py recommend -n 100 -g 5 --strategy heat` | 热号策略推荐 |
| `python main.py recommend -n 100 -g 5 --strategy overdue` | 遗漏策略推荐 |
| `python main.py recommend -n 100 -g 5 --strategy co_occur` | 共现策略推荐 |
| `python main.py recommend -n 100 -g 5 --strategy cluster` | 相似匹配推荐 |
| `python main.py recommend -n 100 -g 5 --show-detail` | 显示详细打分和推荐理由 |
| `python main.py chart all -n 100` | 生成全部可视化图表（保存到 data/charts/） |
| `python main.py chart heatmap` | 红球频率热力图 |
| `python main.py chart trend` | 红球频率/遗漏趋势折线图 |
| `python main.py chart distribution` | 奇偶/大小/区间分布图 |
| `python main.py clear` | 清空数据库（删除所有记录） |
| `python main.py update-all` | 全量拉取 2003 年至今所有数据（耗时较长）|
| `python main.py run-tui` | 启动交互式 TUI 菜单 |
| `python main.py export --type records --format json` | 导出历史记录为 JSON |
| `python main.py export --type stats --format csv -n 100` | 导出统计报告为 CSV |
| `python main.py export --type recommend --format json -g 10` | 导出推荐结果为 JSON |
| `python main.py serve --port 8080` | 启动 Web 网站（浏览器访问）|

---

## 目录结构说明

```
SmartLottery-AI/
├── core/                  # 核心业务代码
│   ├── data/              # 数据管理模块（爬虫、数据库、模型）
│   │   ├── models.py      # SSQRecord 数据模型
│   │   ├── database.py    # SQLite 数据库操作
│   │   ├── spider.py      # 数据爬虫
│   │   └── manager.py     # 数据管理统一入口
│   ├── analysis/          # 统计分析模块（待实现）
│   ├── visualization/     # 可视化模块（待实现）
│   └── recommender/       # 选号推荐模块（待实现）
├── data/                  # SQLite 数据库存储目录（自动创建）
│   └── ssq.db             # 双色球开奖数据库
├── tests/                 # 单元测试
├── main.py                # CLI 入口脚本
├── requirements.txt       # Python 依赖清单
├── SPEC.md                # 项目规格说明书
└── QUICKSTART.md          # 本文件 —— 快速上手指南
```

---

## 第七步：启动 Web 网站

```bash
# 启动 Web 网站（默认端口 8080）
python main.py serve --port 8080
```

启动后在浏览器打开 `http://localhost:8080`，即可访问：
- **首页**：功能导航
- **历史记录**：分页浏览开奖数据
- **统计分析**：内嵌图表（频率、奇偶、大小、区间分布）
- **选号推荐**：表单生成多策略候选方案

---

## 常见问题

**Q: 运行时提示 `ModuleNotFoundError`？**
> 确保已激活虚拟环境且依赖安装成功。可执行 `pip list` 检查已安装包。

**Q: `update-latest` 抓取失败？**
> 检查网络连接；部分网络环境下可能需要配置代理；也可稍后重试。

**Q: 数据库文件在哪里？**
> 位于 `data/ssq.db`，会在首次运行时自动创建。

**Q: 如何删除图表图片？**
> 图表图片不存储在数据库中，直接操作文件系统即可：
>
> **Linux/macOS (bash/zsh)**：
> ```bash
> # 删除所有图表图片
> rm -rf data/charts/*.png
>
> # 删除指定图表（如红球热力图）
> rm data/charts/freq_heatmap_red.png
> ```
>
> **Windows (PowerShell)**：
> ```powershell
> # 删除所有图表图片
> Remove-Item data/charts/*.png -Force
>
> # 删除指定图表（如红球热力图）
> Remove-Item data/charts/freq_heatmap_red.png -Force
>
> # 删除整个 charts 目录
> Remove-Item data/charts -Recurse -Force
> ```
>
> 注意：重新生成图表时，同名文件会自动覆盖，无需手动删除旧文件。

**Q: 如何参与贡献代码？**
> 1. fork 本项目到自己的 GitHub
> 2. 从 main 分支拉新分支：`git checkout -b feature/your-feature`
> 3. 完成开发后提交 Pull Request