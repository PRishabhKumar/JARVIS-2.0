"""Generate an honest complete-inventory matrix, not placeholder executable tools."""

import json
from pathlib import Path
from jarvis.bootstrap import build_registry
from jarvis.config import Settings

SOURCE = [
    ("Process selection/termination", "list, terminate"),
    ("Zombie inspection", "inspect"),
    ("Priority/affinity", "inspect, set_priority, set_affinity"),
    ("Process ancestry", "inspect"),
    ("Background jobs", "start, status, cancel, restart_recovery"),
    ("IPC inspection/cleanup", "inspect, cleanup"),
    ("Semantic file search", "list_directory, search_names, get_metadata, semantic_search"),
    ("Storage analysis/cleanup", "analyze, preview_cleanup, cleanup"),
    ("Permissions/ACL", "inspect, inspect_acl, modify_acl"),
    ("Symlink audit", "audit"),
    ("Directory watch", "start, events, stop"),
    ("Archive/encrypt", "inspect, create_archive, encrypt"),
    ("Secure deletion", "limitations, ordinary_delete, crypto_erase_guidance"),
    ("Mount/image", "list, mount, unmount, image"),
    ("Log archive/rotation", "inspect, archive, rotate"),
    ("Port ownership", "list"),
    ("Interface configuration", "inspect, configure"),
    ("Firewall", "inspect, preview_rule, apply_rule, recover"),
    ("Per-process bandwidth", "inspect"),
    ("Connectivity diagnostics", "local_status, probe"),
    ("SSH key management", "public_key_metadata, create_key, remove_key"),
    ("Connection audit", "inspect"),
    ("User/group management", "inspect, create, update, remove"),
    ("Password policy", "inspect, update_policy"),
    ("Sudo/admin policy", "inspect, validate_dropin, apply_dropin"),
    ("Login audit", "inspect"),
    ("Linux capabilities", "inspect, modify"),
    ("Integrity baselines", "sha256, create_baseline, compare_baseline"),
    ("Memory/swap diagnostics", "inspect"),
    ("Driver/module management", "inspect_linux_modules, load_module, unload_module"),
    ("Services", "status, start, stop, restart"),
    ("Scheduling", "list, create, update, cancel"),
    ("Hardware inventory", "inspect"),
    ("Power management", "inspect, set_mode"),
    ("Kernel/system logs", "inspect"),
]
ADDED = [
    ("Apps/windows", "list_allowlisted, launch, quit, focus"),
    ("Clipboard", "read_with_consent, write_with_consent"),
    ("Screen capture/recording", "screenshot, record, stop"),
    ("Display settings", "inspect, set_resolution, set_scaling, set_orientation, set_layout"),
    ("Audio controls", "inspect, select_device, set_volume, mute"),
    ("Bluetooth", "discover, pair, connect, disconnect"),
    ("Printer", "discover, queue, pause, resume, cancel_job"),
    ("Software inventory", "os_inventory, python_inventory, launch, uninstall"),
    ("Packages", "detect_manager, install, update"),
    ("OS updates", "status, update, restart_workflow"),
    ("Battery/thermal/health", "battery, thermal, health"),
    ("Lock/signout/restart/shutdown", "preview, schedule, cancel"),
    ("User sessions/desktops", "list, switch, lock"),
    ("Environment/PATH", "inspect_names, inspect_path, set_user, set_system"),
    ("Archive extraction", "preview_safe_extraction, extract"),
    ("Duplicate files", "detect, review, deduplicate"),
    ("Recycle Bin/Trash", "inspect, restore, empty"),
    ("Backup/snapshot restore", "inspect, snapshot, restore"),
    ("Clock/timezone/locale", "inspect, set_timezone, set_clock, set_locale"),
    ("App permissions/privacy", "inspect_status, guided_settings"),
]


def main():
    root = Path(__file__).resolve().parents[1]
    registry = build_registry(Settings(roots=[str(root)]))
    entries = []
    for group, rows in [("source", SOURCE), ("addition", ADDED)]:
        for n, (name, operations) in enumerate(rows, 1):
            family_id = f"{group}_{n:02d}"
            tools = [t.spec for t in registry.all() if t.spec.domain == family_id]
            entries.append(
                {
                    "family_id": family_id,
                    "name": name,
                    "planned_operations": operations.split(", "),
                    "registered_tools": [t.tool_id for t in tools],
                    "modules": sorted({t.module for t in tools}),
                    "provider_targets": ["Windows", "macOS", "Linux"],
                    "status": "partial" if tools else "not_implemented",
                    "release_blocker": True,
                    "tests": "tests/test_providers.py; tests/test_foundation.py" if tools else None,
                    "limitations": "Read-oriented slice only; remaining operations and target-device validation required."
                    if tools
                    else "Missing provider implementation and operation-specific schemas/tests. NOT an OS unsupported claim.",
                }
            )
    assert len(entries) == 55
    (root / "src/jarvis/catalog.json").write_text(json.dumps(entries, indent=2) + "\n")
    (root / "docs/tool-schemas.json").write_text(
        json.dumps([t.spec.model_dump(mode="json") for t in registry.all()], indent=2) + "\n"
    )
    lines = [
        "# V1 completion matrix — 55 planned families",
        "",
        "**Engineering preview, NOT a completed V1 release.** Missing code is recorded as `not_implemented`, never as an OS limitation. Even partial rows remain release blockers until all planned operations and target-platform evidence exist.",
        "",
        "Actual schemas: `tool-schemas.json`. Machine-readable full inventory: `src/jarvis/catalog.json`.",
        "",
        "| ID | Family | Registered tools | State |",
        "|---|---|---|---|",
    ]
    for e in entries:
        lines.append(
            f"| {e['family_id']} | {e['name']} | {', '.join(e['registered_tools']) or '—'} | {e['status']} · BLOCKER |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- All rows target Windows, macOS and Linux where the underlying capability exists. This is NOT a tested support claim.",
        "- `process.zombies` returns unsupported on Windows (no POSIX zombie API). Linux IPC/modules/capabilities return unsupported on other OSes because the named kernel interfaces do not exist there.",
        "- `services.status`: Windows SCM implemented via psutil; macOS via fixed launchctl profile; Linux systemd only when active. Other Linux init systems remain missing providers, not an assertion that services are impossible.",
        "- No operation-specific stubs for unimplemented families are exposed to Gemini. A missing family fails catalog/release readiness, not runtime OS detection.",
        "- Proposed operations are an implementation checklist, NOT invented runnable APIs. No claims of destructive-provider completeness.",
        "- Run `python scripts/build_matrix.py` after registering tools. Unit tests ensure 35+20 rows and that every registered non-extra tool belongs to a row.",
        "",
    ]
    (root / "docs/COMPLETION_MATRIX.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
