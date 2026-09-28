# Laya late-timeout fix and validation — 2026-09-28

## Change and safety boundary

Baseline: `d83cc85` plus the changes documented here. The client shields a single HTTP worker from the request deadline. Previously its completion callback released the admission slot but did not retrieve a late exception. A transport error after the deadline therefore reached asyncio's default exception logger as `Future exception was never retrieved`, potentially including private transport details.

`app/services/laya.py` now retrieves the completed Future's exception before releasing the slot. Cancellation is checked first. The slot remains occupied until the actual worker finishes; another request cannot queue unbounded work after a timeout. The caller still receives the existing sanitized `timeout` fallback. No new dependency, retry, mode, deadline, threshold, acoustic model, route or authorization rule was added.

The production deadline remains 1.5 seconds. This fixes exception handling, **not Laya's inference speed**. Shadow recommendations never approve an action; fallback leaves deterministic policy and action-bound verification intact.

## Evidence

| Check | Result |
|---|---|
| New regression before fix | Failed: a late `TimeoutError` reached the loop exception handler with private test detail; the other three Laya tests passed. |
| Focused suite after fix | 4 passed. The regression checks timeout fallback, no choice/approval, busy admission while the worker runs, exception retrieval and successful subsequent-worker recovery. |
| Full checkout | 50 passed, 1 skipped, 26 subtests; final run 5.57 s on host Python 3.13. |
| Python 3.11 candidate image | The same new regression function passed, run against the built module with the test file mounted read-only and a minimal `setattr` adapter. This is a focused check, not a full image pytest run. |
| Node UI/microphone smoke | Both passed. |
| Isolated real-model API suite, Laya unreachable | 22 groups passed, 47.895 s; owned test PostgreSQL only. |
| Isolated real-model API suite, actual local Laya reachable | 22 groups passed, 58.172 s; same candidate image/test database. No un-retrieved-exception warning or traceback in the backend logs. |
| Isolated fake-device browser/action suite, Laya unreachable | 15 checks passed, 13 live updates, zero unauthorized completions. HIGH retention, source replacement, OTP and synthetic WAV blocking exercised. Not physical-microphone proof. |
| Same browser/action suite, actual local Laya reachable | 15 checks passed, 13 live updates, zero unauthorized completions; no traceback or un-retrieved-exception warning in backend logs. |
| Twenty policy fixtures | Zero unsafe downgrades, two escalations, three injected failures/one timeout. Live agreement, review rate and calibration remain null; these are not Laya-generated decisions. |

Candidate and deployed image: `sha256:f27a5b3ec1d698fa74bf1451d9ab1acc3c54180c40ae9a0d1eec9454125f347c`.

Source SHA256:

- `app/services/laya.py`: `6f285d064c9bfe53ed6e08110f2f4951a3cf6bea2ed8883131743b7a7bfa5b62`; candidate image matches checkout.
- `tests/test_laya.py`: `922f7c11967f2fa6dd0a462ddae2585eed06274f849396498e000ecbd45b22b6`.

Only the presentation backend was recreated. PostgreSQL and Laya containers/volumes were preserved. Presentation counts before/after deployment were unchanged: 165 sessions, 465 actions, 5,451 audit records. `/readyz` returned 200; zero stored completed actions had HIGH or SERVICE_UNAVAILABLE risk. These counts are an integrity spot-check, not a proof that every historical action is safe.

The first Compose recreation picked up the default `LAYA_ENABLED=false`, unlike the previous manually enabled runtime. A configuration assertion caught it; the backend was recreated with explicit process-level `LAYA_ENABLED=true`, `LAYA_MODE=shadow`, `LAYA_ADVISORY_ENABLED=false`. No `.env` or key was edited. Future ordinary Compose commands still default to disabled unless that opt-in is explicitly supplied.

Five direct structured-metadata probes on the rebuilt, enabled client produced three bounded timeouts (1,501.96–1,502.58 ms) followed by two circuit-open fallbacks. All remained PENDING, with no late-exception warning on stdout/stderr. These were a separate process, not database-audited actions; their circuit state did not alter the serving process. They establish failure handling, not a representative timeout rate or useful recommendation accuracy. Cached Laya stayed healthy with `HF_HUB_OFFLINE=1`; advisory remains off.

The isolated local-service API/browser run also persisted actual shadow audits: ten `STANDARD_VERIFICATION` replies, two timeouts, ten deterministic-hard-gate skips and three evidence-changed fallbacks in the inspected window. The API harness separately persisted one **injected** advisory BLOCK_RECOMMENDED and one advisory hard-gate skip; those are policy tests, not live advisory enablement or Laya predictions. Serving configuration remained shadow/advisory-off. The real timeout audit rows and zero late-error warnings supplement the deterministic regression; they do not establish calibrated agreement.

## Reproduction

Run from the repository with its existing local models and dependencies. Never print or paste the verifier key.

```powershell
python -m pytest -q -p no:cacheprovider tests/test_laya.py
python -m pytest -q -p no:cacheprovider --tb=short
node tests/ui_smoke.cjs
node tests/microphone_smoke.cjs
python -m scripts.evaluate_laya
docker build -t vigilvoice-validation:laya-timeout-0928 .
docker compose --profile laya config --quiet
git diff --check
```

API/browser checks must target an isolated backend and test database. This run used `vv-laya-timeout-0928-backend`, owned `vv-s02-db`, and loopback port 59117. Models were mounted read-only; verifier/signing secrets were freshly generated in memory. The initial network omitted the Laya service to exercise actual transport fallback; it was subsequently connected to `sih_default` for local-service checks. Do not pause or mutate the presentation database for failure injection.

```powershell
docker exec vv-laya-timeout-0928-backend python scripts/check_demo.py --output /tmp/laya-timeout-api-checks.json
python scripts/check_browser.py --base-url http://127.0.0.1:59117/ --action-flow --output docs/validation/artifacts/laya-timeout-browser-rerun
```

The browser command requires `VIGILVOICE_TEST_VERIFIER_KEY` to be populated privately from the **test** backend, then removed from the shell environment. Existing scripts generate reports/screenshots; no credential or OTP is included in the retained receipt.

## Detector validation and recommendation

The separate [public-data receipt](public-validation-2026-09-28.md) records unchanged 72-clip exploratory results, short-duration/channel failures and a bounded IndicSUPERB metadata audit. Those probes do not supply the source-disjoint four-language corpus. Keep the existing detector for the explicitly uncalibrated simulated demo; defer replacement and final threshold selection until rights/lineage-cleared data exist. Keep Laya shadow-only (or disabled); do not infer advisory approval from policy fixtures or unlabeled transport probes.

Final model validation, labeled Laya shadow evaluation, physical capture timing, timed rehearsals, final media and frozen-source packaging remain open. No commit, push, publication, private-audio upload, secret logging or model change was performed. Ruflo recorded coordination; a read-only reviewer checked public dataset rights/lineage, while the root agent remained the only writer.
