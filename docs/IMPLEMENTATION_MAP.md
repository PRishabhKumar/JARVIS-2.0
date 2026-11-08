# Repository audit and implementation decisions

Date: 2026-11-07. Baseline: `/home/user/uploads` contained eleven planning files and no application repository. `/home/user` was not a Git repository. No prior code, framework or user changes were replaced. Created a new `jarvis/` project; original uploads remain untouched. The `.txt` file contained a personal account identifier, not implementation instructions; it is deliberately not copied into the distributable.

## Authority reconciliation

1. The final **V1 scope correction** in 00/06/07 supersedes earlier small-MVP exclusions. Full V1 requires 55 domains, three target platforms, satellite, server and evaluated acoustic wake-word support.
2. First implementation sequence still starts with CLI mock/text, typed registry and safety. The foundation test checkpoint was completed before adding voice.
3. Older instructions to expose `run_shell` and automatically parse model-authored commands are rejected in favor of the later typed capability broker requirement.
4. Older GUI-first/cloud-excluded/wake-later statements do not determine the final architecture. This build has no GUI dependency. Server heartbeat and satellite modules exist, but their existence is **not** evidence of complete V1.
5. Cross-platform plan copies were byte-identical. In this project the named cross-platform plan is canonical; the alternative is a pointer. Its original is preserved; uploaded originals are not edited.
6. Connected services remain iteration 2. No MCP/OAuth service connector has been added prematurely.
7. Accepted owner targets: false accepts ≤0.5/hour, false rejects ≤10%, p95 detection latency ≤800 ms, CPU ≤10% of one core, resident RAM ≤250 MB. **Targets, not measurements.**

## Source → specification map

| Area | Implementation | Current evidence / remaining scope |
|---|---|---|
| CLI-first entry (00/06) | `cli.py`, `__main__.py` | Mock fixtures, tool discovery, direct typed calls, stop/reset, noninteractive demo |
| Typed contracts (05/06) | `contracts.py`, `registry.py` | Strict model envelope and JSON schemas, bounded payloads, exact IDs |
| Safety boundary (05/06/plan) | `policy.py`, `orchestrator.py`, `config.py` | Read ceiling, local confirmation, exact binding, expiry, stop, path roots |
| Computer domains | `agents/*`, `providers/*`, `catalog.json` | 32 tools across 28 partial domains (+clock utility); 27 domains have no implementation |
| Model/session (07) | `models/base.py`, `mock.py`, `gemini.py` | SDK 3.0.0 construction and fake call/response tests; no real API session tested |
| Audio/wake | `voice/audio.py`, `wakeword.py`, `satellite.py` | Real library inference integration, bounded PCM queues and activation gate; no installed weights/device evaluation |
| Server architecture | `server.py`, `voice/connection.py` | Authenticated HTTPS-capable heartbeat client; loopback HTTP service intended behind TLS; no remote job execution |
| Credentials (04) | `storage/credentials.py` | Native keyring adapters only; no plaintext fallback; actual OS keyring not available here |
| Audit/replay (05) | `storage/store.py`, SQL migration | Metadata-only SQLite WAL, unique invocation reservation and no restart replay; no full durable DAG orchestration |
| Autostart | `scripts/render_autostart.py` | Least-privilege Windows task XML/macOS launch agent/Linux user-service generation; not installed or device-tested |
| Verification | Provider verifiers + test suite | Independent app PID/creation-time re-read; reads are bounded observations, not verified admin writes |

## ADR-001: scope and release naming

Ship a runnable **0.1 engineering preview**, not a “complete V1” label. Broad privileged providers cannot be responsibly claimed implemented/verified from a Linux sandbox. Every missing family is a release blocker. Missing code is not an “OS unsupported” feature. The project retains the complete target scope rather than silently moving it to iteration 2.

## ADR-002: conservative action surface

Live exposes read-only tools. Exact local `/call` plus trusted config opt-in can request the allowlisted app-launch tool, with separate approval. No generic shell, model-controlled imports, process termination, deletion, firewall or admin mutation exists. Sensitive read `sessions.list` also needs consent. This deliberately stops short of unrestricted interpretation/planning and the production AC5/AC6 gates.

## ADR-003: thin persistence deviation

The first tested vertical slice uses stdlib SQLite with a versioned SQL migration, not the full SQLAlchemy/Alembic/outbox architecture in 05. This keeps foundation runnable but does **not** satisfy AC2/AC7. It stores invocation/audit metadata only, never task transcripts/results. Unique reservations prevent call-ID replay; there is no durable resumable task graph, worker lease, crash reconciliation or conversational memory. Those remain V1 release blockers.

## ADR-004: ONNX wake runtime

Use explicit openWakeWord acoustic inference; no substring wake trigger and no Porcupine. Library 0.6.0's Linux metadata requires old TFLite wheels incompatible with some Python 3.12/3.13 environments even when using ONNX. Supply an explicit `--no-deps` installer only for the library, paired with separately declared ONNX dependencies. This dependency exception must be reviewed on each target platform; it is not a claim that upstream's TFLite requirement is installed. Models are downloaded only by explicit owner command after source/size/license/destination disclosure.
