# config/
职责：提供配置与"数据型资源"（提示词、图表契约、术语表），不含任何逻辑。
禁止：import 任何业务模块；在别处读 os.environ（只能这里读）。
接口：settings（单例）／load_prompt 走 llm.client。