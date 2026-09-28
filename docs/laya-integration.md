# Local Laya decision support

Laya replaces the hosted Jev call for new actions. It is optional decision support, not the speech detector or an authorization service. The backend sends only named risk, quality, freshness, duration, channel and version buckets. The deterministic hard gate runs first and is rechecked after the call; HIGH, stale/missing evidence and service failures cannot become approval. Every eligible transfer still requires action-bound verification. Historical `JEV_DECISION` audit rows remain; new rows use `LAYA_DECISION`.

`LAYA_MODE=shadow` is the default, but `LAYA_ENABLED=false` skips the service immediately. An enabled backend checks `http://laya:8000/health` for the pinned English checkpoint, then calls `/v1/systemone` on its private Compose network. The optional `laya` profile has no published port. Shadow records one of four non-approval choices without changing the action. `advisory` is gated by `LAYA_ADVISORY_ENABLED=true` and is **not approved** for the presentation. The local request has a 1.5-second bound and no retry; timeout, invalid response, wrong checkpoint and outage fall back to the deterministic result.

The sidecar uses [Laya 0.3.21 code at `9d95567`](https://github.com/NandhaKishorM/laya/tree/9d955671415fc19f069b9cc998928075c1f255ec) and the [Apache-2.0 English checkpoint at `55cf4c4`](https://huggingface.co/convaiinnovations/laya/tree/55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851). English is selected because the request contains English metadata buckets, not speech or transcripts. The weight file is about 843 MB. Laya's own [limitations](https://github.com/NandhaKishorM/laya/blob/9d955671415fc19f069b9cc998928075c1f255ec/README.md) report weak zero-shot typed-decision results; VigilVoice-specific accuracy and calibration are unmeasured.

Build the pinned upstream CPU image in a fresh directory **outside** VigilVoice, then start the opt-in sidecar. Its first start needs Internet to cache public weights; the upstream [CPU Docker guide](https://github.com/NandhaKishorM/laya/blob/9d955671415fc19f069b9cc998928075c1f255ec/docs/docker.md) asks for 8 GB RAM and 10 GB free disk.

```powershell
$layaSource = 'C:\path\to\fresh-laya-source'  # Replace with a new absolute path.
git clone https://github.com/NandhaKishorM/laya.git $layaSource
git -C $layaSource checkout --detach 9d955671415fc19f069b9cc998928075c1f255ec
docker build -t vigilvoice-laya:local $layaSource
docker compose --profile laya up -d --wait laya
$env:LAYA_ENABLED = 'true'
docker compose up -d --no-deps --force-recreate backend
```

Check `/readyz`, then create a fresh LOW/ELEVATED action. Its `LAYA_DECISION` audit row should have a four-choice `choice` and a null `fallback_reason`; shadow must leave the deterministic action result unchanged. Keep recipient, OTP, raw audio and credentials out of Laya input and logs. To disable calls, set `LAYA_ENABLED=false` and recreate only the backend. For an offline Laya rehearsal, first cache weights, set `LAYA_HF_OFFLINE=1`, restart/check the sidecar and disconnect Internet. The main demo works offline without the sidecar.

`python -m pytest -q tests/test_laya.py` and `python -m scripts.evaluate_laya` check transport/policy fixtures, **not** model quality. The [local integration receipt](validation/l01-laya-2026-09-28.md) records image/weight hashes, cached offline load, action/browser checks and sampled latency/resources. Labeled shadow evaluation and final-source packaging remain open before advisory can be considered.
