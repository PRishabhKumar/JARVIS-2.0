CREATE TABLE IF NOT EXISTS invocations (
 session_id TEXT NOT NULL, call_id TEXT NOT NULL, binding TEXT NOT NULL,
 tool TEXT NOT NULL, state TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(session_id, call_id)
);
CREATE TABLE IF NOT EXISTS audit (
 event_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, session_id TEXT NOT NULL,
 tool TEXT, risk TEXT, decision TEXT, outcome TEXT, duration_ms INTEGER NOT NULL
);
PRAGMA user_version = 1;
