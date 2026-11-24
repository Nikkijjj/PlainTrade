# agents/analysts/
职责：三个分析师各管一件事，只陈述有证据的主张（disclosure 只要 fact，fundamental 只要 inference）。
禁止：import ui/pipeline/adapt；自己算数字；给支撑位与买入点。
接口：DisclosureAnalyst/FundamentalAnalyst/TechnicalAnalyst 均继承 BaseAgent，暴露 run(ctx)。