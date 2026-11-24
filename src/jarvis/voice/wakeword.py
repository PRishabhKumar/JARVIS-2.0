from __future__ import annotations

import os
from pathlib import Path
import time


def find_wake_model(explicit_path: str | Path | None = None) -> Path | None:
    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    env_path = os.environ.get("JARVIS_WAKE_MODEL")
    if env_path:
        candidates.append(Path(env_path.strip("\"'")))

    cwd = Path.cwd()
    here = Path(__file__).resolve().parent
    candidates.extend([
        cwd / "models/hey_jarvis/hey_jarvis.onnx",
        cwd / "Code/jarvis/models/hey_jarvis/hey_jarvis.onnx",
        here.parents[1] / "models/hey_jarvis/hey_jarvis.onnx",
        here.parents[2] / "models/hey_jarvis/hey_jarvis.onnx",
        here.parents[3] / "models/hey_jarvis/hey_jarvis.onnx",
    ])
    for c in candidates:
        try:
            resolved = c.expanduser().resolve()
            if resolved.is_file():
                mel = resolved.parent / "melspectrogram.onnx"
                emb = resolved.parent / "embedding_model.onnx"
                if mel.is_file() and emb.is_file():
                    return resolved
        except Exception:
            continue
    return None


class LocalWakeDetector:
    """Real acoustic inference, not substring matching. Explicit assets only; never downloads models."""

    def __init__(self, path, name="hey_jarvis", threshold=0.5, cooldown=2.0):
        try:
            from openwakeword.model import Model
        except ImportError:
            import openwakeword.model as owm
            Model = owm.Model

        p = Path(path).expanduser().resolve(strict=True)
        if p.suffix.lower() != ".onnx":
            raise ValueError("explicit ONNX wake model required")
        self.name, self.threshold, self.cooldown = name, threshold, cooldown
        self.last_detection = -float("inf")
        # openWakeWord's shared feature models must also be installed explicitly.
        mel = p.parent / "melspectrogram.onnx"
        embedding = p.parent / "embedding_model.onnx"
        if not mel.is_file() or not embedding.is_file():
            raise FileNotFoundError("explicit shared ONNX feature models must be beside the wake model")
        self.model = Model(
            wakeword_models=[str(p)],
            inference_framework="onnx",
            melspec_model_path=str(mel),
            embedding_model_path=str(embedding),
        )
        if self.name not in self.model.models:
            raise ValueError("wake-name must exactly match a loaded model key")

    def score(self, pcm16):
        import numpy as np

        if len(pcm16) != 2560:
            raise ValueError("wake detector expects exactly 80 ms of PCM16 at 16 kHz")
        scores = self.model.predict(np.frombuffer(pcm16, dtype="<i2"))
        return float(scores[self.name])

    def feed(self, pcm16):
        score = self.score(pcm16)
        now = time.monotonic()
        if score >= self.threshold and now - self.last_detection >= self.cooldown:
            self.last_detection = now
            self.model.reset()
            return True
        return False

    def reset(self):
        self.model.reset()
        self.last_detection = -float("inf")
