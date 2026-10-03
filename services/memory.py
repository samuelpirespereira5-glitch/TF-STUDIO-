"""Memória do Jarvis: fatos persistentes por sessão + resumo de conversa.
Persistida em SQLite; nada de chave/segredo é guardado aqui."""
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jarvis_memory.db"
_lock = threading.Lock()
MAX_FACTS = 60


def _c():
    DB.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS facts (id INTEGER PRIMARY KEY, owner TEXT, text TEXT, ts TEXT, UNIQUE(owner, text))")
    return c


def remember(owner, text):
    text = re.sub(r"\s+", " ", (text or "").strip())[:300]
    if len(text) < 3:
        raise ValueError("Memória vazia.")
    if re.search(r"(?i)(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|password\s*[:=])", text):
        raise ValueError("Não guardo segredos/credenciais na memória.")
    with _lock, _c() as c:
        c.execute("INSERT OR IGNORE INTO facts (owner,text,ts) VALUES (?,?,?)",
                  (owner, text, datetime.now(timezone.utc).isoformat()))
        c.execute("DELETE FROM facts WHERE owner=? AND id NOT IN (SELECT id FROM facts WHERE owner=? ORDER BY id DESC LIMIT ?)",
                  (owner, owner, MAX_FACTS))


def list_facts(owner):
    with _c() as c:
        return [dict(r) for r in c.execute("SELECT id,text,ts FROM facts WHERE owner=? ORDER BY id DESC", (owner,))]


def forget(owner, fact_id=None):
    with _lock, _c() as c:
        if fact_id is None:
            c.execute("DELETE FROM facts WHERE owner=?", (owner,))
        else:
            c.execute("DELETE FROM facts WHERE owner=? AND id=?", (owner, int(fact_id)))


REMEMBER_RE = re.compile(r"(?i)\b(?:lembre-se|lembre|guarde|memorize|anote|remember)\b(?:\s+que)?[:,]?\s+(.{4,300})")


def extract_memory_command(text):
    m = REMEMBER_RE.search(text or "")
    return m.group(1).strip() if m else None


def as_system_context(owner):
    facts = list_facts(owner)[:20]
    if not facts:
        return ""
    return "MEMÓRIA PERSISTENTE (fatos que o usuário pediu para lembrar):\n" + "\n".join("- " + f["text"] for f in reversed(facts))
