# JARVIS MVP Build Specification

**Status:** Implementation brief for the first runnable version. **Scope:** single-user Windows-first desktop app; keep interfaces portable, but do not claim macOS/Linux support until tested.

## 1. Outcome
A user can type or speak a request, JARVIS can respond conversationally, request an explicitly declared typed tool, execute only a small safe set of local actions, and return the verified result. The application must be usable without Oracle deployment. Hosted model access is configured by the user and may have quota, availability, or pricing restrictions.

## 2. MVP feature boundary
### Include
- Windows 11 local application and configuration wizard.
- Push-to-talk voice interaction with Gemini Live when configured; text input fallback for debugging and when audio is unavailable.
- Session transcript and status display: listening, thinking, tool requested, awaiting confirmation, speaking, error.
- Minimal typed tools: `system.get_time`, `filesystem.list_directory`, `filesystem.search_names`, `filesystem.get_metadata`, `process.list` (read-only), `app.launch_allowlisted`.
- A mock model/session adapter so core logic can run without API credentials.
- Confirmation dialog/voice confirmation for any write or external side effect. MVP tools should avoid writes except user-approved app launch.
- Local structured logs with secrets/audio/transcript content excluded or explicitly configured.
- Stop/cancel control and graceful handling of disconnect, timeout, quota, permission, and malformed tool calls.

### Exclude from MVP
Arbitrary shell, file deletion/editing, account/admin changes, firewall/network mutation, email sending, unbounded browser/UI control, wake-word always-on mode, persistent autonomous jobs, cloud deployment, multi-user accounts, and Linux/macOS production support. These are future gated milestones.

## 3. Runtime architecture
- Desktop UI/audio capture runs on the user's computer. The API key stays in OS credential storage; where supported for direct Live connections, use short-lived ephemeral credentials minted by a small backend. A long-lived API key must never be shipped in frontend code.
- `VoiceSession` handles audio streaming and events only. `AgentCoordinator` validates model events and dispatches typed tool calls. `ToolRegistry` exposes declared schemas. `PolicyGate` authorizes calls. `PlatformProvider` performs native operations. `AuditStore` records redacted metadata.
- Data flow: UI/audio → model session → text/audio or function-call event → strict schema validation → policy decision → user confirmation when needed → provider call → bounded result → model function response → final response.
- Model output is untrusted input. Tool name must exactly match registry; reject unknown names/arguments, extra fields, invalid paths and oversized requests.
- Keep UI responsive; use asynchronous I/O and cancellation. Tool output is capped and normalized.

## 4. First-build interfaces
```python
class ModelSession:
    async def connect(self, config): ...
    async def send_audio(self, chunk): ...
    async def send_text(self, text): ...
    async def receive_events(self): ...
    async def send_tool_result(self, call_id, name, result): ...
    async def close(self): ...

class Tool:
    name: str
    schema: dict
    risk: str
    async def preview(self, args): ...
    async def execute(self, args): ...

class PolicyGate:
    async def decide(self, tool, args, context): ...
```

Use the current official Google GenAI SDK (pin a tested version). Isolate SDK-specific classes behind `ModelSession`; do not leak SDK types through the coordinator.

## 5. Safety rules
- No `eval`, `exec`, shell command built from model text, or automatic installation of model-suggested packages/scripts.
- Validate file paths against configured user roots, resolve symlinks, enforce allowed operation and size limits.
- `filesystem.list_directory`, search and metadata are read-only. `app.launch_allowlisted` accepts an application registry ID, not an executable path or arguments supplied freely by the model.
- Require user confirmation bound to the exact normalized call before any future mutation; changed arguments invalidate approval. A model response saying it has approval is not approval.
- Tool outputs, web pages, transcripts, and file contents are untrusted data, never policy instructions.
- Global stop cancels queued work, active tool tasks when cancellable, and audio playback. Log completion/partial side effects accurately.
- Keep API keys, OAuth tokens, audio, and full transcripts out of logs by default.

## 6. Voice behavior
- Start with push-to-talk; no always-on microphone. Explain mic state visibly.
- Use Gemini Live for audio input/output only after verifying the selected exact model ID supports the required audio modalities and function calling in the current docs.
- Implement audio event loop per Google docs: consume all server events, stream chunks, detect interruption, discard buffered response audio on barge-in, process function calls and return responses manually.
- Text fallback uses the same coordinator and tools, ensuring tests do not require a microphone.
- If the model or connection fails, show/speak a clear recoverable error and preserve no unsafe queued tool call.

## 7. Configuration and setup
- Supply `pyproject.toml` or equivalent with pinned/minimum supported dependencies, `.env.example` with names only, `.gitignore` protecting secrets/logs/models, and `README.md` with Windows setup/run steps.
- First run asks for API credential securely or documents setting it via OS keyring. Never accept credentials through a tool prompt that is persisted in history.
- Provide a mock mode that needs no key and a small smoke command to verify audio device/model connectivity.
- Dependency/model downloads require explicit user action, with source, size, license, and destination shown.

## 8. Acceptance criteria
1. A clean Windows setup can start mock mode and text mode by following README only.
2. A configured Live session can stream user audio and play model audio, and stop/interrupt works without stale audio continuing.
3. A harmless request such as “What time is it?” produces a structured tool call, dispatches `system.get_time`, sends the result back, and speaks/displays the answer.
4. An unknown tool, invalid schema, path traversal, oversized result, timeout, or model disconnect is rejected/reported without executing an unintended action.
5. No arbitrary shell or destructive tool is exposed in MVP.
6. Logs contain event IDs, tool names, risk/decision, durations and outcomes but no key or raw audio.
7. Unit tests cover event parsing, schemas, tool dispatch, policy, cancellation and redaction; mocked integration test covers one full tool round trip.
8. `docs/` or README explicitly lists model ID, tested SDK version, environment, setup, voice limitations, and unimplemented PRD requirements.

## 9. Delivery sequence
A. Repository audit and decisions note. B. Core schemas/coordinator/mock session and tests. C. Text UI and read-only tool round-trip. D. Gemini Live transport and push-to-talk audio. E. safety, logging, packaging, setup docs. F. demo against acceptance criteria. Do not start advanced computer-control agents before this slice works.

## 10. Completion report expected from coding agent
Report files added/changed, exact setup/run commands, model ID tested, supported OS, verification performed, features deferred, and any external account/quota/pricing prerequisites. Do not claim Google usage is unlimited or always free based solely on a displayed quota.

## User-directed iteration architecture (supersedes earlier sequence where conflicting)

### Iteration 1 — CLI + dedicated Python command agents + Gemini Live orchestrator
The first project deliverable is a command-line program. Each command domain/capability lives in a dedicated Python agent/tool module. One main orchestration file owns the Gemini Live session, supplies the approved tool schemas, receives structured function-call events, routes each call through the registry and policy gate to its specific module, sends the result back to Gemini, and renders the response in the CLI.

Suggested layout (adapt to repository reality and existing conventions):
```text
jarvis/
  cli.py                 # CLI entry point and user interaction
  orchestrator.py        # Gemini Live session and agent/tool-call loop
  registry.py            # explicit tool ID -> agent module mapping
  policy.py              # risk decisions, confirmation, cancellation
  agents/
    process_agent.py
    filesystem_agent.py
    network_agent.py
    accounts_agent.py
    services_agent.py
    ...                  # dedicated modules per domain from the command plan
  providers/
    windows/ macos/ linux/ # native implementations, feature detection
  voice/
    capture.py playback.py wakeword.py
  storage/
    credentials.py audit.py workflow_state.py
```
A module may expose several related typed tools. Keep the domain agents modular; do not create 55 redundant files if several listed commands are naturally one domain module. Maintain a manifest so every planned command maps to an implementation module and supported platforms.

Iteration 1 ordering: repository audit → CLI text/mock mode → registry and typed agent tools → Gemini Live function-call round trip → safe read-only computer tools → push-to-talk streaming voice → selected reversible writes with preview/confirmation. The source command domains include privileged/destructive operations; they are not all automatically enabled in the first runnable build. Implement them incrementally behind policy, capability checks, and confirmation.

### Iteration 2 — service connectors and credential-safe guided connection
Add MCP/API connections after the CLI agent loop is working. JARVIS can guide setup and perform non-secret browser/UI steps. It must stop at the point requiring credentials or provider consent, explain the next step, and resume the same durable workflow when the user says “done.” Never send secrets to Gemini. The credential UI talks directly to OS keyring/secure storage and returns only a credential handle/status to orchestration. Clipboard-based capture requires explicit user consent, is local-only, and must not log or forward clipboard contents. Prefer OAuth and minimum scopes where supported; prefer official/maintained MCP implementations where available.

## Wake word
The initial version uses push-to-talk. Wake-word support is opt-in and later. No keyword substring/if matching. Do not assume any library is perfect or require Porcupine. Benchmark suitable local models on false accepts/hour, false rejects, latency, CPU/RAM and target-platform/microphone conditions. Ambient audio remains local until a verified wake event; if a detector fails the required reliability target, retain push-to-talk as the supported activation method.

## V1 scope correction — computer control and wake word are required
This section supersedes earlier statements that limited MVP to a small read-only subset or deferred advanced computer control/wake-word mode. V1 must include hands-free activation and all command families enumerated in `JARVIS_Cross_Platform_Computer_Control_Plan.md`: 35 source domains plus 20 additions, subject to explicit platform capability support.

### V1 deliverables
- CLI application and main Gemini Live orchestrator.
- Always-running user-level device satellite with local wake-word detection, auto-start, multi-turn conversation, voice stop/sleep, VAD/turn handling, barge-in, local pre-wake processing, playback, secure server connection and reconnect behavior.
- All 55 planned command families represented by typed tools in dedicated domain modules, a registry/manifest, risk classification, tool schema, preview, validation, execution, result verification, error handling, and tests.
- Windows, macOS and Linux provider implementations for supported capabilities. A feature unavailable due to OS, hardware, permissions, init system, or installed subsystem must return a reasoned unsupported/permission result and appear in the support matrix. Linux-only kernel concepts are not emulated falsely on other OSes.
- Destructive/admin/security/network/persistence actions must have explicit scoped confirmation, least privilege and recovery/rollback design where technically possible. Arbitrary model-authored shell execution remains prohibited; expose safe structured operations. If a general terminal capability is required, it must be a separate constrained broker with command policy, preview and confirmation, not raw model strings passed to a shell.
- Thorough cross-platform automated tests and safe VM/disposable-fixture integration tests for every command family. No live destructive host mutation in tests.

### What “finished in V1” means
No planned command family is silently deferred. Every family must either have a working provider on each supported platform or a documented capability-specific unsupported response, and all paths must have schemas, policy, verification and tests. The coding agent must provide a completion matrix mapping each of the 55 families to module, provider(s), risk, test, and limitations. The agent must report any family not complete as a release blocker rather than calling V1 done.

### Wake-word acceptance
V1 requires an actual always-on local detector; a mock-only wake event or push-to-talk fallback does not satisfy the requirement. Satellite auto-starts, activates hands-free on the configured phrase, permits follow-up turns without repeating it, supports barge-in and spoken sleep/stop, and keeps pre-wake audio local. Test false accepts/hour, false rejects, activation latency, CPU and memory on intended hardware/OSes. Numeric thresholds must be agreed with the owner before implementation; no detector may be claimed perfect. If targets are missed, tune/evaluate alternative detectors or cascades and state the measured limitation; the wake-word feature cannot simply be removed from V1 scope.

### Dependency and schedule reality
This V1 is materially larger than a thin MVP. Implement incrementally, but preserve the V1 completion matrix. OS-specific and privileged features require Windows/macOS/Linux test environments, permissions, and sometimes physical hardware. Do not claim cross-platform completion based only on mocks or Linux tests.
