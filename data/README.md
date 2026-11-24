# data/
职责：抓取、清洗、入 SQLite，并通过 db.py 提供唯一取数入口。
禁止：import agents/adapt/pipeline/ui/guardrails（取数层不该知道有 agent）。
接口：db.py 六个函数；build_db.main()。业务代码不许写裸 SQL。