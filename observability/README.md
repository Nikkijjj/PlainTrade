# observability/
职责：一次请求一个 run_id，每个 node 一条 JSONL span（状态/耗时/token/成本）。
禁止：import 任何业务模块；写业务判断。
接口：span(name) 上下文管理器 / logger.append_jsonl()