# eval/cases/
职责：golden 用例（yaml），用于回归测试 agent 行为。
禁止：放真实用户数据；放超过 50 条的大样本（大样本放 data_files/）。
接口：`golden.yaml` —— 每条第 id / input / as_of / task / code? / expect 五段，
      expect 是可自动校验的验收点（no_advice / no_fabricated_cause / jargon_explained /
      chart_should_skip / stance_no_view_ok）。schema 说明见 golden.yaml 头注释。
