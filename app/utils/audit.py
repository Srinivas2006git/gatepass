import json
from flask_login import current_user
from ..extensions import db
from ..models import AuditLog


def record(action, entity_type, entity_id, metadata=None):
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        metadata_json=json.dumps(metadata or {}),
        actor_id=current_user.id if current_user and current_user.is_authenticated else None,
    )
    db.session.add(entry)

