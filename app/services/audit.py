import json
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AuditService:
    """Insert into the caller's transaction; an audit failure must fail the action."""

    @staticmethod
    async def log_event(db: AsyncSession, session_id: str | UUID, event_type: str,
                        risk_state: str | None = None, reason_code: str | None = None,
                        details: dict | None = None, action_id: UUID | None = None) -> None:
        await db.execute(text("""
            INSERT INTO audit_logs
                (session_id, action_id, event_type, risk_state, reason_code, details)
            VALUES (:session_id, :action_id, :event_type, :risk_state, :reason_code,
                    CAST(:details AS jsonb))
        """), {"session_id": UUID(str(session_id)), "action_id": action_id,
               "event_type": event_type, "risk_state": risk_state,
               "reason_code": reason_code, "details": json.dumps(details or {}, allow_nan=False)})
