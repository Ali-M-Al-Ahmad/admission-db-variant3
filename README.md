# Автоматизация учета поступления абитуриентов

Учебный проект по дисциплине «Базы данных», вариант 3. Веб-интерфейс реализован на FastAPI, база данных — PostgreSQL.

## 1. Как подключить базу

Параметры по умолчанию:

- host: `localhost`
- port: `5432`
- database: `admission_db`
- user: `postgres`
- password: задается пользователем PostgreSQL

Строка подключения по смыслу: `postgresql://postgres:<PASSWORD>@localhost:5432/admission_db`.

Перед запуском задайте переменные окружения `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` или используйте значения по умолчанию для первых четырех параметров.

## 2. Как создать таблицы

Создайте пустую базу `admission_db`, затем выполните миграции по порядку:

```bat
psql -h localhost -U postgres -d admission_db -f migrations\001_initial.sql
psql -h localhost -U postgres -d admission_db -f migrations\002_demo_data.sql
```

`001_initial.sql` создает домены, 7 таблиц, ключи, ограничения, индексы, представления, процедуры и триггер. `002_demo_data.sql` добавляет демонстрационные данные.

## 3. Как запустить приложение

Установите Python 3.11 и зависимости:

```bat
py -3.11 -m pip install -r requirements.txt
```

В PowerShell передайте пароль PostgreSQL:

```powershell
$env:DB_PASSWORD="ваш_пароль"
py -3.11 -m uvicorn app.main:app --reload
```

Откройте в браузере `http://127.0.0.1:8000/`.

В интерфейсе участвуют все 7 таблиц. Для каждой доступны просмотр, добавление, изменение и удаление. Внешние ключи выбираются из связанных таблиц по понятным названиям. Ошибки ограничений PostgreSQL отображаются пользователю, а операция откатывается.
