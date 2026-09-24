# VigilVoice: Recent Research Papers and Jev Integration

## Direct recommendation

VigilVoice should be positioned as a **prevention-first, real-time voice trust gate**, not merely another audio classifier. The strongest research foundation for the current build is: (1) self-supervised WavLM/wav2vec2 detection, (2) cross-language and cross-generator evaluation, (3) codec/replay and partial-spoof robustness, (4) explainability, and (5) transaction-bound step-up verification.

Jev can be explored as a **secondary, non-authoritative policy experiment**, but it should not replace the local spoof detector or deterministic backend policy. Jev accepts text/JSON state rather than raw audio, so VigilVoice would first compute audio evidence locally and send only structured fields such as detector score, quality, evidence age, alert history, action risk, and verification state.[^1][^2]

## Project alignment

The supplied plan describes a FastAPI/PostgreSQL system with browser AudioWorklet capture, authenticated WebSocket PCM streaming, Silero VAD, a pretrained wav2vec2-family detector, evidence freshness, deterministic LOW/ELEVATED/HIGH policy, action-bound single-use OTP verification, and audit logging. Its evaluation plan correctly prioritizes fixed-FPR detection, per-language results, unseen generators, replay/channel conditions, partial manipulation, short evidence windows, first-alert latency, scorable coverage, and unauthorized-action prevention.[^3][^4]

This design is more defensible than treating a low spoof score as identity authentication. Research repeatedly finds that audio deepfake systems can look strong on familiar benchmarks but degrade under unseen generators, different languages, real recordings, codecs, and distribution shift.[^5][^6][^7][^8]

## Priority reading list

| Priority | Paper | Year / venue | Why it matters to VigilVoice | Recommended use |
|---|---|---|---|---|
| 1 | [A Survey on Speech Deepfake Detection](https://arxiv.org/abs/2404.13914) | 2024 | Reviews more than 200 papers and covers architectures, datasets, generalization, metrics, partial deepfakes, cross-dataset testing, adversarial attacks, and open-source availability.[^5] | Use as the central literature-review source and terminology map. |
| 2 | [Audio Deepfake Detection: What Has Been Achieved and What Lies Ahead](https://www.mdpi.com/1424-8220/25/7/1989) | 2025, *Sensors* | Recent survey of generation, datasets, frontend/backend approaches, end-to-end models, privacy, explainability, fairness, robustness, and deployment gaps.[^9] | Cite for the related-work section and selection of evaluation dimensions. |
| 3 | [Audio Deepfake Detection with Self-Supervised WavLM and Multi-Fusion Attentive Classifier](https://arxiv.org/abs/2312.08089) | ICASSP 2024 | Combines WavLM with layer- and time-level attentive fusion and reports strong ASVspoof 2021 DF results.[^10] | Most directly relevant model paper for the proposed frozen WavLM/wav2vec2 path. |
| 4 | [Audio Deepfake Detection with Self-Supervised XLS-R and SLS Classifier](https://openreview.net/pdf?id=acJMIXJg2u) | ACM MM 2024 | Reports 1.92% EER on ASVspoof 2021 DF and 7.46% on In-the-Wild, showing both benchmark strength and the harder real-world setting.[^11] | Strong alternative candidate if the current baseline fails validation. |
| 5 | [Does Audio Deepfake Detection Generalize?](https://arxiv.org/abs/2203.16263) | Revised 2026 | Uniformly evaluates prior systems and reports severe performance degradation on real-world found audio; also highlights preprocessing effects.[^8] | Use to justify untouched cross-domain testing and restrained claims. |
| 6 | [Where Are We in Audio Deepfake Detection? A Systematic Analysis over Generative and Detection Models](https://web3.arxiv.org/pdf/2410.04324) | 2024 | Compares detectors across generation families and reports better generalization from large pretrained speech representations.[^12] | Supports testing against multiple TTS/VC families rather than random clip splits. |
| 7 | [ASVspoof 5: Crowdsourced Speech Data, Deepfakes, and Adversarial Attacks at Scale](https://arxiv.org/abs/2408.08739) | ASVspoof 2024 | Introduces diverse crowdsourced speech conditions, new attacks, adversarial attacks, evaluation tracks, and deployment-oriented metrics.[^13] | Use as the primary English robustness benchmark and protocol reference. |
| 8 | [Cross-Domain Audio Deepfake Detection: Dataset and Analysis](https://aclanthology.org/2024.emnlp-main.286.pdf) | EMNLP 2024 | Builds over 300 hours from five zero-shot TTS models and studies attack-augmented training and few-shot target-domain adaptation.[^14] | Useful for unseen-generator and domain-adaptation experiments. |
| 9 | [Faking Fluent: Unveiling the Achilles’ Heel of Multilingual Deepfake Detection](https://openreview.net/forum?id=FyjhHoxjzb) | IJCB 2024 | Tests models across languages and accents and finds limited linguistic generalization.[^6] | Essential justification for Hindi, Indian English, Hinglish, and regional-language slices. |
| 10 | [IndicSynth: A Large-Scale Multilingual Synthetic Speech Dataset for Low-Resource Indian Languages](https://aclanthology.org/2025.acl-long.1070/) | ACL 2025 | Provides about 4,000 hours from 989 target speakers across 12 Indian languages, including Hindi, Marathi, and Punjabi.[^15] | Highest-priority Indian-language dataset paper; verify access, licensing, provenance, and split independence before use. |
| 11 | [Toward Robust Real-World Audio Deepfake Detection: Closing the Explainability Gap](https://arxiv.org/html/2410.07436v1) | 2024 | Tests cross-dataset generalization and studies attention rollout and spectrogram occlusion for transformer explanations.[^7] | Better XAI basis than simply adding generic SHAP/LIME screenshots. |
| 12 | [Enhancing Partially Spoofed Audio Localization with Boundary-Aware Attention](https://www.isca-archive.org/interspeech_2024/zhong24_interspeech.pdf) | Interspeech 2024 | Targets frame-level localization of manipulated regions and reports strong PartialSpoof results.[^16] | Supports a future timeline heatmap or partial-clone alert, after the MVP is stable. |
| 13 | [Partial DeepFake Detection Network Based on Multi-scale HarmoF0 and Wav2Vec Features](https://www.isca-archive.org/interspeech_2024/liu24g_interspeech.pdf) | Interspeech 2024 | Combines harmonic pitch and wav2vec features with boundary-focused loss for partial manipulation localization.[^17] | Relevant to genuine-synthetic-genuine transition testing in the current plan. |
| 14 | [FTDKD: Frequency-Time Domain Knowledge Distillation for Low-Quality Compressed Audio Deepfake Detection](https://doi.org/10.1109/TASLP.2024.3511013) | IEEE/ACM TASLP 2024 | Focuses on low-quality compressed audio and evaluates codec robustness, directly matching telephony/VoIP conditions.[^18] | Use to design codec and narrowband stress tests; consider distillation only if latency requires it. |
| 15 | [Robust Audio Deepfake Detection: Exploring Front-/Back-End Combinations and Data Augmentation Strategies](https://www.isca-archive.org/asvspoof_2024/schafer24_asvspoof.html) | ASVspoof 2024 | Compares AASIST, RawGAT-ST, SSL frontends, and augmentation on the ASVspoof 5 evaluation set.[^19] | Useful evidence for a controlled candidate comparison and augmentation choices. |
| 16 | [Detecting Novel Audio Deepfake Algorithm with Real Emphasis and Fake Dispersion](https://www.isca-archive.org/interspeech_2024/xie24_interspeech.pdf) | Interspeech 2024 | Targets recognition of novel deepfake algorithms using frozen wav2vec2 features and AASIST backend.[^20] | Helpful for held-out-generator experiments and future attack-family attribution. |

## EBSCOhost findings

The most directly relevant recent EBSCOhost result was [*The Evolution of Deepfake Generation and Countermeasures — A Review*](https://openurl.ebsco.com/contentitem/lgd:196187793?sid=ebsco:plink:pplx&id=ebsco:lgd:196187793&utm_source=pplx&link_origin=perplexity.ai&domain_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkb21haW4iOiJ0aGFwYXIuZWRiLCJpc3MiOiJwZXJwbGV4aXR5IiwiaWF0IjoxNzkwMTcyNjA3LCJleHAiOjE3OTA3Nzc0MDd9.FzInflkPM3YuXQTgPQ3hbpwEMBMbGFCQMyKgDPMKKwg). It reviews the move from GAN-based generation toward diffusion systems, covers frequency-domain and XAI countermeasures, and reports a cross-dataset generalization gap on unseen data.[^21]

Two additional EBSCOhost papers are useful for framing rather than model implementation. [*Synthetic Media in the Information Battlespace*](https://openurl.ebsco.com/contentitem/lgd:193194482?sid=ebsco:plink:pplx&id=ebsco:lgd:193194482&utm_source=pplx&link_origin=perplexity.ai&domain_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkb21haW4iOiJ0aGFwYXIuZWR1IiwiaXNzIjoicGVycGxleGl0eSIsImlhdCI6MTc5MDE3MjYwMCwiZXhwIjoxNzkwNzc3NDAwfQ.mKWe1Xn4mrUH5t0RVb-hoxUpJjeC2ngzhTIMQTxAuFQ) argues for scalable, explainable, context-aware evaluation across media, while [*Digital Lyrebirds*](https://openurl.ebsco.com/contentitem/lgd:190748655?sid=ebsco:plink:pplx&id=ebsco:lgd:190748655&utm_source=pplx&link_origin=perplexity.ai&domain_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkb21haW4iOiJ0aGFwYXIuZWR1IiwiaXNzIjoicGVycGxleGl0eSIsImlhdCI6MTc5MDE3MjU1OCwiZXhwIjoxNzkwNzc3MzU4fQ.tERdHDZI9jdyMLCdw-izCHs3yTQeyLvGi27xQFnVwHE) experimentally examines how voice clones influence trust and reports that disclosure did not remove the trust-inducing effect in its experiments.[^22][^23]

EBSCOhost produced fewer technically precise audio-countermeasure papers than IEEE, ACM, ISCA, ACL, and arXiv searches. For the implementation chapter, prioritize the conference and journal papers in the table; use the EBSCOhost items for threat motivation, explainability, and system-level evaluation.

## Repository assessment

### MarkHershey AudioDeepFakeDetection

The repository is a useful educational baseline with LFCC/MFCC/raw features and MLP, recurrent, shallow-CNN, and TSSD options. It uses LJSpeech as genuine audio and WaveFake as synthetic audio, but its README says the test set is used for training validation by default, which is not appropriate evidence for VigilVoice’s final claims.[^24]

Use it for understanding feature/model baselines and reproducible training code—not as the main deployed detector or evaluation protocol. The current VigilVoice plan’s source-disjoint validation/test strategy is substantially stronger.

### Deepfake Audio Detection with XAI

The repository compares VGG16, MobileNet, ResNet, and custom CNNs on spectrograms and proposes LIME, Grad-CAM, and SHAP explanations using the Fake-or-Real dataset. Its public README does not provide a clear numeric performance table, robustness evaluation, cross-language test, or explanation-faithfulness study; therefore, treat it as an XAI interface reference rather than research evidence.[^4]

For VigilVoice, use spectrogram attribution only as a **supporting visualization**. Prefer occlusion or attention-based analysis tied to the actual wav2vec2/WavLM detector, test whether highlighted regions remain stable under small perturbations, and never translate a saliency map into an unsupported human-readable claim such as “robotic pitch detected.”[^7]

## Jev decision

Jev is TypeSafe AI’s hosted, text-only System One model. It receives a state and typed questions through `POST /v1/systemone`, then returns structured `Choice`, `Score`, or Boolean-like `Noul` answers with probabilities; it does not accept audio, images, or video.[^2][^25][^1]

That makes Jev unsuitable as the acoustic deepfake detector. It could, however, evaluate **structured evidence after local inference**, for example:

```json
{
  "state": {
    "detector_score": 0.82,
    "quality": "SUPPORTED",
    "evidence_age_ms": 420,
    "speech_seconds": 2.4,
    "codec": "opus",
    "recent_high_seen": true,
    "action": "TRANSFER_INR",
    "amount_band": "HIGH",
    "verification": "PENDING",
    "model_version": "frozen-v1"
  },
  "questions": {
    "route": {
      "type": "Choice",
      "options": ["ALLOW_VERIFICATION", "REQUIRE_REVIEW", "BLOCK"]
    },
    "evidence_unsafe": {
      "type": "Noul"
    }
  }
}
```

### Safe integration pattern

1. **Keep deterministic rules authoritative.** Existing rules—HIGH evidence, stale/missing evidence, detector failure, invalid OTP, or unbound approval—must block regardless of Jev output.
2. **Run Jev in shadow mode first.** Log its suggested route beside the deterministic decision without affecting an action.
3. **Send metadata, not raw voice.** Jev is text-only, and keeping raw speech local preserves the project’s privacy-by-default architecture.[^1]
4. **Fail closed or ignore safely.** Timeout, 401, 429, 529, malformed output, or network loss must never turn unsafe evidence into approval; the API documentation explicitly lists authentication, rate-limit, and overload failures.[^2]
5. **Evaluate Jev independently.** Build a labeled scenario set covering genuine, synthetic, stale, low quality, replay, partial manipulation, detector unavailable, and conflicting evidence; report decision accuracy, unsafe-allow count, latency, calibration, and disagreement with deterministic policy.
6. **Do not add it to the final critical path unless it earns value.** The current plan intentionally avoids Internet dependencies and requires offline operation. A hosted Jev call would violate that property if made mandatory.[^3][^1]

### Best role

The best near-term role is **shadow policy critic or explanation tagger**, not final gatekeeper. For example, Jev can classify an already-produced structured event into `INSUFFICIENT_EVIDENCE`, `SUSPICIOUS_AUDIO`, `STALE_STREAM`, `SYSTEM_UNAVAILABLE`, or `VERIFICATION_REQUIRED`, while the actual allow/block decision remains in ordinary tested code.

## Research contribution

A realistic paper-worthy contribution is:

> **A prevention-first, multilingual, real-time voice-clone risk gate that evaluates acoustic evidence under language, channel, replay, partial-manipulation, and unseen-generator shifts, then binds fresh risk evidence to a protected action and independent step-up approval.**

This is stronger than claiming a novel classifier. Existing work concentrates heavily on file-level EER/accuracy, while the VigilVoice plan also measures first-alert latency, stale-evidence behavior, false alerts per genuine call, action completion/denial, restart safety, and fail-closed operation.[^26][^5][^3]

Suggested research questions:

- **RQ1:** How does a frozen wav2vec2/WavLM detector generalize across Hindi, Indian English, Hinglish, and Marathi/Punjabi under source-disjoint and generator-disjoint testing?
- **RQ2:** How do codec, replay, background noise, clipping, and evidence duration affect recall at a fixed false-positive rate and first-alert latency?
- **RQ3:** Does action-level retention of HIGH evidence prevent unsafe completion during genuine–synthetic–genuine transitions better than window-only smoothing?
- **RQ4:** Do attribution methods identify stable spoof-relevant time-frequency regions under cross-domain shifts?
- **RQ5:** Can a Jev shadow decision layer improve review routing or reason-code quality without increasing unsafe allows, latency, privacy exposure, or Internet dependence?

## Evaluation protocol

| Dimension | Minimum experiment | Report |
|---|---|---|
| Languages | Hindi, Indian English, Hinglish, one regional language | Per-language denominators, recall, false-positive rate, coverage |
| Generators | Known plus held-out TTS/VC family | Generator-wise metrics and unknown-generator gap |
| Channels | Clean, Opus/telephone codec, microphone replay, noise, clipping | Per-condition recall/FPR and quality rejection |
| Duration | 0.5, 1, 2, 4 seconds without repeating audio | Scorable coverage and first-alert latency |
| Partial spoof | Genuine–synthetic–genuine clips | Utterance detection plus transition/localization behavior |
| Calibration | Threshold fixed on validation only | Reliability plot/Brier score if probabilities are claimed; otherwise label outputs as scores |
| Prevention | Genuine approval, synthetic block, stale evidence, stream loss, OTP expiry/replay, restart | Unauthorized completions, legitimate completions, audit consistency |
| Jev shadow | Labeled structured scenarios and network failures | Unsafe allows, agreement, abstention/review rate, p50/p95 latency, failure behavior |

Accuracy alone is insufficient. ASVspoof work commonly reports EER and cost-based measures, while the project should additionally report the operating-point metrics that map to the protected action: recall at the chosen false-positive rate, false HIGH blocks, scorable coverage, no-alert attacks, and unauthorized completion count.[^19][^13]

## What to implement now

1. Finish stream freshness/backlog handling and retained HIGH evidence before adding another model or service.[^3]
2. Freeze a source-disjoint multilingual manifest using permitted genuine recordings plus IndicSynth or other license-verified synthetic sources.[^15][^3]
3. Benchmark the existing wav2vec2 detector, then compare only one justified candidate: WavLM-MFA or XLS-R-SLS.[^11][^10]
4. Add codec/replay/noise and held-out-generator slices before model tuning.[^6][^18][^19]
5. Implement an explanation prototype tied to the selected detector using spectrogram occlusion or attention rollout; do not adopt the XAI repository’s interface claims without validation.[^4][^7]
6. Add Jev only behind a feature flag in shadow mode after obtaining API access, with a short timeout, no raw audio, full audit metadata, and deterministic fallback.[^1][^2]
7. Keep the SIH demo offline-capable; if Internet is disconnected, the primary detector, policy, OTP workflow, and audit must behave identically.[^3]

## Paper title options

- **VigilVoice: A Prevention-First Real-Time Trust Gate for Multilingual Voice-Cloning Attacks**
- **Beyond Detection: Binding Streaming Audio-Deepfake Evidence to Protected Financial Actions**
- **Evaluating Multilingual Audio-Deepfake Detection Under Channel, Replay, and Unseen-Generator Shift**
- **From Spoof Scores to Safe Actions: An Auditable Voice-Cloning Prevention Framework**

## Important claim limits

Do not claim “Indian-language validated,” “real-time,” “explainable,” “unseen-generator robust,” or “prevents fraud” until the corresponding frozen test and end-to-end action evidence passes. IndicSynth improves available Indian-language synthetic coverage, but one dataset cannot establish population-level robustness across accents, devices, ages, languages, or emerging generators.[^15][^6]

Likewise, Jev probabilities should not be presented as proof that an action is safe. The `awesome-jev` repository explicitly warns that listing is not endorsement and that listed projects may be unverified; Jev itself is currently a hosted text decision service rather than an audio-forensics model.[^27][^1]

---

## References

1. [Models - TypeSafe AI](https://docs.typesafe.ai/models)

2. [API reference - TypeSafe AI](https://docs.typesafe.ai/api)

3. [SIH2026-IDEA-Presentation-Format-final-2.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/115130557/b335af03-3b3f-4109-81c7-74d238bb5047/SIH2026-IDEA-Presentation-Format-final-2.pdf?AWSAccessKeyId=ASIA2F3EMEYEYMY4YDNM&Signature=C1JNdCOx6qjuzlErU%2BZ2XaY71KY%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEPf%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJHMEUCIQCCYeBSjd%2FgQcxYMo5LUkWqNTN9F%2B4gC5dBOBnk4f7igQIgMrpz5Nvay%2Fq3bd6siGdIVduyAjs4TMDKvut5Yl7ahY0q%2FAQIwP%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FARABGgw2OTk3NTMzMDk3MDUiDFkWQnjhw%2BueoU5ocirQBDqC9kMYZfg%2BLC%2BtaeibZw76zCtXZXYG5jo5Q9BHyGHG7LzfoXSuTkzUJyoXOl%2B0LGTQzBs0bV9yxXJgDC8Ert6St34YcmQ7bXnyaeC2gv0aUYg6YKcWLhpS1LJDT9MlGVp53kg0MDDZferreIHRyp6c6aQXZPxJTfn99U6gt4DQizeuheCdUdffvWUBSk9IlEtBJWc5A54J5LCXjV3Gf1httmpsmVtilsQLJsjULz%2FaLIvXR%2FYqj21vfQnsiZrYpE3fIya7qA8jtVlEZD8ZbIjWX20i8C8uE2tPBWzKIwhYXMRNodLDEiMdNWQVy%2B8bOrzcieobWtdJff6ddBb30pBBFOGDJ4zNlweTrX91kZXQTkJtPQSOryuWTb2tPE0VP85RT71C6Q%2FCBh9MloIk6cHF1Uc0kNg%2BG3HL3S2wgj3qFxgvRkt4oj2hJiv6y%2Blej%2Foz6G3jfziHc%2Bsx7J3ciC9Yz%2B37gX1ER9zpJR9vVCyLU36abZKf%2BfJrv3kLM39lEDhqFvTz%2F8oLfJqTJTIJP6bZIFCvu2Xgu3XjhsB4fPLcEM7%2BQ6zb0MGumpaY1RlLeGlqX5oWMzk4iSGu2XSRPpVRwJY7TW2ZZUbsCZxXpUyTgdYeR7oJy9AQtTqa0haIsH294AE3v1QJR56Jbb8GtYztFveDMwU86HfSjCZ9E3QpBUcpjE4bivBSOiGsbAEiQndVmYmqXcf%2BCJ1KnG5DPNwxlVF3i6DbR2dKuX4XHnpF4nWSnlPNXCZBCel5KHxvogvV9ZKKUenwr3M4ClhwOqQw683P1QY6mAENc1DkSwQKIZtdCw6IwC2iTSGBbdAce2Yt04SpKyCxGw8iXJj%2FnYwYy%2Fm%2BO46B611KIb6Cx%2BT7g5ET124uNncXGkvcTBZSAd9sBLui0YUvUHo%2BtygbX%2BCYF9l%2F5jtAVa8MkzN4jN98TCrNhJFZFKIsHzkWJgxHhJaLW%2BdBbPpn2hkXJu0DI7IJqwV0Zw0gzN5YGjGwvUY9aQ%3D%3D&Expires=1790178494) - page-1 TITLE PAGESMART INDIA HACKATHON 2026Problem Statement ID -SIH26104Problem Statement Title - A...

4. [final-development-plan-2.md](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/115130557/8fb04689-cee3-4d15-8f08-277db832a8c1/final-development-plan-2.md?AWSAccessKeyId=ASIA2F3EMEYEYMY4YDNM&Signature=nNZE2VO9gH7PoSQrKNiaqIjSnQw%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEPf%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJHMEUCIQCCYeBSjd%2FgQcxYMo5LUkWqNTN9F%2B4gC5dBOBnk4f7igQIgMrpz5Nvay%2Fq3bd6siGdIVduyAjs4TMDKvut5Yl7ahY0q%2FAQIwP%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FARABGgw2OTk3NTMzMDk3MDUiDFkWQnjhw%2BueoU5ocirQBDqC9kMYZfg%2BLC%2BtaeibZw76zCtXZXYG5jo5Q9BHyGHG7LzfoXSuTkzUJyoXOl%2B0LGTQzBs0bV9yxXJgDC8Ert6St34YcmQ7bXnyaeC2gv0aUYg6YKcWLhpS1LJDT9MlGVp53kg0MDDZferreIHRyp6c6aQXZPxJTfn99U6gt4DQizeuheCdUdffvWUBSk9IlEtBJWc5A54J5LCXjV3Gf1httmpsmVtilsQLJsjULz%2FaLIvXR%2FYqj21vfQnsiZrYpE3fIya7qA8jtVlEZD8ZbIjWX20i8C8uE2tPBWzKIwhYXMRNodLDEiMdNWQVy%2B8bOrzcieobWtdJff6ddBb30pBBFOGDJ4zNlweTrX91kZXQTkJtPQSOryuWTb2tPE0VP85RT71C6Q%2FCBh9MloIk6cHF1Uc0kNg%2BG3HL3S2wgj3qFxgvRkt4oj2hJiv6y%2Blej%2Foz6G3jfziHc%2Bsx7J3ciC9Yz%2B37gX1ER9zpJR9vVCyLU36abZKf%2BfJrv3kLM39lEDhqFvTz%2F8oLfJqTJTIJP6bZIFCvu2Xgu3XjhsB4fPLcEM7%2BQ6zb0MGumpaY1RlLeGlqX5oWMzk4iSGu2XSRPpVRwJY7TW2ZZUbsCZxXpUyTgdYeR7oJy9AQtTqa0haIsH294AE3v1QJR56Jbb8GtYztFveDMwU86HfSjCZ9E3QpBUcpjE4bivBSOiGsbAEiQndVmYmqXcf%2BCJ1KnG5DPNwxlVF3i6DbR2dKuX4XHnpF4nWSnlPNXCZBCel5KHxvogvV9ZKKUenwr3M4ClhwOqQw683P1QY6mAENc1DkSwQKIZtdCw6IwC2iTSGBbdAce2Yt04SpKyCxGw8iXJj%2FnYwYy%2Fm%2BO46B611KIb6Cx%2BT7g5ET124uNncXGkvcTBZSAd9sBLui0YUvUHo%2BtygbX%2BCYF9l%2F5jtAVa8MkzN4jN98TCrNhJFZFKIsHzkWJgxHhJaLW%2BdBbPpn2hkXJu0DI7IJqwV0Zw0gzN5YGjGwvUY9aQ%3D%3D&Expires=1790178494) - Last updated 2026-09-13 AsiaCalcutta. Planning baseline 396f36c9d4f3e48fba4ebaa3aad7a670daf28af4, wi...

5. [A Survey on Speech Deepfake Detection](https://arxiv.org/abs/2404.13914) - The availability of smart devices leads to an exponential increase in multimedia content. However, a...

6. [Faking Fluent: Unveiling the Achilles' Heel of Multilingual...](https://openreview.net/forum?id=FyjhHoxjzb) - With the rapid advancement of deep learning techniques, the generation of audio deepfakes has achiev...

7. [Toward Robust Real-World Audio Deepfake Detection - arXiv](https://arxiv.org/html/2410.07436v1)

8. [Does Audio Deepfake Detection Generalize?](https://arxiv.org/abs/2203.16263) - Current text-to-speech algorithms produce realistic fakes of human voices, making deepfake detection...

9. [Audio Deepfake Detection: What Has Been Achieved and What Lies Ahead](https://www.mdpi.com/1424-8220/25/7/1989) - Advancements in audio synthesis and manipulation technologies have reshaped applications such as per...

10. [Audio Deepfake Detection with Self-Supervised WavLM ...](https://arxiv.org/abs/2312.08089) - With the rapid development of speech synthesis and voice conversion technologies, Audio Deepfake has...

11. [Audio Deepfake Detection with Self-Supervised XLS-R and ...](https://openreview.net/pdf?id=acJMIXJg2u)

12. [Where are we in audio deepfake detection? A systematic analysis over generative and detection models](https://web3.arxiv.org/pdf/2410.04324)

13. [ASVspoof 5: Crowdsourced Speech Data, Deepfakes, and Adversarial Attacks at Scale](https://arxiv.org/abs/2408.08739) - ASVspoof 5 is the fifth edition in a series of challenges that promote the study of speech spoofing ...

14. [[PDF] Cross-Domain Audio Deepfake Detection: Dataset and Analysis](https://aclanthology.org/2024.emnlp-main.286.pdf)

15. [IndicSynth: A Large-Scale Multilingual Synthetic Speech Dataset for ...](https://aclanthology.org/2025.acl-long.1070/) - IndicSynth, which contains 4,000 hours of synthetic speech from 989 target speakers, including 456 f...

16. [[PDF] Enhancing Partially Spoofed Audio Localization with Boundary ...](https://www.isca-archive.org/interspeech_2024/zhong24_interspeech.pdf)

17. [[PDF] Partial DeepFake Detection Network based on Multi-scale HarmoF0 ...](https://www.isca-archive.org/interspeech_2024/liu24g_interspeech.pdf)

18. [Audio Deepfake Detection: What Has Been Achieved and What ...](https://pdfs.semanticscholar.org/f87d/b7a843e4f6c81191caa7ae79ec8ddf622291.pdf)

19. [ISCA Archive - Robust audio deepfake detection: exploring ...](https://www.isca-archive.org/asvspoof_2024/schafer24_asvspoof.html)

20. [Detecting Novel Audio Deepfake Algorithm with Real ...](https://www.isca-archive.org/interspeech_2024/xie24_interspeech.pdf)

21. [THE EVOLUTION OF DEEPFAKE GENERATION AND COUNTERMEASURES - A REVIEW.](https://openurl.ebsco.com/contentitem/lgd:196187793?sid=ebsco:plink:pplx&id=ebsco:lgd:196187793&utm_source=pplx&link_origin=perplexity.ai&domain_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkb21haW4iOiJ0aGFwYXIuZWR1IiwiaXNzIjoicGVycGxleGl0eSIsImlhdCI6MTc5MDE3MjYwNywiZXhwIjoxNzkwNzc3NDA3fQ.FzInflkPM3YuXQTgPQ3hbpwEMBMbGFCQMyKgDPMKKwg) - During the modern digital era, the widespread adoption of Artificial Intelligence (AI) has transform...

22. [Digital Lyrebirds: Experimental Evidence That Voice-Based Deep Fakes Influence Trust.](https://openurl.ebsco.com/contentitem/lgd:190748655?sid=ebsco:plink:pplx&id=ebsco:lgd:190748655&utm_source=pplx&link_origin=perplexity.ai&domain_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkb21haW4iOiJ0aGFwYXIuZWR1IiwiaXNzIjoicGVycGxleGl0eSIsImlhdCI6MTc5MDE3MjU1OCwiZXhwIjoxNzkwNzc3MzU4fQ.tERdHDZI9jdyMLCdw-izCHs3yTQeyLvGi27xQFnVwHE) - We consider the pairing of audio chatbot technologies with voice-based deep fakes, that is, voice cl...

23. [Synthetic Media in the Information Battlespace: Scalable Evaluation for Detection, Attribution, and Characterization Analytics.](https://openurl.ebsco.com/contentitem/lgd:193194482?sid=ebsco:plink:pplx&id=ebsco:lgd:193194482&utm_source=pplx&link_origin=perplexity.ai&domain_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkb21haW4iOiJ0aGFwYXIuZWR1IiwiaXNzIjoicGVycGxleGl0eSIsImlhdCI6MTc5MDE3MjYwMCwiZXhwIjoxNzkwNzc3NDAwfQ.mKWe1Xn4mrUH5t0RVb-hoxUpJjeC2ngzhTIMQTxAuFQ) - As synthetic media becomes weaponized in influence operations and cognitive warfare, the ability to ...

24. [GitHub - MarkHershey/AudioDeepFakeDetection: SUTD 50.039 Deep Learning Course Project (2022 Spring)](https://github.com/MarkHershey/AudioDeepFakeDetection) - SUTD 50.039 Deep Learning Course Project (2022 Spring) - MarkHershey/AudioDeepFakeDetection

25. [System One - TypeSafe AI](https://docs.typesafe.ai/concepts/system-one)

26. [Audio Deepfake Detection in the Age of Advanced Text-to- ...](https://hal.science/hal-05478173v1/document)

27. [yibie/awesome-jev: A curated list of public projects ... - GitHub](https://github.com/yibie/awesome-jev) - Jev is not a chat model. It takes unstructured state plus a typed question and returns a typed decis...

