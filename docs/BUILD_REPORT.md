# JARVIS — first runnable build report

**Delivered:** 2026-11-07 · **Version:** 0.1.0 engineering preview  
**Release decision:** **NOT complete against the final V1 specification.**

The build follows the required initial sequence: repository inspection → documented decisions → mock/text CLI → typed registry/policy/gateway → safe native tools → Gemini transport and experimental voice/satellite code. It preserves the complete V1 target rather than claiming the smaller, superseded MVP is the final scope.

## Delivered and tested

- Runnable Python CLI, no GUI requirement and no API key required in mock mode.
- End-to-end structured mock call → validation/policy → `system.get_time` → result → displayed response.
- **32 registered typed tools** with discoverable strict schemas, owning modules, risks, platform declarations, preview, executor, verifier, timeouts and output limits.
- Actual tool implementations cover **28 partial command families**. All **55** planned families appear in the [completion matrix](COMPLETION_MATRIX.md); **27 have no implementation** yet. No row is certified complete across target platforms.
- Central safety boundary: exact IDs, deny unknown fields/tools, filesystem root/symlink checks, read-only ceiling, separate local approval, schema/argument/session binding, expiry, cancellation and duplicate-call/restart replay protection.
- Native OS-keyring bridge with plaintext backends refused; metadata-only SQLite audit and versioned SQL migration. No secrets, audio or transcripts placed in application audit records.
- Gemini Live adapter with manual correlated function responses, interruption handling and optional PCM I/O. SDK types do not cross into domain executors.
- Acoustic openWakeWord/ONNX integration, local pre-wake activation gate, experimental resident satellite, 60-second follow-up window, transcript stop/sleep and server interruption handling.
- Authenticated heartbeat server and HTTPS-only reconnecting satellite client; no remote tool dispatch is exposed.
- Offline wake evaluator, explicit optional asset installer, autostart definition generator for Windows/macOS/Linux, CI workflow and operating instructions.

## Verification performed here

Environment: **Linux x86-64 · kernel 6.1.189+ · Python 3.13.16**.

| Check | Result |
|---|---|
| `python -m pytest -q --junitxml=docs/test-results.xml` | **98 passed**, 3.69 s on final recorded run |
| `python -m ruff check src tests scripts` | Passed |
| `python -m compileall -q src` | Passed |
| `python -m pip check` | Passed for installed core/dev/Live/server profile |
| `python -m jarvis --once "What time is it?"` | Passed; verified mock structured clock round trip |
| `python -m jarvis --once "List this folder"` | Passed; bounded scoped directory output |
| `python -m jarvis smoke` | Passed; no-key smoke |
| Fresh isolated venv, core-only `pip install -e .` and smoke | Passed; no Live/audio/server dependencies needed |
| Built wheel import and packaged SQL migration | Passed in isolated venv |
| `python scripts/check_release.py` | Expected failure: full V1 is blocked; preview remains runnable |
| `python scripts/wake_assets.py` / `install_wake.py` | Disclosure-only runs passed; no assets/library downloaded by these scripts |
| Windows/macOS CI | Workflow supplied; **not run here** |
| Google Live access/model/function calls | Fake SDK transport tested; **no real account/API session** |
| Native OS credential storage | Adapter/fail-closed tests only; **no real keyring write** |
| Audio/wake/device reliability | **Not measured; no microphone/model assets installed** |
| Privileged/destructive actions | No host mutations; no completed privileged providers |

Tests cover validation and argument bounds, mock round trip, known-tool dispatch, read ceilings, approval binding/expiry/denial, output limits, unknown tools, unsupported/permission outcomes, timeouts, stop during execution/approval, replay reservations, audit privacy, prompt-injection text as data, path/symlink traversal, ZIP path checks, native read tools, mocked app identity verification, OS service contracts, Live schema and function-response correlation, disconnect/interruption, pre-wake privacy, evaluator arithmetic, server authentication, catalog completeness and autostart generation.

**Not a claim:** 98 passing tests do not establish 90% natural-language task success, all 55 domain operations, cross-platform parity or wake accuracy. Those release evaluations do not yet exist.

## Exact quick-start commands

From the extracted `jarvis` folder, Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,live,server]"
.\.venv\Scripts\python.exe -m jarvis --once "What time is it?"
.\.venv\Scripts\python.exe -m jarvis --mode mock
.\.venv\Scripts\python.exe -m pytest -q
```

Mock phrases are explicit deterministic demo fixtures, not general intent matching. Use `/tools` and `/call tool.id {JSON}` to exercise the actual registry. For free-form interpretation, securely configure a Google credential and use `--mode live`; see [README](../README.md).

## Model and account prerequisites

Configured default: **`gemini-3.8-live`**. Tested SDK version: **`google-genai==3.0.0`**. **Model ID live-tested: none.** Official model and function-calling documentation were checked, and SDK config construction and fake tool response correlation were validated locally. This does not prove the owner's account has access, sufficient quota or the same pricing terms.

Official references checked during implementation:

- [1](https://ai.google.dev/gemini-api/docs/live-api/tools) — client-managed function declarations/responses.
- [2](https://ai.google.dev/gemini-api/docs/live-api/get-started-sdk) — SDK session/audio/transcription patterns.
- [3](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live) — exact model identity/capabilities; native audio response modality with text transcription.
- [4](https://ai.google.dev/gemini-api/docs/rate-limits) and [5](https://ai.google.dev/gemini-api/docs/pricing) — owner must recheck model/project limits and billing before live use; not verified for their account.

No paid API usage, remote deployment, OAuth connection, service account or cloud infrastructure was provisioned. Google access and billing/quotas remain owner prerequisites. Wake weights are separately licensed and require explicit owner download acceptance.

## Supported OS statement

The **tested environment is Linux only**. Portable stdlib/psutil implementations are intended for Windows/macOS/Linux, with provider contract tests for platform paths; that is not production support certification.

- Linux-only modules/IPC/capability tools explicitly reject incompatible OS interfaces.
- Windows service status uses SCM via psutil; macOS service status uses a fixed launchctl profile; Linux requires detected active systemd. Other init-system providers are missing.
- Batteries and network/process inspection return capability/permission results when the OS/hardware does not expose the information.
- Full target-platform/device/VM testing is a V1 blocker. See [matrix](COMPLETION_MATRIX.md).

## Mandatory V1 release blockers

1. Complete every planned operation in all 55 domains, including actual platform providers, strict operation schemas, privilege handling, preview/recovery/rollback design, identity revalidation, independent verification and safe disposable-VM tests. Twenty-seven families currently have no provider code; partial rows are incomplete too.
2. Implement and validate full typed goals/plans/DAGs, reference clarification, policy preflight, durable task/step state machines, SQLAlchemy/Alembic/outbox, leases, pause/resume/reconciliation, structured memory and model/budget routing from subsystem 05. Current invocation persistence is not that subsystem.
3. Validate a real Gemini tool round trip with the owner's account, quota/disconnect handling, microphone/speaker operation, push-to-talk hotkey, real barge-in and spoken stop/sleep.
4. Install/evaluate real wake assets on Windows, macOS and Linux against the accepted targets. No published acoustic evaluation exists. Tune/evaluate alternatives/cascades if targets are missed. Add independent local spoken stop, measured VAD/AEC behavior and a robust visible mic/hardware-stop UX.
5. Finish satellite/server pairing, scoped identity, secure remote task/conversation coordination, device reconnection/recovery, credentials rotation/revoke and verified autostart. The heartbeat-only server is architectural groundwork, not a finished always-on orchestration service.
6. Run full cross-platform CI and target-hardware tests; expand privacy/supply-chain review and signed deployment design. Current CI has not run on hosted Windows/macOS runners.
7. Execute the required diverse natural-language evaluation suite, release safety gates and performance/resource measurements. Mock fixtures do not count as NLP evaluation.

Connected services (GitHub/Drive/Calendar/Figma/MCP/OAuth) remain **iteration 2**, per the supplied requirements. Computer control and wake remain **mandatory V1 work**, not moved to iteration 2.

## Files and original documents

New code is under `src/jarvis/`; tests under `tests/`; setup scripts under `scripts/`; config example under `config/`; workflow under `.github/workflows/`. Tool schemas, the complete domain catalog, architecture decisions, threat/data-flow notes, wake plan and autostart instructions are supplied.

Original Markdown specifications are copied under `docs/`. The duplicate computer-control file is a pointer in this project, with an original preserved. Uploaded source files were never changed. The account-identifier-only `.txt` attachment is deliberately excluded from the distributable.
