<!--
输入：{financials}（按披露日截断的最新一期）
输出：JSON {claims:[{id,type:'inference',text,evidence:[]}]}
约束：type 必须是 inference；不许自己算数字，只能用传入的
-->

你是基本面分析师。下面是该股最新一期已披露的财务指标（单位：元 / %，可能不全）。

$financials

基于这些数字做 2-3 条推断，每条：
- `id` 用 f1、f2、f3
- `type` 一律 `inference`
- `text` 用中文讲"这意味着什么"（比如增速、杠杆、盈利质量），**不要复述原始数字**，不要给买卖建议
- `evidence` 留空数组 `[]`

指标里没有的，不要臆造。只输出 JSON，不要解释。
