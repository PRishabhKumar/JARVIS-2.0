"""Show exact optional acoustic model download information; default is NO network/download."""

from pathlib import Path
import argparse
import hashlib
import urllib.request

BASE = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/"
ASSETS = [
    ("melspectrogram.onnx", "melspectrogram.onnx", 1087958),
    ("embedding_model.onnx", "embedding_model.onnx", 1326578),
    ("hey_jarvis_v0.1.onnx", "hey_jarvis.onnx", 1271370),
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--destination", default="models/hey_jarvis")
    p.add_argument("--download", action="store_true")
    p.add_argument("--accept-noncommercial-license", action="store_true")
    args = p.parse_args()
    destination = Path(args.destination).resolve()
    print("Source: upstream openWakeWord release v0.5.1, used by library v0.6.0.")
    print(
        "License: CC BY-NC-SA 4.0 model weights; Apache-2.0 library code. Review upstream README and model cards."
    )
    print("Model license:", "https://creativecommons.org/licenses/by-nc-sa/4.0/")
    for source, target, size in ASSETS:
        print(f"{BASE}{source}\n  {size:,} bytes -> {destination / target}")
    print(
        f"Total: {sum(a[2] for a in ASSETS):,} bytes. Expected sizes checked against upstream release metadata."
    )
    print("Models are not bundled or downloaded by JARVIS startup. No perfect-detection guarantee.")
    if not args.download:
        print("No changes. To download, explicitly pass --download --accept-noncommercial-license.")
        return
    if not args.accept_noncommercial_license:
        raise SystemExit("License acceptance is required before any download.")
    destination.mkdir(parents=True, exist_ok=True)
    for source, target, size in ASSETS:
        output = destination / target
        if output.exists():
            raise SystemExit("Refusing overwrite: " + str(output))
        temp = destination / (target + ".part")
        try:
            h = hashlib.sha256()
            count = 0
            with urllib.request.urlopen(BASE + source, timeout=30) as response, temp.open("xb") as f:
                while chunk := response.read(65536):
                    count += len(chunk)
                    if count > size:
                        raise ValueError("asset size exceeds release manifest")
                    h.update(chunk)
                    f.write(chunk)
            if count != size:
                raise ValueError("asset truncated or release changed")
            temp.replace(output)
            print(output.name, "sha256=" + h.hexdigest())
        finally:
            temp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
