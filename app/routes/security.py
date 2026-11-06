from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from ..extensions import db
from ..models import GatePass, SecurityVerificationLog
from ..utils.audit import record
from ..utils.permissions import roles_required
from ..utils.timezone import utc_now

security_bp = Blueprint("security", __name__)


def validate(gate_pass):
    now = utc_now()
    if not gate_pass:
        return "NOT_FOUND", "No matching gate pass exists."
    if gate_pass.status != "APPROVED":
        return "REJECTED", "This pass is not approved."
    if gate_pass.expires_at and gate_pass.expires_at < now:
        return "EXPIRED", "This pass has expired."
    if gate_pass.exit_at:
        return "USED", "Exit has already been recorded for this pass."
    return "VALID", "Pass is valid for exit."


@security_bp.route("/verify", methods=["GET", "POST"])
@roles_required("SUPER_ADMIN", "SECURITY")
def verify():
    gate_pass = None
    result = None
    lookup = request.values.get("lookup", "").strip()
    if lookup:
        gate_pass = GatePass.query.filter((GatePass.pass_number == lookup) | (GatePass.student.has(usn=lookup))).order_by(GatePass.created_at.desc()).first()
        result = validate(gate_pass)
        db.session.add(SecurityVerificationLog(gate_pass=gate_pass, verified_by=current_user, action="LOOKUP", outcome=result[0], details=lookup))
        db.session.commit()
    return render_template("security/verify.html", gate_pass=gate_pass, result=result, lookup=lookup)


@security_bp.get("/verify/token/<token>")
@roles_required("SUPER_ADMIN", "SECURITY")
def verify_token(token):
    gate_pass = GatePass.query.filter_by(verification_token=token).first()
    result = validate(gate_pass)
    db.session.add(SecurityVerificationLog(gate_pass=gate_pass, verified_by=current_user, action="QR_LOOKUP", outcome=result[0]))
    db.session.commit()
    return render_template("security/verify.html", gate_pass=gate_pass, result=result, lookup="QR scan")


@security_bp.post("/<int:pass_id>/exit")
@roles_required("SUPER_ADMIN", "SECURITY")
def exit_student(pass_id):
    gate_pass = db.get_or_404(GatePass, pass_id)
    result = validate(gate_pass)
    if result[0] != "VALID":
        flash(result[1], "danger")
    else:
        gate_pass.exit_at = utc_now()
        db.session.add(SecurityVerificationLog(gate_pass=gate_pass, verified_by=current_user, action="EXIT", outcome="RECORDED"))
        record("STUDENT_EXIT_RECORDED", "gate_pass", gate_pass.pass_number)
        db.session.commit()
        flash("Student exit recorded.", "success")
    return redirect(url_for("security.verify", lookup=gate_pass.pass_number))


@security_bp.post("/<int:pass_id>/return")
@roles_required("SUPER_ADMIN", "SECURITY")
def return_student(pass_id):
    gate_pass = db.get_or_404(GatePass, pass_id)
    if not gate_pass.exit_at or gate_pass.return_at:
        flash("A valid outstanding exit is required before recording return.", "danger")
    else:
        gate_pass.return_at = utc_now()
        db.session.add(SecurityVerificationLog(gate_pass=gate_pass, verified_by=current_user, action="RETURN", outcome="RECORDED"))
        record("STUDENT_RETURN_RECORDED", "gate_pass", gate_pass.pass_number)
        db.session.commit()
        flash("Student return recorded.", "success")
    return redirect(url_for("security.verify", lookup=gate_pass.pass_number))
