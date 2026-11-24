# api/
职责：HTTP 层。把 pipeline.run() 的结果包成 JSON 给前端，并托管静态页面。
禁止：写业务逻辑（那是 pipeline/agents 的）；直接连数据库。
接口：POST /api/ask  GET /api/health