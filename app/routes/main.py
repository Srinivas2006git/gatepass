import csv
import io
from flask import Blueprint, Response, render_template, request
from flask_login import current_user, login_required
from ..models import Department, GatePass, SMSNotification, Student
from ..utils.permissions import roles_required

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def dashboard():
    passes = GatePass.query
    if current_user.has_role("STAFF") and not current_user.has_role("SUPER_ADMIN", "APPROVER"):
        passes = passes.filter_by(created_by_id=current_user.id)
    totals = {
        "students": Student.query.filter_by(is_active=True).count(),
        "all": passes.count(),
        "pending": passes.filter_by(status="PENDING").count(),
        "approved": passes.filter_by(status="APPROVED").count(),
        "rejected": passes.filter_by(status="REJECTED").count(),
        "outside": passes.filter(GatePass.exit_at.isnot(None), GatePass.return_at.is_(None)).count(),
        "sms_sent": SMSNotification.query.filter(SMSNotification.status.in_(["SENT", "DELIVERED", "SIMULATED"])).count(),
        "sms_failed": SMSNotification.query.filter(SMSNotification.status.in_(["FAILED", "REJECTED"])).count(),
    }
    recent = passes.order_by(GatePass.created_at.desc()).limit(8).all()
    return render_template("dashboard.html", totals=totals, recent=recent)


@main_bp.get("/sms-notifications")
@roles_required("SUPER_ADMIN", "APPROVER")
def sms_notifications():
    status = request.args.get("status", "")
    notifications = SMSNotification.query
    if status:
        notifications = notifications.filter_by(status=status)
    return render_template("sms_notifications.html", notifications=notifications.order_by(SMSNotification.created_at.desc()).all(), selected_status=status)


@main_bp.get("/reports")
@roles_required("SUPER_ADMIN", "APPROVER")
def reports():
    status = request.args.get("status", "")
    department_id = request.args.get("department_id", type=int)
    passes = GatePass.query.join(Student)
    if status:
        passes = passes.filter(GatePass.status == status)
    if department_id:
        passes = passes.filter(Student.department_id == department_id)
    records = passes.order_by(GatePass.created_at.desc()).all()
    if request.args.get("format") == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Pass number", "Student", "USN", "Department", "Reason", "Status", "Requested departure", "SMS status"])
        for item in records:
            sms_status = item.notifications[0].status if item.notifications else "NOT_CREATED"
            writer.writerow([item.pass_number, item.student.full_name, item.student.usn, item.student.department.code, item.reason, item.status, item.requested_departure_at.isoformat(), sms_status])
        return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=mrit-gate-pass-report.csv"})
    return render_template("reports.html", passes=records, departments=Department.query.order_by(Department.code).all(), selected_status=status, selected_department=department_id)

