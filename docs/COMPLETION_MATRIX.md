# V1 completion matrix — 55 planned families

**Engineering preview, NOT a completed V1 release.** Missing code is recorded as `not_implemented`, never as an OS limitation. Even partial rows remain release blockers until all planned operations and target-platform evidence exist.

Actual schemas: `tool-schemas.json`. Machine-readable full inventory: `src/jarvis/catalog.json`.

| ID | Family | Registered tools | State |
|---|---|---|---|
| source_01 | Process selection/termination | process.list, process.terminate | partial · BLOCKER |
| source_02 | Zombie inspection | process.zombies | partial · BLOCKER |
| source_03 | Priority/affinity | process.priority | partial · BLOCKER |
| source_04 | Process ancestry | process.ancestry | partial · BLOCKER |
| source_05 | Background jobs | — | not_implemented · BLOCKER |
| source_06 | IPC inspection/cleanup | ipc.inspect | partial · BLOCKER |
| source_07 | Semantic file search | filesystem.list_directory, filesystem.get_metadata, filesystem.search_names | partial · BLOCKER |
| source_08 | Storage analysis/cleanup | storage.analyze | partial · BLOCKER |
| source_09 | Permissions/ACL | permissions.inspect | partial · BLOCKER |
| source_10 | Symlink audit | filesystem.symlink_audit | partial · BLOCKER |
| source_11 | Directory watch | — | not_implemented · BLOCKER |
| source_12 | Archive/encrypt | archive.inspect | partial · BLOCKER |
| source_13 | Secure deletion | — | not_implemented · BLOCKER |
| source_14 | Mount/image | mounts.list | partial · BLOCKER |
| source_15 | Log archive/rotation | — | not_implemented · BLOCKER |
| source_16 | Port ownership | network.ports | partial · BLOCKER |
| source_17 | Interface configuration | network.interfaces, wifi.get_status, wifi.set_state, hotspot.get_status, hotspot.set_state | partial · BLOCKER |
| source_18 | Firewall | — | not_implemented · BLOCKER |
| source_19 | Per-process bandwidth | — | not_implemented · BLOCKER |
| source_20 | Connectivity diagnostics | network.diagnostics | partial · BLOCKER |
| source_21 | SSH key management | — | not_implemented · BLOCKER |
| source_22 | Connection audit | network.connections | partial · BLOCKER |
| source_23 | User/group management | — | not_implemented · BLOCKER |
| source_24 | Password policy | — | not_implemented · BLOCKER |
| source_25 | Sudo/admin policy | — | not_implemented · BLOCKER |
| source_26 | Login audit | — | not_implemented · BLOCKER |
| source_27 | Linux capabilities | security.linux_capabilities | partial · BLOCKER |
| source_28 | Integrity baselines | integrity.sha256 | partial · BLOCKER |
| source_29 | Memory/swap diagnostics | memory.diagnostics | partial · BLOCKER |
| source_30 | Driver/module management | drivers.linux_modules | partial · BLOCKER |
| source_31 | Services | services.status | partial · BLOCKER |
| source_32 | Scheduling | — | not_implemented · BLOCKER |
| source_33 | Hardware inventory | hardware.inventory | partial · BLOCKER |
| source_34 | Power management | — | not_implemented · BLOCKER |
| source_35 | Kernel/system logs | — | not_implemented · BLOCKER |
| addition_01 | Apps/windows | app.list_allowlisted, app.launch_allowlisted | partial · BLOCKER |
| addition_02 | Clipboard | clipboard.read, clipboard.write | partial · BLOCKER |
| addition_03 | Screen capture/recording | screen.capture | partial · BLOCKER |
| addition_04 | Display settings | display.get_brightness, display.set_brightness, display.get_resolution | partial · BLOCKER |
| addition_05 | Audio controls | audio.get_volume, audio.set_volume, audio.toggle_mute | partial · BLOCKER |
| addition_06 | Bluetooth | bluetooth.get_status, bluetooth.set_state | partial · BLOCKER |
| addition_07 | Printer | — | not_implemented · BLOCKER |
| addition_08 | Software inventory | software.python_inventory | partial · BLOCKER |
| addition_09 | Packages | packages.detect | partial · BLOCKER |
| addition_10 | OS updates | — | not_implemented · BLOCKER |
| addition_11 | Battery/thermal/health | health.battery | partial · BLOCKER |
| addition_12 | Lock/signout/restart/shutdown | power.lock, power.restart, power.shutdown, power.cancel_shutdown | partial · BLOCKER |
| addition_13 | User sessions/desktops | sessions.list | partial · BLOCKER |
| addition_14 | Environment/PATH | environment.inspect | partial · BLOCKER |
| addition_15 | Archive extraction | archive.extract | partial · BLOCKER |
| addition_16 | Duplicate files | filesystem.find_duplicates | partial · BLOCKER |
| addition_17 | Recycle Bin/Trash | — | not_implemented · BLOCKER |
| addition_18 | Backup/snapshot restore | — | not_implemented · BLOCKER |
| addition_19 | Clock/timezone/locale | clock.inspect | partial · BLOCKER |
| addition_20 | App permissions/privacy | — | not_implemented · BLOCKER |

## Interpretation

- All rows target Windows, macOS and Linux where the underlying capability exists. This is NOT a tested support claim.
- `process.zombies` returns unsupported on Windows (no POSIX zombie API). Linux IPC/modules/capabilities return unsupported on other OSes because the named kernel interfaces do not exist there.
- `services.status`: Windows SCM implemented via psutil; macOS via fixed launchctl profile; Linux systemd only when active. Other Linux init systems remain missing providers, not an assertion that services are impossible.
- No operation-specific stubs for unimplemented families are exposed to Gemini. A missing family fails catalog/release readiness, not runtime OS detection.
- Proposed operations are an implementation checklist, NOT invented runnable APIs. No claims of destructive-provider completeness.
- Run `python scripts/build_matrix.py` after registering tools. Unit tests ensure 35+20 rows and that every registered non-extra tool belongs to a row.
