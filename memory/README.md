# memory/
职责：短期对话状态（最近 N 轮），供多轮追问使用。
禁止：保存用户资产、收入、持仓等真实财务信息；import 上层模块。
接口：chat_store.push(turn) / recent(n) / clear()