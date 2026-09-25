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

## Remaining V02 gate

If feasible, test a real network pause at the exact verification/completion COMMIT boundary; the injected post-COMMIT cases above do not reproduce transport timing. Recheck on the eventual frozen release image. Interpret an ambiguous 503 as “inspect status,” never “definitely rolled back.” Do not change the demo database, disable HIGH retention, or turn this partial receipt into release acceptance.
