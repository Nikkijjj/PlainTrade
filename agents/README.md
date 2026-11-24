# agents/
职责：研究层（讨论型）——多轮、有状态、可互相反驳，最终产出 ArgDoc。
禁止：import ui/pipeline/adapt；写数据库；出现 task 分支（那是 pipeline 的事）。
接口：各 agent 暴露 run(ctx) -> AgentMessage；manager.decide() -> ArgDoc。