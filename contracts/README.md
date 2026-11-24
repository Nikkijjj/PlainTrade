# contracts/
职责：定义全部跨模块数据契约，零依赖，D2 冻结后只允许新增可选字段。
禁止：import 任何业务模块；写业务逻辑；调模型；读写文件。
接口：ArgDoc / ChartSpec / PlainBrief / AgentMessage / ToolSpec / ToolCall / ToolResult