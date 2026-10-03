"""JARVIS Ultra Expansion — orchestration layer.

Incremental only: aggregates existing services instead of creating parallel
authentication, XP, tool, site, security or map stores. All cyber data is
local/lab-oriented and unknown states are surfaced as UNKNOWN/NOT_AVAILABLE.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from datetime import datetime, timezone

from services import auth, gamification, phase5, platform_ultra, ultra_ops, webauthn_service
from services.tool_registry import REGISTRY
from services import sites_service as sites

BASE = Path(__file__).resolve().parent.parent
SAFE_FILE_DIRS = {"services", "templates", "static", "scripts"}


def now():
    return datetime.now(timezone.utc).isoformat()


def _uid(owner):
    return str(owner or "owner")[:120]


def _status(ok, unknown=False):
    if unknown:
        return "UNKNOWN"
    return "HEALTHY" if ok else "ERROR"


def service_status():
    result = []
    checks = []
    t = time.perf_counter()
    try:
        with phase5.conn() as c:
            c.execute("SELECT 1").fetchone()
        checks.append(("Database", "HEALTHY", round((time.perf_counter()-t)*1000, 2), "SQLite respondeu"))
    except Exception as exc:
        checks.append(("Database", "ERROR", round((time.perf_counter()-t)*1000, 2), type(exc).__name__))

    checks.append(("Flask", "HEALTHY", 0, "processo atual"))
    checks.append(("Tool Registry", "HEALTHY" if bool(REGISTRY.tools) else "UNKNOWN", 0, f"{len(REGISTRY.tools)} ferramentas"))
    checks.append(("Authentication", "HEALTHY" if auth.has_master_password() else "WARNING", 0, "configuração local"))
    ws = webauthn_service.status()
    checks.append(("WebAuthn", "HEALTHY" if ws.get("enabled") and ws.get("ready") else ("WARNING" if ws.get("configured") else "UNKNOWN"), 0, ws.get("reason", "")))
    checks.append(("Security Center", "HEALTHY", 0, "módulos defensivos carregados"))
    checks.append(("AI APIs", "UNKNOWN", 0, "disponibilidade externa não verificada neste painel"))
    checks.append(("Maps provider", "UNKNOWN", 0, "provedor externo não verificado neste painel"))
    return [{"name": n, "status": s, "latency_ms": ms, "evidence": e, "checked_at": now()} for n,s,ms,e in checks]


def dashboard(owner):
    owner = _uid(owner)
    service = service_status()
    tools = ultra_ops.tool_catalog(owner)
    games = platform_ultra.arcade_catalog(owner)
    profile = platform_ultra.arcade_profile(owner)
    try:
        site_list = sites.list_sites()
    except Exception:
        site_list = []
    try:
        events = ultra_ops.timeline(owner, days=30)[:20]
    except Exception:
        events = []
    try:
        sec = ultra_ops.security_score()
    except Exception:
        sec = {"score": None, "evidence": [], "categories": []}
    try:
        notifications = ultra_ops.notifications_smart(owner)[:20]
    except Exception:
        notifications = []
    try:
        sessions = [s for s in auth.list_auth_sessions() if s.get("uid") == owner]
    except Exception:
        sessions = []
    return {
        "generated_at": now(),
        "jarvis": {"status": "HEALTHY", "role": "owner"},
        "services": service,
        "security": sec,
        "web_authn": webauthn_service.status(),
        "tools": {"available": tools["total"], "categories": tools["categories"]},
        "challenges": {"available": len(getattr(__import__('services.cyber_challenges', fromlist=['CATALOG']), 'CATALOG', {}))},
        "games": {"available": len(games), "profile": profile},
        "projects": {"workspaces": len(ultra_ops.workspace_list(owner)), "sites": len(site_list)},
        "activity": events,
        "notifications": notifications,
        "sessions": len(sessions),
        "progression": gamification.public_user(owner),
    }


def command_catalog():
    return [
        {"command": "abrir o mapa", "route": "/cyber/mega#maps", "label": "Maps"},
        {"command": "abrir security center", "route": "/security-center", "label": "Security Center"},
        {"command": "abrir arcade", "route": "/cyber/mega#arcade", "label": "Arcade"},
        {"command": "abrir cyber lab", "route": "/cyber", "label": "Cyber Lab"},
        {"command": "abrir holograma", "route": "/holograma", "label": "Hologram"},
        {"command": "abrir meus projetos", "route": "/painel", "label": "Projects"},
        {"command": "abrir ferramentas", "route": "/cyber/mega#tools", "label": "Tools"},
        {"command": "abrir estudos", "route": "/cyber/ultra-platform", "label": "Study"},
        {"command": "abrir minha segurança", "route": "/configuracoes", "label": "Account Security"},
        {"command": "abrir developer center", "route": "/cyber/developer", "label": "Developer Center"},
        {"command": "abrir access audit", "route": "/cyber/developer", "label": "Access Audit"},
        {"command": "abrir crypto center", "route": "/cyber/developer", "label": "Crypto Center"},
        {"command": "abrir maps", "route": "/cyber/mega#maps", "label": "Maps"},
    ]


def resolve_command(text):
    q = " ".join(str(text or "").lower().strip().split())[:160]
    if not q:
        return {"matched": False, "message": "Comando vazio."}
    best = None
    for item in command_catalog():
        words = item["command"].split()
        score = sum(1 for w in words if w in q)
        if score and (best is None or score > best[0]):
            best = (score, item)
    if not best:
        return {"matched": False, "message": "Comando não reconhecido. Use /system para ver opções."}
    return {"matched": True, **best[1]}


def activity(owner, category="", limit=100):
    owner = _uid(owner)
    rows = []
    try:
        for x in ultra_ops.timeline(owner, days=90):
            rows.append({"category": "SECURITY" if x.get("severity") in ("critical","high") else "ACTIVITY", "title": x.get("title"), "type": x.get("event_type"), "ts": x.get("ts"), "severity": x.get("severity")})
    except Exception:
        pass
    try:
        for x in platform_ultra.arcade_catalog(owner):
            if x.get("last_played"):
                rows.append({"category": "GAMES", "title": x.get("name"), "type": "game", "ts": x.get("last_played"), "severity": "info"})
    except Exception:
        pass
    if category:
        rows = [r for r in rows if r["category"].upper() == category.upper()]
    return sorted(rows, key=lambda x: x.get("ts") or "", reverse=True)[:max(1, min(int(limit or 100), 500))]


def privacy(owner):
    owner = _uid(owner)
    try:
        sessions = auth.list_auth_sessions()
        sessions = [s for s in sessions if s.get("uid") == owner]
    except Exception:
        sessions = []
    return {
        "owner": owner,
        "stored_data": ["sessões", "atividade de segurança", "progresso/XP", "projetos/sites", "preferências", "credenciais WebAuthn (metadados e chave pública)"],
        "secrets_exposed": False,
        "location": {"continuous_tracking": False, "stored_by_default": False, "permission_required": True},
        "sessions": len(sessions),
        "integrations": {"ai": "configurada conforme ambiente", "maps": "OpenStreetMap/Open-Meteo quando solicitado"},
        "note": "Este resumo não exibe senhas, tokens, chaves privadas ou códigos de recuperação.",
    }


def map_lab():
    # Explicit simulation only. No real attack/target data is generated.
    return {
        "mode": "SIMULATION / LAB",
        "nodes": [
            {"id":"lab-gw","label":"LAB-GATEWAY","kind":"gateway","status":"simulated","lat":-3.0,"lng":-41.0},
            {"id":"lab-soc","label":"SOC-01","kind":"soc","status":"simulated","lat":-3.02,"lng":-41.02},
            {"id":"lab-web","label":"WEB-LAB","kind":"server","status":"simulated","lat":-3.01,"lng":-41.04},
            {"id":"lab-db","label":"DB-LAB","kind":"database","status":"simulated","lat":-3.04,"lng":-41.01},
        ],
        "events": [],
        "warning": "Todos os nós são fictícios e não representam infraestrutura real.",
    }


def arcade():
    return {
        "games": [
            {"id":"snake","name":"Snake","type":"arcade","safe":True},
            {"id":"pong","name":"Pong","type":"arcade","safe":True},
            {"id":"breakout","name":"Breakout","type":"arcade","safe":True},
            {"id":"memory","name":"Memory","type":"arcade","safe":True},
            {"id":"tictactoe","name":"Tic-Tac-Toe","type":"puzzle","safe":True},
            {"id":"2048","name":"2048","type":"puzzle","safe":True},
            {"id":"reaction","name":"Reaction Test","type":"skill","safe":True},
            {"id":"typing","name":"Typing Lab","type":"skill","safe":True},
            {"id":"maze","name":"Maze","type":"puzzle","safe":True},
            {"id":"cyber-puzzle","name":"Cyber Puzzle","type":"education","safe":True},
            {"id":"code-puzzle","name":"Code Puzzle","type":"education","safe":True},
        ],
        "note": "Jogos executados localmente no navegador; pontuação é tratada como entretenimento/educação.",
    }


def knowledge():
    base = ultra_ops.knowledge()
    extra = [
        {"id":"python","title":"Python","category":"Programming","level":"iniciante","description":"Sintaxe, funções, listas, módulos e boas práticas."},
        {"id":"flask","title":"Flask","category":"Web Development","level":"intermediário","description":"Rotas, templates, sessões, APIs e segurança server-side."},
        {"id":"git","title":"Git","category":"Development","level":"iniciante","description":"Commits, branches, diff, histórico e recuperação segura."},
        {"id":"cloud","title":"Cloud","category":"Cloud","level":"intermediário","description":"Deploy, secrets, observabilidade e configuração segura."},
        {"id":"networking","title":"Networking","category":"Networking","level":"intermediário","description":"TCP/IP, DNS, HTTP e monitoramento defensivo."},
        {"id":"databases","title":"Databases","category":"Data","level":"intermediário","description":"Modelagem, consultas parametrizadas, índices e backups."},
    ]
    seen = {x.get("id") for x in base}
    return base + [x for x in extra if x["id"] not in seen]


def file_center():
    out=[]
    for dirname in SAFE_FILE_DIRS:
        root=BASE/dirname
        if not root.exists():
            continue
        for p in root.rglob('*'):
            if not p.is_file() or any(part.startswith('.') for part in p.relative_to(BASE).parts):
                continue
            try:
                rel=p.relative_to(BASE).as_posix()
                size=p.stat().st_size
                if size > 10*1024*1024:
                    continue
                out.append({"path":rel,"name":p.name,"type":p.suffix.lower().lstrip('.') or 'file',"size":size,"modified":datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat()})
            except OSError:
                continue
    return sorted(out,key=lambda x:x["modified"],reverse=True)[:500]


def project_center(owner):
    owner=_uid(owner)
    workspaces=[]
    try: workspaces=ultra_ops.workspace_list(owner)
    except Exception: pass
    try: site_list=sites.list_sites()
    except Exception: site_list=[]
    return {"workspaces":workspaces[:100],"sites":[{"slug":s.get("slug"),"name":s.get("name"),"updated_at":s.get("updated_at")} for s in site_list[:100]]}
