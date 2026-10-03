"""Registro completo de acessos (IP, rota, status, horário) em SQLite.

Diferente de `auth.log_access` (só logins, últimas 50 entradas em auth.json),
aqui fica CADA requisição relevante, para detectar varredura/força bruta.

Privacidade (LGPD): IP é dado pessoal. Por isso há retenção automática —
registros mais antigos que ACCESS_LOG_RETENTION_DAYS (padrão 90) são apagados.
Guardamos só o caminho (sem query string, que pode conter tokens).
"""
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_FILE = DATA_DIR / "cyberlab.db"
RETENTION_DAYS = int(os.getenv("ACCESS_LOG_RETENTION_DAYS", "90") or 90)
_lock = threading.Lock()
_last_purge = 0.0


def _conn():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_FILE, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute(
        """CREATE TABLE IF NOT EXISTS access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL, ip TEXT, method TEXT, path TEXT,
            status INTEGER, role TEXT, user_agent TEXT, request_id TEXT
        )"""
    )
    c.execute("CREATE INDEX IF NOT EXISTS ix_access_ts ON access_log(ts)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_access_ip ON access_log(ip)")
    # Compatibilidade com bancos v24 já existentes.
    cols = {row[1] for row in c.execute("PRAGMA table_info(access_log)").fetchall()}
    if "request_id" not in cols:
        c.execute("ALTER TABLE access_log ADD COLUMN request_id TEXT")
    c.execute("CREATE INDEX IF NOT EXISTS ix_access_request ON access_log(request_id)")
    return c


def _purge_locked(c):
    """Apaga registros vencidos; roda no máximo 1x por hora."""
    global _last_purge
    now = time.time()
    if now - _last_purge < 3600:
        return
    _last_purge = now
    limit = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
    c.execute("DELETE FROM access_log WHERE ts < ?", (limit,))


def record(ip, method, path, status, role="", user_agent="", request_id=""):
    try:
        with _lock, _conn() as c:
            c.execute(
                "INSERT INTO access_log (ts,ip,method,path,status,role,user_agent,request_id) VALUES (?,?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), (ip or "")[:64], (method or "")[:8],
                 (path or "")[:300], int(status), (role or "")[:20], (user_agent or "")[:200],
                 (request_id or "")[:100]),
            )
            _purge_locked(c)
    except Exception:
        pass  # log nunca pode derrubar a requisição


def recent(limit=100, ip=None):
    with _conn() as c:
        if ip:
            rows = c.execute("SELECT * FROM access_log WHERE ip=? ORDER BY id DESC LIMIT ?",
                             (ip, int(limit))).fetchall()
        else:
            rows = c.execute("SELECT * FROM access_log ORDER BY id DESC LIMIT ?",
                             (int(limit),)).fetchall()
        return [dict(r) for r in rows]


def top_ips(hours=24, limit=10):
    """IPs mais ativos na janela, com contagem total e de respostas 401/403/404
    (muitas negativas seguidas = provável varredura ou força bruta)."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with _conn() as c:
        rows = c.execute(
            """SELECT ip, COUNT(*) AS total,
                      SUM(CASE WHEN status IN (401,403,404) THEN 1 ELSE 0 END) AS denied,
                      MAX(ts) AS last_seen
               FROM access_log WHERE ts >= ? GROUP BY ip
               ORDER BY total DESC LIMIT ?""", (since, int(limit))).fetchall()
        return [dict(r) for r in rows]
