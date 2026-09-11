"""Offline regression checks; optional real-model smoke uses downloaded local files."""

import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

import numpy as np

from app.services.audio_pipeline import AudioPipeline
from app.services.spoof_detector import ModelUnavailable, SpoofDetector
from app.services.vad_worker import SileroVADWorker


class AudioTests(unittest.TestCase):
    def test_unavailable_models_never_produce_a_score(self):
        with patch("app.services.vad_worker.load_onnx", side_effect=ModelUnavailable), patch(
            "app.services.spoof_detector.load_onnx", side_effect=ModelUnavailable
        ):
            result = AudioPipeline().process_chunk(bytes(32000))
        self.assertEqual(result["risk_state"], "SERVICE_UNAVAILABLE")
        self.assertIsNone(result["spoof_score"])

    def test_speech_and_clipping_expire_with_audio_window(self):
        class Session:
            def run(self, _, inputs):
                probability = float(np.mean(inputs["input"][:, -512:]) > 0.01)
                return np.array([[probability]]), inputs["state"]

        with patch("app.services.vad_worker.load_onnx", return_value=(Session(), "test")):
            vad = SileroVADWorker()
        voiced = np.full(32000, 2000, dtype="<i2")
        voiced[0] = 32767
        _, speech_ms, _, clipped = vad.process_chunk(voiced.tobytes())
        self.assertGreater(speech_ms, 1500)
        self.assertTrue(clipped)
        # Tiny packets must not renew a prior window as new speech evidence.
        _, tiny_speech_ms, _, _ = vad.process_chunk(b"\x00\x00")
        self.assertEqual(tiny_speech_ms, 0)
        _, speech_ms, window, clipped = vad.process_chunk(bytes(65024))
        self.assertEqual(speech_ms, 0)
        self.assertEqual(len(window), 32000)
        self.assertFalse(clipped)
        with self.assertRaises(ValueError):
            vad.process_chunk(b"\x00")

    def test_detector_normalizes_and_rejects_invalid_logits(self):
        class Session:
            def get_inputs(self):
                return [SimpleNamespace(name="input_values", type="tensor(float)"),
                        SimpleNamespace(name="attention_mask", type="tensor(int32)")]

            def run(self, _, inputs):
                self.inputs = inputs
                return [np.array([[0.0, np.log(3.0)]])]

        session = Session()
        with patch("app.services.spoof_detector.load_onnx", return_value=(session, "test")):
            detector = SpoofDetector()
        score = detector.predict(np.linspace(-0.5, 0.5, 32000, dtype=np.float32))
        self.assertAlmostEqual(score, 0.75)
        self.assertAlmostEqual(float(session.inputs["input_values"].mean()), 0, places=6)
        self.assertEqual(session.inputs["attention_mask"].dtype, np.int32)
        with patch.object(session, "run", return_value=[np.array([[0.0, np.nan]])]):
            with self.assertRaises(ModelUnavailable):
                detector.predict(np.zeros(32000, dtype=np.float32))

    def test_ema_does_not_delay_escalation_and_failure_erases_score(self):
        vad = SimpleNamespace(available=True, rms=0.1, reset=lambda: None,
                              process_chunk=lambda _: (30.0, 2000, np.zeros(32000), False))
        detector = SimpleNamespace(available=True, model_version="test", predict=lambda _: 0.1)
        with patch("app.services.audio_pipeline.SileroVADWorker", return_value=vad), patch(
            "app.services.audio_pipeline.SpoofDetector", return_value=detector
        ):
            pipeline = AudioPipeline()
        self.assertEqual(pipeline.process_chunk(b"00")["risk_state"], "LOW")
        detector.predict = lambda _: 0.95
        self.assertEqual(pipeline.process_chunk(b"00")["risk_state"], "HIGH")
        detector.predict = lambda _: 0.1
        result = pipeline.process_chunk(b"00")
        self.assertGreater(result["spoof_score"], 0.1)
        with patch.object(detector, "predict", side_effect=ModelUnavailable):
            result = pipeline.process_chunk(b"00")
        self.assertEqual(result["risk_state"], "SERVICE_UNAVAILABLE")
        self.assertIsNone(result["spoof_score"])
        self.assertIsNone(pipeline.smoothed_score)

    @unittest.skipUnless(os.getenv("RUN_MODEL_SMOKE") == "1", "Set RUN_MODEL_SMOKE=1 after fetching models")
    def test_downloaded_models_infer_real_speech_files(self):
        self.assertTrue(AudioPipeline.status()["available"])
        for name in ("genuine", "synthetic"):
            with self.subTest(sample=name):
                pipeline = AudioPipeline()
                with wave.open(str(Path("models/demo") / f"{name}.wav"), "rb") as audio:
                    self.assertEqual((audio.getnchannels(), audio.getframerate(), audio.getsampwidth()), (1, 16000, 2))
                    results = []
                    while chunk := audio.readframes(16000):
                        results.append(pipeline.process_chunk(chunk))
                scores = [r["spoof_score"] for r in results if r["spoof_score"] is not None]
                self.assertTrue(scores)
                self.assertTrue(all(np.isfinite(s) and 0 <= s <= 1 for s in scores))
                self.assertNotIn("SERVICE_UNAVAILABLE", [r["risk_state"] for r in results])


if __name__ == "__main__":
    unittest.main()
