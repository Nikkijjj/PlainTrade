# eval/cases/
职责：golden 用例（yaml），用于回归测试 agent 行为。
禁止：放真实用户数据；放超过 50 条的大样本（大样本放 data_files/）。
接口：yaml 文件，每条第 input / expect 两段。