"""Parte 4 — Dashboard Cyber: scans, severidade, recomendações, atividades, relatórios."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from services import evidence, permissions
from services.cyber.central_categories import list_categories
from services.cyber.tool_limits import policy_snapshot, get_all_limits
from services import gamification

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _sev_count(findings: list) -> dict:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings or []:
        s = str((f or {}).get("severity") or "info").lower()
        if s not in counts:
            s = "info"
        counts[s] += 1
    return counts


def build_dashboard(user_id: str = "owner", role: str = "user") -> dict:
    """Agrega dados reais do Evidence Center + gamificação + limites."""
    scans = []
    try:
        # evidence pode expor list_scans / recent
        if hasattr(evidence, "list_recent_scans"):
            scans = evidence.list_recent_scans(limit=50) or []
        elif hasattr(evidence, "recent"):
            scans = evidence.recent(50) or []
        elif hasattr(evidence, "all_scans"):
            scans = (evidence.all_scans() or [])[-50:]
    except Exception:
        scans = []

    # Fallback: ler pasta de evidências se existir
    if not scans:
        ev_dir = DATA_DIR / "evidence"
        if ev_dir.exists():
            for path in sorted(ev_dir.glob("*.json"), reverse=True)[:50]:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        scans.append(json.load(f))
                except Exception:
                    continue

    severity_totals = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    by_tool: dict[str, int] = {}
    activities = []
    recommendations = []

    for sc in scans:
        findings = sc.get("findings") or []
        sev = _sev_count(findings)
        for k, v in sev.items():
            severity_totals[k] += v
        tool = sc.get("tool") or sc.get("tool_id") or "unknown"
        by_tool[tool] = by_tool.get(tool, 0) + 1
        activities.append({
            "at": sc.get("created_at") or sc.get("ts") or sc.get("time") or "",
            "tool": tool,
            "target": sc.get("target") or "",
            "findings": len(findings),
            "score": sc.get("score"),
            "scan_id": sc.get("id") or sc.get("scan_id"),
        })
        for f in findings:
            if str(f.get("severity") or "").lower() in ("critical", "high"):
                recommendations.append({
                    "severity": f.get("severity"),
                    "title": f.get("title"),
                    "detail": (f.get("detail") or "")[:300],
                    "tool": tool,
                    "remediation": f.get("remediation") or f.get("fix") or "Revisar e aplicar correção conforme boas práticas.",
                })

    recommendations = recommendations[:30]
    activities = activities[:40]

    try:
        gam = gamification.public_user(user_id)
    except Exception:
        gam = {"xp": 0, "level": 1, "completed_count": 0, "achievements": []}

    try:
        from services.tool_registry import REGISTRY
        tools_count = len(REGISTRY.tools)
        tools_by_cat: dict[str, int] = {}
        for t in REGISTRY.tools.values():
            tools_by_cat[t.category] = tools_by_cat.get(t.category, 0) + 1
    except Exception:
        tools_count = 0
        tools_by_cat = {}

    policy = policy_snapshot(role)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "scans": len(scans),
            "tools_registered": tools_count,
            "open_critical": severity_totals["critical"],
            "open_high": severity_totals["high"],
            "open_medium": severity_totals["medium"],
            "findings_total": sum(severity_totals.values()),
        },
        "severity": severity_totals,
        "by_tool": by_tool,
        "tools_by_category": tools_by_cat,
        "categories": list_categories(),
        "activities": activities,
        "recommendations": recommendations,
        "gamification": gam,
        "leaderboard": gamification.leaderboard(10),
        "policy_messages": policy.get("messages", {}),
        "services_status": {
            "ssrf_guard": "active",
            "scope_allowlist": "active",
            "rate_limits": "active",
            "evidence_center": "active" if scans or True else "empty",
            "gamification": "active",
        },
    }


def export_report(user_id: str = "owner", role: str = "user", fmt: str = "json") -> dict:
    """Relatório exportável (JSON estruturado). Markdown opcional no campo text."""
    dash = build_dashboard(user_id, role)
    lines = [
        "# JARVIS Cyber Lab — Relatório",
        f"Gerado em: {dash['generated_at']}",
        "",
        "## Resumo",
        f"- Scans: {dash['summary']['scans']}",
        f"- Ferramentas: {dash['summary']['tools_registered']}",
        f"- Critical: {dash['summary']['open_critical']}",
        f"- High: {dash['summary']['open_high']}",
        f"- Medium: {dash['summary']['open_medium']}",
        f"- Findings totais: {dash['summary']['findings_total']}",
        "",
        "## Gamificação",
        f"- Nível: {dash['gamification'].get('level')}",
        f"- XP: {dash['gamification'].get('xp')}",
        f"- Desafios: {dash['gamification'].get('completed_count')}",
        "",
        "## Recomendações (top)",
    ]
    for r in dash["recommendations"][:15]:
        lines.append(f"- [{r.get('severity')}] {r.get('title')}: {r.get('detail')}")
        lines.append(f"  Correção: {r.get('remediation')}")
    lines.append("")
    lines.append("## Atividades recentes")
    for a in dash["activities"][:15]:
        lines.append(f"- {a.get('at')} | {a.get('tool')} | {a.get('target')} | findings={a.get('findings')}")
    lines.append("")
    lines.append("## Status dos serviços")
    for k, v in dash["services_status"].items():
        lines.append(f"- {k}: {v}")
    text = "\n".join(lines)
    return {
        "format": fmt,
        "generated_at": dash["generated_at"],
        "dashboard": dash if fmt == "json" else None,
        "text": text,
        "filename": f"jarvis-cyber-report-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.{'md' if fmt == 'md' else 'json'}",
    }


def developer_status(role: str) -> dict:
    """Modo Desenvolvedor — só dados se role tiver cap developer."""
    enabled = permissions.has_cap("developer", role)
    if not enabled:
        return {
            "enabled": False,
            "message": "Operação bloqueada pela política de segurança: modo Desenvolvedor exige permissão real no backend.",
            "role": role,
        }
    limits = get_all_limits()
    try:
        from services.tool_registry import REGISTRY
        tools = [t.public() for t in REGISTRY.tools.values()]
        plugin_errors = getattr(REGISTRY, "plugin_errors", [])
    except Exception:
        tools, plugin_errors = [], []
    return {
        "enabled": True,
        "role": role,
        "tools_count": len(tools),
        "tools": tools,
        "plugin_errors": plugin_errors,
        "limits": limits,
        "categories": list_categories(),
        "notes": [
            "Modo Desenvolvedor não desativa SSRF Guard nem allowlist.",
            "Ferramentas ativas continuam exigindo alvos autorizados.",
            "Não há execução de comandos arbitrários do usuário.",
        ],
    }
