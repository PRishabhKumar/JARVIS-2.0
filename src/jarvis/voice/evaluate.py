from __future__ import annotations

import argparse
import json
import math
import platform
import time
import wave
from pathlib import Path
import psutil
from .wakeword import LocalWakeDetector

TARGETS = {
    "false_accepts_per_hour_max": 0.5,
    "false_reject_rate_max": 0.10,
    "p95_latency_ms_max": 800,
    "cpu_one_core_percent_max": 10,
    "rss_mb_max": 250,
}


def compute_metrics(negative_hours, false_accepts, positive_trials, rejected, latencies):
    if negative_hours <= 0 or positive_trials <= 0:
        raise ValueError("both negative audio and positive trials required")
    values = sorted(latencies)
    return {
        "false_accepts_per_hour": false_accepts / negative_hours,
        "false_reject_rate": rejected / positive_trials,
        "p95_latency_ms": values[max(0, math.ceil(0.95 * len(values)) - 1)] if values else None,
    }


def main(arguments):
    p = argparse.ArgumentParser(description="Offline wake evaluation; local WAVs only; no uploads")
    p.add_argument("manifest", help="JSON with negative WAV paths and positive {path,wake_end_ms} clips")
    p.add_argument("model")
    p.add_argument("--name", default="hey_jarvis")
    p.add_argument("--output", default="wake-evaluation.json")
    args = p.parse_args(arguments)
    manifest_path = Path(args.manifest).resolve(strict=True)
    manifest = json.loads(manifest_path.read_text())
    detector = LocalWakeDetector(args.model, args.name)
    negatives, positives = manifest.get("negative", []), manifest.get("positive", [])
    negative_seconds, false_accepts, rejected, latencies = 0, 0, 0, []
    process = psutil.Process()
    cpu_start = sum(process.cpu_times()[:2])
    total_seconds, peak_rss = 0, 0
    inference_seconds = 0
    for clip, positive in [(p, False) for p in negatives] + [(p, True) for p in positives]:
        detector.reset()
        path = (manifest_path.parent / (clip["path"] if positive else clip)).resolve(strict=True)
        first_hit, frame_count, hits, last_hit = None, 0, 0, -float("inf")
        with wave.open(str(path), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
                raise ValueError("WAV clips must be mono PCM16 16 kHz")
            duration = wav.getnframes() / 16000
            total_seconds += duration
            while frame := wav.readframes(1280):
                if len(frame) < 2560:
                    frame += bytes(2560 - len(frame))
                frame_count += 1
                started = time.perf_counter()
                score = detector.score(frame)
                inference_seconds += time.perf_counter() - started
                if score >= detector.threshold and frame_count * 0.08 - last_hit > 2:
                    hits += 1
                    last_hit = frame_count * 0.08
                    if first_hit is None:
                        first_hit = frame_count * 0.08
                peak_rss = max(peak_rss, process.memory_info().rss)
        if positive:
            if first_hit is None:
                rejected += 1
            else:
                latencies.append(max(0, first_hit * 1000 - clip["wake_end_ms"]))
        else:
            negative_seconds += duration
            false_accepts += hits
    metrics = compute_metrics(negative_seconds / 3600, false_accepts, len(positives), rejected, latencies)
    metrics["cpu_one_core_percent"] = (sum(process.cpu_times()[:2]) - cpu_start) / total_seconds * 100
    metrics["rss_mb"] = peak_rss / 1_000_000
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "targets": TARGETS,
        "metrics": metrics,
        "negative_hours": negative_seconds / 3600,
        "positive_trials": len(positives),
        "false_accepts": false_accepts,
        "false_rejects": rejected,
        "inference_seconds": inference_seconds,
        "release_accepted": False,
        "limitations": "Offline estimate only. No mic/driver/network/AEC latency, no target-device sign-off. Dataset coverage and statistical confidence require owner review.",
    }
    Path(args.output).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
