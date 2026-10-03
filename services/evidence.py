"""Findings + Evidence Center + Scan History + comparação antes/depois."""
import hashlib
import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_FILE = DATA_DIR / "cyberlab.db"
_lock = threading.Lock()

SEVERITIES = ("info", "low", "medium", "high", "critical")
WEIGHT = {"info": 0, "low": 3, "medium": 10, "high": 22, "critical": 40}


def normalize_target(target):
    """Chave estável do alvo: 'host' (ou 'host:porta' se não padrão).
    http://Exemplo.com/a?b, exemplo.com e EXEMPLO.COM:443 → 'exemplo.com'."""
    from urllib.parse import urlparse
    t = (target or "").strip()
    if not t:
        return "local"
    u = urlparse(t if "://" in t else "//" + t)
    host = (u.hostname or t).lower().strip(".")
    port = u.port
    default = {"http": 80, "https": 443}.get(u.scheme)
    if port and port != default and port not in (80, 443):
        return f"{host}:{port}"
    return host


def make_finding(rule, title, severity, evidence="", impact="", fix="", where="", ref=""):
    """Achado padronizado. O id é estável (regra + local), então o mesmo
    problema tem o mesmo id entre scans — base do antes/depois."""
    assert severity in SEVERITIES, severity
    fid = hashlib.sha1(f"{rule}|{where}".encode()).hexdigest()[:12]
    return {
        "id": fid, "rule": rule, "title": title, "severity": severity,
        "evidence": evidence, "impact": impact, "fix": fix, "where": where, "ref": ref,
    }


def risk_score(findings):
    """0 (limpo) a 100 (crítico). Soma ponderada com teto, saturando."""
    raw = sum(WEIGHT[f["severity"]] for f in findings)
    # O score nunca passa do teto da PIOR gravidade encontrada: sem nenhum
    # achado crítico não existe risco "crítico", por mais achados médios que haja.
    cap = {"critical": 100, "high": 69, "medium": 39, "low": 14, "info": 0}
    if findings:
        worst_sev = max((f["severity"] for f in findings), key=SEVERITIES.index)
        raw = min(raw, cap[worst_sev])
    return min(100, raw)


def risk_label(score):
    if score >= 70: return "crítico"
    if score >= 40: return "alto"
    if score >= 15: return "médio"
    if score > 0: return "baixo"
    return "limpo"


def _conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_FILE, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute(
        """CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL, target TEXT NOT NULL, tool TEXT NOT NULL,
            duration_ms INTEGER, score INTEGER, findings TEXT NOT NULL,
            raw TEXT, session_id TEXT
        )"""
    )
    c.execute("CREATE INDEX IF NOT EXISTS ix_scans_target ON scans(target, tool)")
    return c


def save_scan(target, tool, findings, raw=None, duration_ms=0, session_id=""):
    with _lock, _conn() as c:
        cur = c.execute(
            "INSERT INTO scans (ts,target,tool,duration_ms,score,findings,raw,session_id) VALUES (?,?,?,?,?,?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(), target, tool, int(duration_ms),
                risk_score(findings), json.dumps(findings, ensure_ascii=False),
                json.dumps(raw, ensure_ascii=False, default=str)[:200000] if raw is not None else None,
                session_id,
            ),
        )
        return cur.lastrowid


def _row(r, with_raw=False):
    d = {
        "id": r["id"], "ts": r["ts"], "target": r["target"], "tool": r["tool"],
        "duration_ms": r["duration_ms"], "score": r["score"],
        "findings": json.loads(r["findings"]), "session_id": r["session_id"],
    }
    if with_raw:
        d["raw"] = json.loads(r["raw"]) if r["raw"] else None
    return d


def history(target=None, tool=None, limit=50):
    q, args = "SELECT * FROM scans", []
    conds = []
    if target: conds.append("target=?"); args.append(target)
    if tool: conds.append("tool=?"); args.append(tool)
    if conds: q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(int(limit))
    with _conn() as c:
        return [_row(r) for r in c.execute(q, args).fetchall()]


def get_scan(scan_id):
    with _conn() as c:
        r = c.execute("SELECT * FROM scans WHERE id=?", (int(scan_id),)).fetchone()
        return _row(r, with_raw=True) if r else None


def latest_two(target, tool):
    """Último scan e o anterior do mesmo alvo+ferramenta (para retest)."""
    rows = history(target=target, tool=tool, limit=2)
    return (rows[0] if rows else None), (rows[1] if len(rows) > 1 else None)


def compare(before, after):
    """Antes/depois por id estável: resolvidos, persistentes, novos."""
    b = {f["id"]: f for f in before["findings"]}
    a = {f["id"]: f for f in after["findings"]}
    resolved = [b[i] for i in b if i not in a]
    persistent = [a[i] for i in a if i in b]
    new = [a[i] for i in a if i not in b]
    return {
        "before": {"scan_id": before["id"], "ts": before["ts"], "score": before["score"]},
        "after": {"scan_id": after["id"], "ts": after["ts"], "score": after["score"]},
        "delta_score": after["score"] - before["score"],
        "resolved": resolved, "persistent": persistent, "new": new,
        "verdict": (
            "melhorou" if after["score"] < before["score"]
            else "piorou" if after["score"] > before["score"] else "igual"
        ),
    }


def dashboard():
    """Risk Dashboard: último scan de cada (alvo, ferramenta) agregado por alvo."""
    with _conn() as c:
        rows = c.execute(
            """SELECT s.* FROM scans s JOIN (
                 SELECT target, tool, MAX(id) mid FROM scans GROUP BY target, tool
               ) m ON s.id = m.mid"""
        ).fetchall()
    by_target = {}
    for r in rows:
        d = _row(r)
        t = by_target.setdefault(d["target"], {"target": d["target"], "findings": {}, "tools": []})
        t["tools"].append(d["tool"])
        for f in d["findings"]:
            t["findings"][f["id"]] = f
    out = []
    counts_total = {s: 0 for s in SEVERITIES}
    for t in by_target.values():
        fl = list(t["findings"].values())
        counts = {s: 0 for s in SEVERITIES}
        for f in fl:
            counts[f["severity"]] += 1
            counts_total[f["severity"]] += 1
        score = risk_score(fl)
        out.append({
            "target": t["target"], "score": score, "label": risk_label(score),
            "counts": counts, "tools": sorted(set(t["tools"])),
        })
    out.sort(key=lambda x: -x["score"])
    return {"targets": out, "totals": counts_total}
