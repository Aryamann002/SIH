"""Exploratory public Monsoon genuine-only probe; never select a threshold from it.

Only hashes, source offsets and detector results are saved. Source audio stays in memory.
"""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
from urllib.parse import quote, urlparse

from scripts.evaluate_audio import wav_prefix
from scripts.probe_indicsynth import fetch, normalise_wav


DATASETS = {
    "en-IN": ("VoiceArena/MonsoonASR-Open-ASR-leaderboard-en-IN",
              "bc1da7b42ef6e2853123c97bf6d22067e4802d11", 2102),
    "hi-IN": ("VoiceArena/MonsoonASR-Open-ASR-leaderboard-hi-IN",
              "a4b7375e9adea16c16100295976cdb0aabd9fb6d", 753),
}
BATCH_SIZE = 100
PER_BLOCK = 5


def select_rows(batches: list[list[dict]], block_count: int, per_block: int) -> list[dict]:
    if len(batches) != block_count:
        raise ValueError("Unexpected metadata block count")
    selected, speakers = [], set()
    for batch in batches:
        chosen = 0
        for item in batch:
            row = item["row"]
            speaker = row.get("speaker_id")
            if (speaker is None or not row.get("id") or float(row["audio_length_s"]) < 4
                    or speaker in speakers):
                continue
            selected.append(item)
            speakers.add(speaker)
            chosen += 1
            if chosen == per_block:
                break
        if chosen != per_block:
            raise ValueError("Not enough eligible distinct speakers in metadata block")
    return selected


def validate_asset_url(url: str, dataset: str, revision: str, index: int) -> None:
    parsed = urlparse(url)
    expected = f"/cached-assets/{dataset}/--/{revision}/--/default/test/{index}/audio/audio.wav"
    if (parsed.scheme != "https" or parsed.netloc != "datasets-server.huggingface.co"
            or parsed.path != expected or not parsed.query):
        raise ValueError("Unexpected dataset asset URL or revision")


def identifier_hash(dataset: str, value: object) -> str:
    return sha256(f"{dataset}:{value}".encode()).hexdigest()


def probe() -> dict:
    from app.services.audio_evidence import evaluate_wav

    results = []
    blocks = {}
    for language, (dataset, revision, total) in DATASETS.items():
        info = json.loads(fetch(f"https://huggingface.co/api/datasets/{dataset}"))
        if info.get("sha") != revision or info.get("gated") or info.get("private"):
            raise ValueError("Monsoon release changed or became restricted")
        starts = (0, (total - BATCH_SIZE) // 2, total - BATCH_SIZE)
        blocks[language] = starts
        batches = []
        for start in starts:
            url = ("https://datasets-server.huggingface.co/rows?dataset="
                   f"{quote(dataset, safe='')}&config=default&split=test&offset={start}&length={BATCH_SIZE}")
            entries = json.loads(fetch(url))["rows"]
            if len(entries) != BATCH_SIZE or entries[0]["row_idx"] != start:
                raise ValueError("Unexpected Monsoon metadata block")
            batches.append(entries)
        selected = select_rows(batches, len(starts), PER_BLOCK)
        for item in selected:
            index, row = item["row_idx"], item["row"]
            assets = row["audio"]
            if len(assets) != 1 or assets[0].get("type") != "audio/wav":
                raise ValueError("Unexpected Monsoon audio field")
            validate_asset_url(assets[0]["src"], dataset, revision, index)
            print(f"Scoring {language} public row {index}", flush=True)
            source = fetch(assets[0]["src"])
            normalized, source_rate, _ = normalise_wav(source)
            clip = wav_prefix(normalized, 4)
            if clip is None:
                raise ValueError("Selected source is shorter than four seconds")
            started = perf_counter()
            risk = evaluate_wav(clip)
            results.append({
                "language": language, "row_idx": index,
                "clip_id_sha256": identifier_hash(dataset, row["id"]),
                "speaker_id_sha256": identifier_hash(dataset, row["speaker_id"]),
                "source_sha256": sha256(source).hexdigest(),
                "four_second_clip_sha256": sha256(clip).hexdigest(),
                "source_sample_rate": source_rate,
                "source_duration_seconds": row["audio_length_s"],
                "risk_state": risk["risk_state"], "spoof_score": risk["spoof_score"],
                "speech_duration_ms": risk["speech_duration_ms"],
                "reason_codes": risk["reason_codes"],
                "model_version": risk["model_version"],
                "threshold_profile": risk["threshold_profile"],
                "latency_seconds": round(perf_counter() - started, 3),
            })
    return {"purpose": "Exploratory genuine-only public ASR test check; no threshold selection or final test",
            "datasets": {language: {"name": name, "revision": revision} for language, (name, revision, _) in DATASETS.items()},
            "block_starts": blocks, "per_block": PER_BLOCK, "audio_persisted": False,
            "source_recording_ids_verified": False,
            "risk_states": dict(sorted(Counter(row["risk_state"] for row in results).items())),
            "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Refusing to overwrite {args.output}")
    args.output.write_text(json.dumps(probe(), indent=2) + "\n", encoding="utf-8")
