from datetime import date
from pathlib import Path
from typing import Any

import psycopg2
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .db import get_connection

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Приемная комиссия — учет поступления абитуриентов")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

TABLES = {
    "city": {
        "title": "Города", "pk": ["id_city"],
        "fields": [("name", "Город", "text", True)],
        "columns": [("id_city", "Код"), ("name", "Город")],
    },
    "direction": {
        "title": "Направления", "pk": ["id_direction"],
        "fields": [("code", "Шифр", "text", True), ("name", "Направление", "text", True), ("budget_places", "Бюджетных мест", "number", True)],
        "columns": [("id_direction", "Код"), ("code", "Шифр"), ("name", "Направление"), ("budget_places", "Бюджетных мест")],
    },
    "discipline": {
        "title": "Дисциплины", "pk": ["id_discipline"],
        "fields": [("name", "Дисциплина", "text", True)],
        "columns": [("id_discipline", "Код"), ("name", "Дисциплина")],
    },
    "applicant": {
        "title": "Абитуриенты", "pk": ["id_applicant"],
        "fields": [
            ("surname", "Фамилия", "text", True), ("name", "Имя", "text", True),
            ("patronymic", "Отчество", "text", False), ("birth_date", "Дата рождения", "date", True),
            ("phone", "Телефон", "text", False), ("email", "Email", "email", False),
            ("fk_city", "Город", "fk_city", True),
        ],
        "columns": [("id_applicant", "Код"), ("surname", "Фамилия"), ("name", "Имя"), ("patronymic", "Отчество"), ("birth_date", "Дата рождения"), ("city_name", "Город"), ("phone", "Телефон"), ("email", "Email")],
    },
    "application": {
        "title": "Заявления", "pk": ["id_application"],
        "fields": [
            ("fk_applicant", "Абитуриент", "fk_applicant", True), ("fk_direction", "Направление", "fk_direction", True),
            ("application_date", "Дата заявления", "date", True), ("priority", "Приоритет", "number", True),
            ("status", "Статус", "status", True),
        ],
        "columns": [("id_application", "Код"), ("applicant_name", "Абитуриент"), ("direction_name", "Направление"), ("application_date", "Дата"), ("priority", "Приоритет"), ("status", "Статус")],
    },
    "exam_result": {
        "title": "Результаты экзаменов", "pk": ["id_result"],
        "fields": [("fk_applicant", "Абитуриент", "fk_applicant", True), ("fk_discipline", "Дисциплина", "fk_discipline", True), ("score", "Балл", "number", True)],
        "columns": [("id_result", "Код"), ("applicant_name", "Абитуриент"), ("discipline_name", "Дисциплина"), ("score", "Балл")],
    },
    "direction_discipline": {
        "title": "Требования направлений", "pk": ["fk_direction", "fk_discipline"],
        "fields": [("fk_direction", "Направление", "fk_direction", True), ("fk_discipline", "Дисциплина", "fk_discipline", True), ("min_score", "Минимальный балл", "number", True)],
        "columns": [("direction_name", "Направление"), ("discipline_name", "Дисциплина"), ("min_score", "Мин. балл")],
    },
}

STATUS_CHOICES = ["Подано", "Допущено", "Зачислен", "Не зачислен", "Отозвано"]

LIST_SQL = {
    "city": "SELECT * FROM city ORDER BY name",
    "direction": "SELECT * FROM direction ORDER BY code",
    "discipline": "SELECT * FROM discipline ORDER BY name",
    "applicant": """
        SELECT a.*, c.name AS city_name
        FROM applicant a JOIN city c ON c.id_city=a.fk_city
        ORDER BY a.surname, a.name, a.patronymic
    """,
    "application": """
        SELECT ap.*, concat_ws(' ', a.surname,a.name,a.patronymic) AS applicant_name,
               d.code || ' — ' || d.name AS direction_name
        FROM application ap
        JOIN applicant a ON a.id_applicant=ap.fk_applicant
        JOIN direction d ON d.id_direction=ap.fk_direction
        ORDER BY ap.application_date, ap.id_application
    """,
    "exam_result": """
        SELECT er.*, concat_ws(' ', a.surname,a.name,a.patronymic) AS applicant_name,
               di.name AS discipline_name
        FROM exam_result er
        JOIN applicant a ON a.id_applicant=er.fk_applicant
        JOIN discipline di ON di.id_discipline=er.fk_discipline
        ORDER BY a.surname, di.name
    """,
    "direction_discipline": """
        SELECT dd.*, d.code || ' — ' || d.name AS direction_name, di.name AS discipline_name
        FROM direction_discipline dd
        JOIN direction d ON d.id_direction=dd.fk_direction
        JOIN discipline di ON di.id_discipline=dd.fk_discipline
        ORDER BY d.code, di.name
    """,
}


def run_query(sql: str, params: tuple = (), fetch: bool = True):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() if fetch else None
        conn.commit()
        return rows
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fk_options():
    return {
        "fk_city": run_query("SELECT id_city AS value, name AS label FROM city ORDER BY name"),
        "fk_applicant": run_query("SELECT id_applicant AS value, concat_ws(' ',surname,name,patronymic) AS label FROM applicant ORDER BY surname,name"),
        "fk_direction": run_query("SELECT id_direction AS value, code || ' — ' || name AS label FROM direction ORDER BY code"),
        "fk_discipline": run_query("SELECT id_discipline AS value, name AS label FROM discipline ORDER BY name"),
    }


def db_error_message(exc: Exception) -> str:
    if isinstance(exc, psycopg2.errors.UniqueViolation):
        return "Такая запись уже существует. Проверьте уникальные поля."
    if isinstance(exc, psycopg2.errors.ForeignKeyViolation):
        return "Операция невозможна: запись связана с другими данными или выбрано несуществующее значение."
    if isinstance(exc, psycopg2.errors.CheckViolation):
        return "Данные не соответствуют ограничениям базы данных. Проверьте введенные значения."
    if isinstance(exc, psycopg2.errors.NotNullViolation):
        return "Не заполнено обязательное поле."
    if isinstance(exc, ValueError):
        return str(exc)
    return "База данных отклонила операцию. Проверьте введенные данные."


def normalize_value(field_type: str, value: str):
    if value == "":
        return None
    if field_type in {"number", "fk_city", "fk_applicant", "fk_direction", "fk_discipline"}:
        return int(value)
    return value


def get_record(table: str, key_values: list[str]):
    cfg = TABLES[table]
    where = " AND ".join(f"{k}=%s" for k in cfg["pk"])
    rows = run_query(f"SELECT * FROM {table} WHERE {where}", tuple(key_values))
    return rows[0] if rows else None


def key_path(table: str, record: dict[str, Any]) -> str:
    return "/".join(str(record[k]) for k in TABLES[table]["pk"])


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    stats = {}
    try:
        for t in TABLES:
            stats[t] = run_query(f"SELECT count(*) AS n FROM {t}")[0]["n"]
        db_ok = True
        error = None
    except Exception as exc:
        stats = {}
        db_ok = False
        error = db_error_message(exc)
    return templates.TemplateResponse(request, "home.html", {"tables": TABLES, "stats": stats, "db_ok": db_ok, "error": error})


@app.get("/table/{table}", response_class=HTMLResponse)
def list_table(request: Request, table: str):
    if table not in TABLES:
        return HTMLResponse("Неизвестная таблица", status_code=404)
    error = request.query_params.get("error")
    try:
        rows = run_query(LIST_SQL[table])
    except Exception as exc:
        rows, error = [], db_error_message(exc)
    return templates.TemplateResponse(request, "list.html", {"table": table, "cfg": TABLES[table], "rows": rows, "error": error, "key_path": key_path})


@app.get("/table/{table}/add", response_class=HTMLResponse)
def add_form(request: Request, table: str):
    if table not in TABLES:
        return HTMLResponse("Неизвестная таблица", status_code=404)
    return templates.TemplateResponse(request, "form.html", {"table": table, "cfg": TABLES[table], "record": {}, "options": fk_options(), "statuses": STATUS_CHOICES, "mode": "add", "error": None})


@app.post("/table/{table}/add")
def add_record(request: Request, table: str,
               surname: str = Form(""), name: str = Form(""), patronymic: str = Form(""), birth_date: str = Form(""), phone: str = Form(""), email: str = Form(""),
               code: str = Form(""), budget_places: str = Form(""), fk_city: str = Form(""),
               fk_applicant: str = Form(""), fk_direction: str = Form(""), application_date: str = Form(""), priority: str = Form(""), status: str = Form(""),
               fk_discipline: str = Form(""), score: str = Form(""), min_score: str = Form("")):
    if table not in TABLES:
        return HTMLResponse("Неизвестная таблица", status_code=404)
    incoming = locals()
    cfg = TABLES[table]
    fields, values, placeholders = [], [], []
    try:
        for fname, _, ftype, required in cfg["fields"]:
            raw = incoming.get(fname, "")
            value = normalize_value(ftype, raw)
            if required and (value is None or value == ""):
                raise ValueError(f"Поле {fname} обязательно")
            fields.append(fname); values.append(value); placeholders.append("%s")
        run_query(f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({', '.join(placeholders)})", tuple(values), fetch=False)
        return RedirectResponse(f"/table/{table}", status_code=303)
    except Exception as exc:
        return templates.TemplateResponse(request, "form.html", {"table": table, "cfg": cfg, "record": incoming, "options": fk_options(), "statuses": STATUS_CHOICES, "mode": "add", "error": db_error_message(exc)}, status_code=400)


@app.get("/table/{table}/edit/{key:path}", response_class=HTMLResponse)
def edit_form(request: Request, table: str, key: str):
    if table not in TABLES:
        return HTMLResponse("Неизвестная таблица", status_code=404)
    keys = key.split("/")
    record = get_record(table, keys)
    if not record:
        return HTMLResponse("Запись не найдена", status_code=404)
    return templates.TemplateResponse(request, "form.html", {"table": table, "cfg": TABLES[table], "record": record, "options": fk_options(), "statuses": STATUS_CHOICES, "mode": "edit", "error": None, "key": key})


@app.post("/table/{table}/edit/{key:path}")
def edit_record(request: Request, table: str, key: str,
                surname: str = Form(""), name: str = Form(""), patronymic: str = Form(""), birth_date: str = Form(""), phone: str = Form(""), email: str = Form(""),
                code: str = Form(""), budget_places: str = Form(""), fk_city: str = Form(""),
                fk_applicant: str = Form(""), fk_direction: str = Form(""), application_date: str = Form(""), priority: str = Form(""), status: str = Form(""),
                fk_discipline: str = Form(""), score: str = Form(""), min_score: str = Form("")):
    if table not in TABLES:
        return HTMLResponse("Неизвестная таблица", status_code=404)
    incoming = locals(); cfg = TABLES[table]; keys = key.split("/")
    try:
        sets, values = [], []
        for fname, _, ftype, required in cfg["fields"]:
            raw = incoming.get(fname, "")
            value = normalize_value(ftype, raw)
            if required and (value is None or value == ""):
                raise ValueError(f"Поле {fname} обязательно")
            sets.append(f"{fname}=%s"); values.append(value)
        where = " AND ".join(f"{k}=%s" for k in cfg["pk"])
        values.extend(keys)
        run_query(f"UPDATE {table} SET {', '.join(sets)} WHERE {where}", tuple(values), fetch=False)
        return RedirectResponse(f"/table/{table}", status_code=303)
    except Exception as exc:
        return templates.TemplateResponse(request, "form.html", {"table": table, "cfg": cfg, "record": incoming, "options": fk_options(), "statuses": STATUS_CHOICES, "mode": "edit", "error": str(exc), "key": key}, status_code=400)


@app.post("/table/{table}/delete/{key:path}")
def delete_record(table: str, key: str):
    if table not in TABLES:
        return HTMLResponse("Неизвестная таблица", status_code=404)
    cfg = TABLES[table]; keys = key.split("/")
    where = " AND ".join(f"{k}=%s" for k in cfg["pk"])
    try:
        run_query(f"DELETE FROM {table} WHERE {where}", tuple(keys), fetch=False)
        return RedirectResponse(f"/table/{table}", status_code=303)
    except Exception as exc:
        from urllib.parse import quote
        return RedirectResponse(f"/table/{table}?error={quote(db_error_message(exc))}", status_code=303)


@app.get("/reports", response_class=HTMLResponse)
def reports(request: Request):
    try:
        rating = run_query("SELECT * FROM v_application_rating ORDER BY direction_code, total_score DESC, priority, application_date")
        stats = run_query("SELECT * FROM v_direction_statistics ORDER BY code")
        error = None
    except Exception as exc:
        rating, stats, error = [], [], db_error_message(exc)
    return templates.TemplateResponse(request, "reports.html", {"rating": rating, "stats": stats, "error": error})
