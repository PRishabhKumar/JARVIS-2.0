# JARVIS · first runnable build

**Version 0.1.0 — CLI engineering preview. This is not the completed V1 defined by your final scope correction.**

A local-first Python command agent: text/mock and Gemini Live adapters share one typed tool registry, deterministic policy gate and audited execution boundary. There is no GUI dependency and no model-authored shell execution.

## What works in this build

- Runnable no-key mock CLI with full structured call → validation/policy → provider → result → response loop.
- **32 registered tools** spanning **28 partially implemented command families**, plus a clock utility. Discover schemas using `jarvis tools` or `/tools`.
- File name search/metadata, bounded storage reports, process inspection/ancestry/priority, network/interface/port reports, memory/hardware, ZIP inspection, integrity hashes, platform-aware service status, and more.
- Explicit read-only ceiling; separately opted-in, allowlisted app launch with a fresh local approval and process-identity verification.
- Payload/schema/path validation; timeouts; cancellation; duplicate call protection; metadata-only local SQLite audit; secure native keyring bridge.
- Gemini Live SDK transport with structured function responses, output transcription, optional PCM playback and explicit microphone capture.
- Experimental real openWakeWord acoustic detector integration and a resident satellite with local-only pre-wake processing and bounded multi-turn activation. Models/microphone **not tested here**.
- Authenticated heartbeat-only server/client, offline wake evaluator and **generated—not installed—**autostart definitions.

**Full-scope status:** 55 families inventoried; 28 partial, 27 not implemented. No family is certified complete across three operating systems. See [completion matrix](docs/COMPLETION_MATRIX.md) and [build report](docs/BUILD_REPORT.md). Privileged/destructive domains remain V1 release blockers, not iteration-2 features.

## Quick start — Windows PowerShell

Python **3.12 or 3.13**, 64-bit recommended. Extract the project ZIP and open its folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,live,server]"
.\.venv\Scripts\python.exe -m jarvis --once "What time is it?"
.\.venv\Scripts\python.exe -m jarvis --mode mock
```

No key, network API or microphone is required for mock mode. Activation of the virtual environment is optional; the explicit Python commands avoid PowerShell execution-policy changes. If Python 3.12 is not installed, use `py -3.13` consistently instead.

### macOS / Linux

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,live,server]'
python -m jarvis --once 'What time is it?'
python -m jarvis --mode mock
```

Tested here: Linux x86-64, Python 3.13.16. Windows/macOS setup and native adapters require real-OS validation; included CI is not evidence it has run.

## CLI examples

```text
What time is it?
List this folder
Show processes
Show hardware
/tools
/tools network
/call filesystem.search_names {"path":".","query":"report","limit":10}
/call storage.analyze {"path":"."}
/call process.list {"limit":5}
/status
/stop
/reset
/quit
```

The four mock phrases are **explicit demo fixtures, not an NLP engine**. They demonstrate dispatch without pretending that keyword routing is general intelligence. Free-form intent interpretation uses Gemini. `/call` accepts exact registered IDs/JSON from the local user and still passes through schema and policy checks. Full schemas: [tool-schemas.json](docs/tool-schemas.json).

The default file root is the launch directory. Narrow it explicitly:

```sh
python -m jarvis --root /absolute/path/to/a/disposable-folder --mode mock
```

Copy `config/example.json` to `config/local.json` and set absolute roots for normal use. Do not grant an entire drive/home folder. Run with `--config config/local.json`. Config rejects unknown fields and contains **no credentials**. State defaults to `~/.jarvis/state.db`.

## Gemini Live setup

```sh
python -m jarvis credentials set gemini
python -m jarvis doctor
python -m jarvis smoke --mode live
python -m jarvis --mode live
```

The credential prompt is local and hidden, writing directly to the native OS keyring. It is not a chat/tool prompt. No `.env` secret or command-line key argument is used. On headless Linux, configure/unlock SecretService/KWallet; startup fails closed without a recognized native keyring. Windows Credential Manager and macOS Keychain require on-device testing.

- Configured default: **`gemini-3.8-live`**. Official model/tool documentation was checked during this build. SDK pinned/tested locally: **`google-genai==3.0.0`**, using fake session responses, not paid API calls.
- **No exact model ID has been live-tested with your account.** Account access, region, model lifecycle, pricing and quotas still require validation. Usage is not promised free/unlimited.
- Cloud mode sends typed text, approved tool results and activated audio to Google. No audio/transcripts are persisted by JARVIS. Review [security/data flow](docs/SECURITY.md).
- Live exposes **read-only** tools; tool metadata never grants authorization. Outputs are untrusted data. The native-audio model uses `AUDIO` response modality plus output transcription even in typed CLI mode.
- No automatic reconnect/replay for failed Live sessions in this build. Restart after disconnect or `/stop`; writes are never blindly replayed.

### Explicit microphone capture and playback

```sh
python -m pip install -e '.[audio]'
python -m jarvis --mode live --audio
```

Type `/ptt` to open the microphone for **five seconds**. `/stop`, Ctrl+C or hardware mute stops capture/work. This is timed explicit capture, **not** a completed global hold-to-talk hotkey. Input: mono PCM16 16 kHz; output: PCM16 24 kHz. Use a headset. Device permission, PortAudio installation on Linux, echo cancellation and real barge-in must be tested on the target machine. `doctor` reports installed packages only, not hardware/API connectivity.

## Experimental hands-free satellite

The agreed targets are ≤0.5 false accepts/hour, ≤10% false rejects, p95 ≤800 ms, ≤10% one-core CPU and ≤250 MB RAM. **None have been measured on your devices.** Wake is opt-in and not release-certified.

Install the ONNX dependency set and then the explicitly reviewed library:

```sh
python -m pip install -e '.[live,audio,wake]'
python scripts/install_wake.py
python scripts/install_wake.py --confirm
python scripts/wake_assets.py
```

The final command only displays source, exact expected sizes, license and destinations; it does not download anything. The upstream library's Linux TFLite metadata is intentionally bypassed with `--no-deps` only for ONNX operation; review [ADR-004](docs/IMPLEMENTATION_MAP.md). Do not install its old TFLite requirement just to silence `pip check` in this optional profile.

If you agree to upstream model licensing (CC BY-NC-SA 4.0, noncommercial), explicitly download:

```sh
python scripts/wake_assets.py --download --accept-noncommercial-license
python -m jarvis satellite --config config/local.json --wake-model models/hey_jarvis/hey_jarvis.onnx
```

The fixed upstream model is **“hey Jarvis”**, not any arbitrary phrase. Other phrases need a suitable trained model and evaluation. Shared feature models must sit beside the wake model. No package/model installation happens automatically at startup. Model weights are not bundled.

Pre-wake PCM remains local. After an acoustic trigger, follow-up turns use a bounded **60-second** cloud conversation window without repeating the wake phrase. Trigger-frame audio is discarded. “Stop”, “stop everything”, “sleep”, and “go to sleep” are exact high-priority controls from active-session transcripts; an independent local spoken-stop detector is not implemented. Ctrl+C and hardware mute are the independent stop controls. Server interruptions clear playback/cancel tool tasks. A visible terminal is the current mic/status indicator.

This is experimental integration code, not a published reliability result. Validate before using autostart.

## Wake evaluation

Create local mono PCM16 16 kHz WAVs with no secrets, and a JSON manifest:

```json
{"negative":["background-1.wav"],"positive":[{"path":"wake-1.wav","wake_end_ms":1200}]}
```

```sh
python -m jarvis evaluate-wake recordings/manifest.json models/hey_jarvis/hey_jarvis.onnx
```

This local-only evaluator reports observed errors, latency, real-time-equivalent CPU and RSS; it never uploads WAVs or auto-certifies a release. No recordings are supplied or fabricated. See [wake evaluation plan](docs/WAKE_EVALUATION.md).

## Optional coordination server

```sh
python -m jarvis credentials set server
python -m jarvis server
```

Use a random credential of at least 32 characters; provision it locally through native keyrings on both sides. Server binds loopback, with authenticated health and device-heartbeat endpoints. To connect a satellite, use an owner-configured TLS reverse proxy and pass `--server-url https://your-server.example`. HTTP URLs and redirects are rejected by the satellite.

**Heartbeat only:** the server does not execute or delegate computer actions. Pairing, scoped remote jobs, durable conversations and production deployment remain V1 release blockers. Oracle/cloud hosting is not assumed or provisioned.

## Autostart — render, inspect, then opt in

```sh
python scripts/render_autostart.py --os windows --config config/local.json --wake-model models/hey_jarvis/hey_jarvis.onnx --output jarvis-task.xml
```

Use `--os macos` for a launch-agent plist, or `--os linux` for a user service. Generated files are **not installed automatically**. Review paths, microphone privacy and keyring availability first. Installation/removal instructions: [AUTOSTART.md](docs/AUTOSTART.md). No scheduled tasks, services or OS settings were changed during this build.

## Verification / development

```sh
python -m pytest -q
python -m ruff check src tests scripts
python -m compileall -q src
python scripts/build_matrix.py
```

CI workflow covers Python 3.12/3.13 on Linux/macOS/Windows using safe fixtures. It has not been run on those hosted runners here. Optional hardware/cloud/destructive VM acceptance is separate. `requirements-tested.txt` records exact tested top-level versions; `pyproject.toml` declares supported ranges and the exact Live SDK pin.

`python scripts/check_release.py` intentionally exits with status 1 while mandatory V1 requirements remain incomplete.

Read [build report](docs/BUILD_REPORT.md), [implementation decisions](docs/IMPLEMENTATION_MAP.md), [completion matrix](docs/COMPLETION_MATRIX.md) and [security limitations](docs/SECURITY.md) before treating this as a daily-driver or finished V1.
