# Agent 开发需求

> 只写**要做什么**，不写怎么实现。实现细节看代码注释与 [开发文档](开发文档.md)。
> 谁做什么见 [待开发项](待开发项.md)。

## 需求是活的（怎么改）

这份文档写的是**当前共识**，不是不可动的规章。做的过程中发现更好的做法，**改就是了** ——
但按下面三步走，别自己闷头改。

| 能改的（欢迎提） | 不能改的（红线） |
|---|---|
| 某个需求的做法（比如术语门控改成「先替换后补解释」） | `contracts/` 的字段与校验规则（改要三人同意 + 升 `schema_version`） |
| 验收标准（只要能证明「更好」或「够用」） | **as-of 防泄漏**：只认 `publish_time` / `announce_date` |
| 新增需求（用新编号，别改旧编号含义） | **越界红线**：不出现买卖指令、具体比例、目标价 |
| 删掉不做的需求（标 ❌ 并写原因） | **归因不明不出图**（视觉过度归因） |
| 优先级与估时 | 依赖单向（`agents` 不许 import `data`） |

**改的流程（三步，五分钟）：**

1. **先对齐**：群里说一句「我想把 X 改成 Y，因为 Z」，另外两人没意见就过
2. **改文档**：在本文件改对应需求，并在下面的变更记录里加一行
3. **再改代码**：顺序不能反 —— 先改代码后补文档，等于没有文档

> 需求变更是**正常现象**，不是返工。vibe coding 最容易出事的地方是「三个人各自按不同理解实现」，
> 而不是「改了主意」。

### 变更记录

| 日期 | 改了什么 | 为什么 | 谁 |
|---|---|---|---|
| 2026-11-23 | 新增 R-07 术语标注与解释卡 | 说人话需要「随时可查」，光改写不够 | — |
|  |  |  |  |

## 全局约束

1. 依赖单向：`ui → pipeline → agents/adapt/guardrails → tools/research/data → llm/observability`。
   **`agents` 不许 import `data`**，只能走 `tools`。
2. `contracts/` 只读；改字段必须三人同意 + 升 `schema_version`。
3. 单文件 ≤200 行；不新建 `utils.py` 之类的杂物包。
4. 结构化输出必须走 `llm.structured.complete_json`，**禁止裸 `json.loads`**。
5. 失败不抛裸异常：工具返回 `ToolResult(ok=False)`，node 按 `pipeline/graph.py` 降级。
6. 提示词变量用 `$var`（`string.Template`），不是 `{var}`。

自检：`python -m scripts.check_structure` / `check_contracts` / `pytest -q`

---

## R-01 LLM 客户端（B｜P0）

`llm/client.py::complete(prompt_name, *, temperature=None, max_tokens=None, **vars) -> str`

| 项 | 要求 |
|---|---|
| 做什么 | 渲染提示词 → 调 DeepSeek → 返回纯文本 |
| 调用方式 | `requests` 直连，不引入 `openai` 包 |
| 温度 | 默认取 `settings.llm_temperature`（0），保证可复现 |
| 超时/重试 | 60s，失败重试 2 次（退避） |
| 日志 | 每次调用向 `logs/spans.jsonl` 追加一行：prompt 名/hash、token、usd、耗时、run_id |
| 必须 | key 为空时报**中文可读错误**，不能吐 401 traceback |

---

## R-02 三个分析师（B｜P0）

`agents/analysts/*.py`，继承 `BaseAgent`，只需实现 `build_vars` / `parse`。

| 分析师 | 输入 | 输出 | 硬约束 |
|---|---|---|---|
| `disclosure` | `docs` `financials` | claim 列表 | **只 `type=fact`**；禁止推断；无证据返回空 |
| `fundamental` | `financials` | claim 列表 | **只 `type=inference`**；不许自己算数字 |
| `technical` | `indicators` | claim 列表 | **禁止支撑位 / 买入点 / 目标价** |

- `evidence` 只能填 `ctx["evidence_ids"]` 里的 `art_code`；编造的会被 `drop_hallucinated()` 丢掉。
- 单个分析师失败 → 记入 `information_gaps`，链路不中断。

---

## R-03 研究经理（B｜P0）

`agents/manager.py::decide(*, task, code, as_of, messages, debate_result, evidence) -> ArgDoc`

| 要求 | 说明 |
|---|---|
| 唯一有权输出 `stance` | 其余 agent 不得给方向 |
| 证据不足 → `no_view` | 可支撑方向的 `fact` claim ≤1 条，或 `information_gaps` ≥2 条 |
| `confidence` 与缺口负相关 | 缺口每多一条，把握降一档 |
| `invalidation_conditions` 必须可观察 | ✅"下季度营收增速掉到 5% 以下"　❌"如果基本面恶化" |
| `evidence` 只能来自入参 | 不得新造 |
| `explanation_status` | 个股场景填 `not_applicable`；事件场景才用 `unknown` / `single_cause` / `multiple_candidates` |

**验收不是"读起来像分析师"**，而是：证据不足时会 `no_view`、失效条件可观察、置信度与缺口负相关。

---

## R-04 辩论（B｜P1）

`agents/debate.py::debate(claims, evidence_ids, rounds=1) -> DebateResult`

- Bull 找反证，Bear 找失效条件，**都不是唱反调**
- **不得引入新 fact**，只引用已有 `evidence_id`
- 失败返回空 `DebateResult()` 即可（允许降级）
- `settings.debate_enabled=False` 时整步跳过

---

## R-05 编排（B｜P0）

`pipeline/run.py::run(user_text, as_of) -> PlainBrief` 与 `_research(ctx) -> ArgDoc`

| 要求 | 说明 |
|---|---|
| 唯一入口 | 外部只调 `run()` |
| `as_of` 只固定一次 | 入口定下，全链路只传不重取 |
| 唯一联网点 | `live` 模式下的 `refresh.ensure_fresh()`，其余一律读库 |
| 产物 | 必须返回合法 `PlainBrief` |
| **图必须真渲染** | 调 `adapt.render.render()`，把路径填进 `charts[].image_path`；不填前端永远没图 |
| 每步留痕 | 每个 node 一条 span |
| 降级 | 按 `graph.py`：analysts/debate/termgate `skip`，chart `default=不出图`，guardrail `default=拒答` |

---

## R-06 适配层（C｜P0–P1）

**只能靠入参算出结果，不许读取"输入以外的东西"**：不查数据库、不发网络请求、不读别的模块的状态。
（`check_structure` 的依赖矩阵会拦：`adapt` 只允许 import `{adapt, contracts, config, llm}`）

为什么：① `as_of` 防泄漏全在 `data/db.py`，adapt 若能查库就成了绕过它的后门，而漏写 `as_of` **不会报错**；
② 纯函数能用 fixtures 做 0.01 秒单测，不用库、不用网络、不用 key —— 三人并行开发的前提；
③ 进评估指标的东西必须确定，否则"行话率 12%"下周复现不出来。

两处受控例外：`termgate` 可调 `llm` 做改写（改行话只能靠模型）；`render` 可把 PNG **写**到入参指定的 `out_dir`（写产物不算读取）。

| 函数 | 输入 → 输出 | 要求 |
|---|---|---|
| `summarize.summarize(argdoc)` | → `(one_liner, stance_plain, ConfidencePlain)` | `plain_confidence()` 已实现，直接用；一句话 ≤30 字、第二人称、不用"建议" |
| `termgate.detect(text)` | → 命中术语列表（词 + 位置） | 词表在 `config/jargon.json`，**需从 5 条扩到 ≥20 条** |
| `termgate.enforce(text, max_rounds=3)` | → `(改后文本, 轮数)` | 检测→改写→复检；超轮数降级为模板替换。**改写不掉的术语要保留并挂解释**（不是删掉） |
| `fidelity.judge(plain_claim, evidence_quote)` | → `supported\|weakened\|distorted` | 丢失关键限定词（"同比""约"）判 `weakened` |
| `chart.plan(argdoc)` | → `ChartSpec` | `unknown → skip` 已实现；补其余 5 种 need_type |
| `render.render(spec, data, out_dir)` | → PNG 路径 | 确定性（同输入同图）、中文不乱码、涨红跌绿、caption 必带 |

### 图表决策规则

| 场景 | need_type | chart_type |
|---|---|---|
| `explanation_status=unknown` | `no_attribution` | **不出图**（已实现） |
| 事件场景 | `attribution` | `bar`（板块涨跌幅） |
| 钱怎么放 | `allocation` | `stacked_bar`（"示例非建议"水印） |
| 个股 + 含风险判断 | `risk` | `drawdown_curve` |
| 个股 + 与指数/同业对比 | `compare` | `relative_line`（基准=100） |
| 个股 + 序列 ≥20 日 | `trend` | `line` |
| 序列不足 | — | 不出图，给 reason |

**出图必须带 caption**（一句话说"这张图想让用户看到什么"）；**LLM 不接触任何数值**。

**数据不足时不许画空图**：`board_daily` 为空时 `db.board_pct_changes()` 返回 `[]`，
此时 `attribution` 类图必须降级为 `skip`（reason="板块数据不可用"）——
一张空的柱状图和一张乱画的图一样，都属于视觉失真。

---

## R-07 术语标注与解释卡（C｜P1）

"说人话"在交互上的落地：**术语不能只说一遍就算解释过了，要让用户随时能点开看。**

| 环节 | 负责 | 要求 |
|---|---|---|
| 识别 | `adapt.termgate.detect()` | 从 `config/jargon.json`（≥20 条）里找出文本中出现的术语；返回命中项的**词与位置** |
| 改写 | `adapt.termgate.enforce()` | 能把行话改写成通俗说法；改写不掉的，**保留术语并挂上解释**（不是删掉） |
| 产出 | `PlainBrief.glossary[]` | `GlossaryTerm{id, term, plain, analogy}`，`plain` 一句话、`analogy` 打个比方 |
| 渲染 | `frontend/index.html` | 按 `term` 匹配文本 → 包 `<span class="term" data-id>` → **虚线下划线**；**点击**弹出小卡片显示 `plain` + `analogy` |

硬约束：

- 前端**不许**把 `glossary` 拼成 HTML 字符串塞进回答 —— 只允许"匹配到词 → 加标记 → 事件监听"
- 卡片内容**只解释词义**，不得夹带结论、建议、比例
- 关闭方式三选一都要有：点外部 / Esc / 再点该词
- 移动端必须可用（所以不能用 hover 或原生 `title`）

验收：

- [ ] 回答里出现「市盈率」时该词带虚线下划线
- [ ] 点击弹出卡片，含通俗解释与类比
- [ ] 点外部 / Esc 能关闭
- [ ] 术语没被替换掉（原文仍在）
- [ ] 卡片内无任何买卖建议字样（跑 `guardrails.escalation.check()` 为空）

## 通用验收

- [ ] 函数体不再是 `raise NotImplementedError`
- [ ] 至少 1 条 pytest，`pytest -q` 全绿
- [ ] 失败路径有处理，不抛裸异常
- [ ] `check_structure` / `check_contracts` 通过
- [ ] 文件 ≤200 行
