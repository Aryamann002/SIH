import asyncio
import threading
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.api.v1.sessions import _session_creations, admit_session, read_audio
from app.core.config import settings
from app.services.audio_evidence import audio_capacity, infer


class _SlowRequest:
    async def stream(self):
        await asyncio.sleep(1)
        yield b"audio"


class CapacityTests(unittest.TestCase):
    def test_session_creation_is_rate_limited_and_recovers(self):
        _session_creations.clear()
        try:
            for _ in range(60):
                admit_session(now=0)
            with self.assertRaises(HTTPException) as raised:
                admit_session(now=0)
            self.assertEqual(raised.exception.status_code, 429)
            admit_session(now=61)
        finally:
            _session_creations.clear()

    def test_upload_read_has_deadline(self):
        with patch.object(settings, "AUDIO_UPLOAD_TIMEOUT_SECONDS", 0.01):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(read_audio(_SlowRequest()))
        self.assertEqual(raised.exception.status_code, 408)

    def test_one_inference_runs_and_waiters_fail_promptly(self):
        started, release = threading.Event(), threading.Event()

        def blocked():
            started.set()
            release.wait(1)
            return "done"

        async def run():
            first = asyncio.create_task(infer(blocked))
            while not started.is_set():
                await asyncio.sleep(0)
            with self.assertRaises(HTTPException) as raised:
                await infer(lambda: "must not run")
            self.assertEqual(raised.exception.status_code, 503)
            release.set()
            self.assertEqual(await first, "done")
            self.assertEqual(await infer(lambda: "next"), "next")

        with patch.object(settings, "AUDIO_INFERENCE_QUEUE_TIMEOUT_SECONDS", 0.01):
            asyncio.run(run())

    def test_only_one_audio_session_is_admitted(self):
        async def run():
            async with audio_capacity():
                with self.assertRaises(HTTPException) as raised:
                    async with audio_capacity():
                        self.fail("second audio session must not start")
                self.assertEqual(raised.exception.status_code, 503)
            async with audio_capacity():
                pass

        with patch.object(settings, "AUDIO_CAPACITY_WAIT_SECONDS", 0.01):
            asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
