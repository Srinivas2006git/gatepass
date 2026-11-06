import json
import secrets
from flask import current_app
from ..extensions import db
from ..models import SMSNotification, SMSTemplate
from ..utils.timezone import format_india, to_india, utc_now


DEFAULT_TEMPLATE = (
    "The student {student_name} bearing USN {usn} is permitted to go out of the college "
    "for the reason {reason}. on {date} at {time}. Gate Pass Reference: {pass_number}. "
    "Show this SMS and the reference to security for system verification.\n\n"
    "Principal, MRIT"
)


def render_approved_message(gate_pass):
    template = SMSTemplate.query.filter_by(name="gate_pass_approved", is_active=True).first()
    body = template.body if template else DEFAULT_TEMPLATE
    local_time = to_india(gate_pass.requested_departure_at)
    return body.format(
        student_name=gate_pass.student.full_name.upper(), usn=gate_pass.student.usn, pass_number=gate_pass.pass_number,
        reason=gate_pass.reason, date=format_india(gate_pass.requested_departure_at, "%d/%m/%Y"), time=local_time.strftime("%I:%M %p")
    )


def send_approval_sms(gate_pass):
    existing = SMSNotification.query.filter_by(gate_pass_id=gate_pass.id, event_type="APPROVED").first()
    if existing:
        return existing, False
    recipient = gate_pass.student.student_mobile
    sender_id = current_app.config["SMS_SENDER_ID"]
    notification = SMSNotification(
        gate_pass_id=gate_pass.id, recipient_type="STUDENT", recipient=recipient or "UNREGISTERED",
        sender_id=sender_id, rendered_message=render_approved_message(gate_pass),
        provider=current_app.config["SMS_PROVIDER"], status="PENDING",
    )
    db.session.add(notification)
    db.session.flush()
    if not recipient:
        notification.status = "REJECTED"
        notification.error_code = "STUDENT_MOBILE_MISSING"
        notification.safe_response = "No registered student mobile number; no SMS was sent."
        return notification, True
    if sender_id != "CP-MRITPR-S":
        notification.status = "REJECTED"
        notification.error_code = "UNAUTHORIZED_SENDER_ID"
        notification.safe_response = "The configured sender ID is not the authorized MRIT header; no SMS was sent."
        return notification, True
    if current_app.config["SMS_PROVIDER"] != "mock":
        notification.status = "REJECTED"
        notification.error_code = "PROVIDER_NOT_CONFIGURED"
        notification.safe_response = "Live provider adapter has not been enabled. No SMS was sent."
        return notification, True
    notification.status = "SIMULATED"
    notification.provider_message_id = f"MOCK-{secrets.token_hex(8).upper()}"
    notification.sent_at = utc_now()
    notification.safe_response = json.dumps({"simulated": True, "accepted": True})
    return notification, True

