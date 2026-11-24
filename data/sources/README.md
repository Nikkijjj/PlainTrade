# data/sources/
职责：一个数据源一个文件，只把远端数据取回来并标准化。
禁止：写数据库（交给 build_db）；做业务判断；import agents/pipeline/ui。
接口：每模块暴露 fetch_*()，统一用 base.py 的 get_json。