from __future__ import annotations
import asyncio

from pathlib import Path
from time import monotonic
from uuid import uuid4
from jarvis.bootstrap import build_registry
from jarvis.contracts import ExecutionContext
from jarvis.orchestrator import AgentCoordinator
from jarvis.policy import PolicyGate
from jarvis.storage.store import Store
from jarvis.storage.credentials import get_secret
from jarvis.models.gemini import GeminiSession
from .audio import AudioIO
from .wakeword import LocalWakeDetector


class ActivationGate:
    """No ambient audio leaves this state machine before a local acoustic wake event."""

    def __init__(self, detector, session_seconds=60):
        self.detector, self.session_seconds = detector, session_seconds
        self.active_until = 0.0

    def sleep(self):
        self.active_until = 0.0
        self.detector.reset()

    def feed(self, chunk, now=None):
        now = monotonic() if now is None else now
        if now < self.active_until:
            return "active"
        self.active_until = 0
        if self.detector.feed(chunk):
            self.active_until = now + self.session_seconds
            return "wake"  # Trigger frame is not sent to the cloud.
        return "local_only"


async def run_satellite(args, settings):
    if not args.wake_model:
        raise ValueError("supply --wake-model with explicitly installed ONNX assets")
    detector = LocalWakeDetector(args.wake_model, args.wake_name)
    gate = ActivationGate(detector)
    audio = AudioIO()
    registry = build_registry(settings)
    store = Store(Path(settings.state_dir) / "state.db")
    core = AgentCoordinator(registry, PolicyGate(), store, ExecutionContext(session_id=uuid4().hex))
    live = None
    slept = False
    heartbeat = None
    if args.server_url:
        from .connection import heartbeat_loop

        heartbeat = asyncio.create_task(
            heartbeat_loop(
                args.server_url,
                get_secret("server"),
                lambda: "active" if gate.active_until > monotonic() else "local_only",
                "personal-device",
            )
        )

    async def transcript(text):
        nonlocal slept
        # Exact high-priority stop control, NOT wake detection and never approval.
        normalized = text.strip().casefold().rstrip(".!?")
        if normalized in {"stop", "stop everything", "sleep", "go to sleep"}:
            gate.sleep()
            core.stop()
            slept = True
            audio.clear()
            if live:
                live.suppress_output = True
                await live.interrupt()
            print("\n[sleeping · microphone local only]")

    print("[EXPERIMENTAL satellite] Local acoustic wake detector; not target-device validated.")
    print(
        "[microphone LOCAL ONLY] No ambient PCM is sent before activation. Ctrl+C/hardware mute stops capture."
    )
    print("[privacy] After wake, audio goes to Google for a bounded 60-second conversation window.")
    try:
        async for chunk in audio.capture():
            activation = gate.feed(chunk)
            if activation == "local_only":
                if live:
                    await live.close()
                    live = None
                continue
            if activation == "wake":
                core.gate.reset()
                core.calls = 0
                core.context = ExecutionContext(session_id=uuid4().hex)
                core.cache.clear()
                slept = False
                print("[wake detected · connecting]")
                live = GeminiSession(
                    get_secret("gemini"),
                    args.model or settings.model,
                    registry,
                    core,
                    emit=lambda t: print(t, end="", flush=True),
                    audio=audio,
                    on_transcript=transcript,
                )
                try:
                    await live.connect()
                except Exception:
                    await live.close()
                    live = None
                    gate.sleep()
                    print("[connection failed] Staying local. Wake again to retry; no automatic replay.")
                continue
            if slept or (live and live.failed):
                gate.sleep()
                if live:
                    await live.close()
                    live = None
                continue
            if live:
                await live.send_audio(chunk)
    finally:
        if heartbeat:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
        core.stop()
        if live:
            await live.close()
        audio.close()
        store.close()
