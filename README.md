# PlainTrade

> **面向零基础投资者的投资引导 agent。** 用户用大白话提问，多个 agent 讨论后给出"说人话、带图、不越界"的回答。
>
> 它不是荐股工具，也不替你做决定 —— 它做的是把"你现在该知道的事实"讲清楚，判断权留给你。

---

## 这是什么

投资人（尤其是新手）面对的真实困难不是"没有数据"，而是：**数据看不懂、结论不敢信、建议不敢听**。

PlainTrade 用三个入口承接问题：

| 入口 | 典型提问 | 做什么 |
|---|---|---|
| **① 今天怎么了** | "今天科技股跌这么多，怎么了？" | 讲清发生了什么、可能是哪些原因、**以及我们不知道什么** |
| **② 这只怎么样** | "600519 这只怎么样？" | 生意如何、贵不贵、风险在哪、什么情况下我们会错 |
| **③ 钱怎么放** | "我手上有 10 万，该怎么分配？" | 讲分配原则与常见陷阱，**只给示例不给建议** |

每个回答都要满足三条硬要求：

1. **说人话** —— 行话必须解释，否则视为缺陷
2. **不失真** —— 简化不能改变结论；**归因不明时连图都不画**（画图会让人以为"已经知道原因"）
3. **不越界** —— 不出现买卖指令、具体比例、目标价；越界率必须为 0

## 现在到哪一步了

**进度请看 [待开发项](docs/待开发项.md)** —— 已完成什么、还差哪些、每项的验收标准与依赖关系都在那里。

---

## 快速开始

### 1. 装依赖

```bash
cd plantrade
python -m venv .venv              # 建议用独立虚拟环境
.venv\Scripts\activate            # Windows（Mac/Linux：source .venv/bin/activate）
pip install -r requirements.txt
```

### 2. 配置 API Key（真跑 agent 才需要）

```bash
cp .env.example .env              # Windows 用 copy；然后填 DEEPSEEK_API_KEY=sk-xxxx
```

没有 key 也能：跑测试、跑数据自检、看离线演示界面。**只有真跑 agent（问问题）才需要 key。**

### 3. 拿数据（clone 下来就有）

仓库里带了一份数据快照 `data_files/plantrade.db`（约 55 MB，2023-01 ~ 2025-06，
含财报正文 + 板块）。clone 后先校验完整性：

```bash
python -m scripts.db_manifest --verify
```

> 想自己重建（约 10 分钟，需联网）：见 [数据文档 §九](docs/数据状态.md)。

### 4. 跑起来

**启动 Web 界面**：

```bash
python -m api.main                 # 或 python -m uvicorn api.main:app --reload
```

浏览器打开 **http://127.0.0.1:8000**，直接问：

```
600519 这只怎么样？
```

回答是**流式**的（"正在理解你的问题… → 三个分析师分析… → 出图"一步步显示）。

> ⚠️ 要用 `-m`（`python -m api.main`），**不要** `python api/main.py`（会找不到 config 模块）。

**或只看离线演示**（不用装任何服务端依赖）：直接双击 `frontend/index.html`。

**或只跑命令行自检**：

```bash
python -m pytest -q                # 62 passed（不需要 key）
python -m scripts.check_structure  # 目录 / 依赖方向 / 200 行限制
python -m scripts.check_contracts  # 契约校验
python -m scripts.check_pipeline --as-of 2025-01-04 --code 600519
```

---

## 项目结构

```
plantrade/
├── contracts/       唯一跨模块契约（ArgDoc / ChartSpec / PlainBrief / AgentMessage / Tool）
├── config/          设置、14 个提示词、图表契约、术语表、路径解析
├── data/            取数、入库、SQLite 唯一入口 db.py、增量刷新 refresh.py
│   └── sources/     6 个接口封装（东财 5 个 + 巨潮公告正文）
├── research/        检索（FTS5 + jieba）
├── tools/           agent 访问外部世界的唯一边界（6 个工具）
├── llm/             模型调用、结构化输出、缓存、成本
├── agents/          router + 三分析师 + 辩论 + 经理
├── adapt/           适配层（纯函数）：压缩、术语门控、保真度、图表决策、渲染、归因
├── guardrails/      越界检测与拒答
├── pipeline/        编排（四个问题模板 + node 降级）
├── api/             FastAPI：/api/ask（含流式 /api/ask/stream）+ /api/health + 托管前端
├── frontend/        单文件 HTML 界面（CSS/JS 内联，零构建）
├── ui/              旧版 Streamlit 骨架（备用，不参与交付）
├── eval/            评估指标与批量跑
├── scripts/         自检、建库辅助、启动器、打包
├── tests/           62 个测试
└── docs/            开发文档 / Agent 需求 / 数据文档 / 待开发项
```

### 依赖只能单向

```
ui → pipeline → agents / adapt / guardrails → tools / research / data → llm / observability
```

`agents` **不许** import `data`（必须走 `tools`）；`adapt` 只许 import `{adapt, contracts, config, llm}`。
违反会被 `check_structure` 拦下 —— 这不是洁癖，是为了让 **as-of 防泄漏只有一个入口**。

---

## 数据

| 数据 | 现状 | 用途 |
|---|---|---|
| 日线（hfq + qfq） | ✅ 9,616 行 / 601 个交易日 | 收益、回撤、K 线、算市值 |
| 指数 | ✅ 1,202 行（上证 + 创业板） | 事件触发、判断是否普跌、交易日历 |
| 公告 | ✅ 2,816 条标题 + 财报正文 93% | 事实性结论的**唯一证据源**（财报正文经巨潮 PDF） |
| 财务 | ✅ 800 行 / 20 期，带实际披露日 | 营收增速、PE/PB |
| 板块 | ✅ 8 板块 / 4,808 行情 / 340 成分 | 事件场景的板块图 |
| 新闻 | ❌ 0（回放模式正常为空） | 仅近端，**不进历史证据链** |

数据来源：东方财富公开网页接口（行情/财务/公告列表等）+ 巨潮资讯（公告正文 PDF）。抓取已限速。
接口细节、坑、恢复步骤见 **[数据文档](docs/数据状态.md)**（数据部分的唯一真相源）。

**两条必须知道的限制**（写进报告用）：
1. 新闻只能回溯约 40 天 → 用来解释历史事件就是前视偏差，所以证据以公告为主
2. 拿不到全市场涨跌家数 → 文案里不得出现"全市场 X 只下跌"

---

## 技术栈

Python 3.11 · pydantic v2 · SQLite（FTS5 + jieba 分词）· FastAPI · 原生 HTML/CSS/JS · matplotlib · PyInstaller

没有前端构建链（无 npm / 无打包），前端就是一个 HTML 文件。

---

## 文档

| 文档 | 看它解决什么问题 |
|---|---|
| [待开发项](docs/待开发项.md) | 谁做什么、10 个空函数在哪、验收标准、依赖与检查点、**Git 协作流程（分支/PR/冲突）** |
| [Agent 开发需求](docs/Agent开发需求.md) | 每个 agent 模块要做什么、硬约束、图表决策规则 |
| [开发文档](docs/开发文档.md) | 架构全景、数据摘要与缺口影响、agent 分层、可视化设计 |
| [数据文档](docs/数据状态.md) | 数据来源、接口、存储、当前状态、9 个已踩的坑、恢复命令 |
