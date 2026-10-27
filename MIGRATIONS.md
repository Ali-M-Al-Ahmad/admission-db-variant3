# Миграции и назначение таблиц

## 001_initial.sql

Создает структуру PostgreSQL.

| Таблица | Назначение |
|---|---|
| `city` | справочник городов абитуриентов |
| `applicant` | персональные и контактные данные абитуриентов |
| `direction` | направления подготовки и количество бюджетных мест |
| `discipline` | справочник вступительных дисциплин |
| `application` | заявления абитуриентов на направления, дата, приоритет и статус |
| `exam_result` | результаты абитуриентов по дисциплинам |
| `direction_discipline` | связь направлений и обязательных дисциплин с минимальным баллом |

Также создаются домены `dom_score`, `dom_priority`, `dom_app_status`, индексы, представления `v_application_rating`, `v_direction_statistics`, процедуры и триггер контроля бюджетных мест.

## 002_demo_data.sql

Заполняет справочники, абитуриентов, заявления, результаты и требования направлений демонстрационными данными.

## Примеры запросов

### Поиск абитуриента

```sql
SELECT a.id_applicant,
       concat_ws(' ', a.surname, a.name, a.patronymic) AS fio,
       c.name AS city
FROM applicant a
JOIN city c ON c.id_city = a.fk_city
WHERE a.surname ILIKE '%Петров%'
ORDER BY a.surname, a.name;
```

### Заявления с направлениями

```sql
SELECT concat_ws(' ', a.surname, a.name, a.patronymic) AS applicant,
       d.code,
       d.name AS direction,
       ap.priority,
       ap.status
FROM application ap
JOIN applicant a ON a.id_applicant = ap.fk_applicant
JOIN direction d ON d.id_direction = ap.fk_direction
ORDER BY d.code, ap.priority;
```

### Количество заявлений по направлениям

```sql
SELECT d.code, d.name, count(ap.id_application) AS applications_count
FROM direction d
LEFT JOIN application ap ON ap.fk_direction = d.id_direction
GROUP BY d.id_direction, d.code, d.name
ORDER BY d.code;
```

### Рейтинг

```sql
SELECT direction_code, applicant_name, total_score, priority, is_eligible, status
FROM v_application_rating
ORDER BY direction_code, total_score DESC, priority, application_date;
```

### Направления без заявлений

```sql
SELECT d.code, d.name
FROM direction d
LEFT JOIN application ap ON ap.fk_direction = d.id_direction
WHERE ap.id_application IS NULL;
```
