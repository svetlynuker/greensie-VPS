@echo off
start "Greensie Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\activate && uvicorn app.main:app --reload"
start "Greensie Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
