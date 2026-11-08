# Gemini Live Voice and Function Calling Specification

## Purpose
Define the first voice/model integration for JARVIS. This is a design spec, not a promise that a model's current quotas, names, or features remain unchanged. Verify official Google documentation and the user's AI Studio project immediately before implementation.

## Concepts
- Live API is a real-time session over WebSocket with streaming audio/text and optional audio response.
- Function calling is a request from the model to the client. JARVIS must validate and execute the function, then send a function response. The model does not directly control the OS.
- The model list/AI Studio display label is not necessarily the API model ID. Record the exact ID tested.
- Function calling support is model-specific. A general Live API feature overview is not sufficient proof for a chosen model.

## Implementation flow
1. User presses and holds push-to-talk; capture supported audio format and stream short chunks with correct MIME/sample-rate metadata.
2. Open Live connection with system instruction, response modality, transcription options, and a small set of function declarations. Keep tool descriptions narrow and schemas strict.
3. Read every server event. Surface user/output transcription and audio chunks. Track turn completion, interruptions, session errors, expiry, and reconnect.
4. On function-call event, validate call ID, exact registered name, strict JSON schema, argument size and policy. Reject malformed/unknown calls.
5. For read-only MVP tools, execute within timeout and return bounded JSON result. For mutations, show exact preview and await independent user approval before dispatch.
6. Send function response correlated to the original call ID and name. Continue consuming events until model turn completes.
7. On interruption, stop playback immediately and clear buffered chunks. On Stop, cancel local operation where possible and close or reset the session safely.

## Tool declaration and implementation requirements
- The declaration is not a permission grant. It describes what the model may request; local policy decides what is allowed.
- Expose only relevant tools per session. Use stable names such as `system_get_time`; do not expose a generic `run_command` in the MVP.
- Define required fields, types, bounds, enums, and `additionalProperties: false` where supported. Validate again locally with a schema library.
- Treat model-generated arguments as untrusted. Enforce path roots, app registry IDs, maximum results, timeouts, and per-turn call limits.
- Return structured results with success/error fields, concise summaries, and no secrets. Send execution errors as tool results rather than claiming success.
- Tool side effects must be idempotent where feasible or protected against duplicate call delivery.

## Session and credential security
- Never embed a permanent API key in a packaged desktop frontend or browser bundle.
- Prefer backend-minted short-lived ephemeral tokens for direct client-to-Google Live sessions where available and appropriate. Restrict token lifetime and session configuration as documented.
- Alternative: a trusted JARVIS backend holds API key and proxies the websocket. This increases latency and places audio/transcripts on the backend; secure transport, storage, and access accordingly.
- Keep secrets in OS keyring/server secret storage; redact SDK errors and diagnostics.
- Explain that audio/transcripts are sent to Google when cloud Live is enabled; provide explicit mic state and a stop control.

## Model selection and verification checklist
Before coding or release, for the exact model ID confirm from official docs and a harmless prototype:
- Live API availability and current lifecycle status (preview/stable/deprecation).
- Input audio format and output modalities.
- Function calling capability and any blocking/non-blocking constraints.
- Whether multiple calls, tool responses, interruption, transcription, session resumption and context compression are supported.
- Context/session/token limits, rate limits, pricing/free-tier applicability, and regional/access requirements.
- SDK/API version needed and quota behavior when exceeded.

Test with `system_get_time` and `filesystem.list_directory` restricted to a disposable test folder. Verify a structured call event and correlated response in logs. A spoken sentence like “I checked” is not proof the function executed. Repeat enough times to catch inconsistent tool selection; retain deterministic text-mode tests alongside live audio tests.

## Failure handling
- Rate limit/quota: stop retry loop; back off with jitter, show retry option, and do not replay side-effecting calls blindly.
- Network/session expiry: preserve conversation summary if safe, reconnect with a bounded retry policy, and require reconfirmation for pending writes.
- Missing/invalid function response: report failure and avoid asserting action completion.
- Audio device unavailable: expose text mode and actionable device selection.
- Model tries to narrate a tool call without structured event: treat as plain text; do not execute based on narration.

## References to verify during implementation
- Live API overview: https://ai.google.dev/gemini-api/docs/live
- Live API tools: https://ai.google.dev/gemini-api/docs/live-api/tools
- Live API capabilities: https://ai.google.dev/gemini-api/docs/live-api/capabilities
- Live API SDK quickstart: https://ai.google.dev/gemini-api/docs/live-api/get-started-sdk
- Ephemeral tokens: https://ai.google.dev/gemini-api/docs/ephemeral-tokens
- Models: https://ai.google.dev/gemini-api/docs/models
- Rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Pricing: https://ai.google.dev/gemini-api/docs/pricing

## User-required module routing and later service setup
For Iteration 1, keep the CLI and main Live orchestrator explicit. Each command domain is implemented by dedicated Python module(s), registered with stable typed schemas. The orchestrator receives Gemini function-call events and routes only by exact tool ID through the registry. It does not dynamically import paths or execute model-authored shell text. Return the provider result through the Live function-response mechanism.

Iteration 2 adds service connectors. Use MCP where a trustworthy maintained MCP server/endpoint exists; otherwise use official OAuth/API integration. Guided setup may automate public documentation navigation and non-secret configuration, but credential entry and OAuth consent remain local/user-controlled. Persist a workflow state so “done” resumes the correct setup task. Secrets are stored directly in OS keyring or server secret storage, never passed through the LLM. A local credential bridge may accept a pasted/copied token only after an explicit user action, write directly to secure storage, and return an opaque reference. Do not treat model context retention as secure workflow persistence.

## Wake-word constraint
Do not use substring/if-based phrase detection or Porcupine. Begin with push-to-talk. Evaluate candidate local open-source acoustic/streaming detectors empirically; no detector is assumed to catch every call. Report measured false-accept/false-reject rates, latency and CPU/RAM on target hardware before enabling wake-word mode. Keep pre-activation audio local and provide an obvious mic mute/stop control.

## V1 completion scope
Wake-word operation and the entire computer-control command catalog are required V1 deliverables, not later enhancements. Implement all 35 original domains plus 20 added command families from the cross-platform plan. Every command must be represented in the registry and completion matrix with schema, OS/provider support, risk policy, preview, execution, verification, errors and automated tests. The implementation may report an OS capability as unsupported only when the underlying OS/hardware/API truly lacks it and the matrix explains why; silently omitting a domain fails V1.

A real local wake detector is required in V1, along with hands-free session continuation, barge-in, stop/sleep, auto-start and local-only pre-wake processing. Mock detector tests supplement but cannot replace target-device evaluation. Agree numeric reliability targets with the owner and report measured false accepts/hour, false rejects, latency and resource use. Perfect recognition is not promised.
