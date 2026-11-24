# tools/
职责：agent 访问外部世界的唯一边界；每个工具声明 ToolSpec（JSON Schema 参数 + 超时）。
禁止：import agents/adapt/pipeline/ui；自己发 HTTP 或写 SQL（一律走 data/db.py）。
接口：registry.get(name) / registry.call(ToolCall) / registry.describe_all()