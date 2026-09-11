import hashlib
import hmac
from uuid import UUID
from fastapi import Header, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.schemas import RiskState


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def otp_digest(challenge_id: UUID, code: str) -> str:
    return hmac.new(settings.VERIFICATION_SECRET.encode(), f"{challenge_id}:{code}".encode(),
                    hashlib.sha256).hexdigest()


def bearer(authorization: str = Header(default="", max_length=256)) -> str:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not 32 <= len(token) <= 128:
        raise HTTPException(401, "A session bearer token is required.")
    return token


async def owned_session(db: AsyncSession, session_id: UUID, token: str, lock: bool = False):
    query = "SELECT * FROM sessions WHERE session_id = :id AND token_hash = :hash"
    if lock:
        query += " FOR UPDATE"
    row = (await db.execute(text(query), {"id": session_id, "hash": digest(token)})).mappings().first()
    if row is None:
        raise HTTPException(404, "Session not found.")
    return row


async def owned_action(db: AsyncSession, action_id: UUID, token: str, lock: bool = True):
    row = (await db.execute(text("SELECT session_id FROM protected_actions WHERE action_id=:id"), {"id": action_id})).first()
    if row is None:
        raise HTTPException(404, "Action not found.")
    session = await owned_session(db, row.session_id, token, lock)
    query = "SELECT * FROM protected_actions WHERE action_id=:id" + (" FOR UPDATE" if lock else "")
    action = (await db.execute(text(query), {"id": action_id})).mappings().one()
    return action, session


async def evidence(db: AsyncSession, session) -> tuple[RiskState, dict]:
    if session["status"] not in ("LIVE", "FILE_READY"):
        return RiskState.SERVICE_UNAVAILABLE, {"reason_codes": ["STREAM_OR_FILE_UNAVAILABLE"]}
    row = (await db.execute(text("""
        SELECT *, EXTRACT(EPOCH FROM (clock_timestamp() - timestamp)) AS age
        FROM risk_evaluations WHERE id = :id AND session_id = :session_id
    """), {"id": session["latest_evaluation_id"], "session_id": session["session_id"]})).mappings().first()
    if row is None:
        return RiskState.INSUFFICIENT_EVIDENCE, {"reason_codes": ["NO_CURRENT_EVIDENCE"]}
    ttl = settings.STREAM_EVIDENCE_TTL_SECONDS if session["status"] == "LIVE" else settings.FILE_EVIDENCE_TTL_SECONDS
    if not 0 <= float(row["age"]) < ttl:
        return RiskState.SERVICE_UNAVAILABLE, {"reason_codes": ["STALE_EVIDENCE"]}
    try:
        risk = RiskState(row["risk_state"])
        score = row["score"]
        if risk in (RiskState.LOW, RiskState.ELEVATED) and (score is None or not 0 <= score <= 1):
            raise ValueError("invalid score")
    except (ValueError, TypeError):
        return RiskState.SERVICE_UNAVAILABLE, {"reason_codes": ["INVALID_EVIDENCE"]}
    return risk, dict(row)


async def db_now(db: AsyncSession):
    return (await db.execute(text("SELECT clock_timestamp()"))).scalar_one()


def eligible(risk: RiskState) -> bool:
    return risk in (RiskState.LOW, RiskState.ELEVATED)
