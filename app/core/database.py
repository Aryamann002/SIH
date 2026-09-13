import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_timeout=settings.DATABASE_TIMEOUT_SECONDS,
    connect_args={"timeout": settings.DATABASE_TIMEOUT_SECONDS,
                  "command_timeout": settings.DATABASE_TIMEOUT_SECONDS},
)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

REQUIRED_COLUMNS = {
    ("sessions", column) for column in
    ("session_id", "created_at", "status", "token_hash", "generation", "latest_evaluation_id")
} | {
    ("risk_evaluations", column) for column in
    ("id", "session_id", "timestamp", "score", "snr_db", "speech_duration_ms", "risk_state",
     "reason_codes", "model_version", "threshold_profile")
} | {
    ("protected_actions", column) for column in
    ("action_id", "session_id", "action_type", "payload", "status", "risk_state", "created_at", "completed_at")
} | {
    ("verification_challenges", column) for column in
    ("challenge_id", "action_id", "code_hash", "attempts", "status", "expires_at")
} | {
    ("approval_tokens", column) for column in
    ("action_id", "token_hash", "expires_at", "consumed_at")
} | {
    ("audit_logs", column) for column in
    ("id", "session_id", "timestamp", "event_type", "risk_state", "reason_code", "details", "action_id")
}


async def database_status():
    async def probe():
        async with engine.connect() as connection:
            rows = (await connection.execute(text("""
                SELECT table_name, column_name FROM information_schema.columns
                WHERE table_schema=current_schema()
            """))).all()
        columns = {(row[0], row[1]) for row in rows}
        return True, REQUIRED_COLUMNS <= columns

    try:
        return await asyncio.wait_for(probe(), timeout=2)
    except Exception:
        return False, False


async def invalidate_interrupted_audio():
    async with AsyncSessionLocal() as session:
        await session.execute(text("""
            WITH interrupted AS (
                UPDATE sessions
                SET status='DISCONNECTED', generation=NULL, latest_evaluation_id=NULL
                WHERE status IN ('LIVE', 'PROCESSING_FILE')
                RETURNING session_id
            )
            INSERT INTO audit_logs (session_id,event_type,risk_state,reason_code,details)
            SELECT session_id,'AUDIO_UNAVAILABLE','SERVICE_UNAVAILABLE','BACKEND_RESTART','{}'::jsonb
            FROM interrupted
        """))
        await session.commit()


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
