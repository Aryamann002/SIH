import csv
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
import wave

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
        threshold, _ = select_threshold(rows, .4)
        self.assertEqual(threshold, .81)
        with self.assertRaisesRegex(ValueError, "validation rows only"):
            select_threshold([{**rows[0], "split": "test"}], .4)
        self.assertIsNone(metrics([rows[4]])["FRR_genuine_high_risk_blocked"])
        self.assertEqual(source_group("real/yt_0000_p2_part_167.flac"), "yt_0000")
        self.assertEqual(source_group("fake/el_0001_c_part_002.flac"), "el_0001")

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


if __name__ == "__main__":
    unittest.main()
