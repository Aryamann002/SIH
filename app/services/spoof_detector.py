"""Local pretrained Wav2Vec2 ONNX inference; no synthetic fallback scores."""

from functools import lru_cache
from hashlib import file_digest
from pathlib import Path

import numpy as np

from app.core.config import settings


class ModelUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=4)
def load_onnx(path: str):
    """Share immutable model sessions; callers own recurrent state."""
    try:
        import onnxruntime as ort

        resolved = Path(path).expanduser().resolve(strict=True)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(
            str(resolved), sess_options=options, providers=["CPUExecutionProvider"]
        )
        with resolved.open("rb") as model_file:
            digest = file_digest(model_file, "sha256").hexdigest()
        return session, digest
    except Exception as exc:
        raise ModelUnavailable("Local ONNX model cannot be loaded") from exc


class SpoofDetector:
    """Contract: normalized 16 kHz waveform -> logits [real, fake]."""

    def __init__(self, onnx_model_path: str | None = None):
        self.session = None
        self.model_version = "unavailable"
        try:
            self.session, digest = load_onnx(
                onnx_model_path or getattr(settings, "SPOOF_MODEL_PATH", "models/spoof_detector.onnx")
            )
            if {item.name for item in self.session.get_inputs()} != {
                "input_values", "attention_mask"
            }:
                raise ModelUnavailable("Unsupported detector input contract")
            mask = next(item for item in self.session.get_inputs() if item.name == "attention_mask")
            if mask.type not in {"tensor(int32)", "tensor(int64)"}:
                raise ModelUnavailable("Unsupported attention mask type")
            self.mask_dtype = np.int32 if mask.type == "tensor(int32)" else np.int64
            version = getattr(settings, "SPOOF_MODEL_VERSION", "wav2vec2-xlsr-int8-4b1c4a294ab6")
            self.model_version = f"{version}:sha256:{digest}"
        except ModelUnavailable:
            self.session = None

    @property
    def available(self) -> bool:
        return self.session is not None

    def predict(self, pcm_data: np.ndarray) -> float:
        if self.session is None:
            raise ModelUnavailable("Spoof model is unavailable")
        if (pcm_data.ndim != 1 or not 400 <= len(pcm_data) <= 64000
                or not np.isfinite(pcm_data).all() or np.max(np.abs(pcm_data)) > 1):
            raise ValueError("Expected 400..64000 finite mono PCM samples in [-1, 1]")
        audio = np.asarray(pcm_data, dtype=np.float32)
        audio = (audio - audio.mean()) / np.sqrt(audio.var() + 1e-7)
        values = audio.reshape(1, -1)
        try:
            logits = np.asarray(self.session.run(None, {
                "input_values": values,
                "attention_mask": np.ones_like(values, dtype=self.mask_dtype),
            })[0], dtype=np.float64)
            if logits.shape != (1, 2) or not np.isfinite(logits).all():
                raise ModelUnavailable("Invalid detector logits")
            probabilities = np.exp(logits[0] - logits[0].max())
            return float(probabilities[1] / probabilities.sum())
        except Exception as exc:
            raise ModelUnavailable("Spoof inference failed") from exc
