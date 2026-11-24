# ui/
职责：**旧版 Streamlit 骨架，已不作为交付界面**（正式界面是 `frontend/` + `api/`）。
禁止：在这里加新功能；新界面一律改 `frontend/index.html`。
接口：ui/app.py（26 行骨架）；要跑得先 `pip install -e ".[legacy]"`。
