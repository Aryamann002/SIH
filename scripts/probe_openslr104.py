"""Exploratory genuine-only four-second probe on the pinned OpenSLR-104 test archive.

The ASR test partition is development material here, not VigilVoice's final test.
No audio is extracted to disk, and this command never selects a threshold.
"""

import argparse
from collections import Counter
from hashlib import file_digest, sha256
import io
import json
import math
from pathlib import Path
import re
import tarfile
from time import perf_counter
import wave


ARCHIVE_SHA256 = "93e358b3bf8233a897fcd353c1f4f98fdda6b8c01b7eed17a70c7dd26e984b37"


def select_segments(segments_text: str, speakers_text: str) -> list[dict]:
    speakers = {}
    for line in speakers_text.splitlines():
        utterance, speaker = line.split()
        if utterance in speakers or not re.fullmatch(r"[A-Za-z0-9_]+", speaker):
            raise ValueError("Invalid speaker mapping")
        speakers[utterance] = speaker
    selected = {}
    seen = set()
    recording_speakers = {}
    for line in segments_text.splitlines():
        utterance, source, start_text, end_text = line.split()
        if utterance in seen or utterance not in speakers or not re.fullmatch(r"[A-Za-z0-9]+", source):
            raise ValueError("Missing, duplicate or unsafe speaker mapping")
        seen.add(utterance)
        start, end = float(start_text), float(end_text)
        if not all(map(math.isfinite, (start, end))) or start < 0 or end <= start:
            raise ValueError("Invalid segment boundaries")
        speaker = speakers[utterance]
        recording_speakers.setdefault(source, set()).add(speaker)
        if end - start < 4:
            continue
        candidate = {"utterance_id": utterance, "source_recording_id": source,
                     "speaker_id": speaker, "start_seconds": start}
        previous = selected.get(speaker)
        if previous is None or (source, start, utterance) < (
                previous["source_recording_id"], previous["start_seconds"], previous["utterance_id"]):
            selected[speaker] = candidate
    if seen != speakers.keys() or any(len(group) != 1 for group in recording_speakers.values()):
        raise ValueError("Incomplete or mixed-source speaker mapping")
    return [selected[speaker] for speaker in sorted(selected)]


def four_second_clip(source_wav: bytes, start_seconds: float) -> bytes:
    with wave.open(io.BytesIO(source_wav), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()) != (
                1, 2, 16000, "NONE"):
            raise ValueError("Expected mono 16 kHz PCM16 source WAV")
        start = round(start_seconds * 16000)
        if start + 64000 > audio.getnframes():
            raise ValueError("Source WAV is too short for selected excerpt")
        audio.setpos(start)
        pcm = audio.readframes(64000)
    if len(pcm) != 128000:
        raise ValueError("Source WAV is too short for selected excerpt")
    output = io.BytesIO()
    with wave.open(output, "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(16000)
        clip.writeframes(pcm)
    return output.getvalue()


def probe(archive_path: Path) -> dict:
    with archive_path.open("rb") as source:
        digest = file_digest(source, "sha256").hexdigest()
    if digest != ARCHIVE_SHA256:
        raise ValueError(f"Unexpected OpenSLR-104 archive SHA256: {digest}")
    from app.services.audio_evidence import evaluate_wav

    with tarfile.open(archive_path, "r:gz") as archive:
        def metadata(name):
            member = archive.getmember(name)
            if not member.isfile():
                raise ValueError(f"Invalid archive member: {name}")
            return archive.extractfile(member).read().decode("utf-8")

        selected = select_segments(metadata("test/transcripts/segments"),
                                   metadata("test/transcripts/utt2spk"))
        if len(selected) != 30 or len({row["source_recording_id"] for row in selected}) != 30:
            raise ValueError("Expected 30 distinct speakers and source recordings")
        results = []
        for row in selected:
            name = f"test/{row['source_recording_id']}.wav"
            member = archive.getmember(name)
            if not member.isfile():
                raise ValueError(f"Invalid archive member: {name}")
            clip = four_second_clip(archive.extractfile(member).read(), row["start_seconds"])
            started = perf_counter()
            risk = evaluate_wav(clip)
            results.append({**row, "clip_sha256": sha256(clip).hexdigest(),
                            "risk_state": risk["risk_state"], "spoof_score": risk["spoof_score"],
                            "speech_duration_ms": risk["speech_duration_ms"],
                            "reason_codes": risk["reason_codes"],
                            "model_version": risk["model_version"],
                            "threshold_profile": risk["threshold_profile"],
                            "latency_seconds": round(perf_counter() - started, 3)})
    states = Counter(row["risk_state"] for row in results)
    return {"purpose": "Exploratory genuine-only OpenSLR-104 check; no threshold selection or final test",
            "archive_sha256": digest, "selection": "First >=4-second segment per speaker; exact 4-second prefix",
            "samples": len(results), "risk_states": dict(sorted(states.items())),
            "genuine_high_false_blocks": states["HIGH"], "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(probe(args.archive), indent=2)
    if args.output:
        if args.output.exists():
            parser.error(f"Refusing to overwrite {args.output}")
        args.output.write_text(report + "\n", encoding="utf-8")
    else:
        print(report)
