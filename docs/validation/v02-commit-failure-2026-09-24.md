# V02 commit-failure checkpoint — 2026-09-24

The isolated `vv-v04-backend` image (`sha256:b2543871eefbf2ff2461fb45c15e6f23339f99aa85dd84e0245813b124eee04f`) used the isolated `vv-s02-db`, not the existing demo database. Runtime application code was unchanged; `scripts/check_demo.py` was copied into this test-only container. HEAD before the new harness change was `6418c1c`; this is a dirty-source test receipt, not a release snapshot.

The added check creates a valid VERIFIED action, then injects `SQLAlchemyError` at the final transaction commit after the completion updates and audit insert have run. Closing that failed SQLAlchemy session rolls back the transaction. A fresh database query found `status=VERIFIED`, `completed_at=NULL`, `approval_tokens.consumed_at=NULL` and zero `ACTION_COMPLETED` events. A subsequent normal completion succeeded once. The existing audit-insert failure, ownership, OTP, HIGH-retention and other API checks also passed.

Reproduction on the isolated test stack:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_readiness.py tests/test_capacity.py
docker cp scripts/check_demo.py vv-v04-backend:/app/scripts/check_demo.py
docker exec vv-v04-backend python scripts/check_demo.py --output /tmp/v02-diagnose.json
```

The final harness run exited normally with [22/22 groups](v02-commit-checks-2026-09-24.json) in 39.808 s; receipt SHA256 `f20ff7eb2ccb54efcbbd13fa45b9d8a0b8be2a89296cf13ea9e957402e23cf4a`. The focused local tests passed 12/12 with 26 subtests; final regression was 31 passed, 1 skipped, 26 subtests, and both Node smoke suites passed. A local readiness test also asserts that a database exception maps to 503 without exposing its detail.

An earlier run wrote a passing 22-check report but its Python process did not exit; that test-only process was terminated after the report was saved. A second run with a timed traceback diagnostic exited 0, so the hang was not reproduced. Its cause is unknown. This injection proves transaction rollback on commit failure, **not** behavior during an actual PostgreSQL/network outage. V02 remains IN_PROGRESS until an authorized, isolated outage/readiness/recovery check is completed. No real database process or volume was stopped or deleted here.
