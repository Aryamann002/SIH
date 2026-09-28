"""Exercise deterministic Laya integration rules with labeled, synthetic scenarios.

This never calls Laya. Live agreement, latency and calibration remain unmeasured.
"""
from collections import Counter
import json
from pathlib import Path

from app.services.laya import CHOICES, final_action_status


SCENARIOS = Path(__file__).resolve().parents[1] / "tests/laya_scenarios.json"


def evaluate(rows):
    names = set()
    counts = Counter()
    for row in rows:
        if row["name"] in names:
            raise ValueError("Duplicate scenario name")
        names.add(row["name"])
        if row["choice"] is not None and row["choice"] not in CHOICES:
            raise ValueError("Invalid simulated Laya choice")
        final = final_action_status(row["deterministic"], row)
        if final != row["expected"]:
            raise AssertionError(f"{row['name']}: expected {row['expected']}, got {final}")
        counts["cases"] += 1
        counts["unsafe_downgrades"] += final == "PENDING" and row["deterministic"] == "BLOCKED"
        counts["escalations"] += final == "BLOCKED" and row["deterministic"] == "PENDING"
        counts["enhanced_review_recommendations"] += row["choice"] == "ENHANCED_REVIEW"
        counts["injected_failures"] += row["fallback_reason"] in ("timeout", "malformed_response", "http_error")
        counts["injected_timeouts"] += row["fallback_reason"] == "timeout"
    if counts["cases"] != 20 or counts["unsafe_downgrades"]:
        raise AssertionError("Scenario suite incomplete or unsafe")
    return {**counts, "laya_deterministic_agreement_rate": None,
            "manual_review_rate": None,
            "laya_p50_latency_ms": None, "laya_p95_latency_ms": None,
            "live_failure_rate": None, "live_timeout_rate": None, "calibration": None,
            "offline_behavior": "The fixture keeps deterministic PENDING plus action-bound verification when Laya is absent.",
            "note": "Choices/failures are fixtures, not Laya service observations; no approval or OTP is exercised here."}


if __name__ == "__main__":
    print(json.dumps(evaluate(json.loads(SCENARIOS.read_text(encoding="utf-8"))), indent=2))
