from flask import Flask, render_template, request, redirect, flash, url_for
import psycopg2
import os
import re
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "secret"


# ==============================
# Подключение к БД
# ==============================
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT"),
        sslmode="require"
    )


# ==============================
# Главная панель HR
# ==============================
@app.route("/")
def dashboard():
    return render_template("dashboard.html")


# ==============================
# Регистрация сотрудника
# ==============================
@app.route("/employees/new", methods=["GET", "POST"])
def new_employee():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM countries WHERE is_active = TRUE")
    countries = cur.fetchall()

    if request.method == "POST":

        pinfl = request.form["pinfl"]
        phone = request.form["phone"]

        # Валидация
        if not re.fullmatch(r"\d{14}", pinfl):
            flash("ПИНФЛ должен состоять из 14 цифр")
            return redirect(url_for("new_employee"))

        if not re.fullmatch(r"\d+", phone):
            flash("Телефон должен содержать только цифры")
            return redirect(url_for("new_employee"))

        try:
            cur.execute("""
                INSERT INTO employees (
                    pinfl,
                    last_name,
                    first_name,
                    gender,
                    birth_date,
                    citizenship_country_id,
                    passport_series,
                    passport_number,
                    passport_issue_date,
                    passport_issued_by,
                    phone,
                    registration_address,
                    residence_address,
                    hire_date,
                    salary
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                pinfl,
                request.form["last_name"],
                request.form["first_name"],
                request.form["gender"],
                request.form["birth_date"],
                request.form["citizenship_country_id"],
                request.form["passport_series"],
                request.form["passport_number"],
                request.form["passport_issue_date"],
                request.form["passport_issued_by"],
                phone,
                request.form["registration_address"],
                request.form["residence_address"],
                request.form["hire_date"],
                request.form["salary"]
            ))

            conn.commit()
            flash("Сотрудник зарегистрирован")
            return redirect(url_for("dashboard"))

        except Exception as e:
            flash(f"Ошибка: {str(e)}")

    cur.close()
    conn.close()

    return render_template("employee_form.html", countries=countries)


# ==============================
# Просмотр анкеты
# ==============================
@app.route("/employees/<int:employee_id>")
def view_employee(employee_id):

    conn = get_connection()
    cur = conn.cursor()

    # --- Основные данные сотрудника ---
    cur.execute("""
        SELECT e.employee_id,
               e.personnel_number,
               e.pinfl,
               e.last_name,
               e.first_name,
               e.gender,
               e.birth_date,
               COALESCE(c.name, '—'),
               e.hire_date,
               e.salary
        FROM employees e
        LEFT JOIN countries c
            ON e.citizenship_country_id = c.id
        WHERE e.employee_id = %s
          AND e.is_deleted = FALSE
    """, (employee_id,))

    employee = cur.fetchone()

    if not employee:
        cur.close()
        conn.close()
        return redirect(url_for("dashboard"))

    # --- Стаж ---
    hire_date = employee[8]
    today = datetime.today().date()
    experience_days = (today - hire_date).days
    experience_years = experience_days // 365

    # --- Отпуска ---
    cur.execute("""
        SELECT start_date, end_date, vacation_year
        FROM employee_vacations
        WHERE employee_id = %s
          AND is_deleted = FALSE
        ORDER BY start_date DESC
    """, (employee_id,))
    vacations = cur.fetchall()

    # --- Больничные ---
    cur.execute("""
        SELECT start_date, end_date, days_count
        FROM sick_leaves
        WHERE employee_id = %s
          AND is_deleted = FALSE
        ORDER BY start_date DESC
    """, (employee_id,))
    sick_leaves = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "employee_profile.html",
        employee=employee,
        experience_years=experience_years,
        vacations=vacations,
        sick_leaves=sick_leaves
    )

# ==============================
# Редактирование
# ==============================
@app.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
def edit_employee(employee_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT employee_id, personnel_number, pinfl,
               last_name, first_name,
               hire_date, salary,
               citizenship_country_id
        FROM employees
        WHERE employee_id = %s
          AND is_deleted = FALSE
    """, (employee_id,))

    employee = cur.fetchone()

    if employee is None:
        cur.close()
        conn.close()
        flash("Сотрудник не найден")
        return redirect(url_for("dashboard"))

    cur.execute("SELECT id, name FROM countries WHERE is_active = TRUE")
    countries = cur.fetchall()

    if request.method == "POST":
        try:
            cur.execute("""
                UPDATE employees
                SET last_name = %s,
                    first_name = %s,
                    hire_date = %s,
                    salary = %s,
                    citizenship_country_id = %s,
                    updated_at = NOW()
                WHERE employee_id = %s
            """, (
                request.form["last_name"],
                request.form["first_name"],
                request.form["hire_date"],
                request.form["salary"],
                request.form["citizenship_country_id"],
                employee_id
            ))

            conn.commit()
            flash("Данные обновлены")
            return redirect(f"/employees/{employee_id}")

        except Exception as e:
            flash(f"Ошибка: {str(e)}")

    cur.close()
    conn.close()

    return render_template(
        "edit_employee.html",
        employee=employee,
        countries=countries
    )


# ==============================
# Soft delete
# ==============================
@app.route("/employees/<int:employee_id>/delete", methods=["POST"])
def delete_employee(employee_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE employees
        SET is_deleted = TRUE,
            deleted_at = NOW()
        WHERE employee_id = %s
    """, (employee_id,))

    conn.commit()
    cur.close()
    conn.close()

    flash("Сотрудник удалён")
    return redirect(url_for("dashboard"))


# ==============================
# Больничный
# ==============================
@app.route("/employees/<int:employee_id>/sick", methods=["GET", "POST"])
def sick_leave(employee_id):

    if request.method == "POST":
        try:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO sick_leaves
                (employee_id, start_date, end_date)
                VALUES (%s, %s, %s)
            """, (
                employee_id,
                request.form["start_date"],
                request.form["end_date"]
            ))

            conn.commit()
            cur.close()
            conn.close()

            flash("Больничный оформлен")
            return redirect(f"/employees/{employee_id}")

        except Exception as e:
            flash(f"Ошибка: {str(e)}")
            return redirect(f"/employees/{employee_id}/sick")

    return render_template("sick_leave.html", employee_id=employee_id)


# ==============================
# Отпуск (авто 21 день)
# ==============================
@app.route("/employees/<int:employee_id>/vacation", methods=["GET", "POST"])
def vacation(employee_id):

    if request.method == "POST":
        try:
            conn = get_connection()
            cur = conn.cursor()

            start_date = datetime.strptime(
                request.form["start_date"],
                "%Y-%m-%d"
            )

            end_date = start_date + timedelta(days=20)

            cur.execute("""
                INSERT INTO employee_vacations
                (employee_id, start_date, end_date, vacation_year, days_taken)
                VALUES (%s, %s, %s, %s, 21)
            """, (
                employee_id,
                start_date.date(),
                end_date.date(),
                start_date.year  # ← год берём автоматически
            ))

            conn.commit()
            cur.close()
            conn.close()

            flash("Отпуск оформлен (21 день)")
            return redirect(f"/employees/{employee_id}")

        except Exception as e:
            flash(f"Ошибка: {str(e)}")
            return redirect(f"/employees/{employee_id}/vacation")

    return render_template("vacation.html", employee_id=employee_id)

# ==============================
# Отпуск (авто 21 день)
# ==============================

@app.route("/employees/search", methods=["GET", "POST"])
def search_employee():
    conn = get_connection()
    cur = conn.cursor()

    employees = []

    if request.method == "POST":
        last_name = request.form.get("last_name")
        first_name = request.form.get("first_name")
        pinfl = request.form.get("pinfl")
        personnel_number = request.form.get("personnel_number")

        query = """
            SELECT employee_id, last_name, first_name, pinfl, personnel_number
            FROM employees
            WHERE is_deleted = FALSE
        """

        params = []

        if last_name:
            query += " AND last_name ILIKE %s"
            params.append(f"%{last_name}%")

        if first_name:
            query += " AND first_name ILIKE %s"
            params.append(f"%{first_name}%")

        if pinfl:
            query += " AND pinfl = %s"
            params.append(pinfl)

        if personnel_number:
            query += " AND personnel_number = %s"
            params.append(personnel_number)

        cur.execute(query, params)
        employees = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("search.html", employees=employees)
