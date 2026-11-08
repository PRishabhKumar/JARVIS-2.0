"""Fail closed when a preview is mistaken for the full V1 release."""

import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    rows = json.loads((root / "src/jarvis/catalog.json").read_text())
    blockers = [r for r in rows if r["release_blocker"] or r["status"] != "complete"]
    print(f"V1 release NOT ready: {len(blockers)}/55 families require completion/target-platform validation.")
    print(
        "Additional blockers: real Live account test; acoustic wake measurements on 3 OSes; durable goal/plan orchestration; full satellite/server coordination; privacy/hardware/VM release gates."
    )
    print("This does not prevent running the 0.1 engineering preview. See docs/BUILD_REPORT.md.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
