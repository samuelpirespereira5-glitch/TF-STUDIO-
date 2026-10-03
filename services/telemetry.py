"""Logs de Telemetria e Auditoria: toda execução de ferramenta (Cyber Lab
ou não) fica registrada aqui, para o painel de auditoria."""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
try:
    from flask import has_request_context, request, g
except Exception:
    has_request_context = lambda: False
    request = g = None

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_FILE = DATA_DIR / "cyberlab.db"
_lock = threading.Lock()


def _conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_FILE, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute(
        """CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL, role TEXT, session_id TEXT, tool TEXT NOT NULL,
            target TEXT, ok INTEGER, duration_ms INTEGER, error TEXT, request_id TEXT
        )"""
    )
    # Migração: bancos antigos (ex.: data/cyberlab.db) não têm request_id.
    cols = {r[1] for r in c.execute("PRAGMA table_info(audit_log)").fetchall()}
    if "request_id" not in cols:
        try:
            c.execute("ALTER TABLE audit_log ADD COLUMN request_id TEXT")
            c.commit()
        except sqlite3.OperationalError:
            pass
    c.execute("CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_log(ts)")
    return c


def log(role, session_id, tool, target, ok, duration_ms=0, error=None, request_id=None):
    with _lock, _conn() as c:
        if request_id is None and has_request_context():
            request_id = getattr(g, "request_id", "")
        c.execute(
            "INSERT INTO audit_log (ts,role,session_id,tool,target,ok,duration_ms,error,request_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), role, session_id, tool, target or "",
             1 if ok else 0, int(duration_ms), (error or "")[:300], (request_id or "")[:100]),
        )


def recent(limit=100):
    with _conn() as c:
        rows = c.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]
