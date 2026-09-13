# B05 capacity and verifier recovery receipt

Date: 2026-09-13 22:30 Asia/Calcutta

Result: **PASS**. One audio session is admitted per backend process; excess sessions fail promptly while action, audit and verifier APIs remain responsive. Lost or expired local verifier delivery now expires the old action and requires a new action without storing or reissuing a plaintext code.

## Source and runtime

- Baseline commit: `5a5e62b766c2cfe22e7bd20021458a36541bc170`; B04 and B05 remain one uncommitted reviewable source state.
- Final backend image: `sha256:a41f612317a99a5a8944ce66ade05ccb1dadfc7db9b68b5c906c5d53c9a59d37`.
- Runtime: Python 3.11.16, FastAPI 0.141.1, SQLAlchemy 2.0.52, asyncpg 0.31.0 and ONNX Runtime 1.30.0.
- Models/profile: `wav2vec2-xlsr-int8-4b1c4a294ab6` SHA256 `7af799e8443c3d030bb3ef644ffc6e74f5b6fddcd6a4286ee9abe9e828cb762e`; `silero-v5.1` SHA256 `2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4a3cc5bdd788f`; `prototype-uncalibrated-v1`.
- Exact B05 source SHA256: `actions.py` `4d8bfc0e2e27fb5eddae037d7b6fbbadf18d9dfe28610aab01672768e12bc25e`; `sessions.py` `7f299c7ea4458c23c0c69acce0cccb8ebabf7b69c83060eafe0fb59d40b50dd2`; `stream.py` `48e993f37e5a5652becfd1e380883283d77034be3b1dc72e919ee4e8c952e63b`; `config.py` `e373c5a9390056f2babfc68f79d090a1948be561a1d511dc1027d8cb56ab3a22`; `database.py` `4b7191b40ea40ce8ac0d532d2f2742dca2c97d91c2caf073d0873dde226f86be`; `audio_evidence.py` `73c7f35453d77f7527e33c68ce29a88ab3b70c9762668555afcfcc60cae81cfe`; `policy_engine.py` `dd472ff287df4a7b5421db54a7a11c1cb8b3c44115b72afaed715dbdd5b66a28`; `app.js` `b2cce6dc1a03b416b8fbb365e73702a8e8de186b9e1b5d55fe57e54f899b0d77`; `verify.js` `70a66bb18bd738e405664ff5f81421a645ab20232e44e76c0b236357d8d59fec`; `check_demo.py` `98e62c5a239f65a159bc8981bca209b6e4c1dd3bcc2cd2e2cd47c4fa8e357fe1`; `migrate.py` `c70284f906a617c90e3e8cbdead889e743423446fac7a2a5b06ef2e302b6e44e`.
- Exact focused-check SHA256: `test_capacity.py` `6c2b1e7d3dc647e4b66897277575e383ea8a2f3c379ceb1b8eef99437d7483b0`; `test_policy.py` `4c21b39ebb8dc7fea29e0670aad76063f754800504c240feea46fe352973a70a`; `test_readiness.py` `132e40dd99a811e27ce02d6390eb46b01ec542ddb4e4e7da3d25c45147d639d3`; `ui_smoke.cjs` `21d4b0d39760e70212626de526968fc16ba79dd3888960fe2ebe1f6541bf32f5`.

## Bounded behavior

- Database pool, connection and command waits: 2 seconds. Upload body read: 5 seconds. Active audio admission: one session with a 0.1-second wait. Inference queue: 1 second. Running inference: 10 seconds.
- An authenticated replacement attempt invalidates prior evidence before capacity admission. Upload timeout or overload leaves the session disconnected and the action unapproved.
- WebSocket policy/input failures close with 1008, capacity saturation with 1013, and inference timeout/service failure with 1011.
- Existing unexpired challenges are returned only while the matching in-memory local delivery exists. Restart loss marks both challenge and action `EXPIRED`, audits the denial, and returns a 409 requiring a new action.
- UI controls now treat an issued challenge and verified approval as single-use action state. Expiry, restart loss and backend-mutated denial direct the operator to **New transfer**. The verifier key is still cleared after each lookup.
- Removed misleading `VERIFIED_LOW_RISK` and `HIGH_SPOOF_PROBABILITY` reason labels. LOW now means only `NO_STRONG_SYNTHETIC_EVIDENCE`; HIGH reports `HIGH_SPOOF_SCORE`.

## Checks

- `python -m pytest -q -p no:cacheprovider`: 23 passed, 1 optional model smoke skipped, 26 subtests passed; one third-party `python_multipart` pending-deprecation warning.
- `node tests/ui_smoke.cjs` and `node tests/microphone_smoke.cjs`: passed.
- Python 3.11 image focused `unittest`: 11 passed, covering configuration, readiness, upload deadline, one-session admission and one-slot inference contention.
- Rebuilt live stack suite: 15/15 groups passed, including sessions 2 and 3 rejected with WebSocket 1013 while action/audit/verifier endpoints stayed responsive. [Machine receipt](b05-demo-checks-2026-09-13.json), SHA256 `7e2dade3a5ef4b6aa81621bfef61f5237cd5237babcdc3d3d830ef2774de47d8`.
- Hard SIGKILL restart suite: 5/5 groups passed, including delivery-loss expiry, no plaintext-code audit fields, persistent exactly-once completion and fresh-action recovery. [Machine receipt](b05-restart-checks-2026-09-13.json), SHA256 `97e4195ee1c96b26c78f7d7e2409547088a16cbafd604e6fa690e825685f0eee`.
- `python -m compileall -q app tests scripts`, `git diff --check` and final `/readyz`: passed. PostgreSQL volume and existing records were preserved. Temporary tester container was removed; final backend and database remain healthy.

The first restart verification run reached the recovery check but failed in the test harness because a local row variable shadowed the `challenge()` helper. The variable was renamed, the image rebuilt, and both full live and hard-restart suites were rerun from fresh records against the final source above.

## Scope

Capacity is deliberately one active audio session for this local presentation build. Multi-worker delivery, distributed queues, Redis and plaintext OTP persistence were not added. V03 still must measure long-run behavior and presentation-laptop latency; S01/S02 must add and bound continuous browser capture and stream backlog.
