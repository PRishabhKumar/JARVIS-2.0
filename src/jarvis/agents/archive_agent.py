from __future__ import annotations

from pathlib import Path, PurePosixPath
import zipfile
from jarvis.contracts import ToolResult, ToolSpec, Risk
from jarvis.registry import schema, PATH


def safe_member(name):
    p = PurePosixPath(name)
    return not (p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name or "\x00" in name)


def register(registry, settings, scope):
    async def inspect_archive(args):
        p = scope.resolve(args["path"])
        if p.stat().st_size > 32 * 1024 * 1024:
            return ToolResult.error("FILE_SIZE_LIMIT")
        try:
            with zipfile.ZipFile(p) as z:
                entries = z.infolist()
                if len(entries) > 1000:
                    return ToolResult.error("ARCHIVE_ENTRY_LIMIT")
                unsafe = [e.filename for e in entries if not safe_member(e.filename)]
                return ToolResult.ok(
                    entries=[{"name": e.filename, "size": e.file_size} for e in entries[:50]],
                    entry_count=len(entries),
                    unsafe_count=len(unsafe),
                    uncompressed_bytes=sum(e.file_size for e in entries),
                    note="Read-only inspection. No extraction, overwrite, decryption or execution",
                )
        except zipfile.BadZipFile:
            return ToolResult.error("ARCHIVE_INVALID")

    registry.register(
        ToolSpec(
            tool_id="archive.inspect",
            domain="source_12",
            module=__name__,
            description="Inspect ZIP directory and unsafe paths; do not extract",
            input_schema=schema({"path": PATH}, ["path"]),
        ),
        inspect_archive,
    )

    async def extract_archive(args):
        src = scope.resolve(args["path"])
        dest = scope.resolve(args["destination"], exists=False)
        dest.mkdir(parents=True, exist_ok=True)
        overwrite = args.get("overwrite", False)

        if src.stat().st_size > 64 * 1024 * 1024:
            return ToolResult.error("FILE_SIZE_LIMIT", message="Archive exceeds 64 MiB limit")

        try:
            with zipfile.ZipFile(src) as z:
                entries = z.infolist()
                if len(entries) > 2000:
                    return ToolResult.error("ARCHIVE_ENTRY_LIMIT", message="Too many entries in archive")
                total_uncompressed = sum(e.file_size for e in entries)
                if total_uncompressed > 256 * 1024 * 1024:
                    return ToolResult.error("UNCOMPRESSED_SIZE_LIMIT", message="Uncompressed size exceeds 256 MiB")

                for e in entries:
                    if not safe_member(e.filename):
                        return ToolResult.error("UNSAFE_ARCHIVE_MEMBER", message=f"Path traversal detected: {e.filename}")

                extracted = []
                for e in entries:
                    target_file = dest / e.filename
                    if target_file.exists() and not overwrite and not e.is_dir():
                        return ToolResult.error("DESTINATION_FILE_EXISTS", message=f"File exists: {e.filename}")
                    z.extract(e, dest)
                    extracted.append(e.filename)

                return ToolResult.ok(
                    destination=str(dest),
                    extracted_count=len(extracted),
                    uncompressed_bytes=total_uncompressed,
                )
        except zipfile.BadZipFile:
            return ToolResult.error("ARCHIVE_INVALID")

    async def verify_extracted(args, result):
        if result.status != "succeeded":
            return True
        dest = Path(args["destination"])
        return dest.is_dir()

    registry.register(
        ToolSpec(
            tool_id="archive.extract",
            domain="addition_15",
            module=__name__,
            description="Safely extract ZIP archive to an allowed destination folder",
            input_schema=schema(
                {"path": PATH, "destination": PATH, "overwrite": {"type": "boolean"}},
                ["path", "destination"],
            ),
            risk=Risk.R1,
            effect="local_write",
            rollback="extracted files remain in destination directory",
            verification="Confirm destination directory exists and contains extracted files",
        ),
        extract_archive,
        preview=lambda a: f"Extract archive {a['path']!r} to {a['destination']!r} (overwrite={a.get('overwrite', False)})",
        verifier=verify_extracted,
    )
