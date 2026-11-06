import io
import qrcode
from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from ..extensions import db
from ..models import GatePass, Student
from ..services.gate_pass_service import create_gate_pass, decide_gate_pass
from ..utils.audit import record
from ..utils.permissions import roles_required
from ..utils.timezone import format_india, parse_india_datetime

passes_bp = Blueprint("passes", __name__)
REASONS = ["Medical emergency", "Personal work", "Family emergency", "Exam completed", "College-related work", "Other"]


def parse_datetime(value):
    if not value:
        raise ValueError("Requested departure date and time are required.")
    return parse_india_datetime(value)


def can_view(gate_pass):
    return current_user.has_role("SUPER_ADMIN", "APPROVER", "SECURITY") or gate_pass.created_by_id == current_user.id


@passes_bp.route("/create", methods=["GET", "POST"])
@roles_required("SUPER_ADMIN", "STAFF")
def create():
    student = None
    usn = request.values.get("usn", "").strip().upper()
    if usn:
        student = Student.query.filter_by(usn=usn, is_active=True).first()
    if request.method == "POST":
        if not student:
            flash("Active student not found for that USN.", "danger")
        elif not student.student_mobile:
            flash("This student has no registered mobile number. Update the student record before creating a gate pass.", "danger")
        else:
            try:
                departure_at = parse_datetime(request.form.get("requested_departure_at"))
                expected_return = parse_datetime(request.form.get("expected_return_at")) if request.form.get("expected_return_at") else None
                reason = request.form.get("reason", "").strip()
                if reason == "Other":
                    reason = request.form.get("custom_reason", "").strip()
                if not reason:
                    raise ValueError("Provide a reason for leaving.")
                gate_pass = create_gate_pass(student, current_user, reason, departure_at, expected_return, request.form.get("remarks", "").strip())
                record("GATE_PASS_REQUESTED", "gate_pass", gate_pass.pass_number)
                db.session.commit()
                flash("Gate pass request submitted for approval.", "success")
                return redirect(url_for("passes.detail", pass_id=gate_pass.id))
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
    return render_template("passes/create.html", student=student, usn=usn, reasons=REASONS)


@passes_bp.get("/")
@roles_required("SUPER_ADMIN", "STAFF", "APPROVER", "SECURITY")
def list_passes():
    status = request.args.get("status", "")
    passes = GatePass.query
    if current_user.has_role("STAFF") and not current_user.has_role("SUPER_ADMIN", "APPROVER"):
        passes = passes.filter_by(created_by_id=current_user.id)
    if status:
        passes = passes.filter_by(status=status)
    return render_template("passes/list.html", passes=passes.order_by(GatePass.created_at.desc()).all(), selected_status=status)


@passes_bp.get("/<int:pass_id>")
@roles_required("SUPER_ADMIN", "STAFF", "APPROVER", "SECURITY")
def detail(pass_id):
    gate_pass = db.get_or_404(GatePass, pass_id)
    if not can_view(gate_pass):
        abort(403)
    return render_template("passes/detail.html", gate_pass=gate_pass)


@passes_bp.post("/<int:pass_id>/decision")
@roles_required("SUPER_ADMIN", "APPROVER")
def decision(pass_id):
    gate_pass = db.get_or_404(GatePass, pass_id)
    try:
        notification = decide_gate_pass(gate_pass, current_user, request.form.get("decision"), request.form.get("remarks", "").strip())
        record(f"GATE_PASS_{gate_pass.status}", "gate_pass", gate_pass.pass_number, {"sms_status": notification.status if notification else None})
        db.session.commit()
        flash("Gate pass approved; SMS to the student's registered mobile was simulated." if notification and notification.status == "SIMULATED" else f"Gate pass {gate_pass.status.lower()}.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("passes.detail", pass_id=pass_id))


@passes_bp.get("/<int:pass_id>/qr.png")
@roles_required("SUPER_ADMIN", "STAFF", "APPROVER", "SECURITY")
def qr_code(pass_id):
    gate_pass = db.get_or_404(GatePass, pass_id)
    if not can_view(gate_pass):
        abort(403)
    image = qrcode.make(url_for("security.verify_token", token=gate_pass.verification_token, _external=True))
    output = io.BytesIO()
    image.save(output, "PNG")
    output.seek(0)
    return send_file(output, mimetype="image/png")


@passes_bp.get("/<int:pass_id>/print.pdf")
@roles_required("SUPER_ADMIN", "STAFF", "APPROVER")
def print_pdf(pass_id):
    gate_pass = db.get_or_404(GatePass, pass_id)
    if not can_view(gate_pass) or gate_pass.status != "APPROVED":
        abort(403)
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    width, height = A4
    pdf.setTitle(f"MRIT Gate Pass {gate_pass.pass_number}")
    pdf.setFont("Helvetica-Bold", 18); pdf.drawString(20 * mm, height - 25 * mm, "M. R. INSTITUTE OF TECHNOLOGY")
    pdf.setFont("Helvetica-Bold", 14); pdf.drawString(20 * mm, height - 36 * mm, "APPROVED STUDENT GATE PASS")
    pdf.setFont("Helvetica", 10)
    fields = [("Pass number", gate_pass.pass_number), ("Student", gate_pass.student.full_name), ("USN", gate_pass.student.usn),
              ("Department", gate_pass.student.department.name), ("Reason", gate_pass.reason), ("Approved by", gate_pass.approved_by.full_name),
              ("Departure", format_india(gate_pass.requested_departure_at)), ("Status", gate_pass.status)]
    y = height - 52 * mm
    for label, value in fields:
        pdf.setFont("Helvetica-Bold", 10); pdf.drawString(20 * mm, y, f"{label}:")
        pdf.setFont("Helvetica", 10); pdf.drawString(62 * mm, y, str(value))
        y -= 9 * mm
    pdf.drawString(20 * mm, 30 * mm, "Verify using the QR code in the dashboard. This pass is digitally generated.")
    pdf.showPage(); pdf.save(); output.seek(0)
    return send_file(output, mimetype="application/pdf", as_attachment=True, download_name=f"{gate_pass.pass_number}.pdf")

