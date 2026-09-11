import asyncio
from datetime import datetime, timezone
from uuid import UUID


# ponytail: one-process local delivery simulation; replace with trusted delivery before multiple workers.
inbox: dict[UUID, dict] = {}


def prune() -> None:
    now = datetime.now(timezone.utc)
    for action_id in list(inbox):
        if inbox[action_id]["expires_at"] <= now:
            inbox.pop(action_id, None)


def deliver(action_id: UUID, code: str, expires_at: datetime, payload: dict) -> None:
    prune()
    inbox[action_id] = {"action_id": action_id, "otp_code": code,
                        "expires_at": expires_at, "payload": payload}
    ttl = max(0, (expires_at - datetime.now(timezone.utc)).total_seconds())
    asyncio.get_running_loop().call_later(ttl, inbox.pop, action_id, None)
