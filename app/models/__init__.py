from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from ..extensions import db
from ..utils.timezone import UTCDateTime, utc_now


user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    db.Column("role_id", db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


def utcnow():
    return utc_now()


class TimestampMixin:
    created_at = db.Column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at = db.Column(UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False)


class Role(db.Model, TimestampMixin):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    display_name = db.Column(db.String(80), nullable=False)


class User(db.Model, UserMixin, TimestampMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    roles = db.relationship("Role", secondary=user_roles, lazy="selectin")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_role(self, *role_names):
        return any(role.name in role_names for role in self.roles)


class Department(db.Model, TimestampMixin):
    __tablename__ = "departments"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), unique=True, nullable=False)
    students = db.relationship("Student", back_populates="department")


class Student(db.Model, TimestampMixin):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    usn = db.Column(db.String(30), unique=True, nullable=False, index=True)
    semester = db.Column(db.SmallInteger, nullable=False)
    section = db.Column(db.String(10), nullable=False)
    # Guardian details are retained for administration only; never use them for gate-pass SMS.
    parent_name = db.Column(db.String(150), nullable=False)
    parent_mobile = db.Column(db.String(15), nullable=False)
    student_mobile = db.Column(db.String(15), index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True)
    department = db.relationship("Department", back_populates="students")
    gate_passes = db.relationship("GatePass", back_populates="student")


class GatePass(db.Model, TimestampMixin):
    __tablename__ = "gate_passes"
    id = db.Column(db.Integer, primary_key=True)
    pass_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    verification_token = db.Column(db.String(96), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="PENDING", index=True)
    reason = db.Column(db.String(500), nullable=False)
    requested_departure_at = db.Column(UTCDateTime(), nullable=False, index=True)
    expected_return_at = db.Column(UTCDateTime())
    additional_remarks = db.Column(db.Text)
    approval_remarks = db.Column(db.Text)
    approved_at = db.Column(UTCDateTime(), index=True)
    expires_at = db.Column(UTCDateTime(), index=True)
    exit_at = db.Column(UTCDateTime(), index=True)
    return_at = db.Column(UTCDateTime(), index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    student = db.relationship("Student", back_populates="gate_passes", foreign_keys=[student_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])
    approvals = db.relationship("GatePassApproval", back_populates="gate_pass", cascade="all, delete-orphan")
    notifications = db.relationship("SMSNotification", back_populates="gate_pass", cascade="all, delete-orphan")


class GatePassApproval(db.Model, TimestampMixin):
    __tablename__ = "gate_pass_approvals"
    id = db.Column(db.Integer, primary_key=True)
    decision = db.Column(db.String(20), nullable=False)
    remarks = db.Column(db.Text)
    gate_pass_id = db.Column(db.Integer, db.ForeignKey("gate_passes.id"), nullable=False, index=True)
    approver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    gate_pass = db.relationship("GatePass", back_populates="approvals")
    approver = db.relationship("User")


class SMSTemplate(db.Model, TimestampMixin):
    __tablename__ = "sms_templates"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class SMSNotification(db.Model, TimestampMixin):
    __tablename__ = "sms_notifications"
    __table_args__ = (db.UniqueConstraint("gate_pass_id", "event_type", name="uq_sms_gate_pass_event"),)
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(40), nullable=False, default="APPROVED")
    recipient_type = db.Column(db.String(20), nullable=False, default="STUDENT")
    recipient = db.Column(db.String(15), nullable=False)
    sender_id = db.Column(db.String(20), nullable=False, default="CP-MRITPR-S")
    rendered_message = db.Column(db.Text, nullable=False)
    provider = db.Column(db.String(40), nullable=False)
    provider_message_id = db.Column(db.String(150), index=True)
    status = db.Column(db.String(20), nullable=False, default="PENDING", index=True)
    error_code = db.Column(db.String(80))
    safe_response = db.Column(db.Text)
    retry_count = db.Column(db.SmallInteger, default=0, nullable=False)
    sent_at = db.Column(UTCDateTime())
    delivered_at = db.Column(UTCDateTime())
    gate_pass_id = db.Column(db.Integer, db.ForeignKey("gate_passes.id"), nullable=False)
    gate_pass = db.relationship("GatePass", back_populates="notifications")


class SecurityVerificationLog(db.Model, TimestampMixin):
    __tablename__ = "security_verification_logs"
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(30), nullable=False)
    outcome = db.Column(db.String(30), nullable=False)
    details = db.Column(db.Text)
    gate_pass_id = db.Column(db.Integer, db.ForeignKey("gate_passes.id"), index=True)
    verified_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    gate_pass = db.relationship("GatePass")
    verified_by = db.relationship("User")


class AuditLog(db.Model, TimestampMixin):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.String(80), nullable=False)
    metadata_json = db.Column(db.Text)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    actor = db.relationship("User")
