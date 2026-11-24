# pipeline/
职责：编排。全系统唯一知道"三个入口"存在的地方。
禁止：import ui；写业务逻辑（那是 agents/adapt 的）；自造数据。
接口：graph.NODES / run.run(user_text, as_of) -> PlainBrief