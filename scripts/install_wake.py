"""Explicit ONNX-only installation; no downloads until --confirm. Does NOT install model weights."""

import argparse
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument("--confirm", action="store_true")
a = p.parse_args()
print("Installs openwakeword 0.6.0 from PyPI (Apache-2.0 code) into the active Python environment.")
print(
    'Uses --no-deps intentionally to avoid upstream Linux tflite-runtime dependency; ONNX dependencies must first be installed with pip install -e ".[wake,audio]".'
)
print(
    "No model assets are downloaded. Pretrained wake models have separate CC BY-NC-SA licensing; review before use."
)
if not a.confirm:
    print("No changes made. Review then rerun with --confirm.")
else:
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "openwakeword==0.6.0"], check=True)
