"""Validate a source-disjoint audio manifest before model fitting or evaluation."""
import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import wave


FIELDS = (
    "clip_id", "file_path", "sha256", "label", "language", "speaker_id",
    "source_dataset", "source_recording_id", "transcript_id", "generator_family",
    "generator_model", "attack_type", "genuine_or_synthetic", "duration",
    "sample_rate", "codec", "channel", "replay_status", "augmentation_parent",
    "consent_or_license", "split", "source_speaker_id", "target_speaker_id",
)
SPLITS = {"train", "validation", "test"}
UNKNOWN = {"", "unknown", "n/a", "na", "null"}


def _file_digest(path):
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _pcm_digest(path):
    try:
        with wave.open(str(path), "rb") as audio:
            digest = sha256()
            for block in iter(lambda: audio.readframes(65536), b""):
                digest.update(block)
            return digest.hexdigest(), audio.getnframes() / audio.getframerate(), audio.getframerate()
    except (wave.Error, EOFError, ZeroDivisionError):
        return None


def validate(path, heldout_generator):
    path = Path(path).resolve(strict=True)
    root = path.parent
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not set(FIELDS) <= set(reader.fieldnames or ()):
            raise ValueError(f"Missing manifest columns: {sorted(set(FIELDS) - set(reader.fieldnames or ())) }")
        rows = list(reader)
    if not rows:
        raise ValueError("Manifest is empty")
    ids, digests, pcm_digests, group_splits = set(), set(), set(), {}
    counts = Counter()
    heldout_count = 0
    for row in rows:
        clip = row["clip_id"].strip()
        if not clip or clip in ids:
            raise ValueError("clip_id must be unique and nonempty")
        ids.add(clip)
        split = row["split"].strip()
        label = row["label"].strip()
        if split not in SPLITS or label not in {"genuine", "spoof"}:
            raise ValueError(f"Invalid split or label for {clip}")
        if row["genuine_or_synthetic"].strip() != ("genuine" if label == "genuine" else "synthetic"):
            raise ValueError(f"Label disagrees with genuine_or_synthetic for {clip}")
        for field in ("language", "speaker_id", "source_dataset", "source_recording_id",
                      "transcript_id", "attack_type", "codec", "channel", "replay_status",
                      "consent_or_license"):
            if row[field].strip().lower() in UNKNOWN:
                raise ValueError(f"Missing or unknown {field} for {clip}; quarantine incomplete lineage")
        family = row["generator_family"].strip()
        model = row["generator_model"].strip()
        if label == "spoof" and (family.lower() in UNKNOWN or model.lower() in UNKNOWN):
            raise ValueError(f"Synthetic generator identity missing for {clip}")
        if label == "genuine" and (family.lower() != "none" or model.lower() != "none"):
            raise ValueError(f"Genuine clip must use generator none for {clip}")
        if family == heldout_generator:
            if split != "test" or label != "spoof":
                raise ValueError("Held-out generator appears outside synthetic test")
            heldout_count += 1
        if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError(f"Invalid SHA256 for {clip}")
        relative = Path(row["file_path"])
        resolved = (root / relative).resolve(strict=True)
        if relative.is_absolute() or not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError(f"Audio path escapes manifest directory for {clip}")
        if _file_digest(resolved) != row["sha256"]:
            raise ValueError(f"Audio checksum mismatch for {clip}")
        if row["sha256"] in digests:
            raise ValueError("Duplicate audio SHA256")
        digests.add(row["sha256"])
        try:
            duration, sample_rate = float(row["duration"]), int(row["sample_rate"])
        except ValueError as exc:
            raise ValueError(f"Invalid duration or sample rate for {clip}") from exc
        if not math.isfinite(duration) or duration <= 0 or sample_rate <= 0:
            raise ValueError(f"Invalid duration or sample rate for {clip}")
        if resolved.suffix.lower() == ".wav":
            pcm = _pcm_digest(resolved)
            if pcm is None:
                raise ValueError(f"Invalid WAV for {clip}")
            pcm_hash, actual_duration, actual_rate = pcm
            if pcm_hash in pcm_digests:
                raise ValueError("Duplicate PCM content")
            pcm_digests.add(pcm_hash)
            if actual_rate != sample_rate or abs(actual_duration - duration) > 0.02:
                raise ValueError(f"WAV metadata mismatch for {clip}")
        # IDs are global lineage identifiers. Same speaker, source, transcript, or
        # voice used in conversion must never straddle splits.
        for field in ("speaker_id", "source_recording_id", "transcript_id",
                      "source_speaker_id", "target_speaker_id"):
            value = row[field].strip()
            if value.lower() in UNKNOWN:
                continue
            key = (field, value)
            previous = group_splits.setdefault(key, split)
            if previous != split:
                raise ValueError(f"{field} leakage between {previous} and {split}: {value}")
        counts[(split, label)] += 1
    by_id = {row["clip_id"].strip(): row for row in rows}
    for row in rows:
        parent = row["augmentation_parent"].strip()
        if parent:
            if parent not in by_id or by_id[parent]["split"] != row["split"]:
                raise ValueError("Augmentation parent missing or crosses splits")
            if row["split"] != "train":
                raise ValueError("Augmentations are permitted only in train")
    if heldout_count == 0:
        raise ValueError("Held-out generator absent from test")
    for split in SPLITS:
        if not counts[(split, "genuine")] or not counts[(split, "spoof")]:
            raise ValueError(f"Both classes required in {split}")
    return {"rows": len(rows), "split_class_counts": {f"{s}:{l}": n for (s, l), n in sorted(counts.items())},
            "heldout_generator": heldout_generator, "heldout_test_clips": heldout_count,
            "manifest_sha256": _file_digest(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--heldout-generator", required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.manifest, args.heldout_generator), indent=2))


if __name__ == "__main__":
    main()
