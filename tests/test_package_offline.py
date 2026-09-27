"""Keep the offline source archive complete without admitting local secrets."""

from pathlib import Path
from zipfile import ZipFile

from scripts.package_offline import ROOT, ROOT_FILES, package, source_files


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
                "docs/validation/r02-narration-draft-2026-09-27.txt",
                "docs/validation/r02-video-preview-2026-09-27.md",
                "docs/VigilVoice-Build-and-Launch-Guide.pdf"} <= names
        assert all(not name.startswith(("models/", "docs/validation/artifacts/")) for name in names)
        assert all(Path(name).suffix not in {".env", ".key", ".pem", ".wav", ".tar", ".zip"}
                   for name in names)
        assert ".env" not in names


def test_package_root_alias_does_not_break_local_links():
    alias = ROOT / ".." / ROOT.name
    assert source_files(alias) == source_files(ROOT)


def test_preview_named_receipt_is_kept_but_preview_directory_is_not(tmp_path):
    for name in ROOT_FILES:
        (tmp_path / name).touch()
    receipt = tmp_path / "docs" / "validation" / "r02-video-preview-check.md"
    generated = tmp_path / "docs" / "validation" / "render-preview-assets" / "frame.png"
    receipt.parent.mkdir(parents=True)
    generated.parent.mkdir(parents=True)
    receipt.touch()
    generated.touch()

    names = {path.relative_to(tmp_path).as_posix() for path in source_files(tmp_path)}
    assert receipt.relative_to(tmp_path).as_posix() in names
    assert generated.relative_to(tmp_path).as_posix() not in names
