"""Evaluate the real upload pipeline; select an offline HIGH threshold on validation only."""
import argparse
from collections import Counter
import csv
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
QUALITY = {"POOR_QUALITY", "INSUFFICIENT_EVIDENCE", "INVALID_AUDIO"}


def read_manifest(path):
    path = path.resolve(strict=True)
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not {"path", "label", "split", "group", "sha256"} <= set(reader.fieldnames or []):
            raise ValueError("Manifest requires path,label,split,group,sha256")
        rows = list(reader)
    if not 1 <= len(rows) <= 10000:
        raise ValueError("Manifest must have 1..10000 rows")
    groups, digests, pcm_digests = {}, set(), set()
    for row in rows:
        if row["label"] not in {"genuine", "spoof"} or row["split"] not in {"validation", "test"}:
            raise ValueError("Use labels genuine/spoof and splits validation/test")
        if not row["group"].strip():
            raise ValueError("Every clip needs a source group")
        previous = groups.setdefault(row["group"], row["split"])
        if previous != row["split"]:
            raise ValueError("Source group leakage between validation and test")
        relative = Path(row["path"])
        resolved = (path.parent / relative).resolve(strict=True)
        if relative.is_absolute() or not resolved.is_relative_to(path.parent) or not resolved.is_file():
            raise ValueError("Audio paths must stay within the manifest directory")
        if resolved.stat().st_size > 960044:
            raise ValueError("Audio exceeds the upload byte limit")
        data = resolved.read_bytes()
        digest = sha256(data).hexdigest()
        if digest != row["sha256"]:
            raise ValueError("Audio checksum mismatch")
        if digest in digests:
            raise ValueError("Duplicate audio content")
        digests.add(digest)
        try:
            with wave.open(io.BytesIO(data), "rb") as audio:
                pcm_digest = sha256(audio.readframes(audio.getnframes())).hexdigest()
            if pcm_digest in pcm_digests:
                raise ValueError("Duplicate PCM content, including differently headed WAVs")
            pcm_digests.add(pcm_digest)
        except (wave.Error, EOFError):
            pass  # The upload decoder will record invalid WAVs as rejected input.
        row["absolute_path"] = str(resolved)
    for split in ("validation", "test"):
        if {r["label"] for r in rows if r["split"] == split} != {"genuine", "spoof"}:
            raise ValueError("Both classes are required in each split")
    return rows


def metrics(rows, threshold=None):
    confusion = {label: {"eligible_for_otp": 0, "high_risk_blocked": 0} for label in ("genuine", "spoof")}
    quality = Counter()
    unavailable = Counter()
    for row in rows:
        state = row["risk_state"]
        if state in QUALITY:
            quality[row["label"]] += 1
        elif state == "SERVICE_UNAVAILABLE":
            unavailable[row["label"]] += 1
        elif state in {"LOW", "ELEVATED", "HIGH"}:
            score = row["maximum_chunk_score"]
            if score is None or not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("Scorable results require a finite score in [0,1]")
            blocked = state == "HIGH" if threshold is None else score >= threshold
            confusion[row["label"]]["high_risk_blocked" if blocked else "eligible_for_otp"] += 1
        else:
            raise ValueError(f"Unknown risk state: {state}")
    genuine, spoof = (sum(confusion[label].values()) for label in ("genuine", "spoof"))
    far = confusion["spoof"]["eligible_for_otp"] / spoof if spoof else None
    frr = confusion["genuine"]["high_risk_blocked"] / genuine if genuine else None
    return {"total": len(rows), "scorable": genuine + spoof, "confusion": confusion,
            "quality_rejections": dict(quality), "service_unavailable": dict(unavailable),
            "FAR_spoof_eligible_for_otp": far, "FRR_genuine_high_risk_blocked": frr,
            "balanced_error": (far + frr) / 2 if far is not None and frr is not None else None}


def select_threshold(validation, elevated):
    if not validation or any(row["split"] != "validation" for row in validation):
        raise ValueError("Threshold selection accepts validation rows only")
    # ponytail: fixed 0.01 grid for exploratory evidence; use a prespecified cost objective on representative data before promotion.
    candidates = [n / 100 for n in range(math.ceil(elevated * 100), 101)]
    evaluated = [(threshold, metrics(validation, threshold)) for threshold in candidates]
    viable = [(threshold, result) for threshold, result in evaluated if result["balanced_error"] is not None]
    if not viable:
        raise ValueError("Both validation classes need scorable audio; cannot select a threshold")
    return min(viable, key=lambda pair: (pair[1]["balanced_error"], pair[1]["FAR_spoof_eligible_for_otp"], pair[0]))


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evaluation-output")
    args = parser.parse_args()
    rows = read_manifest(args.manifest)
    from app.core.config import settings
    from app.services.audio_evidence import evaluate_wav
    from app.services.audio_pipeline import AudioPipeline

    start = time.perf_counter()
    status = AudioPipeline.status()
    startup = time.perf_counter() - start
    if not status["available"]:
        raise SystemExit("Local models unavailable; no evaluation report generated")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    process = AudioPipeline.process_chunk
    for index, row in enumerate(rows, 1):
        chunks = []

        def capture(self, data):
            result = process(self, data)
            chunks.append(result)
            return result

        started = time.perf_counter()
        try:
            with patch.object(AudioPipeline, "process_chunk", capture):
                result = evaluate_wav(Path(row["absolute_path"]).read_bytes())
        except ValueError as exc:
            result = {"risk_state": "INVALID_AUDIO", "spoof_score": None, "reason_codes": [str(exc)]}
        latency = time.perf_counter() - started
        scores = [chunk["spoof_score"] for chunk in chunks if chunk["spoof_score"] is not None]
        results.append({**{key: value for key, value in row.items() if key != "absolute_path"}, **result,
                        "maximum_chunk_score": max(scores) if scores else None,
                        "chunk_count": len(chunks), "latency_seconds": latency})
        print(f"{index}/{len(rows)} {row['split']} {row['label']} {result['risk_state']} {latency:.2f}s", flush=True)
    validation = [row for row in results if row["split"] == "validation"]
    test = [row for row in results if row["split"] == "test"]
    threshold, validation_metrics = select_threshold(validation, settings.ELEVATED_RISK_SPOOF_THRESHOLD)
    latencies = [row["latency_seconds"] for row in results]
    report = {
        "purpose": "Exploratory teacher demonstration; no model training or production threshold change",
        "manifest_sha256": sha256(args.manifest.read_bytes()).hexdigest(),
        "models": status, "threshold_profiles": sorted({r["threshold_profile"] for r in results if "threshold_profile" in r}),
        "source_sha256": {str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
                          for path in [ROOT / "scripts/evaluate_audio.py", *sorted((ROOT / "app").rglob("*.py"))]},
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
        "pipeline": "Exact evaluate_wav decoding, 6400-byte chunks, VAD, quality gates, EMA, and upload file aggregation",
        "definitions": "FAR = spoof files eligible for OTP / scorable spoof files; FRR = HIGH-blocked genuine files / scorable genuine files. Eligibility never means a completed transaction. Quality and service failures are reported separately, excluded from these denominators.",
        "default_high_threshold": settings.HIGH_RISK_SPOOF_THRESHOLD,
        "default_validation": metrics(validation), "default_test": metrics(test),
        "candidate": {"high_threshold": threshold, "promoted": False,
                      "selection": "Validation only: minimum balanced error on 0.01 grid >= fixed elevated threshold; ties lower FAR, then lower threshold",
                      "replay": "Offline max per-chunk score compared to frozen candidate HIGH threshold; original quality/service disposition retained; elevated threshold fixed",
                      "validation": validation_metrics, "test": metrics(test, threshold)},
        "latency_seconds": {"model_load": startup, "median_file": statistics.median(latencies),
                            "p95_file": percentile(latencies, 0.95), "total_files": sum(latencies)},
        "limitations": ["40 selected English clips are exploratory, not an accuracy certification",
                        "Source recording groups and synthetic provider prefixes are separated between these splits; speaker/text independence is unverified",
                        "Overlap with pretrained detector training data is unverified",
                        "No Indian-language, replay, phone-channel or added-noise coverage in this corpus",
                        "Scores are not calibrated fraud probabilities; candidate is not deployed",
                        "Offline file latency excludes HTTP/database overhead and does not establish streaming latency"],
    }
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Exploratory audio evaluation", "", report["purpose"], "", report["definitions"], "",
             "| Run | Scorable/total | Spoof eligible / scorable spoof (FAR) | Genuine blocked / scorable genuine (FRR) | Quality rejected | Unavailable |",
             "|---|---:|---:|---:|---:|---:|"]
    for name, result in (("Default validation", report["default_validation"]), ("Default test", report["default_test"]),
                         (f"Candidate {threshold:.2f} validation", validation_metrics), (f"Frozen candidate {threshold:.2f} test", report["candidate"]["test"])):
        counts = result["confusion"]
        def rate(label, key, rate_key):
            value = result[rate_key]
            return f"{counts[label][key]}/{sum(counts[label].values())} ({value:.1%})" if value is not None else "n/a"
        lines.append(f"| {name} | {result['scorable']}/{result['total']} | {rate('spoof', 'eligible_for_otp', 'FAR_spoof_eligible_for_otp')} | {rate('genuine', 'high_risk_blocked', 'FRR_genuine_high_risk_blocked')} | {sum(result['quality_rejections'].values())} | {sum(result['service_unavailable'].values())} |")
    lines.extend(["", f"Median file inference: {statistics.median(latencies):.2f}s; p95: {percentile(latencies, .95):.2f}s. Model loading: {startup:.2f}s.",
                  "", "Candidate selection uses validation only. Test results never influence selection. The candidate remains offline.", "",
                  *[f"- {item}" for item in report["limitations"]], "", "See report.json for confusion counts, model/config/source hashes and results.json for every clip."])
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report written: {output / 'report.md'}", flush=True)


if __name__ == "__main__":
    main()
