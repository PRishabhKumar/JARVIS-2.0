# JARVIS — Technical Requirements Document (TRD)

**Version:** 0.1 | Companion to PRD v0.1

## 1. Core architectural idea
Replace "router + hand-written handlers" with **one agent loop over a dynamic tool registry**:

```
Mic → VAD/Wake → STT ─┐
                      ▼
              ┌── Agent Core (LLM, tool-calling loop) ──┐
   Memory ◄──►│  plan → call tool → observe → repeat    │──► TTS → Speaker
              └───────┬───────────────┬─────────────────┘
                      ▼               ▼
              Safety Gate        Tool Registry
          (risk tier, confirm)   ├─ MCP servers (GitHub, Gmail, Drive, …)
                      │          ├─ Native computer tools (shell, fs, apps)
                      ▼          └─ Computer-use fallback (screen + input)
                 Audit Log
```
The LLM sees tool *schemas*, not intents. "Open YouTube" and "pull up that cat video site" take the same path: the model picks a tool. Nothing in code mentions specific commands.

## 2. Technology choices
| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.11+ (asyncio) | Best ecosystem for audio, MCP SDK, automation; matches reference repo |
| Voice (option A, recommended to start) | **Gemini Live API** (native audio, function calling) | Lowest-latency single-hop voice, streaming, barge-in, tool calls built in |
| Voice (option B) | Pipeline: faster-whisper/Deepgram STT → LLM → Piper/ElevenLabs TTS | Model-agnostic, works offline-ish, more control; higher latency |
| Planner LLM | Behind an adapter: Gemini or Claude (configurable) | Strong tool use; swap without touching the rest |
| Tool protocol | **MCP** (official `mcp` Python SDK as client; stdio + streamable HTTP) | Your stated requirement; large server ecosystem |
| Computer control | `subprocess` (shell), `pywinauto`/UI Automation (Windows), `pyautogui`, `mss` screenshots, Playwright | Layered from most to least reliable |
| Memory | SQLite (+FTS5), optional embeddings (sqlite-vec) | Local, simple |
| UI | Lightweight overlay (Electron/Tauri or PyQt) + system tray | Live transcript, step view, kill button |
| Secrets | OS keyring; OAuth tokens never in config files | Security |

**Decision to make early:** A (fast, vendor-coupled) vs B (flexible, more work). Recommended: build the agent core against an interface so A is the first implementation of `VoiceFrontend` and B can follow.

## 3. Components

### 3.1 Voice layer
- Audio capture 16 kHz mono, VAD (Silero) to segment; push-to-talk hotkey plus optional wake word (openWakeWord).
- Streaming STT; partial transcripts forwarded to UI.
- Streaming TTS with sentence-level chunking; **barge-in**: VAD on mic during playback cancels TTS and the in-flight LLM turn.
- Echo cancellation: use headset by default; software AEC later.

### 3.2 Agent core
- Single async loop: build context (system prompt + memory snippets + conversation + selected tools) → model → if tool calls, pass through Safety Gate → execute (parallel when independent) → append observations → repeat until final answer or step/budget cap (default 25 steps).
- **Two-speed design:** fast voice model handles chit-chat and acknowledgements immediately ("Checking your repo…") while a planner model runs long tasks as a background job whose progress is narrated. Jobs are cancellable by voice.
- Structured tool results are truncated/summarized before re-entering context (large diffs, long emails).

### 3.3 Tool registry
- Loads `tools.yaml`: list of MCP servers (command/URL, env, auto-start, default risk overrides).
- On startup, connects, lists tools, normalizes to an internal schema `{name, description, params, server, risk}`.
- **Dynamic tool exposure:** with dozens of servers the full tool list hurts accuracy and cost. Keep a small always-on core set (shell, fs, open_app, search_tools, ask_user) and expose others via `search_tools(query)` backed by embeddings of tool descriptions; the agent loads the relevant ones for the turn.
- Hot reload on config change; per-call timeouts; health checks; auto-restart crashed servers.
- Candidate MCP servers (verify current maintainers/versions before adoption): GitHub official MCP server, a Gmail/Google Calendar/Drive MCP (Google now offers MCP endpoints; a community Workspace server is the fallback), Filesystem, Playwright MCP, a git MCP server.

### 3.4 Native computer tools (always available)
| Tool | Purpose |
|------|---------|
| `run_shell(cmd, cwd, timeout)` | PowerShell/bash; streams output; the workhorse (e.g. `git status`, `git diff --stat`) |
| `fs_*` | read/list/search/write with path allow-list |
| `open_app / open_path / focus_window` | `code <path>`, Antigravity CLI, `start`, etc. |
| `clipboard_get/set`, `notify` | Small utilities |
| `list_windows`, `ui_tree` | Accessibility-tree inspection (UIA) |
| `screenshot`, `click`, `type`, `hotkey`, `scroll` | **Computer-use fallback**: model sees screenshot, issues actions, verifies by re-screenshot |
Order of preference taught in the system prompt: MCP/API → shell/CLI → accessibility tree → pixel-level control.

### 3.5 Safety gate (most important non-feature)
- Every tool has a risk tier: **T0** read-only; **T1** reversible local write; **T2** destructive, external, or irreversible (send mail, `git push`, delete, payments, installing software, running unknown scripts).
- T2 requires explicit confirmation: the system speaks a *specific* summary ("Push 3 commits to origin/main on portfolio?") and waits for a yes. Confirmation is checked by a separate small classifier/regex on the *new* utterance, not by the planner trusting itself.
- Heuristic risk detection for shell: parse commands for `rm`, `del`, `git push`, `git reset --hard`, `format`, network upload, `curl | sh`; unknown → T2.
- Limits: max steps, max tool calls per minute, filesystem allow-list roots, deny-list (system dirs, credential stores).
- Kill switch: voice ("stop") and global hotkey cancel all jobs and release input control.
- **Prompt-injection defense:** tool output from mail/web/files is wrapped as untrusted data; policy: instructions found there are never followed; any T2 call that follows reading untrusted content shows the source in the confirmation.
- Full audit log (timestamp, utterance, tool, args, result summary, confirmation).

### 3.6 Memory
- Tables: `facts` (key/value + source), `projects` (alias → path, repo URL, preferred editor), `sessions` (summary), `prefs`.
- Retrieval: FTS5 + optional vectors; top-k injected into prompt. Resolve "the portfolio project" via alias match, then fuzzy folder search under configured roots; ask once if ambiguous, then store the alias.
- End-of-session summarization (as in the reference).
- The user can say "forget that"; deletion is real.

### 3.7 Proactive/background (opt-in)
Scheduler for user-requested monitors (e.g. "tell me if the build fails"); runs agent jobs headless with T0 tools only unless pre-authorized.

## 4. Worked flow: the git example
1. STT: "any pending changes left to commit or push in the portfolio project?"
2. Memory resolves alias → `D:\projects\portfolio`.
3. Agent calls `run_shell("git status --porcelain=v1 -b", cwd)` and `git log @{u}..HEAD --oneline` (T0).
4. Optionally `open_app("code", path)` if asked to open it; `git diff --stat` then targeted `git diff` of key files; output truncated.
5. Model summarizes by voice: "Four files changed in the resume section, plus two unpushed commits."
6. User: "Commit and push that." → agent drafts message → T2 gate speaks it and asks → on "yes", runs `git add -A && git commit -m … && git push` (checking for secrets in staged files first) → reports result.

## 5. Interfaces
```python
class VoiceFrontend: async def stream_in()->AsyncIterator[Utterance]; async def say(chunks); def cancel()
class ModelAdapter:  async def step(messages, tools)->ModelTurn    # text and/or tool calls
class Tool:          name; schema; risk; async def call(args)->ToolResult
class SafetyGate:    async def authorize(call, context)->Decision   # allow | confirm | deny
```
All swappable; the agent core depends only on these.

## 6. Performance targets and tactics
Keep prompts small (tool retrieval, truncated outputs); stream everything; prewarm MCP connections; parallelize independent tool calls; cache project resolution; use a fast model for acknowledgements.

## 7. Security and privacy
Tokens in keyring; least-privilege OAuth scopes (read-only Gmail by default, send scope only if enabled); local logs encrypted at rest optionally; document that transcripts, screenshots and tool outputs are sent to the model provider; "private mode" disables screenshots.

## 8. Testing strategy
- Unit: safety classifier, shell risk parser, alias resolution.
- Simulated: scripted tool servers returning fixtures to test the loop.
- **Utterance suite:** 50+ paraphrased requests per scenario, run text-in for regression; scored on success and on *zero unsafe actions*.
- Red-team: injected instructions in emails/files; misheard-command tests.
- Latency benchmarks per turn type.

## 9. Open questions
Voice option A vs B; Windows-only or cross-platform in v1; which Google MCP endpoint to use; whether Antigravity exposes a CLI/MCP interface for opening/inspecting projects (verify; fall back to `code` or UI control).
