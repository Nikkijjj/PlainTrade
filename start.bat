@echo off
REM 兜底启动方式：exe 被杀毒拦时用这个（需要已装 Python 3.11+）
cd /d "%~dp0"
python -m scripts.launcher
pause