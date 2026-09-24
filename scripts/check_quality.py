"""Diagnostic quality probes on the two public demo WAVs; not an accuracy test."""
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import wave

import numpy as np

from app.services.audio_evidence import evaluate_wav


def encode(samples):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        audio.writeframes(np.clip(np.rint(samples * 32768), -32768, 32767).astype("<i2").tobytes())
    return output.getvalue()


def main(output):
    rows = []
    for name in ("genuine", "synthetic"):
        source = Path("models/demo") / f"{name}.wav"
        raw = source.read_bytes()
        with wave.open(io.BytesIO(raw), "rb") as audio:
            assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 16000)
            samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").astype(np.float32) / 32768
        rng = np.random.default_rng(26104)
        noise = rng.normal(size=len(samples)).astype(np.float32)
        noise *= np.sqrt(np.mean(samples ** 2)) / (np.sqrt(np.mean(noise ** 2)) * 10 ** (10 / 20))
        spectrum = np.fft.rfft(samples)
        frequencies = np.fft.rfftfreq(len(samples), 1 / 16000)
        spectrum[(frequencies < 300) | (frequencies > 3400)] = 0
        bandlimited = np.fft.irfft(spectrum).astype(np.float32)
        variants = {
            "clean": samples,
            "quiet_30db": samples * (10 ** (-30 / 20)),
            "clipped": np.clip(samples * (2 / np.max(np.abs(samples))), -1, 1),
            "added_noise_nominal_10db": np.clip(samples + noise, -1, 1),
            "simulated_telephone_band": bandlimited,
            **{f"first_{seconds:g}s": samples[:int(16000 * seconds)]
               for seconds in (0.5, 1, 2, 4) if len(samples) >= 16000 * seconds},
        }
        for condition, clip in variants.items():
            result = evaluate_wav(encode(clip))
            rows.append({"source": name, "source_sha256": sha256(raw).hexdigest(),
                         "condition": condition, "duration_seconds": round(len(clip) / 16000, 3),
                         "risk_state": result["risk_state"], "spoof_score": result["spoof_score"],
                         "snr_db": result["snr_db"], "speech_duration_ms": result["speech_duration_ms"],
                         "reason_codes": result["reason_codes"]})
            print(name, condition, result["risk_state"], result["reason_codes"], flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"scope": "Two public demo clips with deterministic transformations; no population accuracy claim",
                                  "rows": rows}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output)
