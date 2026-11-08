# Wake evaluation — agreed targets; measurements pending

Owner accepted the balanced targets in this conversation on 2026-11-07:

| Metric | Target | Windows | macOS | Linux |
|---|---|---|---|---|
| False accepts/hour | ≤0.5 | Not measured | Not measured | Not measured |
| False-reject rate | ≤10% | Not measured | Not measured | Not measured |
| p95 detection after phrase end | ≤800 ms | Not measured | Not measured | Not measured |
| CPU relative to one core | ≤10% | Not measured | Not measured | Not measured |
| Resident memory | ≤250 MB | Not measured | Not measured | Not measured |

No benchmark audio or fabricated measurements are included. The `ActivationGate` tests use deterministic acoustic-detector fakes to prove local-before-wake data flow; those tests are **not** acoustic-accuracy tests.

## Proposed project-owned dataset

Owner should approve the evaluation cohort/environment before release:

- At least 200 annotated positive utterances per target setup; owner accent, normal/quiet voice, distances and room noise represented.
- At least 10 hours of negative background audio per setup: TV/music, conversation, keyboard/fan noise, near-phrases. Measure false accepts/hour and confidence intervals; one short zero-error run is not evidence of compliance.
- Separate tuning and holdout sets. Do not tune thresholds on the release test set.
- Record microphone/model hashes, OS/build, CPU, RAM, distance, sound conditions, detector threshold/cooldown and sample format. Consent from anyone whose voice is captured is required. Never commit private recordings.
- Annotate wake-phrase end in positive clips (`wake_end_ms`) and review whether detections occur on the actual phrase. The basic evaluator uses first detection; positives containing earlier distractors must be reviewed manually or split to avoid optimistic labeling.
- Test device audio loss, unplug/replug, sleep/resume, offline behavior, model quota/disconnect and secure keyring availability separately.

## Tooling

`jarvis evaluate-wake MANIFEST MODEL` processes explicitly supplied WAV files locally. It reports observed false accepts/hour, false rejects, first-detection p95, detector processing time, process-CPU-seconds/audio-seconds and peak sampled RSS. These are offline estimates; CPU is not a calibrated real-time resident-satellite measurement and latency excludes microphone/driver buffering. No automatic “release passed” claim is made.

For final acceptance, run real-time measurement on each OS while the resident satellite is idle/listening/active. Include mic buffers and OS scheduling in end-to-end p95. Include the full idle satellite and audio queue allocation in CPU/RAM. Measure barge-in with actual playback and headset/AEC conditions, hands-free follow-up turns, stop/sleep and independent hardware-mute/Ctrl+C response.

If targets fail, evaluate threshold/VAD cascades, user-specific verifier models or a second current local acoustic engine, using a fresh holdout. Do not substitute keyword substrings or claim every utterance will activate. Wake remains a mandatory V1 release requirement, not an omitted feature.

## Licensing and assets

The optional loader uses openWakeWord 0.6.0 with ONNX. Code is Apache-2.0; upstream describes bundled pretrained models as CC BY-NC-SA 4.0. Review suitability for personal/noncommercial use. `scripts/wake_assets.py` discloses fixed upstream release source, exact expected sizes and destination before downloading; no model is downloaded by startup. Asset checksums are displayed after download; release-pinned signed/hash provenance review is still required before redistribution.
