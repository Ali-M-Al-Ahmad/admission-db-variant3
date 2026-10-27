-- ============================================================================
-- Индивидуальная работа по дисциплине "Базы данных"
-- Тема 3: Автоматизация учета поступления абитуриентов
-- СУБД: PostgreSQL
-- ============================================================================

-- Скрипт рассчитан на запуск в ПУСТОЙ базе данных admission_db.
-- При повторном запуске существующие объекты проекта удаляются.

DROP VIEW IF EXISTS v_direction_statistics CASCADE;
DROP VIEW IF EXISTS v_application_rating CASCADE;
DROP FUNCTION IF EXISTS fn_check_budget_places() CASCADE;
DROP PROCEDURE IF EXISTS sp_enroll_by_rating(integer);
DROP PROCEDURE IF EXISTS sp_set_exam_result(integer, integer, smallint);
DROP PROCEDURE IF EXISTS sp_submit_application(integer, integer, smallint);
DROP TABLE IF EXISTS exam_result CASCADE;
DROP TABLE IF EXISTS application CASCADE;
DROP TABLE IF EXISTS direction_discipline CASCADE;
DROP TABLE IF EXISTS applicant CASCADE;
DROP TABLE IF EXISTS discipline CASCADE;
DROP TABLE IF EXISTS direction CASCADE;
DROP TABLE IF EXISTS city CASCADE;
DROP DOMAIN IF EXISTS dom_app_status CASCADE;
DROP DOMAIN IF EXISTS dom_priority CASCADE;
DROP DOMAIN IF EXISTS dom_score CASCADE;

CREATE DOMAIN dom_score AS smallint
    CHECK (VALUE BETWEEN 0 AND 100);

CREATE DOMAIN dom_priority AS smallint
    CHECK (VALUE > 0);

CREATE DOMAIN dom_app_status AS varchar(20)
    CHECK (VALUE IN (
        'Подано',
        'Допущено',
        'Зачислен',
        'Не зачислен',
        'Отозвано'
    ));

CREATE TABLE city (
    id_city serial PRIMARY KEY,
    name varchar(80) NOT NULL UNIQUE
);

CREATE TABLE direction (
    id_direction serial PRIMARY KEY,
    code varchar(20) NOT NULL UNIQUE,
    name varchar(120) NOT NULL,
    budget_places integer NOT NULL CHECK (budget_places >= 0)
);

CREATE TABLE discipline (
    id_discipline serial PRIMARY KEY,
    name varchar(80) NOT NULL UNIQUE
);

CREATE TABLE applicant (
    id_applicant serial PRIMARY KEY,
    surname varchar(50) NOT NULL,
    name varchar(50) NOT NULL,
    patronymic varchar(50),
    birth_date date NOT NULL,
    phone varchar(20),
    email varchar(100),
    fk_city integer NOT NULL
        REFERENCES city(id_city)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT ck_applicant_email
        CHECK (email IS NULL OR position('@' IN email) > 1)
);

CREATE TABLE direction_discipline (
    fk_direction integer NOT NULL
        REFERENCES direction(id_direction)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    fk_discipline integer NOT NULL
        REFERENCES discipline(id_discipline)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    min_score dom_score NOT NULL,
    PRIMARY KEY (fk_direction, fk_discipline)
);

CREATE TABLE application (
    id_application serial PRIMARY KEY,
    fk_applicant integer NOT NULL
        REFERENCES applicant(id_applicant)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    fk_direction integer NOT NULL
        REFERENCES direction(id_direction)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    application_date date NOT NULL DEFAULT CURRENT_DATE,
    priority dom_priority NOT NULL,
    status dom_app_status NOT NULL DEFAULT 'Подано',
    CONSTRAINT uq_application_direction
        UNIQUE (fk_applicant, fk_direction),
    CONSTRAINT uq_application_priority
        UNIQUE (fk_applicant, priority)
);

CREATE TABLE exam_result (
    id_result serial PRIMARY KEY,
    fk_applicant integer NOT NULL
        REFERENCES applicant(id_applicant)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    fk_discipline integer NOT NULL
        REFERENCES discipline(id_discipline)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    score dom_score NOT NULL,
    CONSTRAINT uq_exam_result
        UNIQUE (fk_applicant, fk_discipline)
);

CREATE INDEX ix_applicant_city ON applicant(fk_city);
CREATE INDEX ix_applicant_surname ON applicant(surname);
CREATE INDEX ix_application_direction ON application(fk_direction);
CREATE INDEX ix_application_applicant ON application(fk_applicant);
CREATE INDEX ix_application_status ON application(status);
CREATE INDEX ix_exam_result_applicant ON exam_result(fk_applicant);
CREATE INDEX ix_exam_result_discipline ON exam_result(fk_discipline);

CREATE OR REPLACE VIEW v_application_rating AS
SELECT
    ap.id_application,
    a.id_applicant,
    concat_ws(' ', a.surname, a.name, a.patronymic) AS applicant_name,
    d.id_direction,
    d.code AS direction_code,
    d.name AS direction_name,
    ap.priority,
    ap.application_date,
    ap.status,
    count(dd.fk_discipline) AS required_count,
    count(er.id_result) AS received_count,
    coalesce(sum(er.score), 0)::integer AS total_score,
    CASE
        WHEN count(dd.fk_discipline) > 0
         AND count(er.id_result) = count(dd.fk_discipline)
         AND bool_and(er.score >= dd.min_score)
        THEN true
        ELSE false
    END AS is_eligible
FROM application ap
JOIN applicant a ON a.id_applicant = ap.fk_applicant
JOIN direction d ON d.id_direction = ap.fk_direction
LEFT JOIN direction_discipline dd ON dd.fk_direction = d.id_direction
LEFT JOIN exam_result er
  ON er.fk_applicant = a.id_applicant
 AND er.fk_discipline = dd.fk_discipline
GROUP BY ap.id_application, a.id_applicant, d.id_direction;

CREATE OR REPLACE VIEW v_direction_statistics AS
SELECT
    d.id_direction,
    d.code,
    d.name,
    d.budget_places,
    count(v.id_application) AS applications_count,
    count(v.id_application) FILTER (WHERE v.is_eligible) AS eligible_count,
    count(v.id_application) FILTER (WHERE v.status = 'Зачислен') AS enrolled_count,
    round(avg(v.total_score) FILTER (WHERE v.is_eligible), 2) AS avg_total_score,
    CASE
        WHEN d.budget_places = 0 THEN NULL
        ELSE round(count(v.id_application)::numeric / d.budget_places, 2)
    END AS competition_per_place
FROM direction d
LEFT JOIN v_application_rating v ON v.id_direction = d.id_direction
GROUP BY d.id_direction, d.code, d.name, d.budget_places;

CREATE OR REPLACE PROCEDURE sp_submit_application(
    p_applicant integer,
    p_direction integer,
    p_priority smallint
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM applicant WHERE id_applicant = p_applicant) THEN
        RAISE EXCEPTION 'Абитуриент % не найден', p_applicant;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM direction WHERE id_direction = p_direction) THEN
        RAISE EXCEPTION 'Направление % не найдено', p_direction;
    END IF;

    IF EXISTS (
        SELECT 1 FROM application
        WHERE fk_applicant = p_applicant
          AND fk_direction = p_direction
    ) THEN
        RAISE EXCEPTION 'Заявление на это направление уже существует';
    END IF;

    IF EXISTS (
        SELECT 1 FROM application
        WHERE fk_applicant = p_applicant
          AND priority = p_priority
    ) THEN
        RAISE EXCEPTION 'Приоритет % уже используется', p_priority;
    END IF;

    INSERT INTO application(fk_applicant, fk_direction, priority)
    VALUES (p_applicant, p_direction, p_priority);
END;
$$;

CREATE OR REPLACE PROCEDURE sp_set_exam_result(
    p_applicant integer,
    p_discipline integer,
    p_score smallint
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_score < 0 OR p_score > 100 THEN
        RAISE EXCEPTION 'Балл должен находиться в диапазоне 0..100';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM applicant WHERE id_applicant = p_applicant) THEN
        RAISE EXCEPTION 'Абитуриент % не найден', p_applicant;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM discipline WHERE id_discipline = p_discipline) THEN
        RAISE EXCEPTION 'Дисциплина % не найдена', p_discipline;
    END IF;

    INSERT INTO exam_result(fk_applicant, fk_discipline, score)
    VALUES (p_applicant, p_discipline, p_score)
    ON CONFLICT (fk_applicant, fk_discipline)
    DO UPDATE SET score = EXCLUDED.score;
END;
$$;

CREATE OR REPLACE FUNCTION fn_check_budget_places()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_places integer;
    v_enrolled integer;
BEGIN
    IF NEW.status <> 'Зачислен' THEN
        RETURN NEW;
    END IF;

    SELECT budget_places
      INTO v_places
      FROM direction
     WHERE id_direction = NEW.fk_direction;

    IF v_places IS NULL THEN
        RAISE EXCEPTION 'Направление % не найдено', NEW.fk_direction;
    END IF;

    SELECT count(*)
      INTO v_enrolled
      FROM application
     WHERE fk_direction = NEW.fk_direction
       AND status = 'Зачислен'
       AND id_application <> coalesce(NEW.id_application, -1);

    IF v_enrolled >= v_places THEN
        RAISE EXCEPTION
            'Количество зачисленных не может превышать число бюджетных мест (%)',
            v_places;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_check_budget_places
BEFORE INSERT OR UPDATE OF status, fk_direction
ON application
FOR EACH ROW
EXECUTE FUNCTION fn_check_budget_places();

CREATE OR REPLACE PROCEDURE sp_enroll_by_rating(p_direction integer)
LANGUAGE plpgsql
AS $$
DECLARE
    v_places integer;
BEGIN
    SELECT budget_places
      INTO v_places
      FROM direction
     WHERE id_direction = p_direction;

    IF v_places IS NULL THEN
        RAISE EXCEPTION 'Направление % не найдено', p_direction;
    END IF;

    UPDATE application
       SET status = 'Не зачислен'::dom_app_status
     WHERE fk_direction = p_direction
       AND status <> 'Отозвано';

    WITH ranked AS (
        SELECT
            id_application,
            row_number() OVER (
                ORDER BY
                    total_score DESC,
                    priority ASC,
                    application_date ASC,
                    id_application ASC
            ) AS rn
        FROM v_application_rating
        WHERE id_direction = p_direction
          AND is_eligible = true
          AND status <> 'Отозвано'
    )
    UPDATE application a
       SET status = CASE
            WHEN r.rn <= v_places THEN 'Зачислен'::dom_app_status
            ELSE 'Не зачислен'::dom_app_status
       END
      FROM ranked r
     WHERE a.id_application = r.id_application;
END;
$$;

CREATE OR REPLACE PROCEDURE sp_refresh_eligibility()
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE application a
       SET status = CASE
            WHEN v.is_eligible THEN 'Допущено'::dom_app_status
            ELSE 'Подано'::dom_app_status
       END
      FROM v_application_rating v
     WHERE a.id_application = v.id_application
       AND a.status IN ('Подано', 'Допущено');
END;
$$;
