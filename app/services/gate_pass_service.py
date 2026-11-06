import secrets
from datetime import timedelta
from flask import current_app
from ..extensions import db
from ..models import GatePass, GatePassApproval, utcnow
from .sms_service import send_approval_sms


def create_pass_number():
    while True:
        candidate = f"MRIT-{utcnow():%Y%m%d}-{secrets.token_hex(3).upper()}"
        if not GatePass.query.filter_by(pass_number=candidate).first():
            return candidate


def create_gate_pass(student, creator, reason, departure_at, expected_return_at=None, remarks=None):
    gate_pass = GatePass(
        pass_number=create_pass_number(), verification_token=secrets.token_urlsafe(32), student=student,
        created_by=creator, reason=reason, requested_departure_at=departure_at,
        expected_return_at=expected_return_at, additional_remarks=remarks,
    )
    db.session.add(gate_pass)
    return gate_pass


def decide_gate_pass(gate_pass, approver, decision, remarks=""):
    if gate_pass.status != "PENDING":
        raise ValueError("This gate pass has already been decided.")
    if decision not in {"APPROVED", "REJECTED"}:
        raise ValueError("Invalid decision.")
    now = utcnow()
    gate_pass.status = decision
    gate_pass.approval_remarks = remarks
    gate_pass.approved_by = approver
    gate_pass.approved_at = now
    if decision == "APPROVED":
        gate_pass.expires_at = gate_pass.requested_departure_at + timedelta(hours=current_app.config["PASS_VALIDITY_HOURS"])
    db.session.add(GatePassApproval(gate_pass=gate_pass, approver=approver, decision=decision, remarks=remarks))
    db.session.flush()
    notification = None
    if decision == "APPROVED":
        notification, _ = send_approval_sms(gate_pass)
    return notification
