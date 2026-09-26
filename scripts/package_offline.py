"""Build a source-and-docs ZIP for an offline VigilVoice handoff.

Docker images and pinned local models are separate artifacts. This command never
packages credentials, recordings, model weights, or previous archives.
"""

import argparse
import hashlib
from pathlib import Path
import re
from urllib.parse import unquote
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {".dockerignore", "Dockerfile", "README.md", "docker-compose.yml", "init.sql", "pytest.ini", "requirements.txt"}
CODE_SUFFIXES = {".css", ".html", ".js", ".py", ".sql", ".txt"}
DOC_SUFFIXES = {".html", ".json", ".md", ".mp4", ".pdf", ".png"}


def source_files(root: Path = ROOT) -> list[Path]:
    root = root.resolve()
    paths = [root / name for name in ROOT_FILES]
    for folder in ("app", "config", "scripts"):
        paths.extend(path for path in (root / folder).rglob("*")
                     if path.is_file() and path.suffix in CODE_SUFFIXES)
    paths.extend(path for path in (root / "tests").rglob("*")
                 if path.is_file() and path.suffix in {".py", ".cjs", ".json"})
    paths.extend(path for path in (root / "docs").rglob("*")
                 if path.is_file() and path.suffix in DOC_SUFFIXES
                 and "artifacts" not in path.relative_to(root / "docs").parts
                 and not any("-preview-" in part for part in path.parts))
    selected = set()
    for path in paths:
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Missing or unsafe package path: {path}")
        selected.add(path.relative_to(root).as_posix())
    for url in re.findall(r"\]\(([^)]+)\)", (root / "README.md").read_text(encoding="utf-8")):
        target = unquote(url.strip("<>").split("#", 1)[0])
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        linked = (root / target).resolve()
        if not linked.is_relative_to(root) or linked.relative_to(root).as_posix() not in selected:
            raise ValueError(f"README link is absent from offline package: {url}")
    return [root / name for name in sorted(selected)]


def package(output: Path, root: Path = ROOT) -> tuple[int, str]:
    root = root.resolve()
    files = source_files(root)
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing archive: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in files:
            entry = ZipInfo(path.relative_to(root).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, path.read_bytes())
    return len(files), hashlib.sha256(output.read_bytes()).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    count, digest = package(args.output)
    print(f"{count} files; SHA256 {digest}; {args.output.resolve()}")
