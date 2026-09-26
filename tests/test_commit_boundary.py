from unittest.mock import patch

import pytest

from scripts import check_commit_boundary as probe


def test_commit_probe_refuses_presentation_database():
    assert all(db != "vigilvoice_db" for db, _, _ in probe.TARGETS.values())
    with patch.object(probe, "docker", side_effect=["true false", "true",
                                                    f"127.0.0.1:{probe.PORT}", "vigilvoice_db"]):
        with pytest.raises(RuntimeError, match="isolated test database"):
            probe.ready()
