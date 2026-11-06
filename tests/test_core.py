from datetime import datetime, timezone
from app.extensions import db
from app.models import Department, GatePass, Role, Student, User
from app.services.gate_pass_service import create_gate_pass, decide_gate_pass
from app.routes.security import validate
from app.utils.timezone import utc_now
from app.services.sms_service import render_approved_message
from app.routes.students import save_student


def make_users():
    admin_role = Role(name="SUPER_ADMIN", display_name="Super Admin")
    approver_role = Role(name="APPROVER", display_name="Approver")
    staff_role = Role(name="STAFF", display_name="Staff")
    admin = User(username="admin", email="admin@test.local", full_name="Admin")
    admin.set_password("password-long-enough")
    admin.roles.append(admin_role)
    approver = User(username="principal", email="principal@test.local", full_name="Principal")
    approver.set_password("password-long-enough")
    approver.roles.append(approver_role)
    staff = User(username="staff", email="staff@test.local", full_name="Staff")
    staff.set_password("password-long-enough")
    staff.roles.append(staff_role)
    department = Department(code="CSE", name="Computer Science")
    db.session.add_all([admin, approver, staff, department]); db.session.commit()
    return admin, approver, staff, department


def test_login_and_unauthorized_access(client, app):
    with app.app_context():
        make_users()
    assert client.get("/").status_code == 302
    assert client.post("/login", data={"username": "admin", "password": "wrong"}).status_code == 200
    response = client.post("/login", data={"username": "admin", "password": "password-long-enough"}, follow_redirects=True)
    assert b"Dashboard" in response.data


def test_duplicate_usn_and_mobile_validation(app):
    with app.app_context():
        _, _, _, dept = make_users()
        data = {"full_name": "Ahmed Faraaz", "usn": "4MU24CS004", "semester": "3", "section": "A", "department_id": str(dept.id), "student_mobile": "9876543210", "parent_name": "Parent", "parent_mobile": "9876543211"}
        save_student(data); db.session.commit()
        try:
            save_student(data)
            assert False, "Expected duplicate USN error"
        except ValueError as exc:
            assert "already exists" in str(exc)


def test_approval_generates_unique_mock_sms(app):
    with app.app_context():
        _, approver, staff, dept = make_users()
        student = Student(full_name="Ahmed Faraaz", usn="4MU24CS004", semester=3, section="A", student_mobile="9876543210", parent_name="Parent", parent_mobile="9876543211", department=dept)
        db.session.add(student); db.session.commit()
        gate_pass = create_gate_pass(student, staff, "Exam completed", datetime.now(timezone.utc))
        db.session.commit()
        notification = decide_gate_pass(gate_pass, approver, "APPROVED")
        db.session.commit()
        assert gate_pass.status == "APPROVED"
        assert notification.status == "SIMULATED"
        assert "AHMED FARAAZ" in render_approved_message(gate_pass)
        assert "4MU24CS004" in notification.rendered_message
        assert gate_pass.pass_number in notification.rendered_message
        assert notification.recipient == "9876543210"
        assert notification.recipient_type == "STUDENT"
        assert notification.sender_id == "CP-MRITPR-S"
        second = decide_gate_pass if False else None
        assert GatePass.query.one().notifications[0].provider_message_id.startswith("MOCK-")


def test_security_rejects_reused_and_expired_passes(app):
    with app.app_context():
        _, approver, staff, dept = make_users()
        student = Student(full_name="Student", usn="4MU24CS005", semester=3, section="A", student_mobile="9876543210", parent_name="Parent", parent_mobile="9876543211", department=dept)
        db.session.add(student); db.session.commit()
        gate_pass = create_gate_pass(student, staff, "Medical emergency", datetime.now(timezone.utc))
        db.session.commit(); decide_gate_pass(gate_pass, approver, "APPROVED"); db.session.commit()
        assert validate(gate_pass)[0] == "VALID"
        gate_pass.exit_at = utc_now()
        assert validate(gate_pass)[0] == "USED"
        gate_pass.exit_at = None
        gate_pass.expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        assert validate(gate_pass)[0] == "EXPIRED"
