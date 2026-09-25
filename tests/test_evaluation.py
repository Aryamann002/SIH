import csv
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

import pytest

from scripts import evaluate_audio
from scripts.evaluate_audio import metrics, read_manifest, select_threshold
from scripts.prepare_evaluation import source_group


class EvaluationTests(unittest.TestCase):
    def test_metrics_denominators_and_frozen_selection(self):
        rows = [dict(label=label, split="validation", risk_state=state, maximum_chunk_score=score)
                for label, state, score in [("genuine", "LOW", .1), ("genuine", "HIGH", .8),
                                             ("spoof", "LOW", .2), ("spoof", "HIGH", .9),
                                             ("genuine", "POOR_QUALITY", None),
                                             ("spoof", "SERVICE_UNAVAILABLE", None)]]
        result = metrics(rows)
        self.assertEqual(result["scorable"], 4)
        self.assertEqual(result["FAR_spoof_eligible_for_otp"], .5)
        self.assertEqual(result["FRR_genuine_high_risk_blocked"], .5)
        self.assertEqual(result["quality_rejections"], {"genuine": 1})
        self.assertEqual(result["service_unavailable"], {"spoof": 1})
        self.assertEqual(result["ROC_AUC"], .75)
        self.assertEqual(result["EER"], .5)
        self.assertEqual(result["HIGH_recall_scorable_spoof"], .5)
        self.assertEqual(result["HIGH_precision"], .5)
        self.assertEqual(result["HIGH_F1"], .5)
        self.assertEqual(result["no_alert_synthetic_attacks"], 2)
        threshold, _ = select_threshold(rows, .4)
        self.assertEqual(threshold, .81)
        with self.assertRaisesRegex(ValueError, "validation rows only"):
            select_threshold([{**rows[0], "split": "test"}], .4)
        self.assertIsNone(metrics([rows[4]])["FRR_genuine_high_risk_blocked"])
        self.assertEqual(source_group("real/yt_0000_p2_part_167.flac"), "yt_0000")
        self.assertEqual(source_group("fake/el_0001_c_part_002.flac"), "el_0001")

    def test_rich_threshold_respects_frozen_false_block_limit(self):
        rows = [dict(label="genuine", split="validation", risk_state="LOW", maximum_chunk_score=score)
                for score in (.1, .2, .3, .79)]
        rows += [dict(label="spoof", split="validation", risk_state="LOW", maximum_chunk_score=score)
                 for score in (.5, .6, .7, .9)]
        threshold, result = select_threshold(rows, .4, max_fpr=.10)
        self.assertGreater(threshold, .79)
        self.assertEqual(result["HIGH_false_positive_rate_scorable_genuine"], 0)
        self.assertEqual(result["HIGH_recall_scorable_spoof"], .25)
        rows[3]["maximum_chunk_score"] = 1.0
        with self.assertRaisesRegex(ValueError, "false-block limit"):
            select_threshold(rows, .4, max_fpr=.10)

    def test_manifest_detects_source_and_content_leakage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for i, (split, label) in enumerate((('validation', 'genuine'), ('validation', 'spoof'),
                                                ('test', 'genuine'), ('test', 'spoof'))):
                audio = root / f"{i}.wav"
                with wave.open(str(audio), "wb") as output:
                    output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                    output.writeframes(bytes([i, 0]) * 100)
                rows.append(dict(path=audio.name, label=label, split=split, group=f"group{i}",
                                 sha256=sha256(audio.read_bytes()).hexdigest()))
            manifest = root / "manifest.csv"

            def write():
                with manifest.open("w", newline="") as output:
                    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)

            write()
            self.assertEqual(len(read_manifest(manifest)), 4)
            rows[2]["group"] = rows[0]["group"]
            write()
            with self.assertRaisesRegex(ValueError, "group leakage"):
                read_manifest(manifest)
            rows[2]["group"] = "group2"
            rows[2]["path"], rows[2]["sha256"] = rows[0]["path"], rows[0]["sha256"]
            write()
            with self.assertRaisesRegex(ValueError, "Duplicate audio"):
                read_manifest(manifest)
            rows[2]["path"], rows[2]["sha256"] = "2.wav", "0" * 64
            write()
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                read_manifest(manifest)


def test_rich_evaluator_scores_only_requested_phase(monkeypatch, tmp_path):
    from app.services import audio_evidence
    from app.services.audio_pipeline import AudioPipeline

    manifest = tmp_path / "manifest.csv"
    manifest.write_text("fixture", encoding="utf-8")
    rows = []
    for number, (split, label) in enumerate((("validation", "genuine"), ("validation", "spoof"),
                                              ("test", "genuine"), ("test", "spoof")), 1):
        audio = tmp_path / f"{number}.wav"
        audio.write_bytes(bytes([number]))
        rows.append({"file_path": audio.name, "path": audio.name, "absolute_path": str(audio),
                     "split": split, "label": label, "language": "hi"})
    seen = []

    def fake_process(self, data):
        spoof = data[0] % 2 == 0
        return {"risk_state": "HIGH" if spoof else "LOW", "spoof_score": .9 if spoof else .1,
                "reason_codes": [], "threshold_profile": "fixture"}

    def fake_evaluate(data):
        seen.append(data[0])
        return AudioPipeline.process_chunk(None, data)

    monkeypatch.setattr(evaluate_audio, "read_manifest", lambda *_: rows)
    monkeypatch.setattr(AudioPipeline, "status", staticmethod(lambda: {"available": True}))
    monkeypatch.setattr(AudioPipeline, "process_chunk", fake_process)
    monkeypatch.setattr(audio_evidence, "evaluate_wav", fake_evaluate)
    for phase, expected in (("validation", [1, 2]), ("final-test", [3, 4])):
        seen.clear()
        output = tmp_path / phase
        command = ["evaluate_audio.py", str(manifest), "--phase", phase, "--output", str(output)]
        if phase == "final-test":
            command += ["--frozen-high-threshold", "0.75"]
        monkeypatch.setattr(sys, "argv", command)
        evaluate_audio.main()
        report = json.loads((output / "report.json").read_text(encoding="utf-8"))
        results = json.loads((output / "results.json").read_text(encoding="utf-8"))
        assert seen == expected and {row["split"] for row in results} == {"test" if phase == "final-test" else "validation"}
        assert report["phase"] == phase
        assert report["default_test" if phase == "validation" else "default_validation"] is None
        assert report["candidate"]["test" if phase == "validation" else "validation"] is None
        assert report["validation_slices" if phase == "validation" else "test_slices"]["language"]["hi"]["total"] == 2
        assert report["test_slices" if phase == "validation" else "validation_slices"] == {}
        assert report["candidate_validation_slices" if phase == "validation" else "candidate_test_slices"]["language"]["hi"]["total"] == 2
        assert report["candidate_test_slices" if phase == "validation" else "candidate_validation_slices"] == {}
    seen.clear()
    monkeypatch.setattr(sys, "argv", ["evaluate_audio.py", str(manifest), "--phase", "final-test",
                                    "--frozen-high-threshold", "nan"])
    with pytest.raises(SystemExit):
        evaluate_audio.main()
    assert not seen

    monkeypatch.setattr(evaluate_audio, "read_manifest", lambda *_: [
        {key: value for key, value in row.items() if key != "file_path"} for row in rows])
    output = tmp_path / "legacy"
    monkeypatch.setattr(sys, "argv", ["evaluate_audio.py", str(manifest), "--output", str(output)])
    evaluate_audio.main()
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert seen == [1, 2, 3, 4] and report["phase"] == "legacy_exploratory"
    assert report["default_validation"] is not None and report["default_test"] is not None


if __name__ == "__main__":
    unittest.main()
