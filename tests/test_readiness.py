import asyncio
import math
import unittest
from unittest.mock import AsyncMock, Mock, patch

from pydantic import ValidationError

from app.core.config import Settings, settings
from app.core.database import REQUIRED_COLUMNS, database_status
from app.api.v1.sessions import model_status, readiness
from app.services.audio_pipeline import AudioPipeline


class ConfigTests(unittest.TestCase):
    def test_defaults_are_valid(self):
        Settings(_env_file=None)

    def test_invalid_numeric_configuration_is_rejected(self):
        cases = [
            {"MIN_SNR_DB": math.nan},
            {"ELEVATED_RISK_SPOOF_THRESHOLD": 0.8, "HIGH_RISK_SPOOF_THRESHOLD": 0.8},
            {"MIN_SPEECH_DURATION_MS": 0},
            {"MIN_SPEECH_DURATION_MS": 2001, "AUDIO_WINDOW_SECONDS": 2},
            {"AUDIO_WINDOW_SECONDS": 4.01}, {"EMA_ALPHA": 0}, {"VAD_THRESHOLD": 0},
            {"MIN_RMS": 1.01}, {"AUDIO_INFERENCE_TIMEOUT_SECONDS": 0},
            {"OTP_TTL_SECONDS": 0}, {"APPROVAL_TTL_SECONDS": 0},
            {"FILE_EVIDENCE_TTL_SECONDS": 0}, {"STREAM_EVIDENCE_TTL_SECONDS": 0},
            {"MAX_OTP_ATTEMPTS": 2}, {"MAX_OTP_ATTEMPTS": 4},
            {"MAX_AUDIO_BYTES": 44}, {"MAX_AUDIO_BYTES": 960045},
        ]
        for values in cases:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                Settings(_env_file=None, **values)


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _Connection:
    def __init__(self, rows):
        self.rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        pass

    async def execute(self, _query):
        return _Result(self.rows)


class _Engine:
    def __init__(self, rows):
        self.rows = rows

    def connect(self):
        return _Connection(self.rows)


class _BrokenEngine:
    def connect(self):
        raise RuntimeError("database unavailable")


class ReadinessTests(unittest.TestCase):
    def test_database_probe_requires_migrated_schema(self):
        rows = list(REQUIRED_COLUMNS)
        with patch("app.core.database.engine", _Engine(rows)):
            self.assertEqual(asyncio.run(database_status()), (True, True))
        with patch("app.core.database.engine", _Engine([row for row in rows if row != ("sessions", "status")])):
            self.assertEqual(asyncio.run(database_status()), (True, False))
        with patch("app.core.database.engine", _BrokenEngine()):
            self.assertEqual(asyncio.run(database_status()), (False, False))

    def test_readiness_requires_every_dependency(self):
        models = {"available": True, "vad_available": True, "detector_available": True,
                  "model_version": "spoof", "vad_model_version": "vad", "calibrated": False}
        with patch("app.api.v1.sessions.database_status", AsyncMock(return_value=(True, True))), \
                patch("app.api.v1.sessions.model_status", AsyncMock(return_value=models)), \
                patch.object(settings, "DEMO_VERIFIER_KEY", "configured"):
            self.assertTrue(asyncio.run(readiness())["ready"])
        for database, schema, vad, detector, verifier in [
            (False, False, True, True, "configured"), (True, False, True, True, "configured"),
            (True, True, False, True, "configured"), (True, True, True, False, "configured"),
            (True, True, True, True, ""),
        ]:
            broken = {**models, "vad_available": vad, "detector_available": detector}
            with self.subTest(database=database, schema=schema, vad=vad, detector=detector, verifier=bool(verifier)), \
                    patch("app.api.v1.sessions.database_status", AsyncMock(return_value=(database, schema))), \
                    patch("app.api.v1.sessions.model_status", AsyncMock(return_value=broken)), \
                    patch.object(settings, "DEMO_VERIFIER_KEY", verifier):
                self.assertFalse(asyncio.run(readiness())["ready"])

    def test_model_timeout_returns_stable_unavailable_status(self):
        with patch("app.api.v1.sessions.infer", AsyncMock(side_effect=TimeoutError)):
            info = asyncio.run(model_status())
        self.assertFalse(info["available"])
        self.assertFalse(info["vad_available"])
        self.assertFalse(info["detector_available"])

    def test_model_warmup_executes_both_models_and_fails_closed(self):
        vad = Mock(available=True, model_version="vad")
        detector = Mock(available=True, model_version="spoof")
        detector.predict.side_effect = RuntimeError("invalid output")
        AudioPipeline.status.cache_clear()
        try:
            with patch("app.services.audio_pipeline.SileroVADWorker", return_value=vad), \
                    patch("app.services.audio_pipeline.SpoofDetector", return_value=detector):
                info = AudioPipeline.status()
            vad.process_chunk.assert_called_once()
            detector.predict.assert_called_once()
            self.assertTrue(info["vad_available"])
            self.assertFalse(info["detector_available"])
        finally:
            AudioPipeline.status.cache_clear()

    def test_readiness_endpoint_fails_without_disabling_liveness(self):
        from app.main import health_check, readiness_check

        with patch("app.main.readiness", AsyncMock(return_value={"ready": False})):
            self.assertEqual(asyncio.run(readiness_check()).status_code, 503)
        self.assertEqual(asyncio.run(health_check())["status"], "ok")

    def test_lifespan_runs_bounded_model_status(self):
        from app.main import lifespan

        warmup = AsyncMock(return_value={"available": False})

        async def run():
            with patch("app.main.model_status", warmup):
                async with lifespan(None):
                    pass

        asyncio.run(run())
        warmup.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
