# llm/
职责：唯一的模型调用通道：调用、结构化输出、缓存、计费。
禁止：写提示词（在 config/prompts/）；做业务判断；import agents/pipeline/ui。
接口：client.complete() / structured.complete_json() / cache.key() / cost.usd()