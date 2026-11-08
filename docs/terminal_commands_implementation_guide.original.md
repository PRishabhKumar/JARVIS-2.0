# JARVIS Cross-Platform Computer Control — Implementation Plan

## Goal
Build a natural-language computer-control layer for Windows, macOS, and Linux. The provided source lists 35 Linux-focused specialist agents. Reimplement their user capabilities as portable, typed tools with OS-specific providers; do not let the model compose arbitrary shell strings.

## Product requirements
- Requests resolve into a typed action plan: intent, arguments, target OS/provider, risk, preconditions, preview, confirmation requirement, execution, and result.
- Start with read-only discovery. For every mutation show the exact target and effect and request explicit confirmation. Require stronger confirmation for destructive, privileged, network, account, security, persistence, and power actions.
- Use least privilege; never silently elevate. No credential collection in prompts, shell history, logs, or model context.
- Commands are structured tool calls with schemas and allow-listed operations. Never interpolate user/model text into shell commands. Prefer native APIs; if CLI needed, invoke executable with argument array, no shell, timeout, bounded output, cancellation, and captured exit status.
- Every operation reports unsupported capability/provider, permission failure, partial result, and rollback availability honestly.
- Maintain an audit record (time, intent, normalized arguments, provider, confirmation, outcome) with secrets and sensitive content redacted.

## Architecture
1. **Conversation/router**: classify intent, collect missing parameters, produce typed action plan; disallow action execution from model-generated free-form commands.
2. **Policy/plan engine**: risk classification, validation, dry-run preview, confirmation, idempotency, cancellation, rollback hooks.
3. **Capability registry**: canonical command ID, JSON schema, read/write classification, OS support, permissions, dependencies, risk, timeout, tests.
4. **Platform providers**: `windows`, `macos`, `linux` implementations behind common interfaces. Detect OS/version and available capabilities at runtime; never assume Linux `/proc`, systemd, inotify, iptables, or a package manager.
5. **Execution broker**: isolated process invocation/native APIs, output normalization, resource limits, audit and error mapping.
6. **Background task service**: durable job IDs, status/cancel, bounded logs, completion notification, restart recovery.
7. **UI/API**: preview and confirmation; show progress, result, affected resource, and undo where supported.

## Cross-platform design rules
- Use Python standard interfaces where reliable (`psutil` for process/system stats; `pathlib`, `stat`, `os`, `hashlib`, `zipfile`, `tarfile`, `subprocess` with argv). Isolate optional dependencies and feature-detect them.
- Windows: PowerShell cmdlets/CIM, Windows service/task scheduler/firewall APIs, NTFS ACLs, Windows Defender Firewall; use Job Objects for process lifetime where practical.
- macOS: `launchctl`, `launchd`, `diskutil`, `networksetup`, PF firewall only when supported, POSIX APIs, FSEvents; respect TCC permissions and SIP.
- Linux: `/proc`, netlink, systemd only when detected, inotify/fanotify, POSIX tools, nftables/ufw only when installed.
- Translate canonical concepts (process, service, scheduled task, ACL, link, mount, interface) into provider-specific semantics. Expose capability differences and avoid false portability claims.

## Port the 35 source agents
Implement these as capability bundles, not independent unrestricted LLM agents:
1 process selection/termination; 2 zombie inspection; 3 priority/affinity; 4 process ancestry; 5 background jobs; 6 IPC inspection/cleanup (Linux first, elsewhere capability-dependent).
7 semantic file search; 8 storage analysis/cleanup; 9 permissions/ACL; 10 symlink audit; 11 directory watch; 12 archive/encrypt; 13 secure deletion; 14 mount/image; 15 log archive/rotation.
16 port ownership; 17 interface configuration; 18 firewall; 19 per-process bandwidth (capability-dependent); 20 connectivity diagnostics; 21 SSH key management; 22 connection audit with optional GeoIP disabled by default.
23 user/group management; 24 password policy; 25 sudo/admin policy (provider-specific and opt-in); 26 login audit; 27 capabilities (Linux-specific); 28 integrity baselines.
29 memory/swap diagnostics (never promise cache clearing improves performance); 30 driver/module management (Linux-specific); 31 services; 32 scheduling; 33 hardware inventory; 34 power management; 35 kernel/system logs.

Important corrections to source examples: never automatically kill a zombie's parent; signal the actual process only after identity revalidation and confirmation. Do not claim secure overwrite works on SSDs, copy-on-write, journaled, or cloud storage; offer cryptographic erasure guidance and ordinary deletion clearly labeled. Never clear caches or change kernel settings by default. Validate firewall rules with preview and recovery path. Do not write sudoers directly; use validated provider-supported drop-in and syntax check. Do not assume service names or distro-specific commands.

## Proposed new command families (20 additions)
These are additions beyond the 35 source agent domains; implement as canonical intents, each with provider adapters:
1. App launch/quit and window focus (no arbitrary UI automation by default).
2. Clipboard read/write with explicit user consent and secret masking.
3. Screenshot/screen recording with permission checks and visible capture status.
4. Display settings: resolution, scaling, orientation, monitor layout.
5. Audio controls: output/input device, volume, mute.
6. Bluetooth device discovery/pair/connect/disconnect.
7. Printer discovery, queue status, pause/resume/cancel jobs.
8. Software inventory and installed-app launch/uninstall (uninstall always confirmed).
9. Package installation/update via detected trusted package manager, with package/source preview.
10. OS update status and user-confirmed update/restart workflow.
11. Battery/thermal/health report (distinct from power mode).
12. Lock screen, sign out, restart, and shutdown with confirmation and delay/cancel.
13. User session/desktop management (switch/lock; no bypass of login controls).
14. Environment variables and PATH inspection/edit, scoped user/system with preview.
15. Archive extraction with path traversal and overwrite protection.
16. File duplicate detection and reviewable deduplication.
17. Recycle Bin/Trash inspection and restore/empty, with confirmation for empty.
18. Backup/restore snapshot orchestration through detected OS/provider facilities.
19. Time zone/clock and locale inspection/change with confirmation where needed.
20. App permission/privacy status inspection and guided settings links; do not bypass OS permission prompts.

Count: **20 new command families**. Existing-source baseline: 35 listed agent domains. A family can contain several typed operations; do not inflate count by counting aliases or CRUD verbs separately.

## Command contract
Every tool definition must include: stable ID/version; description; strict input schema; supported OS/capability predicate; permission needs; read/write and risk labels; timeout/output limits; preview function; execute function; verification function; rollback or explicit non-reversible status; normalized result/error schema; audit redaction policy.

Example canonical process API:
- `process.list(filters)` → PID, stable identity/start time, name, owner, CPU/RAM, state.
- `process.terminate(target, signal, force=false)` → revalidate identity immediately before action; graceful first; force only separately confirmed.
- `process.set_priority(target, priority)` → provider range and permission constraints.

## Risk and confirmation
- R0: read-only low sensitivity; execute directly.
- R1: reversible user-level change; preview and confirmation.
- R2: destructive, security, networking, persistence, account, or system-wide change; explicit confirmation with exact target/effect; privilege is separately granted by OS.
- R3: irreversible/high-impact (bulk deletion, disk/partition, secure erase, firewall lockout, shutdown); require typed confirmation phrase or UI confirmation and scoped target; offer cancellation/rollback where possible.
- Never infer confirmation from the original natural-language request. Confirmation binds to a specific immutable plan; any changed argument requires reconfirmation.

## Delivery phases
1. **Foundation**: inspect existing JARVIS architecture; create capability registry, schemas, policy engine, OS detection, provider interface, audit/error types, preview/confirm UI/API.
2. **Read-only MVP**: process/system info, file search/metadata, storage reports, ports/connections, connectivity, hardware, logs, services status, installed apps. Add tests across OS adapters and permission conditions.
3. **Safe user actions**: app launch, jobs, archive/extract, watches, clipboard/screen with consent, audio/display, printer, Bluetooth; implement cancellation and verification.
4. **Sensitive administration**: process termination, files/permissions, network/firewall, accounts, services/scheduler, package/update, mount, power, shutdown. Require plan confirmation, least privilege, and rollback/recovery design.
5. **Advanced/OS-specific**: IPC, capabilities/modules, ACL edge cases, per-process bandwidth, secure-delete limitations, sudo/admin policy. Mark unsupported features explicitly.
6. **Hardening and release**: threat review, signed provider binaries if any, dependency inventory, audit privacy review, accessibility, localization, OS/version compatibility matrix, upgrade/migration plan.

## Testing and acceptance
- Unit tests for intent-to-schema mapping, validation, risk, confirmation binding, redaction, timeouts, cancellation, and provider normalization.
- Provider contract tests using mocks; integration tests in Windows, macOS, and Linux CI runners. Tests must not alter host settings; use disposable fixtures/VMs for mutations.
- Test unsupported OS features and denied permissions as first-class outcomes.
- Acceptance: no model-originated shell string executes; every mutation is previewed and gated at the defined risk; target identity is revalidated for process/file/network changes; failed/partial operations are reported; all 35 source domains map to a supported, unsupported, or deferred capability; 20 additions have schemas and OS support declarations; platform tests pass.

## Agent instructions
Before coding, inspect the repository and preserve its framework, language, UI, and naming conventions. Implement the capability registry and policy/execution boundary before adding tools. Deliver a support matrix, schemas, provider code, tests, and user-facing examples. Do not claim feature parity across operating systems where APIs or permissions differ.
