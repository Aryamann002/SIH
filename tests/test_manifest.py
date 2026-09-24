import csv
from hashlib import sha256
from pathlib import Path
import tempfile
import wave

import pytest

from scripts.validate_manifest import FIELDS, validate
from scripts.evaluate_audio import read_manifest, select_phase


def test_manifest_rejects_lineage_duplicates_and_heldout_leakage():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        rows = []
        for index, (split, label) in enumerate((
            ("train", "genuine"), ("train", "spoof"),
            ("validation", "genuine"), ("validation", "spoof"),
            ("test", "genuine"), ("test", "spoof"),
        )):
            audio = root / f"{index}.wav"
            with wave.open(str(audio), "wb") as output:
                output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                output.writeframes(bytes([index + 1, 0]) * 100)
            rows.append(dict.fromkeys(FIELDS, "") | {
                "clip_id": str(index), "file_path": audio.name,
                "sha256": sha256(audio.read_bytes()).hexdigest(), "label": label,
                "language": "hi", "speaker_id": f"speaker-{index}",
                "source_dataset": "fixture", "source_recording_id": f"original-{index}",
                "transcript_id": f"prompt-{index}",
                "generator_family": "none" if label == "genuine" else ("family-b" if split == "test" else "family-a"),
                "generator_model": "none" if label == "genuine" else "model-1",
                "attack_type": "none" if label == "genuine" else "tts",
                "genuine_or_synthetic": "genuine" if label == "genuine" else "synthetic",
                "duration": str(100 / 16000), "sample_rate": "16000", "codec": "PCM_16",
                "channel": "microphone", "replay_status": "original",
                "consent_or_license": "fixture-only", "split": split,
                "source_speaker_id": f"source-{index}", "target_speaker_id": f"target-{index}",
            })
        manifest = root / "manifest.csv"

        def write():
            with manifest.open("w", newline="", encoding="utf-8") as output:
                writer = csv.DictWriter(output, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)

        write()
        assert validate(manifest, "family-b")["heldout_test_clips"] == 1
        evaluation_rows = read_manifest(manifest, "family-b")
        assert len(evaluation_rows) == 4
        with pytest.raises(ValueError, match="requires --phase"):
            select_phase(evaluation_rows, None, None)
        validation, rich = select_phase(evaluation_rows, "validation", None)
        assert rich and {row["split"] for row in validation} == {"validation"} and len(validation) == 2
        with pytest.raises(ValueError, match="omit --frozen-high-threshold"):
            select_phase(evaluation_rows, "validation", 0.75)
        with pytest.raises(ValueError, match="requires --frozen-high-threshold"):
            select_phase(evaluation_rows, "final-test", None)
        test, rich = select_phase(evaluation_rows, "final-test", 0.75)
        assert rich and {row["split"] for row in test} == {"test"} and len(test) == 2
        rows[4]["source_recording_id"] = rows[0]["source_recording_id"]
        write()
        with pytest.raises(ValueError, match="source_recording_id leakage"):
            validate(manifest, "family-b")
        rows[4]["source_recording_id"] = "original-4"
        rows[4]["file_path"], rows[4]["sha256"] = rows[0]["file_path"], rows[0]["sha256"]
        write()
        with pytest.raises(ValueError, match="Duplicate audio SHA256"):
            validate(manifest, "family-b")
        rows[4]["file_path"] = "4.wav"
        rows[4]["sha256"] = sha256((root / "4.wav").read_bytes()).hexdigest()
        rows[3]["generator_family"] = "family-b"
        write()
        with pytest.raises(ValueError, match="Held-out generator"):
            validate(manifest, "family-b")
        rows[3]["generator_family"] = "family-a"
        rows[4]["augmentation_parent"] = "0"
        write()
        with pytest.raises(ValueError, match="Augmentation parent"):
            validate(manifest, "family-b")
