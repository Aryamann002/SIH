import numpy as np
from typing import Optional


class SpoofDetector:
    """
    Single-model WavLM/wav2vec2 spoof detector interface.
    Uses frozen WavLM + classification head with acoustic spectral feature fallback.
    """

    def __init__(self, onnx_model_path: Optional[str] = None):
        self.model_name = "WavLM-Large-Spoof-Head"
        self.session = None

        if onnx_model_path:
            try:
                import onnxruntime as ort
                self.session = ort.InferenceSession(onnx_model_path)
            except Exception:
                self.session = None

    def predict(self, pcm_data: np.ndarray) -> float:
        """Predict synthetic/spoof probability score S in range [0.0, 1.0]."""
        if len(pcm_data) == 0:
            return 0.0

        if self.session:
            try:
                inputs = {self.session.get_inputs()[0].name: pcm_data.reshape(1, -1)}
                outputs = self.session.run(None, inputs)
                score = float(outputs[0][0][1])  # Class index 1 = Spoof
                return round(float(np.clip(score, 0.0, 1.0)), 4)
            except Exception:
                pass  # Fallback to acoustic feature heuristic if ONNX execution fails

        # Acoustic spectral & entropy heuristic
        variance = float(np.var(pcm_data))
        if variance < 1e-7:
            return 0.99  # Digital silence / generated silence artifact

        # High frequency spectral energy ratio check
        fft_vals = np.abs(np.fft.rfft(pcm_data))
        hf_energy = float(np.sum(fft_vals[len(fft_vals) // 2 :]))
        total_energy = float(np.sum(fft_vals)) + 1e-9
        hf_ratio = hf_energy / total_energy

        # Synthetic voice often exhibits abnormal HF artifacts or unnatural periodicity
        if hf_ratio > 0.45 or hf_ratio < 0.02:
            score = 0.82
        else:
            score = float(np.clip(1.0 - (variance * 60.0), 0.05, 0.65))

        return round(score, 4)

