# 所有入口统一用 -m（需要先 pip install -e .）
.PHONY: install db run api legacy render test leak check

install: ; pip install -e .
db:      ; python -m data.build_db
run:     ; python -m scripts.launcher
api:     ; uvicorn api.main:app --reload
legacy:  ; streamlit run ui/app.py   # 旧版，需 pip install -e ".[legacy]"
render:  ; python -m scripts.preview_kline
test:    ; pytest -q
leak:    ; pytest -q tests/test_leakage.py
check:   ; python -m scripts.check_structure && python -m scripts.check_contracts