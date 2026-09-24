# M01 rich-manifest phase separation — 2026-09-24

Before this change, `scripts/evaluate_audio.py` read rich-manifest validation and test rows together, scored both, then selected a HIGH threshold using only validation rows. The threshold calculation did not use test scores, but the intended untouched test was nevertheless exposed before selection/freeze. `read_manifest` still validates declared lineage and file integrity across all splits; it does not infer on a clip during that step.

The CLI now requires `--phase validation` or `--phase final-test` for a rich manifest. Validation runs inference only on validation rows and reports no test metrics. Final test runs inference only on test rows, requires `--frozen-high-threshold`, and performs no threshold selection. The value must be finite, at least the configured ELEVATED threshold, and at most 1. The historical five-column English regression CLI retains its existing combined exploratory behavior. Reports identify the phase and include only that phase's score metrics/slices. No deployed model, threshold, audio policy or action gate changed.

```powershell
python scripts/validate_manifest.py <corpus>/manifest.csv --heldout-generator <family>
python scripts/evaluate_audio.py <corpus>/manifest.csv --heldout-generator <family> --phase validation --output docs/evaluation-output/<validation-run>
# After an independently recorded model/policy/threshold freeze:
python scripts/evaluate_audio.py <corpus>/manifest.csv --heldout-generator <family> --phase final-test --frozen-high-threshold <selected-value> --output docs/evaluation-output/<final-test-run>
```

Focused `python -m pytest -q -p no:cacheprovider tests/test_evaluation.py tests/test_manifest.py` passed 4 tests. A mocked evaluator-path test asserted validation saw only its two clips, final test saw only its two clips, final test returned no validation metrics, validation returned no test metrics, and the legacy path still saw both splits. A `nan` frozen threshold was rejected before inference. The final-source Python suite passed 32, skipped 1, with 26 subtests; both Node UI/microphone smoke suites passed. `python scripts/evaluate_audio.py --help` showed both new flags.

This is a test/tooling safety fix, **not** a representative detector evaluation. No approved rich four-language corpus was available and no untouched test was run. The manifest validator still reads test files for checksum/WAV integrity during a validation-phase command; it produces no test model scores. The CLI cannot prove that a caller froze model/preprocessing/policy, prevent someone from making another final-test invocation under a different output path, or detect hidden pretrained/cross-dataset ancestry. A signed external freeze receipt and one controlled final-test execution are still required.

Source state: HEAD `6418c1c` plus a dirty worktree, not an immutable release snapshot. SHA256: `scripts/evaluate_audio.py` `4989b8c65a866a195e6eca69289395aa4b3a90baf607288cc34980a995ca0bee`; `tests/test_evaluation.py` `faf791e8d5389b1b9d17543aee91eb132f5b2228dcb0fafa0867565b008eeb8f`; `tests/test_manifest.py` `eb1a94ad76765b977f7a6409a6a300c2ac181b19c82ff6ed7a36e80d2f309b6d`. No commit, push or private audio.
