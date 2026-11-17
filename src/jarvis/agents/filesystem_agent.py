from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import stat
import time
from pathlib import Path
import psutil
from jarvis.contracts import ToolResult, ToolSpec, Risk
from jarvis.registry import schema, PATH, TEXT, LIMIT


CATEGORY_EXTENSIONS: dict[str, set[str]] = {
    "Word": {".doc", ".docx", ".dot", ".dotx", ".odt", ".rtf"},
    "Excel": {".xls", ".xlsx", ".xlsm", ".xltx", ".csv", ".tsv"},
    "PowerPoint": {".ppt", ".pptx", ".potx", ".ppsx", ".odp"},
    "PDF": {".pdf"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".tiff", ".ico"},
    "Audio": {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"},
    "Video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"},
    "Code": {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json",
        ".cpp", ".c", ".h", ".cs", ".java", ".go", ".rs", ".sql", ".sh", ".ps1",
    },
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
    "Documents": {".txt", ".md", ".log", ".tex"},
}


def classify_extension(ext: str) -> str:
    ext_lower = ext.lower()
    for cat, exts in CATEGORY_EXTENSIONS.items():
        if ext_lower in exts:
            return cat
    return "Other" if ext else "No_Extension"


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

    async def locate_path(args):
        query = args["query"].strip()
        search_root = args.get("root")
        target_type = args.get("type", "any")
        max_depth = min(args.get("max_depth", 5), 8)
        limit = min(args.get("limit", 10), 20)

        skip_dirs = {
            ".git", ".venv", "node_modules", "appdata", "$recycle.bin",
            "system volume information", "windows", "program files", "program files (x86)",
            ".cache", "__pycache__", ".vscode", ".idea",
        }

        roots_to_search = []
        if search_root:
            try:
                roots_to_search.append(scope.resolve(search_root))
            except (OSError, PermissionError):
                return ToolResult.error("ROOT_OUT_OF_SCOPE", message=f"Search root {search_root} is not allowed")
        else:
            roots_to_search.extend(scope.roots)

        matches = []
        query_cf = query.casefold()

        for r in roots_to_search:
            if not r.is_dir():
                continue
            base_depth = len(r.parts)
            for current_root, dirs, files in os.walk(r, followlinks=False):
                current_path = Path(current_root)
                current_depth = len(current_path.parts) - base_depth
                if current_depth > max_depth:
                    dirs.clear()
                    continue

                dirs[:] = [d for d in dirs if d.casefold() not in skip_dirs and not d.startswith(".")]

                if target_type in ("directory", "any"):
                    for d in dirs:
                        if query_cf == d.casefold() or query_cf in d.casefold():
                            d_full = current_path / d
                            try:
                                resolved = scope.resolve(str(d_full))
                                matches.append({
                                    "path": str(resolved),
                                    "name": d,
                                    "type": "directory",
                                    "exact": query_cf == d.casefold(),
                                })
                            except (OSError, PermissionError):
                                pass
                            if len(matches) >= limit:
                                break

                if target_type in ("file", "any") and len(matches) < limit:
                    for f in files:
                        if query_cf == f.casefold() or query_cf in f.casefold():
                            f_full = current_path / f
                            try:
                                resolved = scope.resolve(str(f_full))
                                matches.append({
                                    "path": str(resolved),
                                    "name": f,
                                    "type": "file",
                                    "exact": query_cf == f.casefold(),
                                })
                            except (OSError, PermissionError):
                                pass
                            if len(matches) >= limit:
                                break

                if len(matches) >= limit:
                    break
                await asyncio.sleep(0)

        matches.sort(key=lambda m: (not m["exact"], len(m["path"])))
        return ToolResult.ok(
            query=query,
            found=len(matches) > 0,
            matches=matches,
            count=len(matches),
            best_match=matches[0]["path"] if matches else None,
        )

    async def inspect_directory(args):
        p = scope.resolve(args["path"])
        if not p.is_dir():
            return ToolResult.error("NOT_A_DIRECTORY", message=f"{p} is not a directory")

        recursive = args.get("recursive", False)
        extensions = {}
        categories = {}
        file_list = []
        dir_count = 0
        total_bytes = 0

        if recursive:
            walker = os.walk(p, followlinks=False)
        else:
            walker = [(str(p), [], [e.name for e in os.scandir(p) if e.is_file()])]
            dir_count = sum(1 for e in os.scandir(p) if e.is_dir())

        for current_root, dirs, files in walker:
            if recursive:
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                dir_count += len(dirs)
            for fname in files:
                fpath = Path(current_root) / fname
                try:
                    s = fpath.stat()
                    size = s.st_size
                    total_bytes += size
                    ext = fpath.suffix.lower()
                    cat = classify_extension(ext)
                    extensions[ext] = extensions.get(ext, 0) + 1
                    categories[cat] = categories.get(cat, 0) + 1
                    if len(file_list) < 100:
                        file_list.append({
                            "name": fname,
                            "path": str(fpath),
                            "extension": ext,
                            "category": cat,
                            "size_bytes": size,
                        })
                except (OSError, PermissionError):
                    continue
                await asyncio.sleep(0)

        return ToolResult.ok(
            path=str(p),
            file_count=sum(extensions.values()),
            directory_count=dir_count,
            total_bytes=total_bytes,
            extensions=extensions,
            categories=categories,
            sampled_files=file_list,
        )

    async def create_directory(args):
        p = scope.resolve(args["path"], exists=False)
        if p.exists() and not p.is_dir():
            return ToolResult.error("FILE_ALREADY_EXISTS", message=f"{p} exists and is not a directory")
        p.mkdir(parents=True, exist_ok=True)
        return ToolResult.ok(
            path=str(p),
            created=True,
            directory=p.name,
        )

    async def move_items(args):
        dest = scope.resolve(args["destination"])
        if not dest.is_dir():
            return ToolResult.error("DESTINATION_NOT_A_DIRECTORY", message=f"{dest} is not a directory")

        sources = args["sources"]
        overwrite = args.get("overwrite", False)
        moved = []
        errors = []

        for src_str in sources:
            try:
                src = scope.resolve(src_str)
                if not src.exists():
                    errors.append({"source": src_str, "error": "NOT_FOUND"})
                    continue
                target = dest / src.name
                if target.exists() and not overwrite:
                    errors.append({"source": src_str, "error": "TARGET_ALREADY_EXISTS"})
                    continue
                shutil.move(str(src), str(target))
                moved.append({"source": str(src), "destination": str(target)})
            except Exception as e:
                errors.append({"source": src_str, "error": str(e)})
            await asyncio.sleep(0)

        return ToolResult.ok(
            destination=str(dest),
            moved_count=len(moved),
            moved=moved,
            error_count=len(errors),
            errors=errors,
        )

    async def copy_items(args):
        dest = scope.resolve(args["destination"])
        if not dest.is_dir():
            return ToolResult.error("DESTINATION_NOT_A_DIRECTORY", message=f"{dest} is not a directory")

        sources = args["sources"]
        overwrite = args.get("overwrite", False)
        copied = []
        errors = []

        for src_str in sources:
            try:
                src = scope.resolve(src_str)
                if not src.exists():
                    errors.append({"source": src_str, "error": "NOT_FOUND"})
                    continue
                target = dest / src.name
                if target.exists() and not overwrite:
                    errors.append({"source": src_str, "error": "TARGET_ALREADY_EXISTS"})
                    continue
                if src.is_dir():
                    shutil.copytree(str(src), str(target), dirs_exist_ok=overwrite)
                else:
                    shutil.copy2(str(src), str(target))
                copied.append({"source": str(src), "destination": str(target)})
            except Exception as e:
                errors.append({"source": src_str, "error": str(e)})
            await asyncio.sleep(0)

        return ToolResult.ok(
            destination=str(dest),
            copied_count=len(copied),
            copied=copied,
            error_count=len(errors),
            errors=errors,
        )

    async def delete_items(args):
        paths = args["paths"]
        deleted = []
        errors = []

        for p_str in paths:
            try:
                p = scope.resolve(p_str)
                if not p.exists():
                    errors.append({"path": p_str, "error": "NOT_FOUND"})
                    continue
                if p.is_dir():
                    shutil.rmtree(str(p))
                else:
                    p.unlink()
                deleted.append(str(p))
            except Exception as e:
                errors.append({"path": p_str, "error": str(e)})
            await asyncio.sleep(0)

        return ToolResult.ok(
            deleted_count=len(deleted),
            deleted=deleted,
            error_count=len(errors),
            errors=errors,
        )

    async def organize_by_type(args):
        folder = scope.resolve(args["folder_path"])
        if not folder.is_dir():
            return ToolResult.error("NOT_A_DIRECTORY", message=f"{folder} is not a directory")

        grouping = args.get("grouping", "category")
        custom_mapping = args.get("custom_mapping")

        files_to_organize = []
        for entry in os.scandir(folder):
            if entry.is_file():
                ext = Path(entry.name).suffix.lower()
                files_to_organize.append((Path(entry.path), ext))

        if not files_to_organize:
            return ToolResult.ok(
                folder=str(folder),
                organized_count=0,
                message="No files found to organize in the directory."
            )

        target_groups: dict[str, list[Path]] = {}
        for fpath, ext in files_to_organize:
            if custom_mapping:
                assigned = False
                for group_name, ext_list in custom_mapping.items():
                    norm_exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in ext_list}
                    if ext in norm_exts:
                        target_groups.setdefault(group_name, []).append(fpath)
                        assigned = True
                        break
                if not assigned:
                    target_groups.setdefault("Other", []).append(fpath)
            elif grouping == "extension":
                group_name = f"{ext.lstrip('.').upper()}_Files" if ext else "No_Extension"
                target_groups.setdefault(group_name, []).append(fpath)
            else:
                cat = classify_extension(ext)
                target_groups.setdefault(cat, []).append(fpath)

        created_folders = []
        moved_files = []
        summary = {}

        for group_name, flist in target_groups.items():
            if not flist:
                continue
            dest_folder = folder / group_name
            dest_folder.mkdir(parents=True, exist_ok=True)
            created_folders.append(str(dest_folder))
            for f in flist:
                target_file = dest_folder / f.name
                if target_file.exists():
                    target_file = dest_folder / f"{f.stem}_{int(time.time())}{f.suffix}"
                shutil.move(str(f), str(target_file))
                moved_files.append({"file": f.name, "category": group_name, "to": str(target_file)})
            summary[group_name] = len(flist)

        return ToolResult.ok(
            folder=str(folder),
            organized_count=len(moved_files),
            folders_created=created_folders,
            summary=summary,
            grouping_used=grouping,
        )

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
        (
            "filesystem.locate_path",
            "extra",
            "Fast recursive search across drives for a folder or file by name",
            schema(
                {
                    "query": TEXT,
                    "root": PATH,
                    "type": {"type": "string", "enum": ["directory", "file", "any"]},
                    "max_depth": {"type": "integer", "minimum": 1, "maximum": 8},
                    "limit": LIMIT,
                },
                ["query"],
            ),
            locate_path,
        ),
        (
            "filesystem.inspect_directory",
            "extra",
            "Deep breakdown of files in a directory grouped by extensions, categories, counts, and sizes",
            schema({"path": PATH, "recursive": {"type": "boolean"}}, ["path"]),
            inspect_directory,
        ),
    ]:
        registry.register(
            ToolSpec(tool_id=name, domain=domain, module=__name__, description=desc, input_schema=params), fn
        )

    for name, domain, desc, params, fn, risk in [
        (
            "filesystem.create_directory",
            "extra",
            "Create a new directory (and parents) safely at the target path",
            schema({"path": PATH}, ["path"]),
            create_directory,
            Risk.R1,
        ),
        (
            "filesystem.move_items",
            "extra",
            "Move one or more files/directories into a target destination directory",
            schema(
                {"sources": {"type": "array", "items": PATH, "minItems": 1}, "destination": PATH, "overwrite": {"type": "boolean"}},
                ["sources", "destination"],
            ),
            move_items,
            Risk.R1,
        ),
        (
            "filesystem.copy_items",
            "extra",
            "Copy one or more files/directories into a target destination directory",
            schema(
                {"sources": {"type": "array", "items": PATH, "minItems": 1}, "destination": PATH, "overwrite": {"type": "boolean"}},
                ["sources", "destination"],
            ),
            copy_items,
            Risk.R1,
        ),
        (
            "filesystem.delete_items",
            "extra",
            "Delete one or more files or directories (mandatory confirmation guardrail)",
            schema({"paths": {"type": "array", "items": PATH, "minItems": 1}}, ["paths"]),
            delete_items,
            Risk.R2,
        ),
        (
            "filesystem.organize_by_type",
            "extra",
            "Intelligently organize files in a folder into subfolders by category, extension, or custom mapping",
            schema(
                {
                    "folder_path": PATH,
                    "grouping": {"type": "string", "enum": ["category", "extension"]},
                    "custom_mapping": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}},
                },
                ["folder_path"],
            ),
            organize_by_type,
            Risk.R1,
        ),
    ]:
        registry.register(
            ToolSpec(
                tool_id=name,
                domain=domain,
                module=__name__,
                description=desc,
                input_schema=params,
                risk=risk,
                effect="local_write",
                rollback="no automatic rollback",
            ),
            fn,
        )
