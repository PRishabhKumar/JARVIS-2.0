from __future__ import annotations

import asyncio
import hashlib
import os
import stat
from pathlib import Path
import psutil
from jarvis.contracts import ToolResult, ToolSpec
from jarvis.registry import schema, PATH, TEXT, LIMIT


async def walk(scope, root, limit=2000):
    scanned = 0
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [n for n in dirs if not n.startswith(".") and not Path(base, n).is_symlink()][:100]
        for name in dirs + names:
            scanned += 1
            if scanned > limit:
                return
            try:
                p = scope.resolve(str(Path(base, name)))
            except (OSError, PermissionError):
                continue
            yield p
            await asyncio.sleep(0)


def register(registry, settings, scope):
    async def listing(args):
        p = scope.resolve(args["path"])
        items, skipped = [], 0
        with os.scandir(p) as entries:
            for entry in entries:
                if len(items) >= args.get("limit", 50):
                    break
                try:
                    resolved = scope.resolve(entry.path)
                    items.append(
                        {"name": entry.name, "directory": resolved.is_dir(), "symlink": entry.is_symlink()}
                    )
                except (OSError, PermissionError):
                    skipped += 1
                await asyncio.sleep(0)
        return ToolResult.ok(entries=items, skipped=skipped, bounded=True)

    async def metadata(args):
        p = scope.resolve(args["path"])
        s = p.stat()
        return ToolResult.ok(
            name=p.name,
            bytes=s.st_size,
            modified=s.st_mtime,
            directory=p.is_dir(),
            mode=stat.filemode(s.st_mode),
        )

    async def search(args):
        root = scope.resolve(args["path"])
        results = []
        async for p in walk(scope, root):
            if args["query"].casefold() in p.name.casefold():
                results.append(str(p.relative_to(root)))
            if len(results) >= args.get("limit", 50):
                break
        return ToolResult.ok(matches=results, bounded=True, search_type="filename only, not semantic")

    async def storage(args):
        root = scope.resolve(args["path"])
        largest, total = [], 0
        async for p in walk(scope, root):
            try:
                if p.is_file():
                    size = p.stat().st_size
                    total += size
                    largest.append({"path": str(p.relative_to(root)), "bytes": size})
                    largest.sort(key=lambda item: item["bytes"], reverse=True)
                    largest = largest[:20]
            except OSError:
                continue
        disk = psutil.disk_usage(str(root))
        return ToolResult.ok(
            largest_files=largest,
            sampled_bytes=total,
            bounded=True,
            disk={"total": disk.total, "free": disk.free},
            note="No cleanup performed",
        )

    async def symlinks(args):
        root = scope.resolve(args["path"])
        entries = []
        scanned = 0
        for base, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = dirs[:100]
            for name in dirs + names:
                scanned += 1
                if scanned > 2000:
                    return ToolResult.ok(links=entries, bounded=True)
                p = Path(base, name)
                if p.is_symlink():
                    try:
                        scope.resolve(str(p))
                        state = "in_scope"
                    except FileNotFoundError:
                        state = "broken"
                    except PermissionError:
                        state = "outside_scope_or_sensitive"
                    entries.append({"path": str(p.relative_to(root)), "state": state})
                    if len(entries) >= 100:
                        return ToolResult.ok(links=entries, bounded=True)
                await asyncio.sleep(0)
        return ToolResult.ok(links=entries, bounded=True)

    async def checksum(args):
        p = scope.resolve(args["path"])
        if not p.is_file() or p.stat().st_size > 32 * 1024 * 1024:
            return ToolResult.error("FILE_SIZE_OR_TYPE_LIMIT")
        before = p.stat()
        h = hashlib.sha256()
        with p.open("rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
                await asyncio.sleep(0)
        after = p.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            return ToolResult.error("RESOURCE_CHANGED")
        return ToolResult.ok(sha256=h.hexdigest(), bytes=after.st_size, name=p.name)

    async def permissions(args):
        p = scope.resolve(args["path"])
        s = p.stat()
        return ToolResult.ok(
            mode=stat.filemode(s.st_mode),
            uid=getattr(s, "st_uid", None),
            gid=getattr(s, "st_gid", None),
            note="POSIX mode only; Windows ACLs and macOS extended ACLs not implemented",
        )

    async def mounts(args):
        return ToolResult.ok(
            partitions=[
                {"device": d.device, "mountpoint": d.mountpoint, "fstype": d.fstype}
                for d in psutil.disk_partitions()[:50]
            ]
        )

    async def duplicates(args):
        root = scope.resolve(args["path"])
        min_bytes = args.get("min_bytes", 1024)
        limit = args.get("limit", 20)
        by_size: dict[int, list[Path]] = {}
        scanned = 0

        async for p in walk(scope, root, limit=3000):
            try:
                if p.is_file() and not p.is_symlink():
                    sz = p.stat().st_size
                    if sz >= min_bytes:
                        by_size.setdefault(sz, []).append(p)
            except (OSError, PermissionError):
                continue
            scanned += 1

        dupes = []
        for sz, files in by_size.items():
            if len(files) < 2:
                continue
            by_hash: dict[str, list[str]] = {}
            for f in files:
                try:
                    if sz > 32 * 1024 * 1024:
                        continue
                    h = hashlib.sha256(f.read_bytes()).hexdigest()
                    by_hash.setdefault(h, []).append(str(f))
                except (OSError, PermissionError):
                    continue
            for h, matching in by_hash.items():
                if len(matching) > 1:
                    dupes.append({"sha256": h, "size_bytes": sz, "paths": matching})
                    if len(dupes) >= limit:
                        break
            if len(dupes) >= limit:
                break

        return ToolResult.ok(duplicate_groups=dupes, count=len(dupes), scanned_files=scanned)

    for name, domain, desc, params, fn in [
        (
            "filesystem.list_directory",
            "source_07",
            "List directory names within configured roots",
            schema({"path": PATH, "limit": LIMIT}, ["path"]),
            listing,
        ),
        (
            "filesystem.get_metadata",
            "source_07",
            "Read in-scope file metadata",
            schema({"path": PATH}, ["path"]),
            metadata,
        ),
        (
            "filesystem.search_names",
            "source_07",
            "Bounded filename search (not semantic content search)",
            schema({"path": PATH, "query": TEXT, "limit": LIMIT}, ["path", "query"]),
            search,
        ),
        (
            "storage.analyze",
            "source_08",
            "Report largest sampled files and disk free space; no deletions",
            schema({"path": PATH}, ["path"]),
            storage,
        ),
        (
            "filesystem.symlink_audit",
            "source_10",
            "Audit symlinks without exposing out-of-scope targets",
            schema({"path": PATH}, ["path"]),
            symlinks,
        ),
        (
            "integrity.sha256",
            "source_28",
            "SHA256 an in-scope regular file, at most 32 MiB",
            schema({"path": PATH}, ["path"]),
            checksum,
        ),
        (
            "permissions.inspect",
            "source_09",
            "Read basic file mode; not full ACL support",
            schema({"path": PATH}, ["path"]),
            permissions,
        ),
        (
            "mounts.list",
            "source_14",
            "List mounted filesystem metadata; do not mount/unmount",
            schema(),
            mounts,
        ),
        (
            "filesystem.find_duplicates",
            "addition_16",
            "Scan directory to identify duplicate files by SHA256 checksum",
            schema({"path": PATH, "min_bytes": {"type": "integer", "minimum": 1}, "limit": LIMIT}, ["path"]),
            duplicates,
        ),
    ]:
        registry.register(
            ToolSpec(tool_id=name, domain=domain, module=__name__, description=desc, input_schema=params), fn
        )
