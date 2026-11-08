# JARVIS Planning Docs — Coding Agent Entry Point

## Purpose
This folder contains product intent, technical design, implementation sequencing, subsystem specifications, and the cross-platform computer-control plan. Read this entry point first, then the linked documents in order.

## Documents
1. `01_PRD.md` — product vision, scope, user stories, requirements, success measures.
2. `02_TRD.md` — intended architecture, interfaces, safety, memory, voice and tool design.
3. `03_Implementation_Doc.md` — original phased implementation proposal. Treat this as a proposal where newer specifications below supersede it.
4. `04_JARVIS_Connection_Manager_Subsystem_Spec.md` — service connection/account integrations.
5. `05_JARVIS_Agent_Core_and_Orchestration_Subsystem_Spec.md` — agent loop and orchestration.
6. `06_MVP_Build_Spec.md` — authoritative first-build scope and acceptance criteria for a coding agent.
7. `07_Gemini_Live_Voice_and_Function_Calling_Spec.md` — Live API voice session, tool-call round trip, limits and security.
8. `JARVIS_Cross_Platform_Computer_Control_Plan.md` — cross-platform computer-control command domains and rollout.
9. `terminal_commands_implementation_guide.md` — duplicate/alternate title of the computer-control plan; reconcile before editing either copy.

## Authority and conflict rules
- User requirements in `01_PRD.md` are the product intent. `06_MVP_Build_Spec.md` narrows that intent to the first deliverable and is authoritative for MVP scope.
- The subsystem specifications `04` and `05` govern their respective components unless they conflict with the MVP safety requirements; use the safer/more restrictive behavior.
- `07_Gemini_Live_Voice_and_Function_Calling_Spec.md` governs Gemini Live integration details. Verify model IDs, SDK APIs, quotas, and pricing against current official docs during implementation; these change over time.
- `JARVIS_Cross_Platform_Computer_Control_Plan.md` is a later capability roadmap, not an instruction to expose every privileged command in the MVP.
- The computer-control files are duplicated. Keep one canonical file and make the other a pointer or remove it only with the owner's approval.
- When documents disagree, record the conflict and choose the safer, narrower MVP behavior. Do not invent product requirements silently.

## Coding agent instructions
1. Inspect the actual repository, Git state, runtime, and existing code before choosing frameworks or replacing files. The current project may contain only planning documents; never assume the proposed `jarvis/` tree exists.
2. Produce a short implementation map from current source to these specifications. Note missing decisions and make conservative assumptions where safe.
3. Build a runnable thin vertical slice first: text input → Gemini Live/session adapter or documented text-only mock → safe typed tool call → result → response. Voice can be layered in the same milestone only if the actual hardware and SDK path can be verified.
4. Do not implement unrestricted natural-language-to-shell execution. Use a typed, allow-listed capability broker and explicit policy checks. If a general shell is later enabled, default deny/elevate unknown commands to confirmation and isolate it.
5. Keep credentials out of source/config/logs; use OS credential storage locally and server-side secrets on hosted deployments. Never put a long-lived Google API key in a browser/client bundle.
6. Declare exact supported OSes and feature gaps. An MVP may target Windows first; cross-platform expansion is a subsequent milestone.
7. Implement tests from `06_MVP_Build_Spec.md`; report unimplemented requirements, setup steps, verification results, and known limitations.

## Product decisions recorded so far
- Initial user: single user, Windows laptop.
- Primary voice direction: Gemini Live API, contingent on exact model's current function-calling support and access limits.
- Preferred long-term computer-control design: typed tools with policy/confirmation, platform adapters, not arbitrary command strings.
- Cloud: Oracle Always Free A1 has been discussed as an optional ARM Linux host for backend/harness. It is not required for local MVP and should not be assumed available or suitable for local LLM inference.
- Voice API quotas displayed in AI Studio must be rechecked for the user's actual project/model; quota labels do not establish guaranteed availability or fixed future terms.

## Iteration plan (authoritative user direction, 2026-11-07)
### Iteration 1: CLI command-agent system
- Deliver a command-line application first; no GUI dependency in this iteration.
- Implement the listed computer-control domains as dedicated, discoverable Python modules (one domain or tightly related agent per file) that export typed function tools. The source has 35 Linux-inspired domains plus 20 proposed command families; retain the platform/capability distinctions and safety requirements in the cross-platform plan.
- Provide one main orchestration entry point that opens the Gemini Live API session, listens for user intent, exposes tool declarations, dispatches structured function calls to the matching Python module, returns results to Gemini, and presents text/audio responses in the CLI.
- Keep a central tool registry mapping stable tool IDs to their owning agent module, schema, supported OS/capabilities, risk tier, preview, executor, and verifier. Gemini chooses among declared tools; it must never choose/import arbitrary Python files or submit a shell string for blind execution.
- Build CLI text mode and mock mode before microphone integration, so the dispatch/safety loop can be exercised without API access or audio hardware. Add push-to-talk Live voice after the tool-call round trip is reliable.
- Make cross-platform providers part of each relevant agent API, with explicit Windows/macOS/Linux support declarations. Linux-only agents return a clear unsupported result elsewhere.

### Iteration 2: connected services and guided setup
- Add integrations for GitHub, Google Drive, Calendar, Figma, and other user-selected services. Prefer maintained official MCP servers or MCP-compatible endpoints where available; use direct APIs/OAuth or another documented connector where MCP is unavailable or unsuitable.
- Add a guided connection agent that identifies the correct connector and setup route, opens official setup pages, and completes non-secret steps with the user. It pauses at credential creation/authorization and explains the exact next user action.
- Credentials are entered or captured only by a trusted local credential UI/keyring flow. Never place raw secrets in Gemini prompts, tool-call arguments, assistant transcripts, logs, analytics, screenshots returned to the model, or MCP discovery text. The connection agent receives only an opaque credential reference and connection status.
- Preserve context across the user completing a step and saying “done.” Resume the pending setup workflow by workflow ID and explicit state, not by relying only on a model's conversational memory. If a key is copied to clipboard, a local-only credential capture action may read it after explicit user authorization, pass it directly to the OS keyring, and immediately clear/avoid retaining clipboard contents. Prefer a secure local paste field; never automatically ingest clipboard content without clear consent.
- After secret storage, validate the connector using a non-secret test call, show success/failure, and offer revoke/remove instructions. OAuth consent should use the provider's authorization flow and least-privilege scopes rather than asking users to paste passwords.

### Wake word requirement
- Push-to-talk is the initial reliable voice activation path. Wake word is a later, independently measured feature and must be opt-in with visible microphone state and a hardware mute/stop path.
- The user explicitly rejects simple `if`/substring matching and does not want to rely on Porcupine. Do not claim any wake-word engine responds to every utterance; false accepts and false rejects are inherent and must be measured on target microphones, environments, accents, and distances.
- Evaluate local open-source keyword spotting/streaming speech models (including openWakeWord or other current candidates) against a project-owned test set. Select only after measuring false-reject rate, false-accept rate per hour, latency, CPU/RAM, and cross-platform behavior. A robust cascade may combine acoustic wake-word detection with local VAD and a short local confirmation stage; this stage must not send ambient audio to Gemini before activation.
- If the target reliability is not met, ship push-to-talk and keep wake word disabled rather than presenting a fragile detector as robust.

## V1 scope correction (user-directed, 2026-11-07)
V1 is not complete without both (a) hands-free wake-word operation and (b) the planned computer-control capabilities. The coding agent must not defer wake word or computer control to a later release. V1 includes the command domains listed in `JARVIS_Cross_Platform_Computer_Control_Plan.md`: all 35 source domains plus all 20 added command families.

“Complete” means every planned command has a registered typed schema, implementation or explicit platform provider, policy/risk classification, preview/confirmation behavior as applicable, result verification/error path, and automated test coverage. OS-specific capabilities must be implemented on the OSes that expose them and report unsupported capability on other OSes; this is acceptable only where documented in the support matrix. Do not silently omit or label deferred any domain. The target matrix is Windows, macOS, and Linux, with Linux distribution/init-system differences capability-detected.

The CLI, resident device satellite, and always-on server are all part of the V1 architecture. Service connectors (GitHub, Drive, Calendar, Figma, etc.) remain iteration 2. The computer-control plan's delivery phases are implementation sequencing within V1, not later project iterations.

Wake-word quality remains testable rather than an impossible promise of perfect detection. V1 must include a real local wake detector (not only a mock), hands-free multi-turn sessions, stop/sleep, barge-in, local pre-wake audio processing, autostart, and a published evaluation on each supported target platform. Do not claim “every call” reliability; establish numeric false-accept/hour, false-reject, latency, CPU and memory acceptance targets with the owner before implementation and report measured results. If a selected library cannot meet them, evaluate alternatives/cascades before release.
