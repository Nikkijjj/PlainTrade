# guardrails/
职责：出口安全层：越界检测、重写、拒答。独立成包，禁止内联进 agent。
禁止：import agents/pipeline/ui；做通俗化改写（那是 adapt/termgate）。
接口：escalation.check(text) -> list[str] / enforce(text) -> (text, rejected)