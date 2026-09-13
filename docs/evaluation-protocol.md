# VigilVoice frozen evaluation protocol

Frozen: 2026-09-13, before threshold tuning or model comparison.

## Supported presentation languages

Hindi, Indian English, Hinglish, and **Marathi**. Marathi is the selected regional language because Mozilla Common Voice 25.0 lists a 561.35 MB Marathi corpus under CC0 1.0, while AI4Bharat's Indic Parler-TTS model card explicitly supports Marathi, Hindi, and Indian English. This is a presentation-scale evaluation scope, not a population claim.

## Source and consent inventory

| Material | Planned use | License/access | Status |
|---|---|---|---|
| [Mozilla Common Voice 25.0](https://commonvoice.mozilla.org/en/datasets), Marathi `mr` | Genuine Marathi baseline | CC0 1.0; version 25.0 | Publicly listed; not downloaded |
| [AI4Bharat IndicVoices](https://huggingface.co/datasets/ai4bharat/IndicVoices) | Optional genuine Hindi/Marathi supplement | CC BY 4.0; gated contact-sharing acceptance | Candidate only; access not accepted or verified |
| Team recordings | Genuine Hindi, Indian English, Hinglish, Marathi; replay/channel trials | Written consent required before capture; private raw audio excluded from Git | Speakers and consent not yet obtained |
| [AI4Bharat Indic Parler-TTS](https://huggingface.co/ai4bharat/indic-parler-tts) | Synthetic Hindi, Indian English, Marathi; experimental Hinglish only after bilingual review | Apache 2.0 model; gated contact-sharing acceptance; pin revision at acquisition | Candidate only; access not accepted or verified |
| A second independently implemented TTS/voice-cloning family | Held-out generator evaluation | Must permit local research/demo use and redistribution of evaluation-derived metrics | Not selected; required before claiming held-out-generator coverage |
| Existing Gary Stafford 40-clip corpus | Regression only | CC BY 4.0, already pinned locally | Acquired; excluded from final four-language threshold selection |

No external service receives team voice recordings. A participant consent record must name the speaker ID, permitted presentation/evaluation use, retention deadline, and withdrawal contact. Consent records stay outside Git; the manifest stores only an opaque consent ID. Synthetic prompts must be team-authored or permissively licensed, and must not impersonate a real person without that person's specific cloning consent.

## Frozen corpus and split

- Target 320 independent source clips: for each language, 40 genuine and 40 synthetic clips, with 20 of each class in validation and 20 in untouched test.
- Use at least five genuine speakers per language where available and report the actual count. Clips are not a substitute for speaker diversity.
- Validation selects thresholds and any candidate model. Test is run once after model, preprocessing, cadence, quality gates, smoothing, and policy are frozen.
- Assign whole connected groups to one split. A group joins the same speaker/source recording, normalized transcript or prompt, related segment, augmentation, replay, codec transform, and derivative synthetic clip. Duplicate PCM or file hashes are rejected.
- Use source-provided speaker IDs where available. Missing speaker identity is recorded as unknown and cannot support a speaker-independent claim.
- Reserve the entire second generator family for test. If no permitted second family is obtained, report held-out-generator coverage as missing; do not relabel voice styles or random seeds as independent generators.
- Demo clips, rehearsed examples, and any training/fine-tuning material are separate from validation and test.
- Freeze source/model revisions and SHA-256 hashes at acquisition. No file may enter evaluation without a recorded source, license or consent ID, language, class, group, duration, channel, condition, and hash.

Required manifest fields are `path,label,split,group,sha256,source_sha256,source,license,language,speaker_id,prompt_id,generator_family,generator_revision,channel,condition,consent_id`. Blank values are allowed only when inapplicable; unknown provenance fields remain explicitly `unknown` and block the corresponding independence claim.

## Frozen conditions

- Baseline clean audio plus real speaker-to-microphone replay, recorded phone/narrowband audio, added noise, low-volume/accented genuine speech, held-out generator, and genuine-to-synthetic-to-genuine partial manipulation.
- At least 10 genuine and 10 synthetic source recordings per supplemental condition where available. Derivatives remain linked to their source group and never inflate independent-source counts.
- Evaluate 0.5, 1, 2, and 4 second excerpts without looping audio. With the deployed 1.5 second minimum speech gate, shorter evidence may correctly be `INSUFFICIENT_EVIDENCE`; detector-only diagnostics must be labeled separately.

## Frozen acceptance metrics

- At most 10% HIGH false blocks among scorable genuine validation clips; choose the highest-recall threshold satisfying that bound.
- At least 90% HIGH recall among scorable synthetic test clips at the frozen threshold.
- At least 85% scorable coverage for both genuine and synthetic supported-quality baseline clips, with quality rejection, insufficient evidence, and service failure counted separately.
- Report numerators, denominators, and two-sided 95% Wilson confidence intervals overall and per language/condition. Report false alerts per genuine call and keep detector misses separate from unauthorized action completion.
- Capture-to-first-HIGH p95 at most 4 seconds among detected, scorable two-second-evidence trials, and at least 85% alerted within 4 seconds using all scorable attack trials as denominator. Every miss/no-alert remains visible.
- Warmed end-to-end analysis p95 at most 10 seconds for a 10-second WAV; no growing backlog during a 10-minute stream. Report cold start separately.
- One live operator stream must leave verification/action/audit responsive. Measure 2 and 3 streams and reject excess load promptly if unsupported.

A failed language or condition remains failed even if aggregate metrics pass. Any tuning after the untouched test run requires a new untouched holdout and a new receipt.
