import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.models.schemas import RiskState
from app.services.action_gate import evidence
from app.services.audio_evidence import _active_streams, end_audio, stream_connected
from app.api.v1.sessions import get_session


def test_disconnected_stream_fails_closed_even_when_audit_write_fails():
    session_id, generation = uuid4(), uuid4()
    risk, info = asyncio.run(evidence(None, {"session_id": session_id, "generation": generation,
                                           "status": "LIVE"}))
    assert risk == RiskState.SERVICE_UNAVAILABLE
    assert info["reason_codes"] == ["STREAM_NOT_CONNECTED"]

    class Db:
        async def execute(self, *_args, **_kwargs):
            return SimpleNamespace(first=lambda: (session_id,))

    _active_streams[str(session_id)] = generation
    with patch("app.services.audio_evidence.block_unfinished", new_callable=AsyncMock, return_value=[]), patch(
        "app.services.audio_evidence.AuditService.log_event", new_callable=AsyncMock,
        side_effect=RuntimeError("injected audit failure")
    ):
        try:
            asyncio.run(end_audio(Db(), session_id, generation, "STREAM_DISCONNECTED_OR_FAILED"))
        except RuntimeError:
            pass
        else:
            raise AssertionError("Audit failure was silently ignored")
    assert not stream_connected(session_id, generation)


def test_session_exposes_server_evidence_age_and_stale_age():
    session_id = uuid4()
    with patch("app.api.v1.sessions.owned_session", new_callable=AsyncMock,
               return_value={"status": "FILE_READY"}), patch(
        "app.api.v1.sessions.evidence", new_callable=AsyncMock,
        return_value=(RiskState.LOW, {"age": 2.5, "score": 0.1, "reason_codes": []})
    ):
        current = asyncio.run(get_session(session_id, "test-token", None))
    assert current["evidence_age_ms"] == 2500

    class Db:
        async def execute(self, *_args, **_kwargs):
            return SimpleNamespace(mappings=lambda: SimpleNamespace(
                first=lambda: {"age": 121.0}))

    risk, info = asyncio.run(evidence(Db(), {"session_id": session_id, "status": "FILE_READY",
                                            "latest_evaluation_id": uuid4()}))
    assert risk == RiskState.SERVICE_UNAVAILABLE
    assert info == {"reason_codes": ["STALE_EVIDENCE"], "age": 121.0}
