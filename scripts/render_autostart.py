"""Generate, but never install, a least-privilege user autostart definition."""

from __future__ import annotations

import argparse
import plistlib
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


def render(os_name, argv):
    if any("\n" in x or "\r" in x or "\x00" in x for x in argv):
        raise ValueError("invalid argument")
    if os_name == "linux":
        quoted = " ".join(
            '"' + a.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"' for a in argv
        )
        return (
            "[Unit]\nDescription=JARVIS local acoustic satellite (experimental)\nAfter=graphical-session.target\n\n"
            "[Service]\nType=simple\nExecStart=" + quoted + "\nRestart=on-failure\nRestartSec=10\n"
            "UMask=0077\nNoNewPrivileges=yes\n\n[Install]\nWantedBy=default.target\n"
        ).encode()
    if os_name == "macos":
        return plistlib.dumps(
            {
                "Label": "local.jarvis.satellite",
                "ProgramArguments": argv,
                "RunAtLoad": True,
                "KeepAlive": False,
                "ThrottleInterval": 10,
            }
        )
    root = ET.Element("Task", version="1.2", xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task")
    triggers = ET.SubElement(root, "Triggers")
    trigger = ET.SubElement(triggers, "LogonTrigger")
    ET.SubElement(trigger, "Enabled").text = "true"
    principals = ET.SubElement(root, "Principals")
    principal = ET.SubElement(principals, "Principal", id="Author")
    ET.SubElement(principal, "LogonType").text = "InteractiveToken"
    ET.SubElement(principal, "RunLevel").text = "LeastPrivilege"
    actions = ET.SubElement(root, "Actions", Context="Author")
    execute = ET.SubElement(actions, "Exec")
    ET.SubElement(execute, "Command").text = argv[0]
    ET.SubElement(execute, "Arguments").text = subprocess.list2cmdline(argv[1:])
    return ET.tostring(root, encoding="utf-16", xml_declaration=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--os", choices=["windows", "macos", "linux"], required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--wake-model", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--python", default=sys.executable)
    args = p.parse_args()
    argv = [
        str(Path(args.python).resolve()),
        "-m",
        "jarvis",
        "satellite",
        "--config",
        str(Path(args.config).resolve()),
        "--wake-model",
        str(Path(args.wake_model).resolve()),
    ]
    Path(args.output).write_bytes(render(args.os, argv))
    print("Generated only. Review the microphone/privacy behavior and paths before installing:", args.output)


if __name__ == "__main__":
    main()
