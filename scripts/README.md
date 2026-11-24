# scripts/
职责：一次性工具与自检脚本（探测、爬虫、结构检查），不进主流程。
禁止：被 pipeline/agents 引用；写业务逻辑。
接口：python -m scripts.check_structure / check_contracts