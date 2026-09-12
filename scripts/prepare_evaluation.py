"""Prepare 40 pinned English clips for an exploratory, source-group-separated check."""
import argparse
import csv
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from urllib.request import urlopen

REPO = "garystafford/deepfake-audio-detection"
REVISION = "fcf5344bb7f82b54b6b932291326d29750ef1e82"
BASE = f"https://huggingface.co/datasets/{REPO}"
LIMIT = 100 * 1024 * 1024


def source_group(path):
    match = re.fullmatch(r"(?:real|fake)/([a-z]+_\d+)(?:_c|_p2)?_part_\d+\.flac", path)
    if not match:
        raise ValueError(f"Unknown source naming convention: {path}")
    return match[1]


def select(items, label):
    groups = {}
    for item in items:
        group = source_group(item["path"])
        if group in {"yt_0000", "el_0001"}:  # Exclude the two existing demo source recordings.
            continue
        groups.setdefault(group, []).append(item)
    units = sorted(groups) if label == "genuine" else sorted({g.split("_")[0] for g in groups})
    selected = []
    for index, split in enumerate(("validation", "test")):
        allowed = units[index::2]
        ordered_groups = sorted(groups.items(), key=lambda pair: (int(pair[0].split("_")[1]), pair[0]))
        queues = [sorted(files, key=lambda x: x["path"]) for group, files in ordered_groups
                  if (group if label == "genuine" else group.split("_")[0]) in allowed]
        count = 0
        while count < 10:
            progressed = False
            for queue in queues:
                if queue and count < 10:
                    selected.append((split, label, queue.pop(0)))
                    count += 1
                    progressed = True
            if not progressed:
                raise ValueError("Not enough independent source clips")
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("models/evaluation"))
    args = parser.parse_args()
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    downloaded = 0

    def fetch(url):
        nonlocal downloaded
        with urlopen(url, timeout=60) as response:
            data = response.read(LIMIT - downloaded + 1)
        downloaded += len(data)
        if downloaded > LIMIT:
            raise ValueError("100 MiB download budget exceeded")
        return data

    items = []
    for directory, label in (("real", "genuine"), ("fake", "spoof")):
        listing = fetch(f"https://huggingface.co/api/datasets/{REPO}/tree/{REVISION}/{directory}?limit=1000")
        (root / f"{directory}-tree.json").write_bytes(listing)
        items.extend(select(json.loads(listing), label))
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly

    rows = []
    for split, label, item in items:
        source = item["path"]
        url = f"{BASE}/resolve/{REVISION}/{source}"
        original = root / Path(source).name
        expected = item["lfs"]["oid"]
        if not original.exists() or sha256(original.read_bytes()).hexdigest() != expected:
            data = fetch(url)
            if sha256(data).hexdigest() != expected:
                raise ValueError(f"Source checksum mismatch: {source}")
            original.write_bytes(data)
        audio, rate = sf.read(original)
        if audio.ndim == 2:
            audio = audio.mean(axis=1)
        if not np.isfinite(audio).all() or not 0 < len(audio) <= rate * 30:
            raise ValueError(f"Invalid source duration/values: {source}")
        divisor = math.gcd(rate, 16000)
        audio = resample_poly(audio, 16000 // divisor, rate // divisor)
        destination = original.with_suffix(".wav")
        sf.write(destination, (np.clip(audio, -1, 32767 / 32768) * 32768).astype("<i2"), 16000, subtype="PCM_16")
        rows.append(dict(path=destination.name, label=label, split=split, group=source_group(source),
                         sha256=sha256(destination.read_bytes()).hexdigest(), source_sha256=expected, source=url))
        print(f"Prepared {split} {label}: {destination.name}", flush=True)
    with (root / "manifest.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (root / "DATASET-CARD.md").write_bytes(fetch(f"{BASE}/raw/{REVISION}/README.md"))
    (root / "provenance.json").write_text(json.dumps({
        "dataset": REPO, "revision": REVISION, "license": "CC-BY-4.0",
        "attribution": "Gary Stafford, Deepfake Audio Detection Dataset v4",
        "modifications": "Mono 16 kHz PCM16 WAV conversion; complete clips, no cropping",
        "selection": "Deterministic round-robin; 10 per class per split; source groups disjoint; synthetic provider prefixes disjoint; demo source recordings excluded",
        "downloaded_bytes_this_run": downloaded,
        "limitations": "English only; source filename groups do not establish independent speakers or text; overlap with pretrained model training data is unverified",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Manifest: {root / 'manifest.csv'}; downloaded {downloaded:,} bytes")


if __name__ == "__main__":
    main()
