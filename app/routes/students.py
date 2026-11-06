import csv
import io
import re
from flask import Blueprint, flash, redirect, render_template, request, url_for
from ..extensions import db
from ..models import Department, Student
from ..utils.audit import record
from ..utils.permissions import roles_required

students_bp = Blueprint("students", __name__)
MOBILE_RE = re.compile(r"^[6-9]\d{9}$")


def normalized_mobile(value):
    value = re.sub(r"\D", "", value or "")
    if value.startswith("91") and len(value) == 12:
        value = value[2:]
    return value


def save_student(data):
    parent_mobile = normalized_mobile(data.get("parent_mobile"))
    student_mobile = normalized_mobile(data.get("student_mobile"))
    if not MOBILE_RE.fullmatch(student_mobile):
        raise ValueError("Use a valid 10-digit registered student mobile number.")
    if not MOBILE_RE.fullmatch(parent_mobile):
        raise ValueError("Use a valid 10-digit Indian guardian mobile number.")
    usn = data.get("usn", "").strip().upper()
    if Student.query.filter_by(usn=usn).first():
        raise ValueError(f"USN {usn} already exists.")
    department = db.session.get(Department, int(data.get("department_id", 0)))
    if not department:
        raise ValueError("Select a department.")
    student = Student(full_name=data.get("full_name", "").strip(), usn=usn, semester=int(data.get("semester", 0)),
                      section=data.get("section", "").strip().upper(), parent_name=data.get("parent_name", "").strip(),
                      parent_mobile=parent_mobile, student_mobile=student_mobile, department=department)
    if not all([student.full_name, student.usn, student.parent_name, student.section]) or not 1 <= student.semester <= 8:
        raise ValueError("Complete all required student fields with a semester from 1 to 8.")
    db.session.add(student)
    return student


@students_bp.route("/", methods=["GET", "POST"])
@roles_required("SUPER_ADMIN")
def list_students():
    if request.method == "POST":
        try:
            student = save_student(request.form)
            record("STUDENT_CREATED", "student", student.usn)
            db.session.commit()
            flash("Student added.", "success")
            return redirect(url_for("students.list_students"))
        except (ValueError, TypeError) as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    query = request.args.get("q", "").strip()
    students = Student.query
    if query:
        students = students.filter((Student.usn.ilike(f"%{query}%")) | (Student.full_name.ilike(f"%{query}%")))
    return render_template("students/list.html", students=students.order_by(Student.usn).all(), departments=Department.query.order_by(Department.code).all(), query=query)


@students_bp.post("/import")
@roles_required("SUPER_ADMIN")
def import_csv():
    uploaded = request.files.get("csv_file")
    if not uploaded or not uploaded.filename.lower().endswith(".csv"):
        flash("Upload a CSV file.", "danger")
        return redirect(url_for("students.list_students"))
    reader = csv.DictReader(io.StringIO(uploaded.stream.read().decode("utf-8-sig")))
    created, errors = 0, []
    for line, row in enumerate(reader, start=2):
        try:
            save_student(row)
            created += 1
        except (ValueError, TypeError) as exc:
            errors.append(f"Row {line}: {exc}")
    db.session.commit()
    flash(f"Imported {created} student(s)." + (" " + "; ".join(errors[:3]) if errors else ""), "warning" if errors else "success")
    return redirect(url_for("students.list_students"))
