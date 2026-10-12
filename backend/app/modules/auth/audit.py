from sqlalchemy.orm import Session

from app.modules.auth.models import AuditLog


def record_audit(
    db: Session,
    *,
    actor_id: int | None,
    entity_type: str,
    entity_id: int | str,
    action: str,
    before: dict[str, object] | None = None,
    after: dict[str, object] | None = None,
    ip: str | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=actor_id,
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            before_json=before,
            after_json=after,
            ip=ip,
        )
    )
