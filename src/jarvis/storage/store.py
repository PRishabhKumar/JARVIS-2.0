from __future__ import annotations

import sqlite3
import hashlib
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    """Only non-content invocation/audit metadata is persisted. No automatic write replay."""

    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
        self.db.execute("PRAGMA journal_mode=WAL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            raise ValueError("database schema newer than application")
        if version == 0:
            migration = files("jarvis.storage").joinpath("migrations/001_initial.sql").read_text()
            self.db.executescript(migration)
        self.db.commit()

    def reserve(self, session, call, binding, tool):
        call = hashlib.sha256(call.encode()).hexdigest()
        try:
            with self.db:
                self.db.execute(
                    "INSERT INTO invocations VALUES (?, ?, ?, ?, 'started', ?)",
                    (session, call, binding, tool, now()),
                )
            return None
        except sqlite3.IntegrityError:
            return self.db.execute(
                "SELECT binding,state FROM invocations WHERE session_id=? AND call_id=?", (session, call)
            ).fetchone()

    def finish(self, session, call, state):
        call = hashlib.sha256(call.encode()).hexdigest()
        with self.db:
            self.db.execute(
                "UPDATE invocations SET state=?,updated_at=? WHERE session_id=? AND call_id=?",
                (state, now(), session, call),
            )

    def audit(self, session, tool, risk, decision, outcome, duration_ms=0):
        # Fixed metadata fields only. Never accept arbitrary exception/argument/result payloads.
        with self.db:
            self.db.execute(
                "INSERT INTO audit VALUES (?,?,?,?,?,?,?,?)",
                (uuid4().hex, now(), session, tool, risk, decision, outcome, duration_ms),
            )

    def close(self):
        self.db.close()
