# eval/
职责：指标计算与批量跑。只读 data/ 与 results/，不改业务代码。
禁止：写进主流程（评估必须能在主流程之外独立重跑）。
接口：metrics.* 各一个纯函数；runners.batch.run_batch()