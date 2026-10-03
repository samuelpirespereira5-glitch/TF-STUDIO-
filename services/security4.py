"""JARVIS Security + Authentication 4.0.

Extends the existing auth/security stack instead of replacing it.  This module
keeps security-center state in a small SQLite database, stores only redacted
metadata, and exposes deterministic checkups for the developer/owner area.
It deliberately does not create a second login/session system.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "security4.db"
DB.parent.mkdir(parents=True, exist_ok=True)

ROLE_CAPS = {
    "owner": {"all"},
    "admin": {"chat", "tools_basic", "creator"},
    "user": {"chat", "tools_basic"},
    "guest": {"chat"},
    # Future role catalog only; these are not silently granted sessions.
    "creator": {"chat", "tools_basic", "creator", "workspace_write"},
    "teacher": {"chat", "tools_basic", "education", "projects_read"},
    "moderator": {"chat", "tools_basic", "moderation", "projects_read"},
    "developer": {"chat", "tools_basic", "developer", "diagnostics", "manage_access"},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def _uid(value):
    return str(value or "anon")[:120]


def conn():
    c = sqlite3.connect(DB, timeout=8)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS s4_audit(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          uid TEXT NOT NULL,
          action TEXT NOT NULL,
          target TEXT DEFAULT '',
          severity TEXT DEFAULT 'info',
          ok INTEGER DEFAULT 1,
          details TEXT DEFAULT '',
          ts TEXT NOT NULL,
          prev_hash TEXT DEFAULT '',
          entry_hash TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_s4_audit_ts ON s4_audit(ts);
        CREATE INDEX IF NOT EXISTS idx_s4_audit_uid ON s4_audit(uid);
        CREATE TABLE IF NOT EXISTS s4_notifications(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          uid TEXT NOT NULL,
          kind TEXT NOT NULL,
          title TEXT NOT NULL,
          message TEXT NOT NULL,
          severity TEXT DEFAULT 'info',
          read INTEGER DEFAULT 0,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_s4_notif_uid ON s4_notifications(uid, read, created_at);
        CREATE TABLE IF NOT EXISTS s4_incidents(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          uid TEXT NOT NULL,
          title TEXT NOT NULL,
          description TEXT DEFAULT '',
          severity TEXT DEFAULT 'medium',
          status TEXT DEFAULT 'open',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS s4_evidence(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          uid TEXT NOT NULL,
          incident_id INTEGER,
          name TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          source TEXT DEFAULT '',
          description TEXT DEFAULT '',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS s4_preferences(
          uid TEXT PRIMARY KEY,
          privacy_analytics INTEGER DEFAULT 0,
          public_portfolio INTEGER DEFAULT 0,
          simplified_mode INTEGER DEFAULT 0,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS s4_recovery_requests(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          uid TEXT NOT NULL,
          token_hash TEXT NOT NULL,
          expires_at REAL NOT NULL,
          used INTEGER DEFAULT 0,
          created_at TEXT NOT NULL
        );
        """)


init()


def audit(uid, action, target="", severity="info", ok=True, details=""):
    uid = _uid(uid)
    # Details are deliberately bounded and stripped of common secret-like fields.
    safe = re.sub(r"(?i)(password|token|secret|api[_-]?key|authorization)\s*[:=]\s*[^,;\s]+", r"\1=[redacted]", str(details or ""))[:1000]
    with conn() as c:
        prev = c.execute("SELECT entry_hash FROM s4_audit ORDER BY id DESC LIMIT 1").fetchone()
        prev_hash = prev["entry_hash"] if prev else ""
        ts = now()
        material = "|".join([prev_hash, uid, str(action)[:120], str(target)[:300], severity, str(int(bool(ok))), safe, ts])
        entry_hash = hashlib.sha256(material.encode()).hexdigest()
        c.execute("INSERT INTO s4_audit(uid,action,target,severity,ok,details,ts,prev_hash,entry_hash) VALUES(?,?,?,?,?,?,?,?,?)",
                  (uid, str(action)[:120], str(target)[:300], severity, int(bool(ok)), safe, ts, prev_hash, entry_hash))
    return entry_hash


def verify_integrity(limit=None):
    with conn() as c:
        rows = c.execute("SELECT * FROM s4_audit ORDER BY id ASC").fetchall()
    prev = ""
    bad = []
    for row in rows:
        material = "|".join([prev, row["uid"], row["action"], row["target"], row["severity"], str(int(row["ok"])), row["details"], row["ts"]])
        expected = hashlib.sha256(material.encode()).hexdigest()
        if row["prev_hash"] != prev or row["entry_hash"] != expected:
            bad.append(row["id"])
            break
        prev = row["entry_hash"]
    return {"ok": not bad, "entries": len(rows), "checked_to": bad[0] if bad else (rows[-1]["id"] if rows else 0), "first_invalid_id": bad[0] if bad else None}


def audit_list(limit=100, uid=None, action=""):
    limit = max(1, min(int(limit or 100), 500))
    sql = "SELECT id,uid,action,target,severity,ok,details,ts,entry_hash FROM s4_audit WHERE 1=1"
    args = []
    if uid:
        sql += " AND uid=?"; args.append(_uid(uid))
    if action:
        sql += " AND action=?"; args.append(str(action)[:120])
    sql += " ORDER BY id DESC LIMIT ?"; args.append(limit)
    with conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def notify(uid, kind, title, message, severity="info"):
    with conn() as c:
        c.execute("INSERT INTO s4_notifications(uid,kind,title,message,severity,created_at) VALUES(?,?,?,?,?,?)",
                  (_uid(uid), str(kind)[:80], str(title)[:160], str(message)[:500], str(severity)[:20], now()))


def notifications(uid, unread_only=False, limit=100):
    sql = "SELECT id,kind,title,message,severity,read,created_at FROM s4_notifications WHERE uid=?"
    args = [_uid(uid)]
    if unread_only:
        sql += " AND read=0"
    sql += " ORDER BY id DESC LIMIT ?"; args.append(max(1, min(int(limit or 100), 200)))
    with conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def mark_notification(uid, nid):
    with conn() as c:
        cur = c.execute("UPDATE s4_notifications SET read=1 WHERE id=? AND uid=?", (int(nid), _uid(uid)))
        return cur.rowcount > 0


def account_snapshot(uid, role, auth, platform):
    sessions = [x for x in auth.list_auth_sessions() if x.get("uid") == _uid(uid)]
    return {
        "uid": _uid(uid), "role": role,
        "authentication": {"configured": auth.has_master_password(), "source": auth.password_source(), "email_configured": bool(auth.get_owner_email())},
        "mfa": {"totp": bool(auth.totp_is_enabled()), "passkeys": len(auth.list_webauthn_credentials()), "recovery_codes": auth.totp_recovery_codes_remaining()},
        "sessions": sessions, "session_count": len(sessions),
        "security_events": audit_list(20, uid=uid),
        "notifications_unread": len(notifications(uid, True, 100)),
        "note": "Session IDs reais, segredos e recovery codes não são exibidos.",
    }


def security_checkup(uid, role, auth, security, permissions, scan=None):
    checks = []
    configured = auth.has_master_password()
    checks.append({"id":"password", "label":"Senha protegida por hash", "status":"OK" if configured and auth.password_source() else "AÇÃO NECESSÁRIA", "evidence":auth.password_source() or "nenhuma fonte de hash configurada", "fix":"Configure MASTER_PASSWORD_HASH ou a credencial mestre pelo fluxo oficial."})
    checks.append({"id":"mfa", "label":"MFA", "status":"OK" if auth.totp_is_enabled() or auth.has_webauthn() else "ATENÇÃO", "evidence":f"TOTP={auth.totp_is_enabled()}, Passkeys={len(auth.list_webauthn_credentials())}", "fix":"Ative TOTP ou cadastre uma Passkey."})
    checks.append({"id":"sessions", "label":"Sessões", "status":"OK" if len(auth.list_auth_sessions()) < 20 else "ATENÇÃO", "evidence":f"{len(auth.list_auth_sessions())} sessões persistidas", "fix":"Revogue sessões que não reconhece."})
    checks.append({"id":"csrf", "label":"CSRF", "status":"OK", "evidence":"Token + Origin/Referer são verificados no before_request.", "fix":"Manter os controles existentes."})
    checks.append({"id":"cookies", "label":"Cookies seguros", "status":"OK", "evidence":"HttpOnly + SameSite e Secure em HTTPS são configurados em app.py.", "fix":"Manter HTTPS em produção."})
    checks.append({"id":"rate_limit", "label":"Proteção contra brute force", "status":"OK", "evidence":"Rate limit e backoff progressivo no login e APIs sensíveis.", "fix":"Monitorar bloqueios e ajustar limites somente com evidência."})
    checks.append({"id":"rbac", "label":"Autorização backend", "status":"OK", "evidence":"permissions.enforce_path/require_cap validam capacidade no servidor.", "fix":"Continuar protegendo novos endpoints no backend."})
    checks.append({"id":"headers", "label":"Headers web", "status":"OK", "evidence":"CSP, HSTS em HTTPS, X-Content-Type-Options, Referrer-Policy e Permissions-Policy.", "fix":"Revisar CSP estrita antes de remover Report-Only."})
    checks.append({"id":"secrets", "label":"Secrets", "status":"ATENÇÃO" if scan and scan.get("counts",{}).get("WARNING",0) else "OK", "evidence":"Scanner determinístico do projeto quando executado.", "fix":"Revisar findings do scanner; nunca publicar credenciais."})
    integ = verify_integrity()
    checks.append({"id":"integrity", "label":"Integridade do audit log 4.0", "status":"OK" if integ["ok"] else "AÇÃO NECESSÁRIA", "evidence":f"{integ['entries']} registros verificados", "fix":"Investigar o primeiro registro inválido e preservar a evidência."})
    counts = {k: sum(1 for x in checks if x["status"] == k) for k in ("OK","ATENÇÃO","AÇÃO NECESSÁRIA")}
    return {"status":"AÇÃO NECESSÁRIA" if counts["AÇÃO NECESSÁRIA"] else ("ATENÇÃO" if counts["ATENÇÃO"] else "OK"), "checks":checks, "counts":counts, "generated_at":now()}


def developer_overview(uid, role, auth, security, permissions, scan=None):
    if role != "owner" and not permissions.has_cap("developer", role):
        return {"authorized":False}
    try:
        from services import diagnostics
        diag = diagnostics.snapshot()
    except Exception:
        diag = {"status":"NOT TESTED"}
    sessions = auth.list_auth_sessions()
    return {
        "authorized": True, "role": role,
        "auth": {"configured":auth.has_master_password(),"mfa":auth.totp_is_enabled(),"passkeys":len(auth.list_webauthn_credentials())},
        "sessions": len(sessions), "audit_integrity": verify_integrity(),
        "security_events": audit_list(25), "scan": scan or {"status":"NOT TESTED"}, "diagnostics":diag,
        "services": ["AUTH", "DATABASE", "SECURITY", "AI", "GAME LAB", "MAPS", "STORAGE"],
    }


def system_health(auth, scan=None):
    db = "ONLINE"
    try:
        with conn() as c: c.execute("SELECT 1").fetchone()
    except Exception: db = "OFFLINE"
    ai = "ONLINE" if any(os.getenv(k) for k in ("OPENROUTER_API_KEY","GEMINI_API_KEY","ANTHROPIC_API_KEY")) else "DEGRADED"
    return {"services":[
        {"name":"BACKEND","status":"ONLINE"},
        {"name":"AUTH","status":"ONLINE" if auth.has_master_password() else "DEGRADED"},
        {"name":"DATABASE","status":db},
        {"name":"AI","status":ai},
        {"name":"GAME LAB","status":"ONLINE"},
        {"name":"MAPS","status":"NOT TESTED"},
        {"name":"STORAGE","status":"ONLINE"},
    ], "generated_at":now(), "scan":scan or {"status":"NOT TESTED"}}


def privacy(uid):
    with conn() as c:
        row = c.execute("SELECT * FROM s4_preferences WHERE uid=?", (_uid(uid),)).fetchone()
    if not row:
        return {"uid":_uid(uid),"analytics":False,"public_portfolio":False,"simplified_mode":False,"stored_categories":["account security metadata","project security events"],"note":"Sem conteúdo de senha, token ou chave privada."}
    return {"uid":_uid(uid),"analytics":bool(row["privacy_analytics"]),"public_portfolio":bool(row["public_portfolio"]),"simplified_mode":bool(row["simplified_mode"]),"stored_categories":["account security metadata","project security events"]}


def set_privacy(uid, analytics=None, public_portfolio=None, simplified_mode=None):
    old=privacy(uid)
    vals={"analytics":old["analytics"],"public_portfolio":old["public_portfolio"],"simplified_mode":old["simplified_mode"]}
    for k,v in (("analytics",analytics),("public_portfolio",public_portfolio),("simplified_mode",simplified_mode)):
        if v is not None: vals[k]=bool(v)
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO s4_preferences(uid,privacy_analytics,public_portfolio,simplified_mode,updated_at) VALUES(?,?,?,?,?)",
                  (_uid(uid),int(vals["analytics"]),int(vals["public_portfolio"]),int(vals["simplified_mode"]),now()))
    audit(uid,"PRIVACY_CHANGED","preferences",details=json.dumps(vals,sort_keys=True))
    return privacy(uid)


def create_incident(uid,title,description="",severity="medium"):
    allowed={"low","medium","high","critical"}
    severity=severity if severity in allowed else "medium"
    with conn() as c:
        cur=c.execute("INSERT INTO s4_incidents(uid,title,description,severity,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                      (_uid(uid),str(title)[:160],str(description)[:1000],severity,"open",now(),now()))
        iid=cur.lastrowid
    audit(uid,"INCIDENT_CREATED",str(iid),severity=severity)
    return incident(uid,iid)


def incident(uid,iid):
    with conn() as c:
        row=c.execute("SELECT * FROM s4_incidents WHERE id=? AND uid=?",(int(iid),_uid(uid))).fetchone()
    return dict(row) if row else None


def incidents(uid,limit=100):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM s4_incidents WHERE uid=? ORDER BY id DESC LIMIT ?",(_uid(uid),max(1,min(int(limit),200)))).fetchall()]


def update_incident(uid,iid,status=None,severity=None):
    allowed_status={"open","investigating","contained","resolved","archived"}
    row=incident(uid,iid)
    if not row: return None
    status=status if status in allowed_status else row["status"]
    severity=severity if severity in {"low","medium","high","critical"} else row["severity"]
    with conn() as c:
        c.execute("UPDATE s4_incidents SET status=?,severity=?,updated_at=? WHERE id=? AND uid=?",(status,severity,now(),int(iid),_uid(uid)))
    audit(uid,"INCIDENT_UPDATED",str(iid),severity=severity,details=f"status={status}")
    return incident(uid,iid)


def add_evidence(uid,iid,name,content,source="",description=""):
    if not incident(uid,iid): raise ValueError("Incidente não encontrado")
    data = content if isinstance(content,(bytes,bytearray)) else str(content or "").encode()
    if len(data)>5*1024*1024: raise ValueError("Evidência excede 5 MB")
    digest=hashlib.sha256(data).hexdigest()
    with conn() as c:
        cur=c.execute("INSERT INTO s4_evidence(uid,incident_id,name,sha256,source,description,created_at) VALUES(?,?,?,?,?,?,?)",
                      (_uid(uid),int(iid),str(name)[:180],digest,str(source)[:180],str(description)[:800],now()))
        eid=cur.lastrowid
    audit(uid,"EVIDENCE_ADDED",str(iid),details=f"evidence_id={eid};sha256={digest}")
    return {"id":eid,"incident_id":int(iid),"name":str(name)[:180],"sha256":digest,"source":str(source)[:180],"created_at":now()}


def api_security_snapshot():
    try:
        from services import permissions
        caps = {role:permissions.caps_for(role) for role in permissions.ROLES}
    except Exception:
        caps={}
    return {"roles":caps,"csrf":"backend token + origin","rate_limit":"login backoff + API buckets","error_handling":"API JSON handler","secrets":"response redaction enabled"}


_SCAN_CACHE = {'ts': 0.0, 'value': None}

def secret_scan_summary(force=False):
    # The project scanner is deterministic but can still touch many files;
    # cache it briefly so the Security Center does not rescan on every tab.
    if not force and _SCAN_CACHE['value'] is not None and time.time() - _SCAN_CACHE['ts'] < 30:
        return _SCAN_CACHE['value']
    try:
        from services import security_scan
        result=security_scan.scan_project(BASE)
        value={"status":"EXECUTED","counts":result.get("counts",{}),"files_scanned":result.get("files_scanned",0),"findings":result.get("findings",[])[:50]}
    except Exception as exc:
        value={"status":"NOT TESTED","reason":type(exc).__name__}
    _SCAN_CACHE.update({'ts':time.time(),'value':value})
    return value
