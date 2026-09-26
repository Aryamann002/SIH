# V02 isolated PostgreSQL-pause checkpoint — 2026-09-25

Status: **partial pass; V02 remains in progress**. This is a simulated local failure check, not a production reliability claim. The presentation stack and its database were not paused or changed.

## Change and exact scope

`app/core/database.py` now terminates only the failed asyncpg connection when SQLAlchemy reports a timeout/cancellation. This avoids waiting for the paused server's cancellation handshake during cleanup. `app/main.py` returns a redacted 503 that tells the operator to check the action's current status before retrying. It no longer asserts that every timed-out transaction remained unapproved.

The first isolated image `vigilvoice-validation:v02-timeout` was `sha256:c632b92a0642e98ab3acf7a7bfd38c49d727af9d5c9f7888501e514c63bcb2ca`. It contained the connection termination change but preceded the final 503 wording. The subsequent exact-source image `vigilvoice-validation:v02-final` was `sha256:7e05b4b9ca2322786c1e9fdbbfd707b1eacaf9503b76f4c2783812deb3a6eb52`; its database, main, evaluator and manifest-validator file hashes matched the local checkout. This is still **not** a frozen release artifact. Models were mounted read-only. The isolated containers were `vv-v02-fixed-backend`, `vv-v02-final-backend` and `vv-s02-db`; only the latter was paused, always within recovery cleanup. It was confirmed `running` and not paused afterward.

## Observations

| Isolated trial | Client result while database remained paused | Database state after recovery |
|---|---|---|
| Prepared PENDING action, request verification | 503 in 2.44 s | PENDING; zero challenge rows, issued events, or completions |
| VERIFIED action, request completion | 503 in 2.44 s | VERIFIED; approval not consumed; zero completion events |
| Readiness/liveness | `/readyz` 503 in 2.24 s; `/healthz` 200 in 0.02 s | Readiness recovered |
| Fresh public-WAV action after recovery | ELEVATED → PENDING → VERIFIED → COMPLETED | Action-bound local verification and audit completed |
| Isolated transaction paused immediately before `commit()` after a test-only BLOCKED update | `TimeoutError` in 2.0 s | The BLOCKED update nevertheless committed after recovery |

The last trial matters: once COMMIT is sent, a client timeout or terminated connection cannot prove rollback. The observed late state was safely **BLOCKED**, but the same network-level ambiguity must be accounted for on other transaction paths. The application must check the persisted action ID after an ambiguous 503 and must not blindly create/reuse verification on that assumption. No test deliberately sent an approval or completion COMMIT at this precise boundary.

The first isolated image passed 22/22 API check groups (`scripts/check_demo.py --output /tmp/v02-timeout-checks.json`) after recovery, including ownership, OTP, concurrent completion, audit rollback, retained HIGH and streaming paths. Local `python -m pytest -q -p no:cacheprovider` passed 34 tests, 1 skipped, 26 subtests; `node tests/ui_smoke.cjs` and `node tests/microphone_smoke.cjs` passed. `git diff --check` exited 0 with line-ending warnings. The first image preceded the 503 wording and evaluation-script edits; the exact-source image below includes them.

The exact-source image then passed `/readyz`, a second isolated PENDING verification pause (503 in **2.15 s**, PENDING with zero issue/completion audit events after recovery), and `scripts/check_demo.py --output /tmp/v02-final-checks.json` (**22/22 groups, no error**). The model and VAD reported available. This checked the final 503 wording in the real HTTP path. No credential, OTP, raw audio or private transaction payload was placed in the receipt.

The isolated [post-COMMIT ambiguity check](../../scripts/check_commit_ambiguity.py) (SHA256 `0bc9dd4975d470e736661cdd6042a2e971a0ab1c88de0e7fd66b8cdc723db92b`) injected a timeout **after** the underlying database commit at each route's commit boundary. All three cases passed against `vv-s02-db`:

- Verification challenge persisted but was not delivered: retry rejected the old action; no completion.
- OTP confirmation persisted but its approval token was not returned: retry was rejected and a guessed token could not complete.
- Completion persisted: status was `COMPLETED`, approval consumed, exactly one completion audit event, retry rejected.

The script refuses to run unless both `VIGILVOICE_ISOLATED_TEST_DB=1` and the configured database hostname is `vv-s02-db`; a host-side invocation exited with that refusal before creating data. It was copied into the isolated container after the image build, leaving application files and the presentation stack unchanged. These injected errors are not a substitute for a real paused-network COMMIT probe. They show why the redacted 503 directs the operator to inspect persisted status rather than assuming rollback.

## September 26 real COMMIT-boundary route probes

The new isolated-only [probe](../../scripts/check_commit_boundary.py) (final SHA256 `f78aca186d1ffb65ec3554ab528d5a01eda046459c7817379e1ef066173e0b8a`) used the existing `vv-v02-final-backend` image `sha256:7e05b4b9ca2322786c1e9fdbbfd707b1eacaf9503b76f4c2783812deb3a6eb52`, whose `app/core/database.py`, `app/api/v1/actions.py` and `app/main.py` hashes still match the September 26 working source. It guards an allowlisted test backend port and confirms its database host is the paired test-only DB; it cannot target the presentation database. For each case, it installs a temporary deferred trigger, verifies via `pg_stat_activity` that the transaction is sleeping inside the actual `COMMIT`, pauses only the paired test DB for three seconds, then unpauses and removes the trigger in cleanup. The triggers apply to challenge insertion, approval insertion and approval-consumption update, respectively. The final script adds only an allowlisted `sep26` candidate target to the version that first passed against `vv-s02-db`.

Command: `python scripts/check_commit_boundary.py` from the repository root after starting only the isolated test database/backend. The final three-case run exited 0. Verification returned HTTP 503 in **3.38 s** despite one committed challenge and matching issue audit; retry expired the undelivered challenge, with zero completions. Confirmation returned HTTP 503 in **3.49 s** despite one committed approval and matching verification audit; retry could not return the lost token, a guessed token could not complete, and completion count stayed zero. Completion returned HTTP 503 in **3.41 s** while the action persisted COMPLETED, with one consumed approval and exactly one completion audit; retry was rejected. Thus a 503 did **not** mean rollback. Afterward the test DB was running/unpaused, temporary trigger count was zero, and `/readyz` was 200. The existing API/action/stream harness then passed **22/22 groups**; local Python passed **36 tests, 1 skipped, 26 subtests**, and both Node smoke suites passed. No OTP, verifier key, approval token, recipient other than the script's synthetic test label, or raw audio was printed or saved in this receipt. The test used only `models/demo/genuine.wav`.

Scope: this tests real transport pauses at the **verification challenge, OTP confirmation and completion COMMIT** boundaries, not an actual payment, a production network, or a frozen release image. The earlier injected post-COMMIT tests and pre-COMMIT pause cover distinct failure shapes. Do not assume every failed HTTP response rolled back.

The same three-case probe was rerun with `VIGILVOICE_COMMIT_TARGET=sep26` against image `sha256:c07e5a0212457bdc3b3677334da99e98bbc365f4de497fc4fa39ccbf5652b6f5` on the separately created `vv-sep26-db` volume. The first attempt stopped at the guard before any trigger because Compose's `db` alias was not the expected explicit hostname; the temporary test-only override was corrected to point to `vv-sep26-db`, then readiness returned 200. The guarded retry exited 0: verification/confirmation/completion COMMIT pauses returned 503 in **3.42 / 3.45 / 3.52 s**, with one committed challenge, one committed but undelivered approval, and one exactly-once committed completion respectively; retry/guessed-token checks denied misuse. The test DB was running/unpaused afterward, trigger count was zero, both test and presentation `/readyz` were 200, and the candidate's full API/action/stream harness passed **22/22 groups**. This is a candidate-image recheck, not a final frozen-source release receipt.

## Remaining V02 gate

All three protected route commits now have real isolated COMMIT-boundary pause results. The frozen-release-image recheck remains. Interpret an ambiguous 503 as “inspect status,” never “definitely rolled back.” Do not change the demo database, disable HIGH retention, or turn this partial receipt into release acceptance.
