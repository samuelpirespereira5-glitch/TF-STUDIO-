"""Cyber Lab Phase 2: orchestration around the existing Evidence Center.

This module adds project/asset organization, user tool preferences, alerts,
finding workflow, reports, and educational progression without replacing the
existing scan/evidence/challenge engines.
"""
from __future__ import annotations

import html
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from services import evidence, scope
from services.tool_registry import REGISTRY

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_FILE = DATA_DIR / "cyberlab.db"
_lock = threading.Lock()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_FILE, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS cyber_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, owner_uid TEXT NOT NULL,
        name TEXT NOT NULL, target TEXT NOT NULL, environment TEXT NOT NULL DEFAULT 'development',
        description TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        last_scan_id INTEGER, UNIQUE(owner_uid, target)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS cyber_projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT, owner_uid TEXT NOT NULL,
        name TEXT NOT NULL, description TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(owner_uid, name)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS cyber_project_assets (
        project_id INTEGER NOT NULL, asset_id INTEGER NOT NULL,
        PRIMARY KEY(project_id, asset_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS cyber_tool_prefs (
        owner_uid TEXT NOT NULL, tool_id TEXT NOT NULL, favorite INTEGER NOT NULL DEFAULT 0,
        last_used_at TEXT, use_count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(owner_uid, tool_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS cyber_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, owner_uid TEXT NOT NULL,
        kind TEXT NOT NULL, severity TEXT NOT NULL DEFAULT 'info', title TEXT NOT NULL,
        message TEXT NOT NULL, target TEXT DEFAULT '', scan_id INTEGER,
        created_at TEXT NOT NULL, read_at TEXT
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_cyber_alerts_uid ON cyber_alerts(owner_uid, id DESC)")
    c.execute("""CREATE TABLE IF NOT EXISTS cyber_finding_state (
        owner_uid TEXT NOT NULL, finding_id TEXT NOT NULL, scan_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'open', justification TEXT DEFAULT '', updated_at TEXT NOT NULL,
        PRIMARY KEY(owner_uid, finding_id, scan_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS cyber_challenge_progress (
        owner_uid TEXT NOT NULL, challenge_id TEXT NOT NULL, xp INTEGER NOT NULL DEFAULT 0,
        completed_at TEXT, attempts INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(owner_uid, challenge_id)
    )""")
    return c


def _uid(uid):
    return str(uid or "owner")[:120]


def _authorized_target(target):
    """Only allow an asset to be registered when the existing scope allows it.
    No new authorization mechanism is introduced here."""
    raw = (target or "").strip()
    if not raw:
        raise ValueError("Informe um alvo.")
    # Name-only is appropriate for domains; URL/IP is checked with the same
    # centralized scope service used by real scanners.
    from urllib.parse import urlparse
    host = urlparse(raw if "://" in raw else "//" + raw).hostname or raw.split("/")[0]
    scope.check_name_only(host, context="phase2_asset")
    return scope.normalize_entry(raw)


def list_assets(uid):
    with _conn() as c:
        rows = c.execute("SELECT * FROM cyber_assets WHERE owner_uid=? ORDER BY updated_at DESC", (_uid(uid),)).fetchall()
    out = []
    for r in rows:
        latest = evidence.history(target=evidence.normalize_target(r["target"]), limit=1)
        last = latest[0] if latest else None
        out.append({**dict(r), "last_scan": last})
    return out


def create_asset(uid, name, target, environment="development", description=""):
    target = _authorized_target(target)
    now = _now()
    env = (environment or "development")[:40]
    with _lock, _conn() as c:
        cur = c.execute("""INSERT INTO cyber_assets
            (owner_uid,name,target,environment,description,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?)""", (_uid(uid), (name or target)[:120], target, env,
                                           (description or "")[:500], now, now))
        return dict(c.execute("SELECT * FROM cyber_assets WHERE id=?", (cur.lastrowid,)).fetchone())


def delete_asset(uid, asset_id):
    with _lock, _conn() as c:
        row = c.execute("SELECT id FROM cyber_assets WHERE id=? AND owner_uid=?", (int(asset_id), _uid(uid))).fetchone()
        if not row:
            return False
        c.execute("DELETE FROM cyber_project_assets WHERE asset_id=?", (int(asset_id),))
        c.execute("DELETE FROM cyber_assets WHERE id=?", (int(asset_id),))
        return True


def list_projects(uid):
    with _conn() as c:
        projects = c.execute("SELECT * FROM cyber_projects WHERE owner_uid=? ORDER BY updated_at DESC", (_uid(uid),)).fetchall()
        out = []
        for p in projects:
            assets = c.execute("""SELECT a.* FROM cyber_assets a
                JOIN cyber_project_assets pa ON pa.asset_id=a.id WHERE pa.project_id=?
                ORDER BY a.name""", (p["id"],)).fetchall()
            out.append({**dict(p), "assets": [dict(a) for a in assets]})
        return out


def create_project(uid, name, description=""):
    if not (name or "").strip():
        raise ValueError("Informe o nome do projeto.")
    now = _now()
    with _lock, _conn() as c:
        cur = c.execute("INSERT INTO cyber_projects(owner_uid,name,description,created_at,updated_at) VALUES(?,?,?,?,?)",
                        (_uid(uid), name.strip()[:120], (description or "")[:500], now, now))
        return dict(c.execute("SELECT * FROM cyber_projects WHERE id=?", (cur.lastrowid,)).fetchone())


def attach_asset(uid, project_id, asset_id):
    with _lock, _conn() as c:
        ok = c.execute("SELECT 1 FROM cyber_projects WHERE id=? AND owner_uid=?", (int(project_id), _uid(uid))).fetchone()
        asset = c.execute("SELECT 1 FROM cyber_assets WHERE id=? AND owner_uid=?", (int(asset_id), _uid(uid))).fetchone()
        if not ok or not asset:
            raise ValueError("Projeto ou ativo não encontrado.")
        c.execute("INSERT OR IGNORE INTO cyber_project_assets(project_id,asset_id) VALUES(?,?)", (int(project_id), int(asset_id)))
        c.execute("UPDATE cyber_projects SET updated_at=? WHERE id=?", (_now(), int(project_id)))
        return True


def tool_preferences(uid):
    uid = _uid(uid)
    with _conn() as c:
        rows = {r["tool_id"]: dict(r) for r in c.execute("SELECT * FROM cyber_tool_prefs WHERE owner_uid=?", (uid,)).fetchall()}
    tools = []
    for t in REGISTRY.list_for("owner"):
        p = rows.get(t["id"], {})
        tools.append({**t, "favorite": bool(p.get("favorite", 0)), "use_count": p.get("use_count", 0), "last_used_at": p.get("last_used_at")})
    tools.sort(key=lambda x: (-int(x["favorite"]), -(x["use_count"] or 0), x["name"].lower()))
    return tools


def mark_tool_used(uid, tool_id):
    now = _now()
    with _lock, _conn() as c:
        c.execute("""INSERT INTO cyber_tool_prefs(owner_uid,tool_id,last_used_at,use_count)
            VALUES(?,?,?,1) ON CONFLICT(owner_uid,tool_id) DO UPDATE SET
            last_used_at=excluded.last_used_at,use_count=cyber_tool_prefs.use_count+1""", (_uid(uid), tool_id[:120], now))


def toggle_favorite(uid, tool_id):
    with _lock, _conn() as c:
        row = c.execute("SELECT favorite FROM cyber_tool_prefs WHERE owner_uid=? AND tool_id=?", (_uid(uid), tool_id)).fetchone()
        val = 0 if row and row["favorite"] else 1
        c.execute("""INSERT INTO cyber_tool_prefs(owner_uid,tool_id,favorite,last_used_at,use_count)
            VALUES(?,?,?,NULL,0) ON CONFLICT(owner_uid,tool_id) DO UPDATE SET favorite=excluded.favorite""", (_uid(uid), tool_id[:120], val))
        return bool(val)


def _latest_scan_rows():
    rows = evidence.history(limit=300)
    latest = {}
    for r in rows:
        latest.setdefault((r["target"], r["tool"]), r)
    return list(latest.values())


def dashboard(uid):
    rows = _latest_scan_rows()
    counts = {s: 0 for s in evidence.SEVERITIES}
    targets = set()
    for r in rows:
        targets.add(r["target"])
        for f in r["findings"]:
            if f.get("status", "confirmed") in ("confirmed", "possible"):
                counts[f.get("severity", "info")] += 1
    history = evidence.history(limit=10)
    try:
        from services import telemetry
        activity = telemetry.recent(12)
    except Exception:
        activity = []
    assets = list_assets(uid)
    projects = list_projects(uid)
    try:
        from services import cyber_challenges
        catalog = cyber_challenges.CATALOG
    except Exception:
        catalog = {}
    completed = 0
    xp = 0
    challenge_categories = set()
    # Existing challenge engine is source of truth for current challenge status.
    try:
        from services import sites_service as sites, challenges
        catalog = {c["id"]: c for c in challenges.list_catalog()}
        for s in sites.list_sites():
            if s.get("challenge_status") == "concluido":
                completed += 1
                c = catalog.get(s.get("challenge_id"), {})
                xp += int(c.get("xp", 0) or 0)
                challenge_categories.add(c.get("category", ""))
    except Exception:
        pass
    level = 1 + xp // 300
    badges = []
    if history:
        badges.append({"id":"first-scan","name":"Primeiro Scan","earned":True})
    states = []
    try:
        with _conn() as c:
            states = [dict(r) for r in c.execute("SELECT status FROM cyber_finding_state WHERE owner_uid=?", (_uid(uid),)).fetchall()]
    except Exception:
        pass
    if any(s.get("status") == "fixed" for s in states):
        badges.append({"id":"first-fix","name":"Primeiro Fix","earned":True})
    badges.extend([
        {"id":"web-security","name":"Web Security","earned":bool(challenge_categories & {"xss","sqli","csrf","cors","headers","csp","api-insegura"})},
        {"id":"blue-team","name":"Blue Team","earned":bool(challenge_categories & {"logs","incidente","pcap","malware"})},
        {"id":"incident-investigator","name":"Incident Investigator","earned": "incidente" in challenge_categories},
        {"id":"ctf-beginner","name":"CTF Beginner","earned": "ctf" in challenge_categories},
    ])
    score_values = [r.get("score", 0) for r in rows]
    evolution = list(reversed([{"ts": r["ts"], "score": r.get("score", 0), "target": r["target"], "tool": r["tool"]} for r in history]))
    services = {"database": True, "scope_guard": True, "evidence_center": True, "tool_registry": bool(REGISTRY.list_for("owner"))}
    return {
        "jarvis": "online", "services": services,
        "tools": len(REGISTRY.list_for("owner")), "targets": len(targets),
        "scans": len(history), "vulnerabilities": sum(counts.values()),
        "counts": counts, "challenges_completed": completed, "xp": xp, "level": level, "badges": badges, "projects": len(projects),
        "assets": assets, "projects_data": projects, "recent_scans": history, "activity": activity,
        "evolution": evolution, "security_score": round(sum(score_values)/len(score_values)) if score_values else 0,
        "tool_shortcuts": tool_preferences(uid)[:8],
    }


def _add_alert(c, uid, kind, severity, title, message, target="", scan_id=None):
    # Deduplicate identical scan alerts.
    if scan_id is not None:
        exists = c.execute("SELECT 1 FROM cyber_alerts WHERE owner_uid=? AND kind=? AND scan_id=? LIMIT 1",
                           (_uid(uid), kind, int(scan_id))).fetchone()
        if exists:
            return
    c.execute("""INSERT INTO cyber_alerts(owner_uid,kind,severity,title,message,target,scan_id,created_at)
        VALUES(?,?,?,?,?,?,?,?)""", (_uid(uid), kind, severity, title[:160], message[:500], target[:300], scan_id, _now()))


def sync_scan_alerts(uid, scan):
    if not scan or not scan.get("id"):
        return
    critical = sum(1 for f in scan.get("findings", []) if f.get("severity") == "critical")
    high = sum(1 for f in scan.get("findings", []) if f.get("severity") == "high")
    with _lock, _conn() as c:
        _add_alert(c, uid, "scan_complete", "info", "Scan concluído",
                   f"Scan #{scan['id']} concluído para {scan.get('target','')}.", scan.get("target", ""), scan["id"])
        # Compare with the immediately previous scan of the same tool/target
        # so alerts reflect real remediation instead of UI state.
        previous = evidence.history(target=scan.get("target"), tool=scan.get("tool"), limit=2)
        if len(previous) == 2:
            cmp = evidence.compare(previous[1], previous[0])
            if cmp["resolved"]:
                _add_alert(c, uid, "fixed", "info", "Problema corrigido",
                           f"{len(cmp['resolved'])} finding(s) não apareceram no novo scan #{scan['id']}.", scan.get("target", ""), scan["id"])
        if critical:
            _add_alert(c, uid, "critical", "critical", "Vulnerabilidade crítica encontrada",
                       f"{critical} achado(s) crítico(s) no scan #{scan['id']}.", scan.get("target", ""), scan["id"])
        if high:
            _add_alert(c, uid, "high", "high", "Vulnerabilidade alta encontrada",
                       f"{high} achado(s) alto(s) no scan #{scan['id']}.", scan.get("target", ""), scan["id"])


def alerts(uid, limit=50):
    with _conn() as c:
        rows = c.execute("SELECT * FROM cyber_alerts WHERE owner_uid=? ORDER BY id DESC LIMIT ?", (_uid(uid), min(int(limit), 200))).fetchall()
        return [dict(r) for r in rows]


def mark_alert_read(uid, alert_id):
    with _lock, _conn() as c:
        c.execute("UPDATE cyber_alerts SET read_at=? WHERE id=? AND owner_uid=?", (_now(), int(alert_id), _uid(uid)))
        return c.rowcount > 0


def finding(scan_id, finding_id):
    scan = evidence.get_scan(scan_id)
    if not scan:
        return None
    f = next((x for x in scan["findings"] if x.get("id") == finding_id), None)
    if not f:
        return None
    f = dict(f)
    f["scan"] = {"id": scan["id"], "target": scan["target"], "tool": scan["tool"], "ts": scan["ts"], "raw": scan.get("raw")}
    return f


def set_finding_state(uid, scan_id, finding_id, status, justification=""):
    if status not in {"open", "fixed", "ignored"}:
        raise ValueError("Status inválido.")
    if not finding(scan_id, finding_id):
        raise ValueError("Finding não encontrado.")
    if status == "ignored" and not (justification or "").strip():
        raise ValueError("Uma justificativa é obrigatória ao ignorar um finding.")
    with _lock, _conn() as c:
        c.execute("""INSERT INTO cyber_finding_state(owner_uid,finding_id,scan_id,status,justification,updated_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(owner_uid,finding_id,scan_id) DO UPDATE SET
            status=excluded.status,justification=excluded.justification,updated_at=excluded.updated_at""",
                  (_uid(uid), finding_id[:64], int(scan_id), status, (justification or "")[:500], _now()))
    return True


def get_finding_state(uid, scan_id, finding_id):
    with _conn() as c:
        r = c.execute("SELECT * FROM cyber_finding_state WHERE owner_uid=? AND scan_id=? AND finding_id=?",
                      (_uid(uid), int(scan_id), finding_id)).fetchone()
    return dict(r) if r else {"status": "open", "justification": ""}


def report_html(target):
    rows = evidence.history(target=evidence.normalize_target(target), limit=100)
    if not rows:
        raise ValueError("Nenhum scan salvo para este alvo.")
    latest = {}
    for r in rows:
        latest.setdefault(r["tool"], r)
    findings = {f["id"]: f for r in latest.values() for f in r["findings"]}
    counts = {s: sum(1 for f in findings.values() if f.get("severity") == s) for s in evidence.SEVERITIES}
    score = evidence.risk_score([f for f in findings.values() if f.get("severity") != "info"])
    generated = _now()
    items = []
    for f in sorted(findings.values(), key=lambda x: evidence.SEVERITIES.index(x.get("severity", "info")), reverse=True):
        items.append(f"<article><h3>{html.escape(f.get('title',''))}</h3>"
                     f"<p><b>Severidade:</b> {html.escape(f.get('severity',''))} · <b>Local:</b> {html.escape(f.get('where',''))}</p>"
                     f"<p><b>Evidência:</b><pre>{html.escape(f.get('evidence',''))}</pre></p>"
                     f"<p><b>Impacto:</b> {html.escape(f.get('impact',''))}</p>"
                     f"<p><b>Correção:</b> {html.escape(f.get('fix',''))}</p></article>")
    return f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Relatório de Segurança</title>
<style>body{{font-family:Inter,Arial,sans-serif;max-width:980px;margin:40px auto;color:#182233;line-height:1.5}}h1{{color:#0b5cad}}.summary{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}}.box{{border:1px solid #ccd5e0;padding:12px;border-radius:8px}}article{{page-break-inside:avoid;border-top:1px solid #ccd5e0;padding:16px 0}}pre{{white-space:pre-wrap;background:#f4f6f8;padding:10px;border-radius:6px}}@media print{{body{{margin:15mm}}}}</style></head><body>
<h1>Relatório de Segurança</h1><p><b>Alvo:</b> {html.escape(target)}<br><b>Escopo:</b> alvo previamente autorizado pelo Cyber Lab<br><b>Gerado em:</b> {html.escape(generated)}<br><b>Ferramentas:</b> {html.escape(', '.join(sorted(latest)))}</p>
<div class='summary'><div class='box'><b>Score</b><br>{score}/100</div>{''.join(f"<div class='box'><b>{s.upper()}</b><br>{counts[s]}</div>" for s in evidence.SEVERITIES)}</div>
<h2>Resumo executivo</h2><p>Este relatório reúne os últimos resultados disponíveis no Evidence Center para o alvo. Findings são apresentados conforme a evidência registrada; itens informativos não são tratados como vulnerabilidades.</p>
<h2>Vulnerabilidades e evidências</h2>{''.join(items) or '<p>Nenhum finding registrado.</p>'}
<h2>Histórico</h2><ul>{''.join(f"<li>#{r['id']} · {html.escape(r['tool'])} · {html.escape(r['ts'])} · score {r['score']}</li>" for r in rows[:30])}</ul>
</body></html>"""
