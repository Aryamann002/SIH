"""Exploratory, metadata-only report for 12 fixed public IndicSynth synthetic clips.

No audio is saved. This is not a threshold-selection or untouched-test command.
Requires local FFmpeg to convert the publisher's WAVs to the upload contract.
"""

import argparse
from collections import Counter
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import struct
from time import perf_counter
from urllib.parse import quote, urlparse
from urllib.request import urlopen
import wave


REVISION = "c0a10386b723717aff682f757bd67f72983f269f"
DATASET = "vdivyasharma/IndicSynth"
ROWS = {
    "Hindi": (0, 67959, 135918, 195640),
    "Marathi": (0, 42949, 85898, 123641),
    "Punjabi": (0, 81956, 163912, 235935),
}
MAX_BYTES = 10_000_000


def validate_asset_url(url: str, language: str, offset: int) -> None:
    parsed = urlparse(url)
    expected = f"/cached-assets/{DATASET}/--/{REVISION}/--/{language}/train/{offset}/audio/audio.wav"
    if (parsed.scheme != "https" or parsed.netloc != "datasets-server.huggingface.co"
            or parsed.path != expected or not parsed.query):
        raise ValueError("Unexpected dataset asset URL or revision")


def fetch(url: str) -> bytes:
    with urlopen(url, timeout=30) as response:
        data = response.read(MAX_BYTES + 1)
    if not 1000 <= len(data) <= MAX_BYTES:
        raise ValueError("Unexpected dataset response size")
    return data


def normalise_wav(data: bytes) -> tuple[bytes, int, float]:
    if (len(data) < 44 or len(data) > MAX_BYTES or data[:4] != b"RIFF" or data[8:12] != b"WAVE"
            or struct.unpack_from("<I", data, 4)[0] != len(data) - 8):
        raise ValueError("Invalid source RIFF/WAV")
    chunks = {}
    position = 12
    while position + 8 <= len(data):
        kind = data[position:position + 4]
        length = struct.unpack_from("<I", data, position + 4)[0]
        position += 8
        if position + length > len(data) or kind in chunks:
            raise ValueError("Invalid or duplicate WAV chunk")
        chunks[kind] = data[position:position + length]
        position += length + length % 2
    if position != len(data) or b"fmt " not in chunks or b"data" not in chunks or len(chunks[b"fmt "]) < 16:
        raise ValueError("Incomplete source WAV")
    fmt, channels, rate, byte_rate, align, bits = struct.unpack_from("<HHIIHH", chunks[b"fmt "], 0)
    if (fmt, channels, bits) not in {(1, 1, 16), (3, 1, 32)} or not 8000 <= rate <= 48000:
        raise ValueError("Unsupported source WAV format")
    if align != bits // 8 or byte_rate != rate * align or len(chunks[b"data"]) % align:
        raise ValueError("Invalid source WAV sizing")
    duration = len(chunks[b"data"]) / byte_rate
    if not 0 < duration <= 30:
        raise ValueError("Unsupported source WAV duration")
    try:
        converted = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
             "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"],
            input=data, capture_output=True, check=True, timeout=30).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("FFmpeg normalization failed") from exc
    if not 0 < len(converted) <= 960000 or len(converted) % 2:
        raise ValueError("Invalid normalized PCM length")
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        target.writeframes(converted)
    return output.getvalue(), rate, round(duration, 3)


def probe() -> dict:
    info = json.loads(fetch(f"https://huggingface.co/api/datasets/{DATASET}"))
    if info.get("sha") != REVISION or info.get("gated") or info.get("private"):
        raise ValueError("IndicSynth release changed or became restricted")
    from app.services.audio_evidence import evaluate_wav

    results = []
    for language, offsets in ROWS.items():
        for offset in offsets:
            url = ("https://datasets-server.huggingface.co/rows?dataset="
                   f"{quote(DATASET, safe='')}&config={language}&split=train&offset={offset}&length=1")
            entries = json.loads(fetch(url))["rows"]
            if len(entries) != 1 or entries[0]["row_idx"] != offset:
                raise ValueError("Unexpected dataset row")
            row = entries[0]["row"]
            assets = row["audio"]
            if len(assets) != 1 or assets[0].get("type") != "audio/wav":
                raise ValueError("Unexpected dataset audio field")
            asset_url = assets[0]["src"]
            validate_asset_url(asset_url, language, offset)
            print(f"Scoring {language} public row {offset}", flush=True)
            source = fetch(asset_url)
            wav, rate, duration = normalise_wav(source)
            started = perf_counter()
            risk = evaluate_wav(wav)
            results.append({
                "language": language, "row_idx": offset,
                "generator_model": row["Generative Model"],
                "source_speaker_id": row["Source Speaker_ID"],
                "target_speaker_id": row["Target Speaker ID"],
                "source_reference_audio": row["Source Reference Audio"],
                "target_reference_audio": row["Target Reference Audio"],
                "transcript_present": bool(row["TTS Transcript"]),
                "source_sha256": sha256(source).hexdigest(),
                "normalized_sha256": sha256(wav).hexdigest(),
                "source_sample_rate": rate, "duration_seconds": duration,
                "risk_state": risk["risk_state"], "spoof_score": risk["spoof_score"],
                "speech_duration_ms": risk["speech_duration_ms"],
                "reason_codes": risk["reason_codes"],
                "model_version": risk["model_version"],
                "threshold_profile": risk["threshold_profile"],
                "latency_seconds": round(perf_counter() - started, 3),
            })
    return {"purpose": "Exploratory synthetic-only public check; no threshold selection or final test",
            "dataset": DATASET, "revision": REVISION, "fixed_offsets": ROWS,
            "audio_persisted": False, "risk_states": dict(sorted(Counter(r["risk_state"] for r in results).items())),
            "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Refusing to overwrite {args.output}")
    report = probe()
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
