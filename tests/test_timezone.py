from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.services.sms_service import render_approved_message
from app.utils.timezone import INDIA_TZ, format_india, parse_india_datetime, to_india, utc_now


def test_india_timezone_is_available():
    assert INDIA_TZ == ZoneInfo("Asia/Kolkata")


def test_current_indian_time_is_aware():
    now = to_india(utc_now())
    assert now.tzinfo == INDIA_TZ
    assert now.utcoffset().total_seconds() == 19800


def test_utc_converts_once_to_india_time():
    utc_value = datetime(2026, 10, 28, 8, 17, tzinfo=timezone.utc)
    assert format_india(utc_value) == "28/10/2026 01:47 PM"


def test_ist_form_value_stores_correct_utc_instant():
    stored_value = parse_india_datetime("2026-10-28T13:47")
    assert stored_value == datetime(2026, 10, 28, 8, 17, tzinfo=timezone.utc)
    assert format_india(stored_value) == "28/10/2026 01:47 PM"


def test_sms_timestamp_uses_india_time(app):
    from test_core import make_users
    from app.extensions import db
    from app.models import Student
    from app.services.gate_pass_service import create_gate_pass

    with app.app_context():
        _, _, staff, department = make_users()
        student = Student(full_name="Ahmed Faraaz", usn="4MU24CS099", semester=3, section="A", student_mobile="9876543210", parent_name="Parent", parent_mobile="9876543212", department=department)
        db.session.add(student); db.session.commit()
        gate_pass = create_gate_pass(student, staff, "Exam completed", datetime(2026, 10, 28, 8, 17, tzinfo=timezone.utc))
        db.session.commit()
        message = render_approved_message(gate_pass)
        assert "28/10/2026 at 01:47 PM" in message


def test_pdf_gate_pass_generation_uses_timezone_safe_timestamp(client, app):
    from test_core import make_users
    from app.extensions import db
    from app.models import Student
    from app.services.gate_pass_service import create_gate_pass, decide_gate_pass

    with app.app_context():
        _, approver, staff, department = make_users()
        student = Student(full_name="PDF Student", usn="4MU24CS100", semester=3, section="A", student_mobile="9876543210", parent_name="Parent", parent_mobile="9876543213", department=department)
        db.session.add(student); db.session.commit()
        gate_pass = create_gate_pass(student, staff, "Personal work", datetime(2026, 10, 28, 8, 17, tzinfo=timezone.utc))
        db.session.commit(); decide_gate_pass(gate_pass, approver, "APPROVED"); db.session.commit()
        pass_id = gate_pass.id

    client.post("/login", data={"username": "admin", "password": "password-long-enough"})
    response = client.get(f"/passes/{pass_id}/print.pdf")
    assert response.status_code == 200
    assert response.data.startswith(b"%PDF")
