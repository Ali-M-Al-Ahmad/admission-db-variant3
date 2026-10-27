@echo off
chcp 65001 >nul
set /p DB_PASSWORD=Пароль PostgreSQL: 
py -3.11 -m uvicorn app.main:app --reload
pause
