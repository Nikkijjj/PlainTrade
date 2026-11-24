# eval/metrics/
职责：一个指标一个文件，纯函数，输入是结果数据、输出是数值。
禁止：import pipeline 以外的上层业务；直接访问网络。
接口：各模块暴露一个纯函数，如 unexplained_jargon_rate(text, terms) -> float