@echo off
cd /d C:\Dashboard\MacMarket-Trader
call .venv\Scripts\activate.bat
uvicorn macmarket_trader.api.main:app --reload --port 9510
