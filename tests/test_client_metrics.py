"""Keep streaming timing summaries honest for short and long runs."""

from scripts.test_client import response_summary


def test_response_summary_uses_nearest_rank_and_disjoint_drift_windows():
    short = response_summary([n / 1000 for n in range(1, 22)])
    assert short["p95_response_ms"] == 20
    assert short["first_60_response_ms"] is None
    assert short["last_60_response_ms"] is None

    long = response_summary([n / 1000 for n in range(1, 601)])
    assert long["first_60_response_ms"] == 150.5
    assert long["last_60_response_ms"] == 450.5
