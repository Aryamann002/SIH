# VigilVoice final development plan and progress

Last updated: **2026-09-23 (Asia/Calcutta)**. Planning baseline: `396f36c9d4f3e48fba4ebaa3aad7a670daf28af4`, with pre-existing local configuration/runtime changes.

Presentation target: **2026-10-03**, derived from the user's instruction on September 13: "in 20 days". Day 0 is September 13; Days 1-20 are September 14-October 3. Confirm the exact presentation time during rehearsal scheduling.

User requirement: a presentation-ready system with a fully working backend and a model that detects synthetic/cloned speech. Pretrained models, fine-tuning, or training are all acceptable; team-owned training is not a requirement. Save context and always record progress. This session authorizes planning and persistence; implementation, publication and spending must follow the user's subsequent instructions and existing repository authority rules.

## Resume here

- **Current stage:** B01-B05, D01 and S01 are complete; S02 stream freshness/backlog controls are next while D02 remains access/consent dependent.
- **Next task:** execute S02 on the existing 200 ms browser/WebSocket path: bound queued audio, add server-owned receipt/freshness checks and preserve HIGH evidence during pending actions.
- **Known release blocker:** packaging still needs pinned dependencies and a safe Docker context in R01. The current host Python 3.13 environment now passes the local suite, but Python 3.11 Docker remains the verified release runtime.
- **Critical path:** B01 -> B02/B03 -> S01/S02 -> M02/M03 -> V01/V02 -> R01/R02 -> R03/R04. Dataset work D01/D02 starts alongside backend work because model selection depends on it.
- **Next checkpoint:** end of Day 2, September 15: reproducible backend baseline and fixed evaluation protocol.
- **Final acceptance:** NOT VERIFIED. B02-B05 and S01 prove clean startup, executable models, readiness, protected-action recovery, bounded single-session admission and authenticated continuous browser streaming; stream freshness/backlog, representative evaluation, broader failure checks and physical rehearsals remain open.

## What "fully working for presentation" means

The final build must capture real microphone audio continuously, run actual local model inference, show timely risk and reasons, and enforce the complete protected-action workflow in the backend. It must also support recorded WAV input, persist actions/audit, and recover safely from failure or restart. A direct API call must never bypass the controls displayed in the UI.

The demonstration uses a **simulated INR transfer and local verifier delivery**, as explicitly allowed by Context.pdf and the existing handbook. The model, API, database, verification checks and audit must execute for real. The local verifier illustrates a separate role; it is not a real independent authentication channel. Real banking/SMS integration, production hosting, telecom adapters and multi-tenant accounts are outside this 20-day presentation scope.

Retain one detector in the inference path, Silero VAD, FastAPI, PostgreSQL, ONNX Runtime and native browser code. Reuse existing services, routes and test scripts. Do not add an ensemble, Redis, Kubernetes, WebRTC, speaker verification, watermarking or a new frontend framework for this milestone. Optimize or replace the detector only when measurements justify it.

Preserve the existing strict policy: LOW/ELEVATED can request independent verification; HIGH, unusable/missing/stale evidence and service failure prevent completion. Every simulated transfer requires valid, fresh, action-bound, single-use approval. A lower risk score never authenticates a person.

## PDF requirements and current implementation

All page references below are physical PDF pages, starting at 1. The four PDFs were read during planning; original proposal claims are requirements, not proof of implementation.

| Source | Relevant requirements | Development consequence |
|---|---|---|
| [Context.pdf](../Context.pdf), pp. 1-7, 16-28, 37-43 | Prevention first; Web Audio/AudioWorklet -> authenticated PCM/WebSocket; quality, one detector, action-bound OTP and audit; four language groups; duration/channel/replay/unseen-generator evaluation; six demo cases; offline fallback | Governs the final demo pipeline, test matrix and proof package. Its original 36-hour schedule is superseded by this user's 20-day deadline. |
| [SIH idea deck](<../SIH2026-IDEA-Presentation-Format final 2.pdf>), pp. 1-6 | SIH26104, team Power Rangers; continuous analysis; 2s evidence with 0.5-4s study; calibration; 6-digit/60s/single-use OTP; detection at fixed FPR, first-alert latency and false alerts per genuine call | Implement and measure continuous operation. Revise the final slides to name the actual selected model and measured results. Existing claims of Indian-language/channel validation are not yet supported. |
| [Teacher presentation](teacher-presentation.pdf), pp. 3-7 | Existing pretrained Wav2Vec2 integration, record-then-analyze microphone, simulated workflow, 40-clip exploratory evaluation and explicit pending work | Use as the honest baseline; replace historical results with final evidence rather than declaring proposal features already complete. |
| [Build and launch handbook](VigilVoice-Build-and-Launch-Guide.pdf), pp. 2-10 | Existing architecture, Docker startup, separate operator/verifier screens, expiry rules, checks, recovery and local fallback | Extend these working paths and refresh the handbook after the final build is verified. |

Decisions resolving differences between PDFs:

- The user permits any effective model, so a newly trained frozen WavLM head is optional. The current pretrained Wav2Vec2 classifier is the baseline candidate.
- Continuous browser streaming remains required; record-then-upload is the fallback, not completion of the streaming requirement.
- Keep existing `/api/v1` contracts unless a measured requirement needs an additive change. For example, the current stream route is `/api/v1/stream/ws/{session_id}`; do not rename it just to match the illustrative PDF path.
- Existing PostgreSQL tables and version digests may implement the PDF concepts without creating a separate table or worker process for every illustrated box.
- Threshold selection is required. Probability calibration is conditional on having suitable data and an explicit probability claim; otherwise expose model scores and thresholded risk, as Context.pdf p. 10 allows.

## Verified baseline and gaps

| Area | Evidence as of September 13 | Final work remaining |
|---|---|---|
| Local Python checks | B03: **20 passed, 1 skipped**, 22 validation subtests; Python 3.11 focused readiness: **8 passed** | Final-source regression and later-stage failure/stress evidence remain required. |
| UI logic checks | S01: VM contract checks plus headless Chrome AudioWorklet fake-device stream and WAV fallback passed | Physical microphone and full browser-to-action workflow remain unverified today. |
| Protected actions | B04: ownership, payload/action binding, expiry, OTP lockout, atomic replay/race behavior, audit rollback and hard-restart denial/recovery passed | Revalidate on final source and during later active-stream failure/capacity work. |
| Audio | Local Silero + INT8 Wav2Vec2; native 16 kHz AudioWorklet sends authenticated 200 ms PCM16 frames; headless Chrome reached LOW at 1.5s while capture continued | Backlog/freshness and long-run physical-device capacity remain unverified. |
| Models and evaluation | Historical 40 English clips; default test missed 1/9 scorable spoof and falsely blocked 1/9 scorable genuine; candidate 0.58 falsely blocked 3/9 genuine | Representative language/channel evaluation and defensible threshold choice. Candidate threshold is not deployed. |
| Timing | Historical offline median 3.06s, p95 7.79s per file; model load 7.07s | Capture-to-alert, API overhead, warm startup and limited concurrency on the presentation laptop. |
| Packaging and readiness | B01 source repair plus B02 clean build; B03 liveness/readiness verifies DB, full runtime schema, executable models and verifier | Dependency pinning, `.dockerignore`, offline package and final immutable source/model receipts remain. |
| Presentation assets | Existing slides, handbook, screenshot and 30-second silent video | Refresh for streaming and final metrics; existing video omits the synthetic HIGH/BLOCKED checkpoint. |

Historical evidence: [teacher build receipt](teacher-build-receipt.json), [API checks](demo-checks.json), [browser checks](browser-checks.json), [evaluation report](evaluation-report.md), [model setup](model-setup.md). Existing Ruflo task rows are stale; a prior receipt says its CLI could not mark them complete. The task ledger below is authoritative for this milestone.

## Twenty-day schedule

These are execution windows, not claims of work completed. A missed gate is recorded as blocked or incomplete; it is not silently waived to meet the date.

| Window | Dates | Deliverable and checkpoint |
|---|---|---|
| Days 1-2 | Sep 14-15 | Reproducible source/backend baseline; select target laptop/regional language; freeze dataset protocol and numerical targets before tuning. |
| Days 3-5 | Sep 16-18 | Reliable readiness, validated configuration, protected-action failure handling and restart recovery. Acquire/label data in parallel. |
| Days 6-8 | Sep 19-21 | Continuous microphone-to-backend PCM streaming, fresh risk display, bounded backlog and failure handling. Finish evaluation corpus. |
| Days 9-11 | Sep 22-24 | Benchmark baseline on development/validation data; compare one replacement or train a lightweight head only if needed. Measure duration/channel/quality failures. |
| Days 12-13 | Sep 25-26 | Select model and policy on validation, freeze artifacts and run untouched final test. Stop model experimentation by end of Day 13. |
| Days 14-16 | Sep 27-29 | Full browser/API prevention tests, overload/restart/failure injection, physical microphone and latency/capacity checks; fix defects. |
| Day 17 | Sep 30 | Freeze final source/image/model/profile; generate final evidence, deck, guide and backup video from that exact build. |
| Days 18-20 | Oct 1-3 | Three full rehearsals, offline recovery practice and presentation. Reserve for defects and delivery, not new features. |

## Task ledger - update this table after material progress

Statuses: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `DEFERRED`. `DONE` requires its completion check plus linked evidence. Owner labels are roles, not claims that a worker is currently running. Initially only PLAN is done.

| ID | Window / owner | Status | Work and completion check | Evidence / next action |
|---|---|---|---|---|
| PLAN | Day 0 / integration | DONE | Read PDFs/source, save agreed 20-day scope, task ledger and session instructions | This document; AGENTS.md and CLAUDE.md entry points; Day 0 log below |
| B01 | Days 1-2 / integration | DONE | Correct the broad model ignore rule without exposing weights; ensure `app/models/schemas.py` and all required imports are included in the reviewable source; verify an isolated clean source export builds and imports the app | Root `/models/` remains ignored; `app/models/schemas.py` is addable; clean export tests 12 passed/1 skipped; image `sha256:1a7e7e98a2ff3f8f18dca0f26023c8cdd2292b2d10e9b63df400b8ab48236ef7` imported `app.main` on Python 3.11 |
| B02 | Days 1-2 / backend | DONE | Reproduce local Docker startup, additive migration twice, model checksum checks and existing unit/API checks; save environment and exact-source baseline evidence | [B02 receipt](validation/b02-baseline-2026-09-13.md): rebuilt stack, four idempotent migration runs, pinned checksums, real-model smoke, unit/UI and two 13-group API runs passed; existing DB volume preserved |
| D01 | Days 1-2 / evaluation | DONE | Choose regional language from accessible permitted data, inventory sources/consent and freeze split, metrics, latency and false-block targets before tuning | [Frozen protocol](evaluation-protocol.md): Marathi selected; sources/access/consent inventoried; source grouping, untouched test, manifest fields and numerical targets frozen before tuning |
| B03 | Days 3-4 / backend | DONE | Add readiness for DB/schema, both models and demo verifier; bounded model warmup; validate finite/ordered thresholds, durations, positive TTLs and consistent OTP limits | [B03 receipt](validation/b03-readiness-2026-09-13.md): full schema/executable-model/verifier readiness, fail-closed dependency cases and startup validation passed; final review found no blocker |
| B04 | Days 3-5 / backend | DONE | Verify action state machine, ownership, payload binding, approval replay/races, audit rollback and post-restart denial/recovery | [B04 receipt](validation/b04-actions-2026-09-13.md): 14 API groups, injected audit rollback, 5 hard-restart groups, focused unit/UI checks passed; zero unauthorized completions |
| B05 | Days 4-5 / backend | DONE | Define single-worker capacity and verifier restart behavior; bound upload/auth/inference waits and concurrent sessions; correct expired-challenge and unavailable UI recovery | [B05 receipt](validation/b05-capacity-verifier-2026-09-13.md): one active audio session, sessions 2/3 rejected promptly, bounded DB/upload/inference waits, explicit lost-delivery expiry/new-action recovery, 15 live and 5 hard-restart groups passed |
| D02 | Days 2-8 / evaluation | TODO | Assemble four-language source-disjoint corpus with real/synthetic labels, quality/channel annotations, license/consent and hashes; keep demo/training/test separate | Target 320 independent source clips as below; incomplete slices remain visible |
| S01 | Days 6-7 / browser + backend | DONE | Add native AudioWorklet capture/resampling and authenticated WebSocket client; await ready then stream mono 16kHz PCM16 at a measured cadence; retain recording/WAV fallback | [S01 receipt](validation/s01-browser-streaming-2026-09-13.md): Chrome produced eight live updates while capture continued, LOW at 1.5s, WAV fallback passed; live API and repaired client passed |
| S02 | Days 7-8 / backend | TODO | Bound capture/transport/inference backlog; use server-owned receipt/freshness information; stale/duplicate/out-of-order/gapped input cannot refresh old evidence as new speech | Test delayed frames, saturation, source replacement and genuine-to-synthetic-to-genuine transition; HIGH during a pending action must not be silently erased before completion |
| S03 | Days 7-8 / browser | TODO | Display live risk, evidence age, reasons and action status; handle stop, permission denial, disconnect and reconnect; release devices on navigation | Reconnect starts new evidence; startup badge checks full readiness; expiry offers the correct new-action path |
| M01 | Days 9-10 / evaluation | TODO | Extend existing evaluator for language, duration, channel, replay, held-out generator and partial-manipulation slices; log raw/scorable/rejected counts | Shared runtime preprocessing/policy; measured real replay subset; explicit no-alert outcomes |
| M02 | Days 9-11 / model | TODO | Measure existing detector; if validation misses agreed targets, compare one suitable local candidate or train a lightweight frozen-encoder head using separate training data | Select by validation detection/false-block/latency/availability, not training ownership; no test-set selection |
| M03 | Days 12-13 / model + evaluation | TODO | Select thresholds on validation; freeze model, preprocessing, cadence, quality gates, smoothing and policy; evaluate untouched test once | Hashes, per-slice metrics and confidence intervals; probability calibration only if supported and explicitly tested |
| M04 | Days 11-13 / audio | TODO | Validate noisy/all-speech SNR behavior, clipping, narrowband/phone audio and short evidence; fix demonstrated quality failures and retest before freeze | Keep calibration knobs; channel reason codes only where backed by actual metadata/measurement; no invented safe scores |
| V01 | Days 14-15 / tester | TODO | Exercise complete genuine approval and synthetic blocking in actual browser/API/PostgreSQL flows, including active-stream risk replacement during verification | Extend check_demo.py/check_browser.py; automation must assert completion/denial and audit, not merely receive a score |
| V02 | Days 14-16 / tester | TODO | Prove expiry/3-attempt lockout, reused/wrong-action tokens, foreign sessions, concurrent completion, malformed/oversized audio, stream loss, model/DB/audit failure and restart safety | Every prohibited completion denied; legitimate completion occurs exactly once; failure injection only in isolated test stack |
| V03 | Days 14-16 / performance | TODO | Measure cold/warm start, WAV latency, live first-alert and evidence age, 1/2/3-session stress and long-run stability on presentation hardware | Document supported capacity; one active stream minimum; excess work fails promptly/safely without impairing action checks |
| V04 | Days 15-16 / reviewer | TODO | Check session/verifier separation, bounded unauthenticated endpoints, SQL/input/output safety, no raw-audio or plaintext-token logs, retained-data behavior and dependency issues | Focused evidence plus regression; no generic scanner result substitutes for authorization tests |
| R01 | Day 17 / integration | TODO | Package exact tested dependencies/images/models, safe Docker context and offline startup; verify new clone/source export plus preserved-db restart | Add .dockerignore; keep secrets/weights out of source; model/image manifests and downloadable-artifact provenance |
| R02 | Day 17 / presentation | TODO | Refresh SIH deck/handbook, six-case script, Q&A, measured metrics and narrated backup video including HIGH/BLOCKED | Visual review of every final PDF page; align all model/stream/language claims with evidence |
| R03 | Days 18-19 / presenter + tester | TODO | Run at least three timed full rehearsals with real laptop microphone, separate verifier role, projector and internet disconnected | Record outcomes, hardware, timings and fallback recovery; any change reopens affected verification |
| R04 | Day 20 / integration + presenter | TODO | Check final readiness, checksum-selected artifacts, local clips, verifier access and backup media; close or disclose every release blocker | Final acceptance checklist and handoff; no automatic external deployment/publication |

## Backend implementation notes

Start with `app/api/v1/{sessions,stream,actions}.py`, `app/services/{action_gate,audio_evidence,audio_pipeline,demo_verifier,audit}.py`, `app/core/{config,database}.py` and the existing migration. Preserve row-locking, generation fencing and transaction-bound audit rather than rewriting the backend.

Specific inspected gaps to address:

1. `app/models/schemas.py` is required but ignored/untracked. Fix reproducibility before adding features. The application stack is Python/FastAPI; generated Ruflo TypeScript/npm quick-start instructions are not the application build commands.
2. `/healthz` returns static OK. `/api/v1/system` checks model state but not DB readiness, and the UI currently considers only the spoof detector. Readiness must reflect the complete serving path, without blocking each probe behind expensive inference.
3. The stream accepts a first JSON token frame, then binary PCM, and returns `ready`. Its current check opens and closes a socket without sending speech; `scripts/test_client.py` creates an unregistered UUID and sends PCM before auth. Repair these contracts together.
4. One CPU inference thread currently serves uploads and streams. Keep session VAD state isolated and serialize each session's calls. Separate capture cadence from expensive inference cadence if profiling requires it, and preserve every required quality/freshness check. Do not increase evidence TTL to hide slow processing.
5. Processing time is not capture time. Stream backlog, pauses and replayed buffered frames need bounded age/gap rules so old audio cannot be written as fresh safe evidence. Client-provided timing alone is not authoritative. Verify that HIGH observed during a pending action cannot disappear behind later genuine speech before completion; retain the relevant action-level block/evidence, with explicit new-action recovery.
6. Verification challenges/audit persist; the local delivery inbox does not. Use one backend worker for this scope, demonstrate safe restart/new-action recovery and do not introduce plaintext OTP persistence merely to survive restart. Completed actions and audit must survive restart.
7. Validate configuration at startup and bound network waits/input sizes. Preserve constant-time secret comparisons, hashed tokens, maximum three OTP attempts and existing generation/ownership checks.
8. Replace misleading reason labels such as `VERIFIED_LOW_RISK` and `HIGH_SPOOF_PROBABILITY` with evidence-based language, updating all callers/tests. The default UI must never equate LOW with verified identity.

## Detection, data and measurement protocol

Use the existing evaluator and manifest validation in `scripts/evaluate_audio.py` and `scripts/prepare_evaluation.py`. Add only the metadata and reporting needed for this matrix; a new experiment platform or evaluation database is unnecessary.

- **Languages:** Hindi, Indian English, Hinglish and one regional language chosen in D01. Initial acquisition target: at least 40 genuine and 40 synthetic independent source recordings per language (320 total), split 20+20 per class into validation and test. Training, if needed, uses additional separate data. Count speakers and generator families, not just files. This is a presentation-scale target, not a population accuracy guarantee.
- **Provenance:** permitted public sources or consented recordings; record source, license/consent, language, speaker/source group, generator, duration, channel and hashes. Dataset names in the PDFs are candidates to verify for access/license; they have not all been downloaded or approved for this project.
- **Independence:** keep speakers, source recordings, related transcripts/augmentations and derivative clips together. Reserve generator families from any team-controlled fitting/selection; distinguish this from unknown overlap with a pretrained model's original training data. Never use final test clips to select the demo, threshold or candidate.
- **Conditions:** clean; real phone recording or clearly labeled simulated narrowband/codec transformation; noise; low-volume/accented genuine speech; speaker-to-microphone replay; held-out generator; genuine -> inserted synthetic -> genuine. Include at least 10 genuine and 10 synthetic source recordings in each supplemental stress condition where available; report unmet coverage instead of inflating counts with duplicates. Augmentations remain linked to their original sources.
- **Duration:** evaluate 0.5, 1, 2 and 4 seconds without repeating audio to manufacture speech. With the current 1.5s minimum speech gate, short clips should report insufficient evidence. If diagnostic detector-only results are produced, label them separately; do not weaken the deployed minimum merely to fill a duration table.
- **Detection target, proposed for D01 freeze:** at least 90% HIGH detection among scorable synthetic test clips at no more than 10% HIGH false blocks among scorable genuine clips. Choose the threshold at the predeclared FPR on validation, then report actual test FPR/recall with numerators and 95% confidence intervals. Report each language and stress condition separately. A weak slice stays a failed target; aggregate performance cannot erase it.
- **Coverage target:** at least 85% scorable coverage for both genuine and synthetic supported-quality baseline clips, and zero unexplained model/service failures at supported load. Count quality rejection, insufficient evidence and unavailability separately for each class. Blocking everything is not detection success.
- **Latency targets, proposed for D01 freeze:** p95 first HIGH alert within 4 seconds of synthetic onset among detected, scorable 2-second-evidence attack trials. Report every no-alert/miss separately, and target at least 85% alerted within 4 seconds using ALL scorable attack trials as the denominator. Also target p95 warmed end-to-end analysis <=10 seconds for a 10-second WAV and no growing stream backlog over a 10-minute call. Report cold-start time separately and warm the demo before presentation. If hardware cannot meet these targets, optimize measured work or select a faster detector before model freeze.
- **Capacity:** the release must support one live operator stream while verifier/action/audit endpoints remain responsive. Test 2 and 3 streams to establish limits; explicitly reject excess load if it cannot be supported. Do not advertise unmeasured multi-user scale.
- **Metrics:** HIGH recall at fixed FPR, spoof still eligible for verification, false HIGH blocks, false alerts per genuine call, scorable coverage, quality/unavailable counts, inference time, capture-to-first-alert median/p95, and sensitive-action success/denial. Keep detector misses distinct from unauthorized action completion.
- **Selection:** tune on development/validation, freeze by Day 13, then run final test. If final test fails, record the failure; further tuning requires a new untouched holdout and new evidence. Do not repeatedly tune against the same test set or silently lower acceptance targets.

If the baseline fails validation by Day 10, spend Days 10-11 on one evidence-backed candidate change or lightweight-head training. No full encoder training or multi-model expansion is planned. Any paid compute, external voice upload or restricted data acquisition needs the authority actually required for that action; availability is not assumed.

## Final acceptance and evidence

The following are release checks, not additional task statuses. Keep task status solely in the ledger.

1. Reproducible source export builds; all runtime imports are included; migration is additive/idempotent; required models are pinned and locally available; fresh readiness passes before the audience demo.
2. Genuine/eligible speech -> exact action -> separate verifier -> valid code -> single completion -> persistent audit works through the actual browser and API. HIGH or unsafe evidence cannot complete even with an earlier valid approval.
3. Every negative authorization/failure case in V02 denies completion; database/audit failure rolls back the action; backend restart preserves completion history and never revives expired approval.
4. Live speech produces continuously refreshed evidence with bounded lag. Disconnection, stale input, permission loss and source replacement invalidate it. Actual capture-to-alert and supported capacity are measured.
5. A frozen detector and policy meet the predeclared targets on the supported presentation conditions, with per-language/condition results, denominators, confidence intervals and limitations. Unmet targets remain explicit blockers to claiming those capabilities complete.
6. Three full physical-device rehearsals pass. Demonstrate six PDF cases: genuine approved flow, synthetic block, degraded synthetic audio, difficult genuine audio, held-out generator and system failure. Every displayed outcome is actual measured behavior; a missed detection is disclosed, not replaced with a fabricated score.
7. The final deck, handbook, video and metric panel reference the same source/model/profile. Raw private recordings, credentials and plaintext OTPs are excluded from logs/source/evidence.

Reuse these commands when executing B02 and final validation; check the relevant environment first:

```powershell
python -m pytest -q
node tests/ui_smoke.cjs
node tests/microphone_smoke.cjs
# Explicitly enable local-model smoke; use an environment with ONNX dependencies and verified models.
$env:RUN_MODEL_SMOKE = '1'
python -m unittest discover -s tests -p test_audio.py -v
Remove-Item Env:RUN_MODEL_SMOKE
```

The API/browser scripts in [the demo guide](teacher-demo-guide.md) create simulated sessions/actions. Run them against an isolated test database/stack with validated ports for failure/restart work. Never reset the existing demo database or delete its volume. Update `scripts/check_demo.py` and `scripts/check_browser.py` to cover streaming/full-action checks rather than creating parallel harnesses.

During implementation save evidence under `docs/validation/` and final evaluation under `docs/evaluation-output/` (currently ignored; use a deliberate sharing/export decision for reports). Each final receipt must name the command, timestamp, environment/hardware, result, exact source snapshot, dependency/image versions, model/profile and dataset hashes. A dirty tree requires a snapshot including necessary tracked AND untracked files; HEAD alone is insufficient. Record artifact locations and hashes, not secrets or private audio. No placeholder pass results.

## Future-session and progress rules

1. At every new session, read this file, the latest session log and `git status --short` before planning or editing. Resume the first unfinished dependency-ready task unless the user steers elsewhere. Do not recreate a separate plan or assume stale Ruflo rows describe current progress.
2. On starting a task, mark its row `IN_PROGRESS`, name the actual worker/session and exact scope, and update "Resume here". One writer per worktree; any other writing agent needs an isolated worktree and path ownership. Read-only reviews may share the checkout.
3. After each material change/test, update that row with progress and evidence. Partial implementation remains `IN_PROGRESS`; document remaining checks. Record failures as faithfully as passes.
4. Before every handoff/end of a development session, append a dated log entry with task IDs, changes, commands/results, source state, blockers and the next exact action. Update this document even if the only progress was discovering a blocker. Never mark a task done merely because code exists or a historical receipt passed.
5. A blocker entry states the concrete missing dependency/data/decision, attempted alternatives, impact and next action. Do independent ready work while blocked. `DEFERRED` requires a stated scope decision; never quietly defer a required presentation gate.
6. Reopen affected `DONE` tasks when code/model/data/policy changes invalidate their evidence. Refresh counts only from the table; do not estimate completion percentages from elapsed days.
7. Keep this file below 500 lines. When the log grows, move older entries into a dated file under `docs/progress/` and link it here, retaining current status and the latest handoff. Do not add an automated tracker unless maintaining this single file actually becomes a problem.
8. Ruflo memory may store the plan path, deadline and latest handoff as a secondary index. Git-visible documentation is the source of truth and must work when Ruflo is unavailable. Do not auto-start token-consuming background workers.

Session log template:

```text
YYYY-MM-DD HH:MM Asia/Calcutta | worker/session | task IDs
Status changes:
Changes and source state:
Checks: command -> actual result -> evidence path/hash
Blockers/decisions:
Next exact action:
```

## Session log

### 2026-09-13 | Codex integration | PLAN

- User set the presentation to 20 days away and accepted any model/training approach that produces working detection. Derived target is October 3; model freeze September 26, build freeze September 30.
- Read all 44 pages of Context.pdf, 6 pages of the SIH idea deck, 7 teacher slides and 10 handbook pages by PDF text extraction. No PDF was edited. Two read-only reviewers inspected backend and validation/presentation gaps; integration alone wrote the plan and session entry points.
- Inspected source and discovered the ignored/untracked `app/models/schemas.py` release blocker. Recorded streaming/readiness/restart/data/model gaps without implementing them.
- Fresh checks: `python -m pytest -q -p no:cacheprovider` -> 12 passed, 1 optional model smoke skipped in 0.44s; `node tests/ui_smoke.cjs` -> passed; `node tests/microphone_smoke.cjs` -> passed. These do not establish live API, actual model or physical microphone readiness.
- Ruflo MCP tools were not exposed in this session. Used installed `@claude-flow/cli` 3.38.19 for memory search (no matching plan found), task routing and the documentation policy receipt. Policy outcome: allowed, legacy mode; receipt `sha256:e7dbb66c4b022567902a5b378f2cfd695da47046e273452c3f1d7b0b5a06f3a3`. This records documentation authority, not implementation/release approval.
- Saved a secondary context index at Ruflo `patterns/vigilvoice-final-presentation-plan`. A read-only final plan review checked dates, model flexibility and progress rules; clarified first-alert latency denominators so misses remain visible without accidentally changing the detection target.
- Plan validation: all 10 local Markdown links resolve; 23 unique task IDs, only PLAN marked DONE; document below 500 lines; deadline arithmetic verified; `git diff --check` passed. Application/source/test diffs remain empty. Ruflo context index was retrieved successfully after saving.
- Existing configuration/runtime changes were preserved. No application code, model, threshold, dataset, database, deployment or source-control publication was changed by this planning task.
- Next exact action after implementation is requested: B01, correct the root model-artifact ignore scope and include the required schema module in a reviewable source snapshot; verify clean-source import/startup, then B02 and D01.

### 2026-09-13 12:55 Asia/Calcutta | Codex integration | B01, B02, D01

- Status changes: B01, B02 and D01 moved from pending/in-progress to DONE after their stated checks passed.
- Changes and source state: narrowed the root model ignore rule to `/models/`, exposing required `app/models/schemas.py` without exposing weights; added the B02 receipt and froze the four-language evaluation protocol with Marathi selected. Pre-existing Ruflo state changes were preserved. Baseline commit is `df2e83ee6249bfa0d056e169810152ba3870de43`; the required untracked schema and ignore-file hashes are recorded in the B02 receipt.
- Checks: clean source export -> 12 passed, 1 skipped; clean Python 3.11 image build/import -> passed; Compose rebuild/start -> passed while preserving the existing PostgreSQL container/volume; additive migration -> passed four times across pre/post rebuild; pinned model hashes -> passed; real-model unittest -> 5 passed; UI and microphone smoke -> passed; rebuilt-stack API/action suite -> all 13 groups passed; `git diff --check` -> passed. Evidence: [B02 receipt](validation/b02-baseline-2026-09-13.md), backend image `sha256:6b4e46cb7ff23cd134a9346b505c93614ec914da36e92b3229be21cd3425716a`.
- Blockers/decisions: host Python 3.13.5 with SQLAlchemy 2.0.30 cannot import SQLAlchemy, so Python 3.11 Docker remains the verified runtime. AI4Bharat data/model candidates require gated contact-sharing acceptance; no acceptance or download was performed. Team speakers/consent and a second permitted generator family are still missing for D02. Existing 40 English clips remain regression-only and cannot support final four-language claims.
- Next exact action: start B03 readiness/configuration validation in the existing backend paths while D02 obtains explicit consent and approved dataset/model access; do not tune thresholds before the frozen manifest is assembled.

### 2026-09-13 13:27 Asia/Calcutta | Codex integration + read-only swarm | B03

- Status changes: B03 moved from TODO through IN_PROGRESS to DONE after live success/failure checks and final review passed.
- Changes and source state: added centralized numeric settings validation; complete runtime-schema/database readiness; cached executable VAD/detector startup warmup; aggregate `/readyz` and `/api/v1/system` state; UI readiness and focused tests. The existing PostgreSQL volume and unrelated Ruflo state were preserved. Baseline, patch/test objects and rebuilt image are bound in the [B03 receipt](validation/b03-readiness-2026-09-13.md).
- Checks: 20 passed/1 skipped plus 22 validation subtests; Python 3.11 focused readiness 8 passed; UI/microphone smoke passed; rebuilt Compose stack ready; missing verifier/model/DB and invalid NaN configuration all failed closed; final 13-group live API/action suite passed; read-only re-review found no blocker.
- Blockers/decisions: Ruflo CLI routing failed before execution with npm `Invalid Version`; implementation continued using the Git ledger and a read-only analysis swarm. D02 still needs team consent, accepted gated access and a second permitted generator family. No data was downloaded or threshold tuned.
- Next exact action: B04, extend isolated API checks for database/audit rollback and restart-state denial/recovery, preserving existing demo records; continue consent/access work for D02 independently.

### 2026-09-13 14:02 Asia/Calcutta | Codex integration + Ruflo/read-only swarm | B04

- Status changes: B04 moved from TODO through IN_PROGRESS to DONE after its transaction-failure and hard-restart checks passed.
- Changes and source state: fixed startup handling for interrupted `LIVE`/`PROCESSING_FILE` sessions and extended `scripts/check_demo.py` with audit rollback plus two restart phases. Baseline is `5a5e62b`; the reviewable B04 patch, receipts and Ruflo state are uncommitted. Existing PostgreSQL records/volume were preserved.
- Checks: syntax and diff checks passed; focused Python 3.11 tests 15 passed/1 skipped; live API suite 14/14 passed; hard restart 5/5 passed; UI and microphone smoke passed; final `/readyz` returned 200. Exact hashes and limits are in the [B04 receipt](validation/b04-actions-2026-09-13.md).
- Blockers/decisions: Ruflo v3.35.0 core memory/routing/swarm paths now work; latest-package resolution remains unnecessary because only optional doctor warnings remain. The runtime image omits pytest, so explicit unittest files were run; dependency/test packaging remains R01. D02 access/consent remains open.
- Next exact action: B05, use the restart harness to make lost/expired verifier recovery explicit and bound upload/auth/inference/concurrent-session waits without persisting plaintext verification codes.

### 2026-09-13 22:30 Asia/Calcutta | Codex integration + Ruflo/read-only swarm | B05

- Status changes: B05 moved from TODO through IN_PROGRESS to DONE after focused, live-capacity and hard-restart checks passed.
- Changes and source state: bounded PostgreSQL waits, upload reads, audio admission and inference; fixed WebSocket overload codes and fail-closed source replacement; made lost verifier delivery expire the old challenge/action; corrected operator/verifier recovery text and removed identity/probability-overclaiming reason labels. Baseline is `5a5e62b`; B04/B05 remain an uncommitted reviewable source state bound to image `sha256:a41f612317a99a5a8944ce66ade05ccb1dadfc7db9b68b5c906c5d53c9a59d37`.
- Checks: host pytest 23 passed/1 skipped plus 26 subtests; Python 3.11 focused unittest 11 passed; UI and microphone smoke passed; rebuilt live suite 15/15 passed; hard SIGKILL restart suite 5/5 passed; final readiness returned 200. Evidence: [B05 receipt](validation/b05-capacity-verifier-2026-09-13.md) and linked machine receipts.
- Blockers/decisions: capacity is intentionally one active audio session in one Uvicorn worker; sessions 2/3 fail promptly and were measured only as admission checks, not long-run capacity. The first restart rerun exposed and fixed a harness-only variable shadow, then both full suites passed on the final source. Ruflo stored `patterns/vigilvoice-b05-handoff`; immediate semantic search returned no result, so this Git ledger remains authoritative. D02 still needs consent/access and a second permitted generator family.
- Next exact action: S01, add native continuous browser PCM streaming using the existing WebSocket contract while retaining WAV upload as fallback; then S02 bounds stream freshness/backlog.

### 2026-09-13 23:12 Asia/Calcutta | Codex integration + Ruflo/read-only swarm | S01

- Status changes: S01 moved from TODO through IN_PROGRESS to DONE after contract, live backend and headless Chrome checks passed.
- Changes and source state: added native 16 kHz AudioWorklet capture with 200 ms PCM16 frames; same-origin authenticated WebSocket client waits for `ready`; live results reuse the risk display; stop/failure cleanup preserves WAV fallback. Repaired binary-first backend handling and stale `test_client.py`. Baseline is `b84593e`; S01 is an uncommitted patch bound to image `sha256:f636ae6f920d3c8ac27cd26c1868d3c65fc6247298bff08390ce670c41207aef`.
- Checks: pytest 23 passed/1 skipped plus 26 subtests; microphone and UI smoke passed; live backend suite 15/15 passed; repaired client streamed 24 real-WAV frames; Chrome fake device produced eight updates while capture stayed ready, reached LOW at 1.5s, then passed WAV fallback; final readiness returned 200. Evidence: [S01 receipt](validation/s01-browser-streaming-2026-09-13.md).
- Blockers/decisions: S01 uses browser-native resampling and adds no dependency or reconnect queue. Fake-device browser proof is not physical microphone evidence. Backpressure, server-owned timing, delayed/replayed-frame handling and retained HIGH evidence remain S02; D02 access/consent remains open.
- Next exact action: S02, add the minimum bounded-frame and server-owned freshness protocol to the existing stream, then test stale/gapped input and genuine-to-synthetic-to-genuine action blocking.

### 2026-09-23 19:37 Asia/Calcutta | Codex integration | documentation

- Status changes: none. S02 remains the next development task.
- Changes and source state: added the root README with current setup, workflow, checks and measured limits. S01 is now in commit `b8d7375`; this documentation change is uncommitted. Existing Ruflo policy state was left untouched.
- Checks: README commands, routes and claims checked against application code, Compose, model setup and S01 receipt; `git diff --check` passed before this log update.
- Blockers/decisions: no new development evidence. Streaming freshness, representative evaluation and physical rehearsals remain open.
- Next exact action: implement S02 against the existing 200 ms stream, then test stale/gapped frames and action blocking during changing risk.

### PDF source fingerprints

These bind the plan's source references; refresh them if the PDFs change.

| PDF | SHA256 |
|---|---|
| Context.pdf | `51aba5ac69e1bb29593a9964f5a40942d3beaae76cb74a61154bb81d7b2899e7` |
| SIH2026-IDEA-Presentation-Format final 2.pdf | `2b65f48bdf1344017d78fa085e03c048233def768fcc55cf0f77da0ca1d2944a` |
| docs/teacher-presentation.pdf | `5433d453ffe0038ed3d463a114bdaffd401b2291af4558a74e95b71437599965` |
| docs/VigilVoice-Build-and-Launch-Guide.pdf | `8d8d542f5109d1d568ffdb13345b52df1b7c7f75dcb3182edce3222b25f27399` |
