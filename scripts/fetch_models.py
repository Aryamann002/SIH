"""Fetch pinned public ONNX artifacts. No downloads occur inside API requests."""

import argparse
from hashlib import file_digest
import json
import math
from pathlib import Path
import tempfile
from urllib.request import urlopen


SILERO_REV = "84768cefdf5a3852400e9d8237f7315d14b64a08"
SPOOF_REV = "4b1c4a294ab68ab444dac038fec8e8da2cc1982f"
DATA_REV = "fcf5344bb7f82b54b6b932291326d29750ef1e82"
SPOOF_REPO = "pranjal-pravesh/wav2vec2-large-xlsr-deepfake-audio-classification"
DATA_REPO = "garystafford/deepfake-audio-detection"
MODELS = [
    ("silero_vad.onnx", f"https://raw.githubusercontent.com/snakers4/silero-vad/{SILERO_REV}/src/silero_vad/data/silero_vad.onnx",
     "2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4a3cc5bdd788f", "MIT"),
    ("spoof_detector.onnx", f"https://huggingface.co/{SPOOF_REPO}/resolve/{SPOOF_REV}/model_int8.onnx",
     "7af799e8443c3d030bb3ef644ffc6e74f5b6fddcd6a4286ee9abe9e828cb762e", "Apache-2.0"),
]
SAMPLES = [
    ("genuine", "real/yt_0000_part_001.flac", "a986e4cc4a3689533608307f477cdb43979784c58e1711b3db6620b96aa115e5"),
    ("synthetic", "fake/el_0001_part_001.flac", "5e77dd881ff5562462303e92d37840abe164e7bc56b24616d32fada61d8a85fc"),
]


def digest(path):
    with path.open("rb") as source:
        return file_digest(source, "sha256").hexdigest()


def download(url, destination, expected=None):
    if destination.exists() and expected and digest(destination) == expected:
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
            temporary = Path(output.name)
            with urlopen(url, timeout=60) as response:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        if expected and digest(temporary) != expected:
            raise ValueError(f"Checksum mismatch: {destination.name}")
        temporary.replace(destination)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("models"))
    parser.add_argument("--samples", action="store_true", help="Also fetch two English speech examples; requires soundfile and scipy")
    args = parser.parse_args()
    root = args.directory.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = {"models": [], "samples": []}
    for name, url, expected, license_name in MODELS:
        destination = root / name
        download(url, destination, expected)
        manifest["models"].append({"file": name, "source": url, "sha256": expected, "license": license_name})
        print(f"Verified {name}: {destination.stat().st_size:,} bytes", flush=True)
    for name, url in {
        "SILERO-LICENSE.txt": f"https://raw.githubusercontent.com/snakers4/silero-vad/{SILERO_REV}/LICENSE",
        "SPOOF-MODEL-CARD.md": f"https://huggingface.co/{SPOOF_REPO}/raw/{SPOOF_REV}/README.md",
        "APACHE-2.0.txt": "https://www.apache.org/licenses/LICENSE-2.0.txt",
    }.items():
        download(url, root / name)
    if args.samples:
        import numpy as np
        import soundfile as sf
        from scipy.signal import resample_poly

        demo = root / "demo"
        demo.mkdir(exist_ok=True)
        for label, filename, expected in SAMPLES:
            url = f"https://huggingface.co/datasets/{DATA_REPO}/resolve/{DATA_REV}/{filename}"
            original = demo / f"{label}.flac"
            download(url, original, expected)
            audio, sample_rate = sf.read(original)
            if audio.ndim == 2:
                audio = audio.mean(axis=1)
            divisor = math.gcd(sample_rate, 16000)
            audio = resample_poly(audio, 16000 // divisor, sample_rate // divisor)
            pcm = (np.clip(audio, -1, 32767 / 32768) * 32768).astype("<i2")
            destination = demo / f"{label}.wav"
            sf.write(destination, pcm, 16000, subtype="PCM_16")
            manifest["samples"].append({
                "file": f"demo/{label}.wav", "label": label, "source": url,
                "source_sha256": expected, "sha256": digest(destination),
                "license": "CC-BY-4.0", "attribution": "Gary Stafford, Deepfake Audio Detection Dataset v4",
                "changes": "Downmixed to mono and resampled to 16 kHz PCM16 WAV",
            })
        download(f"https://huggingface.co/datasets/{DATA_REPO}/raw/{DATA_REV}/README.md", demo / "DATASET-CARD.md")
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
