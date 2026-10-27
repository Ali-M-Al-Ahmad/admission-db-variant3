@echo off
chcp 65001 >nul
set /p PGPASSWORD=Пароль PostgreSQL: 
createdb -h localhost -U postgres admission_db 2>nul
psql -h localhost -U postgres -d admission_db -f migrations\001_initial.sql
psql -h localhost -U postgres -d admission_db -f migrations\002_demo_data.sql
pause
