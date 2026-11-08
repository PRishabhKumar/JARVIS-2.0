# Security / data-flow notes — engineering preview

## Data flow

```
Local CLI or activated microphone → Gemini session → structured call
→ exact registry lookup → strict schema → effect ceiling + policy
→ independent local confirmation (if applicable) → bounded provider
→ verification → bounded UNTRUSTED result → Gemini → text/audio
```

Before acoustic activation, microphone frames go only to the local detector. The trigger frame is discarded; subsequent frames may go to Google for a fixed, visible 60-second session window. Text mode does not open the microphone. `/ptt` is explicit five-second capture, **not** a global hold-to-talk hotkey.

## Deterministic boundaries

- No `eval`, `exec`, model-selected Python import, general shell tool or model-provided executable/argv is exposed.
- Native provider command profiles use argument arrays and no shell. Broker output is capped; timed-out/cancelled child processes are terminated and reaped. Descendant containment/Windows Job Objects remain a release gap.
- The model cannot raise its read ceiling or provide approvals. App launch is only direct CLI + trusted local configuration + fresh approval. A model saying “approved” has no authority.
- Confirmations bind normalized arguments, canonical tool ID/version/schema, session and effect ceiling. They expire, do not survive restart, and are not sent to Gemini. Full target before-state binding and immutable multi-step plans remain missing.
- File paths resolve symlinks, must be inside configured roots, and exclude named credential locations and JARVIS state. There are no filesystem mutators. Prefer narrow roots, never the whole home or drive. Race-safe descriptor walking against concurrent symlink swaps is **not implemented**; do not treat these read tools as a multi-user isolation boundary.
- Network metadata and file/process names may be private and go to Google when returned in Live mode. Restrict roots and do not use cloud mode for secret-bearing workloads. File-content reads, clipboard and screenshots are not exposed in this build.
- Tool output is marked untrusted. No string in a result is parsed as a new action or approval. This is not proof of general model prompt-injection immunity.

## Storage and credentials

- Keys are entered with local `getpass`, not tool arguments, env files or CLI argv. Native Windows/macOS/SecretService/KWallet backends are allowed; unknown, chain and plaintext backends fail closed. Native keyring integration still needs real-OS validation.
- Audit DB stores event/session IDs, canonical tool names, risk, decisions, outcome and durations. Invocation DB stores call fingerprints/statuses. No arguments, returned content, transcripts, audio or raw SDK exceptions are retained.
- DB file mode is 0600 and parent creation uses 0700 on POSIX. Existing parent-directory permissions and Windows ACL hardening require owner review. Database is not encrypted at rest; protect the device account/disk.
- No raw exception messages are displayed from the SDK/OS. Error codes intentionally trade detailed diagnostics for avoiding secret leaks. Third-party dependency behavior is outside this small audit implementation and needs a release privacy review.

## Server/satellite

Server is heartbeat-only; it cannot dispatch local tools. Local server binds loopback and disables access logs/docs/CORS. Place it behind an owner-managed TLS reverse proxy for remote use. Satellite rejects non-HTTPS URLs and redirects; credentials use an Authorization header, not URLs. Do not expose the loopback HTTP port directly to the Internet. Full pairing, durable task delegation, scoped device identity, credential rotation, revocation and reconnect recovery are missing release requirements.

## Residual release risks

No Windows/macOS hardware run; no real cloud round trip; no measured wake accuracy, CPU/RAM, capture latency or echo cancellation. Wake false activations can send post-trigger audio to Google. Use a headset, visible console and hardware mute. Spoken stop/sleep is recognized from cloud transcripts after activation, not a guaranteed independent local emergency detector. Ctrl+C/hardware mute is the independent stop path. Satellite has no tray indicator/global hotkey yet. Do not install autostart for unattended use until tested.
