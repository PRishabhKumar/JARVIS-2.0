from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import platform
from pathlib import Path
from uuid import uuid4
from .bootstrap import build_registry
from .config import Settings
from .contracts import ExecutionContext, ToolCall, Risk
from .models.mock import MockSession
from .orchestrator import AgentCoordinator
from .policy import PolicyGate
from .storage.store import Store

BANNER = "JARVIS 0.1 · CLI engineering preview · not a completed V1 release"
HELP = """/help                  show commands
/tools [query]         discover actual registered typed tools
/call tool.id {JSON}   request a tool through the policy gate
/status                invocation budget and busy/stop state
/stop                  cancel active work; never replay writes
/reset                 reset stop latch after cancellation
/quit                  close session
Mock fixtures: What time is it? | List this folder | Show processes | Show hardware
Live mode: free-form text is interpreted by Gemini, not a local intent table.
"""


class Terminal:
    def __init__(self):
        self.pending = None
        self.phrase = None

    async def confirm(self, request):
        if self.pending is not None:
            return False
        self.pending = asyncio.get_running_loop().create_future()
        self.phrase = request.phrase
        print(f"\n[awaiting confirmation · {request.risk}] {request.preview}")
        print(f"Type exactly {request.phrase!r} within 60 seconds, or anything else to deny.")
        try:
            return await self.pending
        finally:
            self.pending = None
            self.phrase = None

    def answer(self, line):
        if self.pending is None:
            return False
        if not self.pending.done():
            self.pending.set_result(line == self.phrase)
        return True


def parser():
    p = argparse.ArgumentParser(description=BANNER)
    p.add_argument(
        "command",
        nargs="?",
        choices=["run", "tools", "doctor", "credentials", "satellite", "server", "evaluate-wake", "smoke"],
        default="run",
    )
    p.add_argument("arguments", nargs="*")
    p.add_argument("--config")
    p.add_argument("--mode", choices=["mock", "live"], default="mock")
    p.add_argument("--once", help="One text request; all confirmations denied in this mode")
    p.add_argument("--root", help="Explicit allowed file root")
    p.add_argument("--model", help="Exact model ID; defaults to settings.model")
    p.add_argument("--audio", action="store_true", help="Enable audio output in Live mode")
    p.add_argument("--wake-model", help="Explicit locally installed ONNX wake model")
    p.add_argument("--wake-name", default="hey_jarvis")
    p.add_argument("--server-url", help="Optional authenticated HTTPS heartbeat server; no remote execution")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    return p


async def run(args, settings):
    registry = build_registry(settings)
    terminal = Terminal()
    state = Path(settings.state_dir)
    store = Store(state / "state.db")
    context = ExecutionContext(
        session_id=uuid4().hex,
        max_calls=settings.max_calls,
        maximum_effect="local_write" if settings.allow_mutations else "read",
    )
    gate = PolicyGate(
        terminal.confirm if not args.once else (lambda _: asyncio.sleep(0, result=False)),
        threshold=Risk(settings.confirmation_threshold),
    )
    core = AgentCoordinator(registry, gate, store, context)
    session = MockSession()
    live = None
    work = None
    try:
        if args.mode == "live":
            from .models.gemini import GeminiSession
            from .storage.credentials import get_secret
            from .voice.audio import AudioIO

            print("[privacy] Typed text, approved tool results and activated microphone audio go to Google.")
            print(
                "[safety] Live model sessions expose read-only tools only. Mutations use /call with local approval."
            )
            audio = AudioIO() if args.audio else None
            live = GeminiSession(
                get_secret("gemini"),
                args.model or settings.model,
                registry,
                core,
                emit=lambda t: print(t, end="", flush=True),
                audio=audio,
            )
            await live.connect()
            session = live
        print(BANNER)
        print("[ready] /help for commands. Files restricted to: " + ", ".join(settings.roots))
        if args.once:
            if live:
                await live.text_turn(args.once)
            else:
                await core.run_turn(session, args.once)
            return

        async def handle(line):
            if line.startswith("/call "):
                _, name, raw = line.split(" ", 2)
                result = await core.dispatch(
                    ToolCall(call_id=uuid4().hex, name=name, arguments=json.loads(raw))
                )
                print(json.dumps(result.model_dump(), indent=2))
            elif line == "/ptt" and live:
                await live.push_to_talk(seconds=5)
            elif live:
                await live.text_turn(line)
            else:
                await core.run_turn(session, line)

        def done(task):
            if task.cancelled():
                print("[cancelled]")
                return
            if task.exception():
                print(
                    "[error] Request failed safely. Check input JSON, connectivity, configuration or quota; raw diagnostics suppressed."
                )

        while True:
            try:
                line = (await asyncio.to_thread(input, "\njarvis> ")).strip()
            except EOFError:
                break
            if line == "/stop":
                core.stop()
                if work:
                    work.cancel()
                if live:
                    await live.stop()
                print(
                    "[stopped] Active work cancelled. "
                    + ("Restart CLI to reconnect Live." if live else "Use /reset for a new request.")
                )
                continue
            if line == "/quit":
                break
            if terminal.answer(line):
                continue
            if line == "/help":
                print(
                    HELP
                    + (
                        "/ptt                   capture microphone for 5 seconds (explicit activation)\n"
                        if live
                        else ""
                    )
                )
            elif line.startswith("/tools"):
                query = line[6:].strip().casefold()
                for t in registry.all():
                    if not query or query in (t.spec.tool_id + " " + t.spec.description).casefold():
                        print(f"{t.spec.tool_id:32} {t.spec.risk.value}  {t.spec.description}")
            elif line == "/status":
                print(
                    f"calls={core.calls}/{context.max_calls}; stopped={gate.stopped}; busy={bool(work and not work.done())}"
                )
            elif line == "/reset":
                if live and not live.session:
                    print("[disconnected] Restart CLI to establish a fresh Live session.")
                    continue
                if not work or work.done():
                    gate.reset()
                    print("[ready] stop latch reset; no queued call replayed")
                else:
                    print("[busy] Wait for cancellation to finish")
            elif line:
                if gate.stopped:
                    print("[stopped] Use /reset")
                elif work and not work.done():
                    print("[busy] Finish or /stop the active request")
                else:
                    work = asyncio.create_task(handle(line))
                    work.add_done_callback(done)
    finally:
        core.stop()
        if work and not work.done():
            work.cancel()
            await asyncio.gather(work, return_exceptions=True)
        await session.close()
        store.close()


def main():
    args = parser().parse_args()
    try:
        settings = Settings.load(args.config)
        if os.environ.get("JARVIS_MODEL"):
            settings = settings.model_copy(update={"model": os.environ["JARVIS_MODEL"]})
        if args.command == "smoke":
            args.once = "What time is it?"
        if args.root:
            settings = settings.model_copy(update={"roots": [str(Path(args.root).resolve(strict=True))]})
        if args.command == "credentials":
            from .storage.credentials import set_secret, delete_secret

            if len(args.arguments) != 2 or args.arguments[0] not in ("set", "delete"):
                raise ValueError("Usage: jarvis credentials set|delete gemini|server")
            operation, name = args.arguments
            if operation == "set":
                secret = getpass.getpass("Credential (local secure input; not sent to model): ")
                set_secret(name, secret)
                del secret
            else:
                delete_secret(name)
            print("Credential operation completed via OS keyring.")
        elif args.command == "doctor":
            import importlib.metadata

            print(BANNER)
            print("Runtime:", platform.system(), platform.release(), platform.python_version())
            print("Audio, Windows/macOS providers, Live access and wake reliability require on-device tests.")
            for dep in ("google-genai", "sounddevice", "openwakeword", "onnxruntime", "psutil"):
                try:
                    print(dep, importlib.metadata.version(dep))
                except importlib.metadata.PackageNotFoundError:
                    print(dep, "not installed")
            print("API account/quota and microphone NOT tested by doctor.")
        elif args.command == "tools":
            registry = build_registry(settings)
            print(json.dumps([t.spec.model_dump(mode="json") for t in registry.all()], indent=2))
        elif args.command == "satellite":
            from .voice.satellite import run_satellite

            asyncio.run(run_satellite(args, settings))
        elif args.command == "server":
            from .server import serve

            serve(args)
        elif args.command == "evaluate-wake":
            from .voice.evaluate import main as evaluate

            evaluate(args.arguments)
        else:
            asyncio.run(run(args, settings))
    except KeyboardInterrupt:
        print("\n[stopped] Interrupted by local user.")
    except Exception:
        print(
            "[error] Startup/request failed. Check configuration, optional dependencies, OS keyring, model access and audio devices. No raw exception or credential was logged."
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
