/* =========================================================
   HR SYSTEM DATABASE
   ========================================================= */


/* =========================================================
   ENUM
   ========================================================= */

-- Пол сотрудника
CREATE TYPE gender_enum AS ENUM ('male', 'female');


/* =========================================================
   СПРАВОЧНИКИ
   ========================================================= */

-- Страны (для гражданства)
CREATE TABLE countries (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE,
    iso_code CHAR(2) UNIQUE,
    is_active BOOLEAN DEFAULT TRUE
);


/* =========================================================
   ОСНОВНАЯ ТАБЛИЦА СОТРУДНИКОВ
   ========================================================= */

CREATE TABLE employees (
    employee_id BIGSERIAL PRIMARY KEY,

    -- Табельный номер HR-00001
    personnel_number VARCHAR(8) UNIQUE
        CHECK (personnel_number ~ '^HR-[0-9]{5}$'),

    -- ПИНФЛ строго 14 цифр
    pinfl VARCHAR(14) NOT NULL UNIQUE
        CHECK (pinfl ~ '^[0-9]{14}$'),

    last_name VARCHAR(100) NOT NULL,
    first_name VARCHAR(100) NOT NULL,

    gender gender_enum NOT NULL,

    birth_date DATE NOT NULL
        CHECK (birth_date < CURRENT_DATE),

    citizenship_country_id BIGINT
        REFERENCES countries(id),

    passport_series VARCHAR(10) NOT NULL,
    passport_number VARCHAR(20) NOT NULL,
    passport_issue_date DATE NOT NULL,
    passport_issued_by VARCHAR(255) NOT NULL,

    -- Телефон только цифры
    phone VARCHAR(20) NOT NULL
        CHECK (phone ~ '^[0-9]+$'),

    registration_address TEXT NOT NULL,
    residence_address TEXT NOT NULL,

    hire_date DATE NOT NULL
        CHECK (hire_date <= CURRENT_DATE),

    salary NUMERIC(12,2) NOT NULL
        CHECK (salary > 0),

    -- Soft delete
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


/* =========================================================
   АВТОГЕНЕРАЦИЯ ТАБЕЛЬНОГО НОМЕРА
   ========================================================= */

-- Последовательность для HR-00001
CREATE SEQUENCE personnel_seq START 1;

CREATE OR REPLACE FUNCTION generate_personnel_number()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.personnel_number IS NULL THEN
        NEW.personnel_number :=
            'HR-' || LPAD(nextval('personnel_seq')::TEXT, 5, '0');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_generate_personnel
BEFORE INSERT ON employees
FOR EACH ROW
EXECUTE FUNCTION generate_personnel_number();


/* =========================================================
   ОТПУСКА (фиксировано 21 день)
   ========================================================= */

CREATE TABLE employee_vacations (
    vacation_id BIGSERIAL PRIMARY KEY,

    employee_id BIGINT NOT NULL
        REFERENCES employees(employee_id)
        ON DELETE CASCADE,

    start_date DATE NOT NULL,

    -- Автоматически 21 день (start + 20)
    end_date DATE NOT NULL,

    vacation_year INT NOT NULL,

    days_taken INT NOT NULL DEFAULT 21
        CHECK (days_taken = 21),

    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Контроль длительности
    CHECK (end_date = start_date + INTERVAL '20 days')
);


/* =========================================================
   БОЛЬНИЧНЫЕ
   ========================================================= */

CREATE TABLE sick_leaves (
    sick_leave_id BIGSERIAL PRIMARY KEY,

    employee_id BIGINT NOT NULL
        REFERENCES employees(employee_id)
        ON DELETE CASCADE,

    start_date DATE NOT NULL,
    end_date DATE NOT NULL
        CHECK (end_date >= start_date),

    -- Автоматический расчёт количества дней
    days_count INT GENERATED ALWAYS AS
        (end_date - start_date + 1) STORED,

    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


/* =========================================================
   ТРИГГЕР ОБНОВЛЕНИЯ updated_at
   ========================================================= */

CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = CURRENT_TIMESTAMP;
   RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_timestamp
BEFORE UPDATE ON employees
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();
