"""Keep the offline source archive complete without admitting local secrets."""

from pathlib import Path
from zipfile import ZipFile

from scripts.package_offline import ROOT, package, source_files


def test_offline_package_is_reproducible_and_keeps_readme_docs(tmp_path):
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    count, digest = package(first)
    assert package(second) == (count, digest)
    with ZipFile(first) as archive:
        names = set(archive.namelist())
        assert count == len(names) == len(source_files())
        assert {"README.md", "docker-compose.yml", "pytest.ini",
                "tests/test_package_offline.py", "tests/ui_smoke.cjs",
                "tests/microphone_smoke.cjs", "tests/jev_scenarios.json",
                "docs/model-setup.md",
                "docs/prototype-runbook.md", "docs/teacher-presentation.pdf",
                "docs/VigilVoice-Build-and-Launch-Guide.pdf"} <= names
        assert all(not name.startswith(("models/", "docs/validation/artifacts/")) for name in names)
        assert all(Path(name).suffix not in {".env", ".key", ".pem", ".wav", ".tar", ".zip"}
                   for name in names)
        assert ".env" not in names


def test_package_root_alias_does_not_break_local_links():
    alias = ROOT / ".." / ROOT.name
    assert source_files(alias) == source_files(ROOT)
