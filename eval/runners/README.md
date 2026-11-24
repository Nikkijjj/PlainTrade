# eval/runners/
职责：批量跑多个实验条件（B1-B4），把结果落到 results/。
禁止：改业务代码；在测试里跑（单独命令跑）。
接口：batch.run_batch(conditions, codes, dates) -> list[dict]