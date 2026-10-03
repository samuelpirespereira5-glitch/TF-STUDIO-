"""Rotas do Jarvis (Tool Router), Cyber Lab, memória, diagnóstico e admin.

Permissão: `permissions.enforce_path()` (before_request) protege por prefixo
(/api/cyber → cyber, /api/admin → manage_access, /api/diagnostics →
diagnostics). Rotas que precisam de algo mais forte usam @require_cap.
"""
import json

from flask import Blueprint, Response, jsonify, request, session, stream_with_context, render_template

from services import (auth as auth_service, diagnostics, evidence, memory,
                      permissions, scope, tool_router)
from services import builtin_tools  # noqa: F401  (registra as ferramentas)
from services.investigator import build_report
from services.permissions import require_cap
from services.tool_registry import REGISTRY, execute
from services import mega_expansion
from services import game_lab
from services import security
from services import platform_ultra
from services import experience6
from services import programming7
from services import learning8
from services import ecosystem8
from services import phase9

bp = Blueprint("cyber", __name__)


def _uid():
    return session.get("tf_uid") or ("owner" if permissions.current_role() == "owner" else "anon")


def _sid():
    return _uid()


def _json():
    return request.get_json(silent=True) or {}


# ------------------------------------------------------------- identidade
@bp.get("/api/me")
def api_me():
    role = permissions.current_role()
    return jsonify({"role": role, "capabilities": permissions.caps_for(role), "uid": _uid()})


# ------------------------------------------------------------- Jarvis
@bp.get("/api/jarvis/tools")
def api_tools():
    role = permissions.current_role()
    return jsonify({"tools": REGISTRY.list_for(role), "role": role,
                    "plugin_errors": REGISTRY.plugin_errors if permissions.has_cap("diagnostics") else []})


@bp.post("/api/jarvis/route")
def api_route():
    """Só planeja (não executa): mostra qual(is) ferramenta(s) o Jarvis usaria."""
    text = _json().get("text", "")
    pl = tool_router.plan(text, permissions.current_role(), _sid())
    return jsonify(pl)


@bp.post("/api/jarvis/run")
def api_run():
    """Planeja E executa, transmitindo eventos NDJSON (explicação, progresso,
    diagnóstico, resultado). Cada linha é um JSON."""
    d = _json()
    role = permissions.current_role()
    if d.get("steps"):  # plano já decidido pelo front (ex.: botão de uma ferramenta)
        pl = {"mode": "tools", "target": d.get("target"), "steps": d["steps"],
              "explain": d.get("explain", "Executando ferramenta solicitada.")}
    else:
        pl = tool_router.plan(d.get("text", ""), role, _sid())
    sid = _sid()

    def gen():
        try:
            for ev in tool_router.run_plan(pl, role, sid):
                yield json.dumps(ev, ensure_ascii=False, default=str) + "\n"
        except Exception as e:  # o stream nunca morre mudo
            yield json.dumps({"event": "error", "error": str(e)}) + "\n"

    return Response(stream_with_context(gen()), mimetype="application/x-ndjson",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@bp.post("/api/jarvis/tool/<tool_id>")
def api_tool_exec(tool_id):
    role = permissions.current_role()
    res = execute(tool_id, _json().get("params", {}), role, {"session_id": _sid()})
    if not res["ok"]:
        d = tool_router.diagnose(res["error"], res.get("error_type", ""), tool_id, _json().get("params", {}))
        res["diagnostic"] = {"cause": d["cause"], "advice": d["advice"]}
        return jsonify(res), (403 if res.get("error_type") == "PermissionDenied" else 400)
    if res.get('ok'):
        try:
            ultra_ops.mark_tool_used(_uid(), tool_id)
            ultra_ops.add_timeline(_uid(), 'tool', f"Ferramenta: {tool_id}", 'info', _uid(), _json().get('params',{}).get('target',''), {'duration_ms':res.get('duration_ms')})
        except Exception:
            pass
    return jsonify(res)


# ------------------------------------------------------------- memória
@bp.get("/api/jarvis/memory")
def api_mem_list():
    return jsonify({"facts": memory.list_facts(_uid())})


@bp.post("/api/jarvis/memory")
def api_mem_add():
    try:
        memory.remember(_uid(), _json().get("text", ""))
        return jsonify({"ok": True, "facts": memory.list_facts(_uid())})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.delete("/api/jarvis/memory")
def api_mem_del():
    memory.forget(_uid(), request.args.get("id"))
    return jsonify({"ok": True})


# ------------------------------------------------------------- Cyber Lab
@bp.get("/api/cyber/targets")
def api_targets():
    return jsonify({"targets": scope.list_targets()})


@bp.post("/api/cyber/targets")
@require_cap("cyber_targets")
def api_target_add():
    d = _json()
    try:
        item = scope.add_target(d.get("target", ""), d.get("note", ""),
                                bool(d.get("confirm_ownership")), added_by=_uid())
        return jsonify({"ok": True, "target": item})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.delete("/api/cyber/targets")
@require_cap("cyber_targets")
def api_target_del():
    ok = scope.remove_target(request.args.get("target", ""))
    return jsonify({"ok": ok})


@bp.get("/api/cyber/history")
def api_history():
    return jsonify({"scans": evidence.history(request.args.get("target"), request.args.get("tool"),
                                              min(int(request.args.get("limit", 50)), 200))})


@bp.get("/api/cyber/scan/<int:scan_id>")
def api_scan(scan_id):
    s = evidence.get_scan(scan_id)
    return (jsonify(s) if s else (jsonify({"error": "Scan não encontrado."}), 404))


@bp.get("/api/cyber/compare")
def api_compare():
    a, b = evidence.get_scan(request.args.get("before", 0)), evidence.get_scan(request.args.get("after", 0))
    if not a or not b:
        return jsonify({"error": "Informe before e after (ids de scans existentes)."}), 400
    if (a["target"], a["tool"]) != (b["target"], b["tool"]):
        return jsonify({"error": "Só é possível comparar scans do mesmo alvo e ferramenta."}), 400
    return jsonify(evidence.compare(a, b))


@bp.post("/api/cyber/retest")
def api_retest():
    """RETESTE: roda de novo a mesma ferramenta no mesmo alvo e compara com o
    scan anterior (mostra o que foi corrigido, o que persiste e o que é novo)."""
    d = _json()
    tool_id, target = d.get("tool"), d.get("target")
    role = permissions.current_role()
    res = execute(tool_id, {"target": target}, role, {"session_id": _sid()})
    if not res["ok"]:
        return jsonify(res), 400
    rows = evidence.history(target=evidence.normalize_target(target), tool=tool_id, limit=2)
    cmp_ = evidence.compare(rows[1], rows[0]) if len(rows) == 2 else None
    return jsonify({"result": res, "comparison": cmp_,
                    "note": None if cmp_ else "Não havia scan anterior para comparar."})


@bp.get("/api/cyber/dashboard")
def api_dashboard():
    """Dashboard agregado: Evidence Center + severidade + gamificação + status."""
    base = evidence.dashboard() if hasattr(evidence, "dashboard") else {}
    try:
        from services import cyber_dashboard, permissions as perms
        role = perms.current_role()
        uid = _uid()
        extra = cyber_dashboard.build_dashboard(uid, role)
        # merge sem apagar o que o evidence já fornece
        if isinstance(base, dict):
            base = {**extra, "evidence": base}
        else:
            base = extra
    except Exception as e:
        if isinstance(base, dict):
            base = dict(base)
            base["cyber_dashboard_error"] = str(e)[:200]
    return jsonify(base)


@bp.get("/api/cyber/audit")
@require_cap("cyber_advanced")
def api_audit():
    from services import telemetry
    return jsonify({"log": telemetry.recent(min(int(request.args.get("limit", 100)), 500))})


@bp.get("/api/cyber/cheatsheet")
def api_cheatsheet():
    from services.cheatsheet import CHEATSHEET
    return jsonify({"sheets": CHEATSHEET})


@bp.post("/api/cyber/report")
def api_report():
    """Relatório em Markdown a partir dos ÚLTIMOS scans salvos do alvo."""
    target = evidence.normalize_target(_json().get("target", "").strip())
    rows = evidence.history(target=target, limit=100)
    if not rows:
        return jsonify({"error": "Nenhum scan salvo para este alvo. Rode uma análise primeiro."}), 404
    latest = {}
    for r in rows:  # já vem do mais novo para o mais antigo
        latest.setdefault(r["tool"], r)
    full = {t: evidence.get_scan(r["id"]) for t, r in latest.items()}
    findings = {f["id"]: f for r in latest.values() for f in r["findings"]}
    raws = {t: (s or {}).get("raw") for t, s in full.items()}
    return jsonify({"markdown": build_report(target, list(findings.values()), raws),
                    "score": evidence.risk_score(list(findings.values())), "tools": sorted(latest)})


@bp.post("/api/cyber/investigate")
def api_investigate():
    """Security Investigator em NDJSON (progresso por estágio)."""
    d = _json()
    role = permissions.current_role()
    from services.investigator import investigate

    def gen():
        try:
            for ev in investigate(d.get("target", ""), role, _sid(), do_ports=d.get("ports", True),
                                  do_subdomains=d.get("subdomains", False)):
                yield json.dumps(ev, ensure_ascii=False, default=str) + "\n"
        except Exception as e:
            yield json.dumps({"event": "error", "error": str(e)}) + "\n"

    return Response(stream_with_context(gen()), mimetype="application/x-ndjson",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------- diagnóstico
@bp.post("/api/diagnostics/run")
def api_diag():
    return jsonify(diagnostics.run_selfcheck(fix=bool(_json().get("fix", True))))


# ------------------------------------------------------------- admin
@bp.get("/api/admin/keys")
def api_keys():
    return jsonify({"keys": auth_service.list_role_keys()})


@bp.post("/api/admin/keys")
def api_key_create():
    d = _json()
    try:
        key = auth_service.create_role_key(d.get("role", "user"), d.get("label", ""))
        return jsonify({"ok": True, "key": key, "note": "Guarde agora: a chave não será mostrada de novo."})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.delete("/api/admin/keys")
def api_key_revoke():
    return jsonify({"ok": auth_service.revoke_role_key(request.args.get("id", ""))})


# ------------------------------------------------------------- Blue Team / Threat Intel / Forense
from services.cyber import blue as blue_service


@bp.get("/api/cyber/mitre")
def api_mitre():
    return jsonify({"tactics": blue_service.mitre_lookup(request.args.get("q", ""))})


@bp.post("/api/cyber/ioc/check")
def api_ioc_check():
    return jsonify(blue_service.check_hash_against_feed(_json().get("hash", "")))


@bp.post("/api/cyber/waf/generate")
def api_waf_generate():
    d = _json()
    return jsonify(blue_service.generate_waf_rules(d.get("engine", "nginx"), d.get("patterns", [])))


@bp.post("/api/cyber/headers/audit")
def api_headers_audit():
    r = blue_service.audit_http_headers(_json().get("headers", ""))
    r["summary"] = f"{len(r['findings'])} cabeçalho(s) de segurança ausente(s) ou fraco(s)"
    return jsonify(r)


@bp.post("/api/cyber/fim/hash")
def api_fim_hash():
    return jsonify(blue_service.fim_hash_files(_json().get("files", {})))


@bp.post("/api/cyber/fim/compare")
def api_fim_compare():
    d = _json()
    return jsonify(blue_service.fim_compare(d.get("baseline", {}), d.get("current", {})))


@bp.post("/api/cyber/email/analyze")
def api_email_analyze():
    r = blue_service.analyze_email_headers(_json().get("headers", ""))
    r["summary"] = f"SPF={r['raw']['spf']} DKIM={r['raw']['dkim']} DMARC={r['raw']['dmarc']} · {len(r['findings'])} achado(s)"
    return jsonify(r)


@bp.get("/api/cyber/ir/playbooks")
def api_ir_list():
    return jsonify({"playbooks": blue_service.list_ir_playbooks()})


@bp.get("/api/cyber/ir/playbooks/<key>")
def api_ir_get(key):
    pb = blue_service.get_ir_playbook(key)
    if not pb:
        return jsonify({"error": "playbook não encontrado"}), 404
    return jsonify(pb)


@bp.post("/api/cyber/tests/generate")
def api_tests_generate():
    d = _json()
    return jsonify(blue_service.generate_security_tests(d.get("language", "python"), d.get("endpoints", [])))


@bp.get("/api/cyber/ctf/challenges")
def api_ctf_list():
    return jsonify({"challenges": blue_service.list_ctf_challenges()})


@bp.get("/api/cyber/ctf/challenges/<cid>")
def api_ctf_get(cid):
    c = blue_service.get_ctf_challenge(cid, reveal_fix=request.args.get("reveal") == "1")
    if not c:
        return jsonify({"error": "desafio não encontrado"}), 404
    return jsonify(c)


@bp.post("/api/cyber/ctf/challenges/<cid>/check")
def api_ctf_check(cid):
    return jsonify(blue_service.check_ctf_answer(cid, _json().get("code", "")))


@bp.post("/api/cyber/audit/report")
def api_audit_report():
    """Gera relatório consolidado a partir de findings enviados pelo front (já reunidos de vários scans)
    OU, se nenhum for enviado, usa o histórico salvo do alvo (evidence.history)."""
    d = _json()
    findings = d.get("findings")
    target = d.get("target", "aplicação")
    if not findings:
        target_key = evidence.normalize_target(target)
        rows = evidence.history(target=target_key, limit=200)
        seen = {}
        for r in rows:
            for f in r["findings"]:
                seen.setdefault(f["id"], f)
        findings = list(seen.values())
    fmt = d.get("format", "markdown")
    report = blue_service.generate_audit_report(findings, fmt=fmt, target=target)
    score = blue_service.compute_security_score(findings)
    return jsonify({"report": report, "format": fmt, "security_score": score})


@bp.post("/api/cyber/password/strength")
def api_pwd_strength():
    return jsonify(blue_service.analyze_password_strength(_json().get("password", "")))


@bp.post("/api/cyber/malware/scan")
def api_malware_scan():
    d = _json()
    r = blue_service.scan_malware_patterns(d.get("text", ""), d.get("filename", ""))
    r["summary"] = f"{len(r['findings'])} padrão(ões) suspeito(s)"
    return jsonify(r)


# ------------------------------------------------------------- Vulnerability Doctor
from services.cyber import vulndoctor as vulndoctor_service


@bp.post("/api/cyber/vulndoctor")
def api_vulndoctor():
    d = _json()
    return jsonify(vulndoctor_service.diagnose(d.get("text", ""), d.get("filename", "")))


@bp.get("/api/cyber/vulndoctor/sites")
def api_vulndoctor_sites():
    from services import sites_service
    return jsonify({"sites": [{"slug": s["slug"], "name": s.get("name") or s["slug"]} for s in sites_service.list_sites()]})


@bp.post("/api/cyber/vulndoctor/site")
def api_vulndoctor_site():
    try:
        return jsonify(vulndoctor_service.diagnose_site(_json().get("slug", "")))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


# ------------------------------------------------------------- Cyber Hub (catálogo por categoria)
from services import cyber_hub


@bp.get("/api/cyber/hub")
def api_cyber_hub():
    return jsonify({"catalog": cyber_hub.catalog_public(REGISTRY)})




@bp.get("/api/cyber/gamification")
def api_cyber_gamification():
    from services import gamification, permissions as perms, challenges
    role = perms.current_role()
    uid = _uid()
    try:
        from services import sites_service as sv
        completed = []
        for site in (sv.list_sites() or []):
            if site.get("challenge_status") == "concluido" and site.get("challenge_id"):
                completed.append(site["challenge_id"])
        gamification.sync_from_challenge_sites(uid, completed, challenges.CATALOG)
    except Exception:
        pass
    return jsonify({
        "user": gamification.public_user(uid),
        "leaderboard": gamification.leaderboard(20),
        "achievements_catalog": gamification.achievements_catalog(),
    })


@bp.get("/api/cyber/developer")
def api_cyber_developer_status():
    from services import cyber_dashboard, permissions as perms
    return jsonify(cyber_dashboard.developer_status(perms.current_role()))


@bp.get("/api/cyber/report/export")
def api_cyber_report_export():
    from services import cyber_dashboard, permissions as perms
    role = perms.current_role()
    uid = _uid()
    fmt = (request.args.get("format") or "json").lower()
    if fmt not in ("json", "md"):
        fmt = "json"
    return jsonify(cyber_dashboard.export_report(uid, role, fmt))

@bp.get("/api/cyber/policies")
def api_cyber_policies():
    """Limites atuais, mensagens de política e categorias da Central de Ferramentas."""
    from services.cyber.tool_limits import policy_snapshot
    from services.cyber.central_categories import list_categories, hub_catalog
    from services import permissions as perms
    role = perms.current_role()
    snap = policy_snapshot(role)
    return jsonify({
        "role": role,
        "policy": snap,
        "categories": list_categories(),
        "notes": hub_catalog().get("policy_notes", []),
        "messages": snap.get("messages", {}),
    })


# ------------------------------------------------------------- TryHackMe Lab (área privada do dono)
from services import thm_lab


@bp.get("/api/thm/categories")
def api_thm_categories():
    return jsonify({"categories": thm_lab.categories()})


@bp.get("/api/thm/items")
def api_thm_items():
    items = thm_lab.list_items(
        category=request.args.get("category") or None,
        q=request.args.get("q") or None,
        only_favorites=request.args.get("favorites") == "1",
        tag=request.args.get("tag") or None,
    )
    return jsonify({"items": items, "stats": thm_lab.stats()})


@bp.post("/api/thm/items")
def api_thm_item_add():
    d = _json()
    try:
        item = thm_lab.add_item(
            title=d.get("title", ""), category=d.get("category", ""), kind=d.get("kind", "tool"),
            description=d.get("description", ""), content=d.get("content", ""),
            tags=d.get("tags", []), url=d.get("url", ""),
        )
        return jsonify({"ok": True, "item": item})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.get("/api/thm/items/<item_id>")
def api_thm_item_get(item_id):
    item = thm_lab.register_view(item_id, by=_uid())
    if not item:
        return jsonify({"error": "Item não encontrado."}), 404
    return jsonify({"item": item})


@bp.put("/api/thm/items/<item_id>")
def api_thm_item_update(item_id):
    d = _json()
    try:
        return jsonify({"ok": True, "item": thm_lab.update_item(item_id, **d)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.delete("/api/thm/items/<item_id>")
def api_thm_item_delete(item_id):
    return jsonify({"ok": thm_lab.delete_item(item_id)})


@bp.post("/api/thm/items/<item_id>/favorite")
def api_thm_item_favorite(item_id):
    try:
        return jsonify({"ok": True, "item": thm_lab.toggle_favorite(item_id)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.get("/api/thm/history")
def api_thm_history():
    return jsonify({"history": thm_lab.history(min(int(request.args.get("limit", 50)), 300))})


@bp.delete("/api/thm/history")
def api_thm_history_clear():
    thm_lab.clear_history()
    return jsonify({"ok": True})

# ------------------------------------------------------------- Phase 2
@bp.get("/api/cyber/phase2/dashboard")
def api_phase2_dashboard():
    from services import cyber_phase2
    return jsonify(cyber_phase2.dashboard(_uid()))


@bp.get("/api/cyber/phase2/tools")
def api_phase2_tools():
    from services import cyber_phase2
    return jsonify({"tools": cyber_phase2.tool_preferences(_uid())})


@bp.post("/api/cyber/phase2/tools/<tool_id>/favorite")
@require_cap("cyber_advanced")
def api_phase2_tool_favorite(tool_id):
    from services import cyber_phase2
    return jsonify({"ok": True, "favorite": cyber_phase2.toggle_favorite(_uid(), tool_id)})


@bp.get("/api/cyber/phase2/assets")
@require_cap("cyber_advanced")
def api_phase2_assets():
    from services import cyber_phase2
    return jsonify({"assets": cyber_phase2.list_assets(_uid())})


@bp.post("/api/cyber/phase2/assets")
@require_cap("cyber_advanced")
def api_phase2_asset_create():
    from services import cyber_phase2
    d = _json()
    try:
        return jsonify({"ok": True, "asset": cyber_phase2.create_asset(
            _uid(), d.get("name", ""), d.get("target", ""), d.get("environment", "development"), d.get("description", ""))})
    except (ValueError, Exception) as e:
        return jsonify({"error": str(e)[:300]}), 400


@bp.delete("/api/cyber/phase2/assets/<int:asset_id>")
@require_cap("cyber_advanced")
def api_phase2_asset_delete(asset_id):
    from services import cyber_phase2
    return jsonify({"ok": cyber_phase2.delete_asset(_uid(), asset_id)})


@bp.get("/api/cyber/phase2/projects")
@require_cap("cyber_advanced")
def api_phase2_projects():
    from services import cyber_phase2
    return jsonify({"projects": cyber_phase2.list_projects(_uid())})


@bp.post("/api/cyber/phase2/projects")
@require_cap("cyber_advanced")
def api_phase2_project_create():
    from services import cyber_phase2
    d = _json()
    try:
        return jsonify({"ok": True, "project": cyber_phase2.create_project(_uid(), d.get("name", ""), d.get("description", ""))})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.post("/api/cyber/phase2/projects/<int:project_id>/assets/<int:asset_id>")
@require_cap("cyber_advanced")
def api_phase2_project_attach(project_id, asset_id):
    from services import cyber_phase2
    try:
        cyber_phase2.attach_asset(_uid(), project_id, asset_id)
        return jsonify({"ok": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.get("/api/cyber/phase2/alerts")
@require_cap("cyber_advanced")
def api_phase2_alerts():
    from services import cyber_phase2
    return jsonify({"alerts": cyber_phase2.alerts(_uid(), min(int(request.args.get("limit", 50)), 200))})


@bp.post("/api/cyber/phase2/alerts/<int:alert_id>/read")
@require_cap("cyber_advanced")
def api_phase2_alert_read(alert_id):
    from services import cyber_phase2
    return jsonify({"ok": cyber_phase2.mark_alert_read(_uid(), alert_id)})


@bp.get("/api/cyber/phase2/finding/<int:scan_id>/<finding_id>")
@require_cap("cyber_advanced")
def api_phase2_finding(scan_id, finding_id):
    from services import cyber_phase2
    f = cyber_phase2.finding(scan_id, finding_id)
    if not f:
        return jsonify({"error": "Finding não encontrado."}), 404
    f["state"] = cyber_phase2.get_finding_state(_uid(), scan_id, finding_id)
    return jsonify({"finding": f})


@bp.post("/api/cyber/phase2/finding/<int:scan_id>/<finding_id>/state")
@require_cap("cyber_advanced")
def api_phase2_finding_state(scan_id, finding_id):
    from services import cyber_phase2
    d = _json()
    try:
        cyber_phase2.set_finding_state(_uid(), scan_id, finding_id, d.get("status", "open"), d.get("justification", ""))
        return jsonify({"ok": True, "state": cyber_phase2.get_finding_state(_uid(), scan_id, finding_id)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.post("/api/cyber/phase2/finding/<int:scan_id>/<finding_id>/rescan")
@require_cap("cyber_advanced")
def api_phase2_finding_rescan(scan_id, finding_id):
    from services import cyber_phase2
    f = cyber_phase2.finding(scan_id, finding_id)
    if not f:
        return jsonify({"error": "Finding não encontrado."}), 404
    tool = f["scan"]["tool"]
    target = f["scan"]["target"]
    role = permissions.current_role()
    res = execute(tool, {"target": target}, role, {"session_id": _sid()})
    if not res.get("ok"):
        return jsonify(res), 400
    rows = evidence.history(target=target, tool=tool, limit=2)
    cmp_ = evidence.compare(rows[1], rows[0]) if len(rows) == 2 else None
    return jsonify({"ok": True, "result": res, "comparison": cmp_})


@bp.get("/api/cyber/phase2/report/html")
@require_cap("cyber_advanced")
def api_phase2_report_html():
    from services import cyber_phase2
    try:
        target = request.args.get("target", "").strip()
        report = cyber_phase2.report_html(target)
        return Response(report, mimetype="text/html")
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.get("/api/cyber/phase2/self-audit")
@require_cap("cyber_advanced")
def api_phase2_self_audit():
    """Read-only static review of the current source tree using existing analyzers."""
    from pathlib import Path
    from services.cyber import local
    base = Path(__file__).resolve().parent
    findings = []
    seen = set()
    for root in (base / "services", base / "static", base / "templates", base):
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p in seen or not p.is_file() or ".git" in p.parts or "__pycache__" in p.parts:
                continue
            seen.add(p)
            if p.suffix.lower() not in {".py", ".js", ".html"}:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")[:400000]
            except Exception:
                continue
            rel = str(p.relative_to(base))
            if p.suffix.lower() in {".py", ".js"}:
                findings.extend(local.scan_code(text, rel)["findings"])
            findings.extend(local.scan_secrets(text, rel)["findings"])
    # The self-audit is advisory: findings still need code-context review.
    return jsonify({"ok": True, "findings": findings, "count": len(findings),
                    "note": "Revisão estática baseada em evidência; confirme contexto antes de tratar um alerta como vulnerabilidade."})

@bp.post("/api/cyber/phase2/jarvis-analyze/<int:scan_id>")
@require_cap("cyber_advanced")
def api_phase2_jarvis_analyze(scan_id):
    from services import ai_engine, cyber_phase2
    scan = evidence.get_scan(scan_id)
    if not scan:
        return jsonify({"error": "Scan não encontrado."}), 404
    findings = scan.get("findings", [])
    facts = json.dumps({"scan_id": scan["id"], "target": scan["target"], "tool": scan["tool"],
                        "score": scan["score"], "findings": findings}, ensure_ascii=False, default=str)[:30000]
    prompt = ("Você é o módulo JARVIS Analyst do Cyber Lab. Analise SOMENTE os fatos do scan abaixo. "
              "Não invente vulnerabilidades, evidências, endpoints ou impactos. Se algo não estiver nos dados, diga que não está disponível. "
              "Explique: resumo, prioridades de investigação sem ranking de preferência, evidência disponível, impacto documentado, correção e o que deve ser reverificado. "
              "Responda em português claro.\nDADOS DO SCAN:\n" + facts)
    try:
        reply = ai_engine.ai_chat([{"role": "system", "content": "Você é um analista de segurança baseado em evidências."},
                                   {"role": "user", "content": prompt}], max_tokens=1600, max_continuations=1)
        return jsonify({"ok": True, "scan_id": scan_id, "reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)[:300]}), 400


@bp.get("/api/cyber/phase2/report/pdf")
@require_cap("cyber_advanced")
def api_phase2_report_pdf():
    from services import cyber_phase2
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.enums import TA_LEFT
        import io
        target = request.args.get("target", "").strip()
        html_report = cyber_phase2.report_html(target)
        # Convert only the structured text we control; this endpoint is optional
        # and exists only when reportlab is already available in the environment.
        rows = evidence.history(target=evidence.normalize_target(target), limit=30)
        buf = io.BytesIO(); doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet(); story = [Paragraph("Relatório de Segurança", styles["Title"]), Paragraph(f"Alvo: {target}", styles["BodyText"]), Paragraph("Escopo: alvo previamente autorizado pelo Cyber Lab", styles["BodyText"]), Spacer(1, 12)]
        for r in rows:
            story.append(Paragraph(f"Scan #{r['id']} · {r['tool']} · score {r['score']} · {r['ts']}", styles["Heading3"]))
            for f in r.get("findings", []):
                story.append(Paragraph(f"{f.get('severity','').upper()} — {f.get('title','')}", styles["Heading4"]))
                story.append(Paragraph(f"Evidência: {f.get('evidence','')}", styles["BodyText"]))
                story.append(Paragraph(f"Correção: {f.get('fix','')}", styles["BodyText"]))
                story.append(Spacer(1, 6))
        doc.build(story); buf.seek(0)
        return Response(buf.read(), mimetype="application/pdf", headers={"Content-Disposition": "attachment; filename=security-report.pdf"})
    except ImportError:
        return jsonify({"error": "PDF indisponível neste ambiente; exporte o relatório HTML."}), 501
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

# ------------------------------------------------------------- Phase 4 / Security Center 2.0
from services import phase4 as phase4_service

@bp.get('/api/cyber/phase4/security-center')
def api_phase4_security_center():
    return jsonify(phase4_service.security_center(_uid()))

@bp.post('/api/cyber/phase4/security-audit')
def api_phase4_security_audit():
    result=phase4_service.self_audit()
    try:
        from services import telemetry
        telemetry.log(permissions.current_role(), _sid(), 'security_center_audit', 'jarvis', True, 0)
    except Exception: pass
    return jsonify(result)

@bp.get('/api/cyber/phase4/hardening')
def api_phase4_hardening():
    return jsonify({'checklist':phase4_service.hardening_checklist()})

@bp.get('/api/cyber/phase4/report')
def api_phase4_report():
    fmt=(request.args.get('format') or 'md').lower()
    if fmt not in ('md','json'): fmt='md'
    result=phase4_service.self_audit()
    body=phase4_service.report(result,fmt)
    if fmt=='json': return jsonify({'format':'json','report':json.loads(body),'generated_at':result['generated_at']})
    return jsonify({'format':'md','report':body,'filename':'jarvis-security-report.md','generated_at':result['generated_at']})

@bp.get('/api/cyber/phase4/challenges')
def api_phase4_challenges():
    return jsonify({'categories':phase4_service.CATEGORIES,'challenges':phase4_service.list_challenges()})

@bp.get('/api/cyber/phase4/challenges/<cid>')
def api_phase4_challenge(cid):
    c=phase4_service.get_challenge(cid,reveal=request.args.get('reveal')=='1')
    if not c: return jsonify({'error':'desafio não encontrado'}),404
    return jsonify(c)

@bp.post('/api/cyber/phase4/challenges/<cid>/check')
def api_phase4_challenge_check(cid):
    d=_json(); return jsonify(phase4_service.check_challenge(_uid(),cid,d.get('answer',''),hint=bool(d.get('hint')),reveal=bool(d.get('reveal'))))

@bp.get('/api/cyber/phase4/progression')
def api_phase4_progression():
    return jsonify(phase4_service.progression(_uid()))

@bp.get('/api/cyber/phase4/incidents')
def api_phase4_incidents():
    return jsonify({'incidents':phase4_service.incident_catalog()})

@bp.get('/cyber/phase4')
def phase4_page():
    return render_template('cyber_phase4.html')

# ------------------------------------------------------------- Mega Expansion / Operations Layer (Phase 5)
from services import phase5 as phase5_service

@bp.get('/api/cyber/operations/dashboard')
def api_ops_dashboard():
    return jsonify(phase5_service.dashboard(_uid()))

@bp.get('/api/cyber/operations/soc')
def api_ops_soc():
    return jsonify(phase5_service.soc(_uid(), request.args.get('q',''), request.args.get('severity',''), request.args.get('status','')))

@bp.post('/api/cyber/operations/incidents')
def api_ops_incident_create():
    d=_json()
    try: return jsonify(phase5_service.create_incident(_uid(),d.get('title'),d.get('severity','medium'),d.get('summary',''))), 201
    except ValueError as e: return jsonify({'error':str(e)}),400

@bp.patch('/api/cyber/operations/incidents/<int:iid>')
def api_ops_incident_update(iid):
    d=_json()
    try:
        r=phase5_service.update_incident(_uid(),iid,d.get('status'),d.get('severity'),d.get('summary'))
        return (jsonify(r),200) if r else (jsonify({'error':'incidente não encontrado'}),404)
    except ValueError as e: return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/operations/vulnerabilities')
def api_ops_vulns():
    return jsonify({'vulnerabilities':phase5_service.vulnerabilities(_uid())})

@bp.patch('/api/cyber/operations/vulnerabilities/<int:iid>')
def api_ops_vuln_update(iid):
    d=_json(); return jsonify({'vulnerabilities':phase5_service.update_vuln(_uid(),iid,d.get('status'),d.get('priority'),d.get('owner'),d.get('retest_scan'))})

@bp.get('/api/cyber/operations/assets')
def api_ops_assets():
    return jsonify({'assets':phase5_service.assets(_uid())})

@bp.get('/api/cyber/operations/threat-intel')
def api_ops_ioc_list():
    return jsonify({'indicators':phase5_service.list_iocs(_uid())})

@bp.post('/api/cyber/operations/threat-intel')
def api_ops_ioc_add():
    d=_json()
    try: return jsonify({'indicators':phase5_service.add_ioc(_uid(),d.get('kind'),d.get('value'),d.get('tag'),d.get('source'),d.get('confidence'),bool(d.get('simulated')))}),201
    except ValueError as e: return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/operations/academy')
def api_ops_academy(): return jsonify({'tracks':phase5_service.ACADEMY})

@bp.post('/api/cyber/operations/academy/complete')
def api_ops_academy_complete():
    d=_json(); return jsonify(phase5_service.award(_uid(),xp=min(100,max(5,int(d.get('xp',25) or 25))),lesson=str(d.get('lesson',''))[:100]))

@bp.get('/api/cyber/operations/labs')
def api_ops_labs(): return jsonify({'labs':phase5_service.LABS})

@bp.post('/api/cyber/operations/labs/complete')
def api_ops_lab_complete():
    d=_json(); return jsonify(phase5_service.award(_uid(),xp=min(300,max(10,int(d.get('xp',50) or 50))),lab=str(d.get('lab',''))[:100]))

@bp.get('/api/cyber/operations/progress')
def api_ops_progress(): return jsonify(phase5_service.progress(_uid()))

@bp.get('/api/cyber/operations/settings')
def api_ops_settings(): return jsonify(phase5_service.settings(_uid()))

@bp.patch('/api/cyber/operations/settings')
def api_ops_settings_update(): return jsonify(phase5_service.update_settings(_uid(),_json()))

@bp.get('/api/cyber/operations/audit')
def api_ops_audit():
    with phase5_service.conn() as c:
        rows=[dict(r) for r in c.execute('SELECT id,action,target,details,ts,entry_hash FROM p5_audit WHERE owner_uid=? ORDER BY id DESC LIMIT 200',(_uid(),)).fetchall()]
    return jsonify({'integrity':phase5_service.verify_audit(),'entries':rows})

@bp.get('/api/cyber/operations/report')
def api_ops_report():
    return jsonify({'format':'markdown','report':phase5_service.report(_uid()),'generated_at':phase5_service.now()})

@bp.get('/api/cyber/operations/search')
def api_ops_search():
    q=(request.args.get('q') or '').strip().lower()[:100]
    if not q: return jsonify({'results':[]})
    from services.tool_registry import REGISTRY
    results=[]
    for t in REGISTRY.list_for(permissions.current_role()):
        if q in (t['name']+' '+t['description']+' '+t['category']).lower(): results.append({'type':'tool','id':t['id'],'title':t['name'],'category':t['category']})
    for c in phase5_service.LABS:
        if q in json.dumps(c,ensure_ascii=False).lower(): results.append({'type':'lab','id':c['id'],'title':c['title'],'category':c['category']})
    for a in phase5_service.ACADEMY:
        if q in json.dumps(a,ensure_ascii=False).lower(): results.append({'type':'academy','id':a['id'],'title':a['title']})
    return jsonify({'results':results[:100]})

@bp.post('/api/cyber/operations/workflows/audit')
def api_ops_workflow_audit():
    """Safe workflow: executes only pre-approved local analysis tools on supplied text."""
    d=_json(); text=str(d.get('text',''))[:200000]
    if not text: return jsonify({'error':'Forneça material local para análise.'}),400
    from services.tool_registry import execute, REGISTRY
    allowed={'sast_secure_code_v5','ioc_matcher_v5','log_correlation_v5','baseline_diff_v5','api_schema_v5','forensics_integrity_v5'}
    requested=d.get('tools') or sorted(allowed); requested=[x for x in requested if x in allowed and REGISTRY.get(x)]
    if not requested: return jsonify({'error':'Nenhuma ferramenta permitida.'}),400
    out=[]
    for tid in requested[:6]: out.append(execute(tid,{'text':text},permissions.current_role(),{'session_id':_sid()}))
    phase5_service.audit(_uid(),'workflow.audit','local',f'tools={requested}')
    return jsonify({'ok':True,'cancelable_between_steps':True,'timeout_per_tool_seconds':10,'results':out})


# ------------------------------------------------------------- Final integrated operations / governance layer
from services import final_ops

@bp.get('/api/cyber/operations/cases')
def api_final_cases(): return jsonify({'cases':final_ops.cases(_uid())})
@bp.post('/api/cyber/operations/cases')
def api_final_case_create():
    d=_json()
    try:return jsonify(final_ops.create_case(_uid(),str(d.get('title','')),str(d.get('description','')),d.get('severity','medium'),str(d.get('assignee','')))),201
    except ValueError as e:return jsonify({'error':str(e)}),400
@bp.patch('/api/cyber/operations/cases/<int:cid>')
def api_final_case_update(cid):
    try:return jsonify(final_ops.update_case(_uid(),cid,**_json()))
    except ValueError as e:return jsonify({'error':str(e)}),400
@bp.post('/api/cyber/operations/cases/<int:cid>/links')
def api_final_case_link(cid):
    d=_json()
    try:return jsonify(final_ops.link_case(_uid(),cid,d.get('kind'),d.get('ref_id')))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/operations/detections')
def api_final_detections(): return jsonify({'rules':final_ops.detections(_uid()),'alerts':final_ops.alerts(_uid())})
@bp.post('/api/cyber/operations/detections')
def api_final_detection_create():
    d=_json()
    try:return jsonify({'rules':final_ops.create_detection(_uid(),str(d.get('name','')),d.get('severity','medium'),d.get('conditions'),d.get('tags'),str(d.get('mitre','')))}),201
    except ValueError as e:return jsonify({'error':str(e)}),400
@bp.patch('/api/cyber/operations/detections/<int:did>')
def api_final_detection_update(did):
    d=_json(); return jsonify({'rules':final_ops.set_detection(_uid(),did,d.get('enabled'),bool(d.get('suppress')))})
@bp.post('/api/cyber/operations/detections/correlate')
def api_final_correlate(): return jsonify({'alerts':final_ops.correlate(_uid(),request.args.get('window',15))})

@bp.get('/api/cyber/operations/posture')
def api_final_posture(): return jsonify({'controls':final_ops.posture(_uid())})
@bp.get('/api/cyber/operations/rbac')
def api_final_rbac(): return jsonify({'roles':final_ops.rbac()})
@bp.get('/api/cyber/operations/configuration')
def api_final_config(): return jsonify({'checks':final_ops.config_security()})
@bp.get('/api/cyber/operations/notifications')
def api_final_notifications(): return jsonify({'notifications':final_ops.notifications(_uid())})
@bp.get('/api/cyber/operations/audit/search')
def api_final_audit_search(): return jsonify({'entries':final_ops.audit_filtered(_uid(),request.args.get('q',''),request.args.get('action',''),request.args.get('limit',200))})
@bp.get('/api/cyber/operations/jobs')
def api_final_jobs(): return jsonify({'jobs':final_ops.jobs(_uid())})
@bp.post('/api/cyber/operations/jobs')
def api_final_job_create():
    d=_json(); return jsonify({'id':final_ops.create_job(_uid(),str(d.get('kind','audit')))}),201
@bp.patch('/api/cyber/operations/jobs/<jid>')
def api_final_job_update(jid): return jsonify(final_ops.update_job(_uid(),jid,**_json()) or {'error':'job não encontrado'})
@bp.get('/api/cyber/operations/health')
def api_final_health(): return jsonify(final_ops.health())
@bp.get('/health')
def api_health_public(): return jsonify({'status':'ok','service':'jarvis'})
@bp.get('/ready')
def api_ready_public():
    h=final_ops.health(); return jsonify(h), (200 if h['status']=='ok' else 503)
@bp.get('/status')
def api_status_public(): return jsonify({'status':'ok','timestamp':final_ops.now()})
@bp.get('/api/cyber/operations/governance')
def api_final_governance(): return jsonify(final_ops.api_governance())
@bp.get('/api/cyber/operations/final-dashboard')
def api_final_dashboard():
    d=phase5_service.dashboard(_uid()); return jsonify({**d,'alerts':len(final_ops.alerts(_uid())),'cases':len(final_ops.cases(_uid())),'notifications_unread':sum(1 for n in final_ops.notifications(_uid()) if not n.get('read_at')),'posture':final_ops.posture(_uid()),'health':final_ops.health()})

@bp.get('/api/cyber/operations/report/executive')
def api_final_exec_report(): return jsonify(final_ops.executive_report(_uid()))
@bp.get('/api/cyber/operations/scans/compare')
def api_final_scan_compare(): return jsonify(final_ops.compare_scans(_uid(),request.args.get('before'),request.args.get('after')))

@bp.get('/cyber/operations')
def phase5_page():
    return render_template('cyber_phase5.html')

# ------------------------------------------------------------- Ultra Expansion (incremental)
from services import ultra_ops

@bp.get('/cyber/ultra')
def ultra_page():
    return render_template('cyber_ultra.html')

@bp.get('/api/cyber/ultra/catalog')
def ultra_catalog():
    d=request.args
    return jsonify(ultra_ops.tool_catalog(_uid(),d.get('q',''),d.get('category',''),d.get('favorite')=='1',d.get('recent')=='1',d.get('sort','name'),permissions.current_role()))

@bp.patch('/api/cyber/ultra/tools/<tool_id>')
@require_cap('cyber_advanced')
def ultra_tool_state(tool_id):
    d=_json(); ultra_ops.set_tool_state(_uid(),tool_id,d.get('favorite')); return jsonify({'ok':True})

@bp.get('/api/cyber/ultra/workspaces')
def ultra_workspaces(): return jsonify({'workspaces':ultra_ops.workspace_list(_uid())})

@bp.post('/api/cyber/ultra/workspaces')
@require_cap('workspace_write')
def ultra_workspace_create():
    d=_json()
    try:return jsonify(ultra_ops.workspace_create(_uid(),d.get('name'),d.get('data'))),201
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/ultra/workspaces/<int:wid>')
def ultra_workspace_get(wid):
    r=ultra_ops.workspace_get(_uid(),wid); return (jsonify(r),200) if r else (jsonify({'error':'workspace não encontrado'}),404)

@bp.put('/api/cyber/ultra/workspaces/<int:wid>')
@require_cap('workspace_write')
def ultra_workspace_save(wid):
    r=ultra_ops.workspace_save(_uid(),wid,_json().get('data') or {}); return (jsonify(r),200) if r else (jsonify({'error':'workspace não encontrado'}),404)

@bp.post('/api/cyber/ultra/workspaces/<int:wid>/archive')
@require_cap('workspace_write')
def ultra_workspace_archive(wid): return jsonify(ultra_ops.workspace_archive(_uid(),wid))

@bp.get('/api/cyber/ultra/timeline')
def ultra_timeline():
    return jsonify({'events':ultra_ops.timeline(_uid(),request.args.get('days',30),request.args.get('type',''),request.args.get('severity',''),request.args.get('asset',''),request.args.get('user',''))})

@bp.post('/api/cyber/ultra/timeline')
@require_cap('cyber_advanced')
def ultra_timeline_add():
    d=_json(); return jsonify({'id':ultra_ops.add_timeline(_uid(),d.get('type','event'),d.get('title','Evento'),d.get('severity','info'),_uid(),d.get('asset',''),d.get('payload'))}),201

@bp.get('/api/cyber/ultra/score')
def ultra_score(): return jsonify(ultra_ops.security_score())

@bp.get('/api/cyber/ultra/recommendations')
def ultra_recommendations(): return jsonify({'recommendations':ultra_ops.posture_recommendations(_uid())})

@bp.get('/api/cyber/ultra/baseline')
def ultra_baseline(): return jsonify({'checks':ultra_ops.baseline()})

@bp.get('/api/cyber/ultra/drift')
def ultra_drift(): return jsonify(ultra_ops.drift(_uid(),request.args.get('kind','security')))

@bp.post('/api/cyber/ultra/snapshots')
@require_cap('cyber_advanced')
def ultra_snapshot():
    d=_json(); return jsonify(ultra_ops.snapshot(_uid(),d.get('kind','security'),d.get('label','snapshot'))),201

@bp.get('/api/cyber/ultra/api-security')
def ultra_api_security(): return jsonify({'endpoints':ultra_ops.api_inventory()})

@bp.get('/api/cyber/ultra/web-security')
def ultra_web_security(): return jsonify(ultra_ops.web_security())

@bp.post('/api/cyber/ultra/code-scan')
@require_cap('cyber_advanced')
def ultra_code_scan(): return jsonify(ultra_ops.code_scan(_json().get('paths')))

@bp.post('/api/cyber/ultra/secrets-scan')
@require_cap('cyber_advanced')
def ultra_secrets_scan(): return jsonify(ultra_ops.secret_scan(_json().get('paths')))

@bp.post('/api/cyber/ultra/impact')
@require_cap('cyber_advanced')
def ultra_impact():
    d=_json(); return jsonify(ultra_ops.impact_analysis(d.get('paths'),d.get('action','review')))

@bp.post('/api/cyber/ultra/safe-actions')
@require_cap('cyber_advanced')
def ultra_safe_action():
    d=_json()
    required=('action','target','impact','consequence')
    if any(not d.get(x) for x in required): return jsonify({'error':'AÇÃO, IMPACTO, ALVO e CONSEQUÊNCIA são obrigatórios.'}),400
    return jsonify(ultra_ops.create_safe_action(_uid(),d['action'],d['target'],d['impact'],d['consequence'])),201

@bp.post('/api/cyber/ultra/safe-actions/<aid>/confirm')
@require_cap('cyber_advanced')
def ultra_safe_action_confirm(aid): return jsonify({'ok':ultra_ops.confirm_safe_action(_uid(),aid),'executed':False,'message':'Confirmação registrada; nenhuma alteração perigosa é aplicada automaticamente.'})

@bp.get('/api/cyber/ultra/scans')
def ultra_scans(): return jsonify({'scans':ultra_ops.scan_history(_uid())})

@bp.get('/api/cyber/ultra/scans/compare')
def ultra_scan_compare(): return jsonify(ultra_ops.scan_compare(request.args.get('before'),request.args.get('after'),_uid()))

@bp.get('/api/cyber/ultra/notifications')
def ultra_notifications(): return jsonify({'groups':ultra_ops.notifications_smart(_uid())})

@bp.get('/api/cyber/ultra/health-services')
def ultra_health_services(): return jsonify(ultra_ops.health_services())

@bp.get('/api/cyber/ultra/knowledge')
def ultra_knowledge(): return jsonify({'articles':ultra_ops.knowledge()})

@bp.get('/api/cyber/ultra/search')
def ultra_search(): return jsonify({'results':ultra_ops.global_search(_uid(),request.args.get('q',''))})

@bp.route('/api/cyber/ultra/preferences',methods=['GET','PUT'])
def ultra_preferences():
    if request.method=='PUT':
        if not permissions.has_cap('cyber_advanced'): return permissions._deny('cyber_advanced')
        return jsonify(ultra_ops.preferences(_uid(),_json()))
    return jsonify(ultra_ops.preferences(_uid()))

@bp.get('/api/cyber/ultra/trends')
def ultra_trends(): return jsonify({'days':int(request.args.get('days',30) or 30),'data':ultra_ops.trends(_uid(),request.args.get('days',30))})

@bp.get('/api/cyber/ultra/maturity')
def ultra_maturity(): return jsonify(ultra_ops.maturity(_uid()))

@bp.get('/api/cyber/ultra/dashboard')
def ultra_dashboard():
    return jsonify({'score':ultra_ops.security_score(),'recommendations':ultra_ops.posture_recommendations(_uid())[:8],'baseline':ultra_ops.baseline(),'health':ultra_ops.health_services(),'smart_notifications':ultra_ops.notifications_smart(_uid())[:12],'preferences':ultra_ops.preferences(_uid())})

@bp.get('/api/cyber/ultra/investigation-board')
def ultra_investigation_board(): return jsonify({'columns':ultra_ops.investigation_board(_uid())})

@bp.get('/api/cyber/ultra/alert-fatigue')
def ultra_alert_fatigue(): return jsonify({'groups':ultra_ops.alert_fatigue(_uid())})

@bp.get('/api/cyber/ultra/copilot')
def ultra_copilot(): return jsonify(ultra_ops.copilot(_uid(),request.args.get('context','SOC'),request.args.get('scan_id'),request.args.get('finding_id')))

# ------------------------------------------------------------- Ultra Platform Expansion 2 (incremental)
from services import platform_ultra, core2, evolution2

@bp.get('/cyber/ultra-platform')
def ultra_platform_page():
    return render_template('ultra_platform.html')


@bp.get('/api/cyber/core2/security')
def core2_security():
    return jsonify(core2.security_overview())

@bp.get('/api/cyber/core2/system')
def core2_system():
    return jsonify(core2.system_overview())

@bp.get('/api/cyber/core2/knowledge')
def core2_knowledge():
    return jsonify(core2.knowledge_search(request.args.get('q',''), request.args.get('limit',20,type=int)))

@bp.get('/api/cyber/core2/access-audit')
@require_cap('developer')
def core2_access_audit():
    return jsonify({'entries': core2.access_audit(request.args.get('limit',150,type=int), request.args.get('q',''))})

@bp.get('/api/cyber/core2/crypto')
@require_cap('developer')
def core2_crypto_info():
    return jsonify(core2.crypto_info())

@bp.post('/api/cyber/core2/crypto')
@require_cap('developer')
def core2_crypto_operation():
    if security.api_rate_limited(security.client_ip(request), 'core2-crypto', 30, 60):
        return jsonify({'error':'Limite temporário atingido.'}), 429
    d=_json()
    try:
        result=core2.crypto_operation(d.get('operation'), d.get('value',''), d.get('algorithm','sha256'))
        security.audit_event('CRYPTO_TOOL_USED', target=str(d.get('operation',''))[:60], ok=True, role=permissions.current_role())
        return jsonify(result)
    except ValueError as exc:
        security.audit_event('CRYPTO_TOOL_FAILURE', target='validation', ok=False, role=permissions.current_role(), error=type(exc).__name__)
        return jsonify({'error':str(exc)}),400

@bp.post('/api/cyber/core2/file-hash')
@require_cap('developer')
def core2_file_hash():
    if security.api_rate_limited(security.client_ip(request), 'core2-file-hash', 20, 60):
        return jsonify({'error':'Limite temporário atingido.'}), 429
    data=request.files.get('file')
    if not data:
        return jsonify({'error':'Arquivo não enviado.'}),400
    try:
        result=core2.file_hash_bytes(data.read(10*1024*1024+1), request.form.get('algorithm','sha256'))
        security.audit_event('FILE_HASH', target=data.filename[:120], ok=True, role=permissions.current_role())
        result['filename']=data.filename[:120]
        return jsonify(result)
    except ValueError as exc:
        return jsonify({'error':str(exc)}),400

@bp.get('/api/cyber/ultra2/account-security')
def ultra2_account_security(): return jsonify(platform_ultra.account_security(_uid()))

@bp.post('/api/cyber/ultra2/sessions/<sid>/revoke')
@require_cap('cyber_advanced')
def ultra2_revoke_session(sid): return jsonify({'ok':platform_ultra.revoke_session(_uid(),sid)})

@bp.post('/api/cyber/ultra2/sessions/revoke-others')
@require_cap('cyber_advanced')
def ultra2_revoke_others():
    return jsonify({'revoked':platform_ultra.revoke_others(_uid(),platform_ultra.current_session_prefix(session.get('tf_sid','')) )})

@bp.get('/api/cyber/ultra2/flags')
@require_cap('cyber_advanced')
def ultra2_flags(): return jsonify({'flags':platform_ultra.feature_flags(_uid())})

@bp.put('/api/cyber/ultra2/flags/<key>')
@require_cap('cyber_advanced')
def ultra2_flag_set(key):
    d=_json();
    try:return jsonify({'flags':platform_ultra.set_flag(_uid(),key,d.get('enabled',False))})
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/ultra2/arcade')
def ultra2_arcade(): return jsonify({'games':platform_ultra.arcade_catalog(_uid()),'profile':platform_ultra.arcade_profile(_uid())})

@bp.post('/api/cyber/ultra2/arcade/<game_id>/score')
def ultra2_game_score(game_id):
    d=_json()
    try:return jsonify(platform_ultra.submit_game(_uid(),game_id,d.get('score',0),d.get('duration_ms',0)))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/ultra2/missions')
def ultra2_missions(): return jsonify({'missions':platform_ultra.daily_missions(_uid())})

@bp.get('/api/cyber/ultra2/quizzes')
def ultra2_quizzes(): return jsonify({'quizzes':platform_ultra.quiz_catalog()})

@bp.get('/api/cyber/ultra2/quizzes/<qid>')
def ultra2_quiz(qid):
    q=platform_ultra.quiz_get(qid); return (jsonify(q),200) if q else (jsonify({'error':'Quiz não encontrado'}),404)

@bp.post('/api/cyber/ultra2/quizzes/<qid>/check')
def ultra2_quiz_check(qid):
    d=_json()
    try:return jsonify(platform_ultra.quiz_check(_uid(),qid,d.get('index',0),d.get('answer',-1)))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/ultra2/learning-paths')
def ultra2_learning_paths(): return jsonify({'paths':platform_ultra.learning_paths()})

@bp.get('/api/cyber/ultra2/project-templates')
def ultra2_project_templates(): return jsonify({'templates':platform_ultra.project_templates()})

@bp.get('/api/cyber/ultra2/diagnostics')
@require_cap('cyber_advanced')
def ultra2_diagnostics(): return jsonify(platform_ultra.diagnostics())

@bp.get('/api/cyber/ultra2/backup-safety')
@require_cap('cyber_advanced')
def ultra2_backup_safety(): return jsonify(platform_ultra.backup_safety())

@bp.get('/api/cyber/ultra2/checklist')
@require_cap('cyber_advanced')
def ultra2_checklist(): return jsonify({'checks':platform_ultra.security_checklist()})

@bp.get('/api/cyber/ultra2/system-health')
def ultra2_system_health(): return jsonify(platform_ultra.system_health())

@bp.get('/api/cyber/ultra2/release')
@require_cap('cyber_advanced')
def ultra2_release(): return jsonify(platform_ultra.release_info())

@bp.get('/api/cyber/ultra2/activity')
def ultra2_activity(): return jsonify({'events':platform_ultra.activity(_uid())})

@bp.post('/api/cyber/ultra2/code-diff')
@require_cap('cyber_advanced')
def ultra2_code_diff():
    d=_json()
    try:return jsonify(platform_ultra.code_diff(d.get('before'),d.get('after'),d.get('filename','arquivo')))
    except ValueError as e:return jsonify({'error':str(e)}),400


# ------------------------------------------------------------- JARVIS Ultra Expansion — platform orchestration
@bp.get('/cyber/mega')
def mega_platform_page():
    return render_template('ultra_core2.html')

@bp.get('/api/cyber/mega/overview')
def mega_overview():
    return jsonify(mega_expansion.dashboard(_uid()))

@bp.get('/api/cyber/mega/services')
def mega_services():
    return jsonify({'services': mega_expansion.service_status()})

@bp.get('/api/cyber/mega/commands')
def mega_commands():
    return jsonify({'commands': mega_expansion.command_catalog()})

@bp.post('/api/cyber/mega/command')
def mega_command():
    return jsonify(mega_expansion.resolve_command(_json().get('text','')))

@bp.get('/api/cyber/mega/activity')
def mega_activity():
    return jsonify({'events': mega_expansion.activity(_uid(), request.args.get('category',''), request.args.get('limit',100,type=int))})

@bp.get('/api/cyber/mega/privacy')
def mega_privacy():
    return jsonify(mega_expansion.privacy(_uid()))

@bp.get('/api/cyber/mega/maps')
def mega_maps():
    return jsonify(mega_expansion.map_lab())

@bp.get('/api/cyber/mega/arcade')
def mega_arcade():
    return jsonify(mega_expansion.arcade())

@bp.get('/api/cyber/mega/knowledge')
def mega_knowledge():
    return jsonify({'topics': mega_expansion.knowledge()})

@bp.get('/api/cyber/mega/files')
@require_cap('cyber_advanced')
def mega_files():
    return jsonify({'files': mega_expansion.file_center()})

@bp.get('/api/cyber/mega/projects')
def mega_projects():
    return jsonify(mega_expansion.project_center(_uid()))


# ------------------------------------------------------------- JARVIS Evolution 2 — incremental orchestration
@bp.get('/cyber/evolution')
def evolution_page():
    return render_template('evolution2.html')

@bp.get('/api/cyber/evolution/status')
def evolution_status(): return jsonify(evolution2.status(_uid()))

@bp.get('/api/cyber/evolution/tasks')
def evolution_tasks(): return jsonify({'tasks':evolution2.tasks(_uid(),request.args.get('status',''))})

@bp.post('/api/cyber/evolution/tasks')
def evolution_task_create():
    try:return jsonify(evolution2.task_create(_uid(),_json())),201
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.put('/api/cyber/evolution/tasks/<int:tid>')
def evolution_task_update(tid):
    try:return jsonify(evolution2.task_update(_uid(),tid,_json()))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/evolution/workflows')
def evolution_workflows(): return jsonify({'workflows':evolution2.workflows(_uid())})

@bp.post('/api/cyber/evolution/workflows')
def evolution_workflow_create():
    d=_json()
    try:return jsonify(evolution2.workflow_create(_uid(),d.get('name'),d.get('steps'))),201
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/evolution/snapshots')
def evolution_snapshots(): return jsonify({'snapshots':evolution2.snapshots(_uid(),request.args.get('project',''))})

@bp.post('/api/cyber/evolution/snapshots')
def evolution_snapshot_create():
    d=_json();return jsonify(evolution2.snapshot_create(_uid(),d.get('project'),d.get('label'),d.get('manifest'))),201

@bp.get('/api/cyber/evolution/agents')
def evolution_agents(): return jsonify({'agents':evolution2.agents()})

@bp.post('/api/cyber/evolution/agent-route')
def evolution_agent_route(): return jsonify({'agent':evolution2.route_agent(_json().get('text',''))})

@bp.get('/api/cyber/evolution/ai-mode')
def evolution_ai_mode(): return jsonify(evolution2.ai_mode(_uid()))

@bp.put('/api/cyber/evolution/ai-mode')
def evolution_ai_mode_set():
    try:return jsonify(evolution2.ai_mode(_uid(),_json().get('mode')))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/evolution/study')
def evolution_study(): return jsonify({'courses':evolution2.study_catalog()})

@bp.get('/api/cyber/evolution/search')
def evolution_search(): return jsonify({'results':evolution2.search(_uid(),request.args.get('q',''),request.args.get('limit',50,type=int))})

@bp.get('/api/cyber/evolution/performance')
@require_cap('developer')
def evolution_performance(): return jsonify(evolution2.performance())

@bp.get('/api/cyber/evolution/database')
@require_cap('developer')
def evolution_database(): return jsonify(evolution2.database_health())

@bp.get('/api/cyber/evolution/integrity')
@require_cap('developer')
def evolution_integrity(): return jsonify({'files':evolution2.integrity()})

@bp.get('/api/cyber/evolution/dependencies')
@require_cap('developer')
def evolution_dependencies(): return jsonify(evolution2.dependency_status())

@bp.get('/api/cyber/evolution/security-report')
def evolution_security_report(): return jsonify(evolution2.security_report())


# ------------------------------------------------------------- JARVIS Kids Code + Game Lab

# ------------------------------------------------------------- JARVIS Programming Universe 7.0
@bp.get('/cyber/programming')
def programming7_page():
    return render_template('programming7.html')

# ------------------------------------------------------------- Learning + Game Studio 8.0
@bp.get('/cyber/learning')
def learning8_page():
    return render_template('programming7.html')

@bp.get('/api/cyber/learning/overview')
def learning8_overview(): return jsonify(learning8.overview(_uid()))

@bp.get('/api/cyber/learning/lesson/<key>')
def learning8_lesson(key):
    try: return jsonify(learning8.lesson(_uid(), key))
    except KeyError: return jsonify({'error':'Aula não encontrada'}),404

@bp.post('/api/cyber/learning/progress')
def learning8_progress():
    d=_json(); key=str(d.get('lesson',''))[:80]
    if key not in learning8.LESSONS: return jsonify({'error':'Aula inválida'}),400
    return jsonify(learning8.record(_uid(),key,bool(d.get('correct',True)),d.get('mode')))

@bp.get('/api/cyber/learning/search')
def learning8_search(): return jsonify({'results':learning8.search(_uid(),request.args.get('q',''))})

@bp.get('/api/cyber/programming/overview')
def programming7_overview(): return jsonify(programming7.overview(_uid()))

@bp.get('/api/cyber/programming/workspace')
def programming7_workspace(): return jsonify(programming7.workspace(_uid()))

@bp.post('/api/cyber/programming/workspace')
def programming7_workspace_save():
    try: return jsonify(programming7.save_workspace(_uid(), _json().get('language'), _json().get('code')))
    except ValueError as e: return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/programming/snapshot')
def programming7_snapshot(): return jsonify(programming7.snapshot(_uid(), _json().get('label','Snapshot')))

@bp.get('/api/cyber/programming/snapshots')
def programming7_snapshots(): return jsonify({'snapshots':programming7.snapshots(_uid())})

@bp.post('/api/cyber/programming/explain')
def programming7_explain(): return jsonify(programming7.explain(_json().get('code',''),_json().get('level','INICIANTE')))

@bp.post('/api/cyber/programming/debug')
def programming7_debug(): return jsonify(programming7.debug(_json().get('code',''),_json().get('language','javascript')))

@bp.post('/api/cyber/programming/quality')
def programming7_quality(): return jsonify(programming7.quality(_json().get('code',''),_json().get('language','javascript')))

@bp.post('/api/cyber/programming/health')
def programming7_health(): return jsonify(programming7.project_health(_json().get('code',''),_json().get('language','javascript')))

@bp.post('/api/cyber/programming/json')
def programming7_json(): return jsonify(programming7.json_lab(_json().get('text','')))

@bp.post('/api/cyber/programming/regex')
def programming7_regex(): return jsonify(programming7.regex_lab(_json().get('pattern',''),_json().get('text',''),_json().get('flags','')))

@bp.get('/api/cyber/programming/algorithm/<kind>')
def programming7_algorithm(kind): return jsonify(programming7.algorithm(kind))

@bp.post('/api/cyber/programming/sql')
def programming7_sql(): return jsonify(programming7.sql_lab(_json().get('query','')))

@bp.get('/api/cyber/programming/api-demo')
def programming7_api_demo():
    programming7.award(_uid(),5,'api','first_api'); programming7.event(_uid(),'API_LAB_OPENED')
    return jsonify(programming7.api_demo())

@bp.post('/api/cyber/programming/projects')
def programming7_project_create():
    try:return jsonify(programming7.create_project(_uid(),_json().get('name'),_json().get('template'))),201
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/cyber/game-lab')
def game_lab_page():
    return render_template('game_lab.html')

@bp.get('/api/cyber/game-lab/overview')
def game_lab_overview():
    return jsonify(game_lab.overview(_uid()))

@bp.get('/api/cyber/game-lab/games/<gid>')
def game_lab_game(gid):
    d=game_lab.game_detail(_uid(),gid)
    return jsonify(d) if d else (jsonify({'error':'Jogo não encontrado'}),404)

@bp.post('/api/cyber/game-lab/games/<gid>/experiment')
def game_lab_experiment(gid):
    try:return jsonify(game_lab.experiment(_uid(),gid,_json().get('values') or {}))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/game-lab/challenges/<cid>/check')
def game_lab_challenge_check(cid):
    try:return jsonify(game_lab.challenge_check(_uid(),cid,_json().get('answer','')))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/game-lab/explain')
def game_lab_explain():
    return jsonify(game_lab.teacher_explain(_json().get('code',''),_json().get('level','BEGINNER')))

@bp.post('/api/cyber/game-lab/code-test')
def game_lab_code_test():
    return jsonify(game_lab.validate_code(_json().get('code','')))

@bp.post('/api/cyber/game-lab/session-report')
def game_lab_session_report():
    d=_json(); return jsonify(game_lab.session_report(_uid(),d.get('started_at',game_lab.now()),d.get('duration',0),d.get('challenges',0),d.get('correct',0),d.get('errors',0),d.get('concepts') or []))

@bp.get('/api/cyber/game-lab/projects')
def game_lab_projects():
    return jsonify({'projects':game_lab.projects(_uid())})

@bp.post('/api/cyber/game-lab/projects')
def game_lab_project_create():
    try:return jsonify(game_lab.create_project(_uid(),_json())),201
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/game-lab/projects/<pid>')
def game_lab_project_get(pid):
    d=game_lab.project(_uid(),pid)
    return jsonify(d) if d else (jsonify({'error':'Projeto não encontrado'}),404)

@bp.put('/api/cyber/game-lab/projects/<pid>')
def game_lab_project_save(pid):
    try:return jsonify(game_lab.save_project(_uid(),pid,_json()))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/game-lab/projects/<pid>/remix')
def game_lab_project_remix(pid):
    try:return jsonify(game_lab.remix(_uid(),pid)),201
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/game-lab/projects/<pid>/versions')
def game_lab_project_versions(pid):
    with game_lab.conn() as c:
        rows=c.execute('SELECT version,changes,created_at FROM kids_project_versions WHERE project_id=? AND owner_uid=? ORDER BY version DESC',(pid,game_lab._uid(_uid()))).fetchall()
    return jsonify({'versions':[dict(r) for r in rows]})

# ------------------------------------------------------------- JARVIS Ultra Platform — World/Experience layer
from services import ultra_experience

@bp.get('/cyber/world')
def jarvis_world_page():
    return render_template('jarvis_world.html')

@bp.get('/api/cyber/world/overview')
def world_overview(): return jsonify(ultra_experience.overview(_uid()))

@bp.get('/api/cyber/world/learning')
def world_learning(): return jsonify(ultra_experience.learning(_uid()))

@bp.get('/api/cyber/world/skills')
def world_skills(): return jsonify({'skills':ultra_experience.skills(_uid())})

@bp.post('/api/cyber/world/skills/<sid>')
def world_skill_update(sid):
    try:return jsonify({'skills':ultra_experience.skill_update(_uid(),sid,_json().get('progress',0))})
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/world/onboarding')
def world_onboarding(): return jsonify(ultra_experience.set_onboarding(_uid(),_json().get('interests',[])))

@bp.get('/api/cyber/world/ideas')
def world_ideas(): return jsonify({'ideas':ultra_experience.ideas(_uid(),request.args.get('q',''))})

@bp.post('/api/cyber/world/projects')
def world_project_create():
    try:return jsonify(ultra_experience.create_project(_uid(),_json())),201
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/world/projects/<pid>')
def world_project_get(pid):
    p=ultra_experience.project(_uid(),pid)
    return jsonify(p or {'error':'Projeto não encontrado'}),(200 if p else 404)

@bp.post('/api/cyber/world/projects/<pid>/stage')
def world_project_stage(pid):
    try:return jsonify(ultra_experience.project_stage(_uid(),pid,_json().get('stage')))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/world/projects/<pid>/visibility')
def world_project_visibility(pid): return jsonify(ultra_experience.project_public(_uid(),pid,bool(_json().get('public'))))

@bp.get('/api/cyber/world/portfolio')
def world_portfolio(): return jsonify(ultra_experience.portfolio(_uid()))

@bp.get('/api/cyber/world/daily')
def world_daily(): return jsonify(ultra_experience.daily(_uid()))

@bp.post('/api/cyber/world/daily/complete')
def world_daily_complete(): return jsonify(ultra_experience.complete_daily(_uid()))

@bp.get('/api/cyber/world/analytics')
def world_analytics(): return jsonify(ultra_experience.analytics(_uid()))

@bp.get('/api/cyber/world/observatory')
def world_observatory(): return jsonify(ultra_experience.observatory(_uid()))

@bp.get('/api/cyber/world/memory')
def world_memory(): return jsonify({'projects':ultra_experience.memory_board(_uid())})

@bp.get('/api/cyber/world/guide')
def world_guide(): return jsonify(ultra_experience.guide(request.args.get('topic','first-game')))

@bp.get('/api/cyber/world/search')
def world_search(): return jsonify({'results':ultra_experience.search(_uid(),request.args.get('q',''))})

@bp.post('/api/cyber/world/command')
def world_command(): return jsonify(ultra_experience.command(_uid(),_json().get('text','')))

# ================================================================
# JARVIS SECURITY + AUTHENTICATION 4.0
# Reuses the existing auth/session/RBAC/CSRF stack; this is a center,
# not a second authentication implementation.
# ================================================================
from services import security4

@bp.get('/api/cyber/security4/account')
def security4_account():
    return jsonify(security4.account_snapshot(_uid(), permissions.current_role(), auth_service, platform_ultra))

@bp.get('/api/cyber/security4/checkup')
def security4_checkup():
    scan = security4.secret_scan_summary()
    return jsonify(security4.security_checkup(_uid(), permissions.current_role(), auth_service, security, permissions, scan))

@bp.get('/api/cyber/security4/health')
@require_cap('developer')
def security4_health():
    return jsonify(security4.system_health(auth_service, security4.secret_scan_summary()))

@bp.get('/api/cyber/security4/developer')
@require_cap('developer')
def security4_developer():
    return jsonify(security4.developer_overview(_uid(), permissions.current_role(), auth_service, security, permissions, security4.secret_scan_summary()))

@bp.get('/api/cyber/security4/audit')
@require_cap('developer')
def security4_audit():
    return jsonify({'integrity':security4.verify_integrity(), 'entries':security4.audit_list(request.args.get('limit',100,type=int), action=request.args.get('action',''))})

@bp.get('/api/cyber/security4/notifications')
def security4_notifications():
    return jsonify({'notifications':security4.notifications(_uid(), request.args.get('unread','0')=='1')})

@bp.post('/api/cyber/security4/notifications/<int:nid>/read')
def security4_notification_read(nid):
    return jsonify({'ok':security4.mark_notification(_uid(), nid)})

@bp.get('/api/cyber/security4/privacy')
def security4_privacy():
    return jsonify(security4.privacy(_uid()))

@bp.post('/api/cyber/security4/privacy')
def security4_privacy_update():
    d=_json()
    out=security4.set_privacy(_uid(), d.get('analytics'), d.get('public_portfolio'), d.get('simplified_mode'))
    return jsonify(out)

@bp.get('/api/cyber/security4/incidents')
@require_cap('developer')
def security4_incidents():
    return jsonify({'incidents':security4.incidents(_uid())})

@bp.post('/api/cyber/security4/incidents')
@require_cap('developer')
def security4_incident_create():
    d=_json();
    if not str(d.get('title','')).strip(): return jsonify({'error':'Título obrigatório.'}),400
    return jsonify(security4.create_incident(_uid(), d.get('title'), d.get('description',''), d.get('severity','medium'))),201

@bp.post('/api/cyber/security4/incidents/<int:iid>')
@require_cap('developer')
def security4_incident_update(iid):
    d=_json(); row=security4.update_incident(_uid(), iid, d.get('status'), d.get('severity'))
    return jsonify(row or {'error':'Incidente não encontrado.'}), 404 if not row else 200

@bp.get('/api/cyber/security4/integrity')
@require_cap('developer')
def security4_integrity():
    return jsonify(security4.verify_integrity())

@bp.get('/api/cyber/security4/api-security')
@require_cap('developer')
def security4_api_security():
    return jsonify(security4.api_security_snapshot())

@bp.get('/security-4')
@require_cap('cyber_advanced')
def security4_page():
    return render_template('security4.html')

# Account-facing subset: authenticated users can manage their own security
# without receiving developer/SOC privileges.
@bp.get('/api/account/security4')
def security4_account_user():
    return jsonify(security4.account_snapshot(_uid(), permissions.current_role(), auth_service, platform_ultra))

@bp.get('/api/account/security4/checkup')
def security4_checkup_user():
    scan = security4.secret_scan_summary()
    return jsonify(security4.security_checkup(_uid(), permissions.current_role(), auth_service, security, permissions, scan))

@bp.get('/api/account/security4/privacy')
def security4_privacy_user():
    return jsonify(security4.privacy(_uid()))

@bp.post('/api/account/security4/privacy')
def security4_privacy_user_update():
    d=_json(); return jsonify(security4.set_privacy(_uid(), d.get('analytics'), d.get('public_portfolio'), d.get('simplified_mode')))

@bp.post('/api/account/security4/sessions/<sid>/revoke')
def security4_revoke_own_session(sid):
    current=auth_service._session_hash(session.get('tf_sid',''))[:12]
    if sid == current:
        return jsonify({'error':'A sessão atual deve ser encerrada pelo Logout.'}),400
    sessions={x['id'] for x in auth_service.list_auth_sessions() if x.get('uid')==_uid()}
    if sid not in sessions: return jsonify({'error':'Sessão não encontrada.'}),404
    ok=auth_service.revoke_session_id(sid)
    security4.audit(_uid(),'SESSION_REVOKED',sid,ok=ok)
    return jsonify({'ok':ok})

@bp.post('/api/account/security4/sessions/revoke-others')
def security4_revoke_own_others():
    current=auth_service._session_hash(session.get('tf_sid',''))[:12]
    revoked=0
    for row in auth_service.list_auth_sessions():
        if row.get('uid')==_uid() and row.get('id')!=current and auth_service.revoke_session_id(row.get('id')):
            revoked+=1
    security4.audit(_uid(),'SESSIONS_REVOKED_OTHERS','account',details=str(revoked))
    return jsonify({'revoked':revoked})


# =============================================================
# JARVIS Experience/Auth/Performance 6.0
# Reuses the existing authentication and RBAC stack.
# =============================================================
@bp.get('/api/jarvis/experience6/session-trust')
def experience6_session_trust():
    return jsonify(experience6.session_trust())

@bp.post('/api/jarvis/experience6/step-up')
def experience6_step_up():
    d = _json()
    action = str(d.get('action') or '').strip()[:120]
    password = str(d.get('password') or '')
    allowed = {'change_password','change_mfa','change_email','manage_permissions','delete_account','admin_critical','revoke_security'}
    if action not in allowed:
        return jsonify({'error':'Ação não elegível para step-up.'}), 400
    if not auth_service.check_master_password(password):
        return jsonify({'error':'Confirmação inválida.'}), 403
    trust = experience6.grant_step_up(action)
    try:
        from services import security
        security.audit_event('STEP_UP_GRANTED', target=action, ok=True, role=session.get('tf_role',''))
    except Exception:
        pass
    return jsonify({'ok': True, **trust})

@bp.post('/api/jarvis/experience6/step-up/clear')
def experience6_step_up_clear():
    experience6.clear_step_up()
    return jsonify({'ok': True, **experience6.session_trust()})

@bp.get('/api/jarvis/experience6/performance')
@require_cap('developer')
def experience6_performance():
    return jsonify(experience6.performance(request.args.get('limit',100,type=int)))

@bp.get('/api/jarvis/experience6/challenges/<cid>')
def experience6_challenge(cid):
    return jsonify(experience6.challenge_detail(cid))

@bp.get('/api/jarvis/experience6/modes')
def experience6_modes():
    return jsonify({'modes':[{'id':i.lower().replace(' ','_'),'name':i,'description':d} for i,d in experience6.MODES]})


# =============================================================
# JARVIS Ecosystem 8.0
# Central project/workflow/creation/learning coordination layer.
# Reuses existing project, programming and learning stores.
# =============================================================
@bp.get('/cyber/ecosystem')
def ecosystem_page():
    return render_template('ecosystem8.html')

@bp.get('/api/cyber/ecosystem/overview')
def ecosystem_overview(): return jsonify(ecosystem8.overview(_uid()))

@bp.get('/api/cyber/ecosystem/workspaces')
def ecosystem_workspaces(): return jsonify({'workspaces':ecosystem8.list_workspaces(_uid())})

@bp.post('/api/cyber/ecosystem/workspaces')
def ecosystem_workspace_create():
    try:return jsonify(ecosystem8.create_workspace(_uid(),_json())),201
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/ecosystem/workspaces/<wid>')
def ecosystem_workspace_get(wid):
    d=ecosystem8.workspace(_uid(),wid)
    return (jsonify(d) if d else (jsonify({'error':'Workspace não encontrado.'}),404))

@bp.post('/api/cyber/ecosystem/planner')
def ecosystem_planner():
    try:return jsonify(ecosystem8.planner(_uid(),_json().get('workspace_id',''),_json().get('prompt','')))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/ecosystem/tasks')
def ecosystem_task_create():
    try:return jsonify(ecosystem8.create_task(_uid(),_json())),201
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.patch('/api/cyber/ecosystem/tasks/<tid>')
def ecosystem_task_update(tid):
    try:return jsonify(ecosystem8.update_task(_uid(),tid,_json()))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/ecosystem/snapshots')
def ecosystem_snapshot():
    try:return jsonify(ecosystem8.snapshot(_uid(),_json().get('workspace_id'),_json().get('label','Snapshot manual'))),201
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/ecosystem/snapshots/<sid>')
def ecosystem_snapshot_get(sid):
    d=ecosystem8.snapshot_get(_uid(),sid)
    return (jsonify(d) if d else (jsonify({'error':'Snapshot não encontrado.'}),404))

@bp.post('/api/cyber/ecosystem/snapshots/compare')
def ecosystem_snapshot_compare():
    try:return jsonify(ecosystem8.diff_snapshots(_uid(),_json().get('from'),_json().get('to')))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/ecosystem/snapshots/restore')
def ecosystem_snapshot_restore():
    try:return jsonify(ecosystem8.restore_snapshot(_uid(),_json().get('id')))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/ecosystem/ideas')
def ecosystem_idea(): return jsonify(ecosystem8.idea(_uid(),_json())),201

@bp.get('/api/cyber/ecosystem/ideas')
def ecosystem_ideas(): return jsonify({'ideas':ecosystem8.ideas(_uid(),request.args.get('q',''))})

@bp.post('/api/cyber/ecosystem/design')
def ecosystem_design():
    try:return jsonify(ecosystem8.design_save(_uid(),_json()))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/ecosystem/workflow')
def ecosystem_workflow():
    try:return jsonify(ecosystem8.workflow_save(_uid(),_json()))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/ecosystem/ai/experiment')
def ecosystem_ai_experiment(): return jsonify(ecosystem8.ai_experiment(_uid(),_json())),201

@bp.post('/api/cyber/ecosystem/ai/agent-policy')
def ecosystem_ai_agent_policy(): return jsonify(ecosystem8.ai_agent_policy(_uid(),_json()))

@bp.post('/api/cyber/ecosystem/tests')
def ecosystem_test():
    try:return jsonify(ecosystem8.test_save(_uid(),_json()))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/ecosystem/quality/<wid>')
def ecosystem_quality(wid):
    try:return jsonify(ecosystem8.quality(_uid(),wid))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/ecosystem/changelog')
def ecosystem_changelog():
    try:return jsonify(ecosystem8.changelog(_uid(),_json().get('workspace_id'),_json()))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/ecosystem/documentation/<wid>')
def ecosystem_documentation(wid):
    try:return jsonify(ecosystem8.documentation(_uid(),wid))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/ecosystem/analytics')
def ecosystem_analytics(): return jsonify(ecosystem8.analytics(_uid()))

@bp.get('/api/cyber/ecosystem/recommendations')
def ecosystem_recommendations(): return jsonify(ecosystem8.recommendation(_uid()))

@bp.get('/api/cyber/ecosystem/portfolio')
def ecosystem_portfolio(): return jsonify(ecosystem8.portfolio(_uid()))

@bp.get('/api/cyber/ecosystem/skill-tree')
def ecosystem_skill_tree(): return jsonify({'skills':ecosystem8.skill_tree(_uid())})

@bp.get('/api/cyber/ecosystem/notifications')
def ecosystem_notifications(): return jsonify({'notifications':ecosystem8.notifications(_uid())})

@bp.get('/api/cyber/ecosystem/search')
def ecosystem_search(): return jsonify({'results':ecosystem8.search(_uid(),request.args.get('q',''))})

@bp.post('/api/cyber/ecosystem/command')
def ecosystem_command(): return jsonify(ecosystem8.command(_json().get('text','')))

@bp.post('/api/cyber/ecosystem/mentor')
def ecosystem_mentor():
    try:return jsonify(ecosystem8.mentor(_uid(),_json()))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/ecosystem/course')
def ecosystem_course(): return jsonify(ecosystem8.course_create(_uid(),_json())),201

@bp.post('/api/cyber/ecosystem/classroom')
def ecosystem_classroom(): return jsonify(ecosystem8.classroom_create(_uid(),_json())),201

@bp.post('/api/cyber/ecosystem/classroom/join')
def ecosystem_classroom_join():
    try:return jsonify(ecosystem8.classroom_join(_uid(),_json().get('code','')))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.get('/api/cyber/ecosystem/classroom')
def ecosystem_classrooms(): return jsonify({'classrooms':ecosystem8.classroom_list(_uid())})

@bp.post('/api/cyber/ecosystem/share')
def ecosystem_share():
    try:return jsonify(ecosystem8.share(_uid(),_json()))
    except ValueError as e:return jsonify({'error':str(e)}),400

@bp.post('/api/cyber/ecosystem/remix')
def ecosystem_remix():
    try:return jsonify(ecosystem8.remix(_uid(),_json().get('workspace_id'))),201
    except ValueError as e:return jsonify({'error':str(e)}),400


# ── Phase 9.0 Education Expansion ──────────────────────────────────────────
@bp.get('/cyber/phase9')
def phase9_page():
    return render_template('phase9.html')

@bp.get('/api/cyber/phase9/overview')
def phase9_overview():
    return jsonify(phase9.overview(_uid()))

@bp.post('/api/cyber/phase9/mode')
def phase9_mode():
    try:
        return jsonify(phase9.set_mode(_uid(), (_json() or {}).get('mode','')))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@bp.get('/api/cyber/phase9/labs')
def phase9_labs():
    return jsonify({'labs': list(phase9.LABS.values())})

@bp.get('/api/cyber/phase9/labs/<lab_id>')
def phase9_lab(lab_id):
    try:
        phase9.record_lab(_uid(), lab_id, 'visit')
        return jsonify(phase9.lab_detail(lab_id))
    except KeyError:
        return jsonify({'error': 'Laboratório não encontrado'}), 404

@bp.get('/api/cyber/phase9/algorithm/<algo_id>')
def phase9_algo(algo_id):
    try:
        return jsonify(phase9.algo_demo(algo_id))
    except KeyError:
        return jsonify({'error': 'Algoritmo não encontrado'}), 404

@bp.get('/api/cyber/phase9/datastructure/<ds_id>')
def phase9_ds(ds_id):
    try:
        return jsonify(phase9.ds_demo(ds_id))
    except KeyError:
        return jsonify({'error': 'Estrutura não encontrada'}), 404

@bp.get('/api/cyber/phase9/debug/<cid>')
def phase9_debug(cid):
    try:
        return jsonify(phase9.debug_challenge(cid))
    except KeyError:
        return jsonify({'error': 'Desafio não encontrado'}), 404

@bp.post('/api/cyber/phase9/debug/<cid>/hint')
def phase9_debug_hint(cid):
    d=_json() or {}
    try:
        return jsonify(phase9.debug_hint(cid, int(d.get('level', 1))))
    except KeyError:
        return jsonify({'error': 'Desafio não encontrado'}), 404

@bp.post('/api/cyber/phase9/debug/<cid>/reveal')
def phase9_debug_reveal(cid):
    try:
        return jsonify(phase9.debug_reveal(cid))
    except KeyError:
        return jsonify({'error': 'Desafio não encontrado'}), 404

@bp.get('/api/cyber/phase9/games')
def phase9_games():
    return jsonify({'games': list(phase9.EDU_GAMES.values())})

@bp.get('/api/cyber/phase9/games/<gid>')
def phase9_game(gid):
    try:
        return jsonify(phase9.edu_game(gid))
    except KeyError:
        return jsonify({'error': 'Jogo não encontrado'}), 404

@bp.post('/api/cyber/phase9/explain')
def phase9_explain():
    d=_json() or {}
    return jsonify(phase9.explain_other_way(d.get('topic',''), d.get('style','analogia')))

@bp.post('/api/cyber/phase9/project-builder')
def phase9_project_builder():
    try:
        return jsonify(phase9.project_builder(_uid(), (_json() or {}).get('idea','')))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@bp.post('/api/cyber/phase9/mentor')
def phase9_mentor():
    d=_json() or {}
    return jsonify(phase9.mentor_step(_uid(), d.get('stage','pergunta'), d.get('context','')))

@bp.post('/api/cyber/phase9/code-review')
def phase9_code_review():
    d=_json() or {}
    return jsonify(phase9.code_review(d.get('code',''), d.get('language','javascript')))

@bp.get('/api/cyber/phase9/architecture')
def phase9_architecture():
    return jsonify(phase9.architecture_view())

@bp.get('/api/cyber/phase9/network-dns')
def phase9_network_dns():
    return jsonify(phase9.network_dns_view())

@bp.get('/api/cyber/phase9/daily')
def phase9_daily():
    return jsonify(phase9.daily_challenge(_uid()))

@bp.get('/api/cyber/phase9/weekly')
def phase9_weekly():
    return jsonify(phase9.weekly_project(_uid()))

@bp.get('/api/cyber/phase9/search')
def phase9_search():
    return jsonify({'results': phase9.smart_search(_uid(), request.args.get('q',''))})

@bp.get('/api/cyber/phase9/quality')
def phase9_quality():
    return jsonify(phase9.quality_center())

@bp.post('/api/cyber/phase9/snapshot')
def phase9_snapshot():
    d=_json() or {}
    return jsonify(phase9.snapshot(_uid(), d.get('label','Snapshot'), d.get('kind','general'), d.get('data') or {}))

@bp.get('/api/cyber/phase9/snapshots')
def phase9_snapshots():
    return jsonify({'snapshots': phase9.snapshots(_uid(), request.args.get('kind'))})

# =============================================================
# Phase 10.0 — Education Hub (dedicated area)
# =============================================================
from services import phase10

@bp.get('/educacao')
@bp.get('/education')
def education_page():
    return render_template('education.html')

@bp.get('/api/cyber/phase10/overview')
def phase10_overview():
    return jsonify(phase10.overview(_uid()))

@bp.get('/api/cyber/phase10/tracks')
def phase10_tracks():
    return jsonify({'tracks': phase10.tracks()})

@bp.get('/api/cyber/phase10/skill-tree')
def phase10_skill_tree():
    return jsonify(phase10.skill_tree())

@bp.get('/api/cyber/phase10/learning-map')
def phase10_learning_map():
    return jsonify(phase10.learning_map())

@bp.get('/api/cyber/phase10/labs')
def phase10_labs_catalog():
    return jsonify({'labs': phase10.labs_catalog()})

@bp.get('/api/cyber/phase10/tools')
def phase10_tools_catalog():
    return jsonify({'tools': phase10.tools_catalog()})

@bp.get('/api/cyber/phase10/games')
def phase10_edu_games():
    return jsonify({'games': phase10.edu_games()})

@bp.get('/api/cyber/phase10/lesson/<key>')
def phase10_lesson_public(key):
    data = phase10.lesson_public(key)
    if not data:
        return jsonify({'error': 'Aula não encontrada', 'hint': 'Use o catálogo de trilhas.'}), 404
    return jsonify(data)

@bp.post('/api/cyber/phase10/explain-another-way')
def phase10_explain_another():
    d = _json()
    return jsonify(phase10.explain_another_way(d.get('lesson_id') or d.get('key') or '', d.get('style', 'cotidiano')))

@bp.post('/api/cyber/phase10/mentor')
def phase10_mentor():
    d = _json()
    return jsonify(phase10.mentor_step(d.get('question', ''), d.get('attempt', ''), d.get('stage', 'pergunta')))

@bp.get('/api/cyber/phase10/daily-public')
def phase10_daily_public():
    return jsonify(phase10.daily_public())

@bp.get('/api/cyber/phase10/weekly-public')
def phase10_weekly_public():
    return jsonify(phase10.weekly_public())

@bp.get('/api/cyber/phase10/search-public')
def phase10_search_public():
    return jsonify({'results': phase10.smart_search_public(request.args.get('q', ''))})

@bp.post('/api/cyber/phase10/algorithm-steps')
def phase10_algorithm_steps():
    d = _json()
    return jsonify(phase10.algorithm_steps(d.get('algo', 'bubble'), d.get('data')))

@bp.post('/api/cyber/phase10/hash-demo')
def phase10_hash_demo():
    d = _json()
    return jsonify(phase10.hash_demo(d.get('text', ''), d.get('algo', 'sha256')))

@bp.post('/api/cyber/phase10/base64')
def phase10_base64():
    d = _json()
    return jsonify(phase10.base64_lab(d.get('text', ''), d.get('mode', 'encode'), d.get('b64', '')))

@bp.get('/api/cyber/phase10/quality')
def phase10_quality():
    return jsonify(phase10.quality_rules())

# ---------------------------------------------------------------------------
# Phase 11.0 — Educação expandida
# ---------------------------------------------------------------------------
from services import phase11

@bp.get('/api/cyber/phase11/overview')
def phase11_overview():
    return jsonify(phase11.overview_phase11())

@bp.get('/api/cyber/phase11/menu')
def phase11_menu():
    return jsonify({'menu': phase11.menu()})

@bp.get('/api/cyber/phase11/videos')
def phase11_videos():
    lang = request.args.get('lang') or request.args.get('linguagem')
    return jsonify({'videos': phase11.videos(lang)})

@bp.get('/api/cyber/phase11/videos/<vid>')
def phase11_video(vid):
    v = phase11.video_by_id(vid)
    if not v:
        return jsonify({'error': 'Vídeo não encontrado'}), 404
    return jsonify(v)

@bp.get('/api/cyber/phase11/beginner')
def phase11_beginner():
    return jsonify({'track': phase11.beginner_track()})

@bp.get('/api/cyber/phase11/beginner/<lid>')
def phase11_beginner_lesson(lid):
    L = phase11.beginner_lesson(lid)
    if not L:
        return jsonify({'error': 'Aula não encontrada'}), 404
    return jsonify(L)

@bp.get('/api/cyber/phase11/challenges')
def phase11_challenges():
    return jsonify({
        'challenges': phase11.challenges(
            request.args.get('categoria'),
            request.args.get('nivel'),
        )
    })

@bp.get('/api/cyber/phase11/challenges/<cid>')
def phase11_challenge(cid):
    c = phase11.challenge_by_id(cid)
    if not c:
        return jsonify({'error': 'Desafio não encontrado'}), 404
    # Não enviar solution no public por padrão (só hints)
    public = {k: v for k, v in c.items() if k != 'solution'}
    return jsonify(public)

@bp.get('/api/cyber/phase11/daily')
def phase11_daily():
    return jsonify(phase11.daily_challenge())

@bp.get('/api/cyber/phase11/achievements')
def phase11_achievements():
    return jsonify({'achievements': phase11.achievements()})

@bp.get('/api/cyber/phase11/search')
def phase11_search():
    return jsonify(phase11.search_edu(request.args.get('q', '')))

@bp.get('/api/cyber/phase11/professor')
def phase11_professor():
    return jsonify({'buttons': phase11.professor_buttons()})

@bp.get('/api/cyber/phase11/templates')
def phase11_templates():
    return jsonify({'templates': phase11.project_templates()})



@bp.get('/certificados')
def certificados_page():
    return render_template('certificados.html')

@bp.get('/certificados/verificar')
@bp.get('/certificados/verificar/<code>')
def certificados_verificar(code=None):
    return render_template('certificados_verificar.html', code=code or request.args.get('c', ''))

@bp.get('/qualidade')
@bp.get('/health-ui')
def qualidade_page():
    return render_template('qualidade.html')

# ---------------------------------------------------------------------------
# Phase 12.0 — Trilhas, Labs, Certificados JARVIS, Notas, Health
# ---------------------------------------------------------------------------
from services import phase12

@bp.get('/api/cyber/phase12/overview')
def phase12_overview():
    return jsonify(phase12.overview_phase12())

@bp.get('/api/cyber/phase12/tracks')
def phase12_tracks():
    return jsonify({'tracks': phase12.list_tracks()})

@bp.get('/api/cyber/phase12/tracks/<tid>')
def phase12_track(tid):
    t = phase12.track_by_id(tid)
    if not t:
        return jsonify({'error': 'Trilha não encontrada'}), 404
    return jsonify(t)

@bp.get('/api/cyber/phase12/debug')
def phase12_debug_list():
    return jsonify({'exercises': phase12.list_debug_exercises(request.args.get('lang'))})

@bp.get('/api/cyber/phase12/debug/<eid>')
def phase12_debug_one(eid):
    d = phase12.debug_by_id(eid, reveal=request.args.get('reveal') == '1')
    if not d:
        return jsonify({'error': 'Exercício não encontrado'}), 404
    return jsonify(d)

@bp.post('/api/cyber/phase12/debug/<eid>/check')
def phase12_debug_check(eid):
    data = request.get_json(silent=True) or {}
    return jsonify(phase12.check_debug(eid, data.get('code', '')))

@bp.get('/api/cyber/phase12/algorithms')
def phase12_algos():
    return jsonify({'algorithms': phase12.list_algorithms(request.args.get('cat'))})

@bp.get('/api/cyber/phase12/algorithms/<aid>')
def phase12_algo(aid):
    a = phase12.algorithm_by_id(aid)
    if not a:
        return jsonify({'error': 'Algoritmo não encontrado'}), 404
    return jsonify(a)

@bp.get('/api/cyber/phase12/api-lab')
def phase12_api_lab():
    return jsonify({'scenarios': phase12.list_api_scenarios()})

@bp.get('/api/cyber/phase12/db-lab')
def phase12_db_lab():
    return jsonify(phase12.db_lab_schema())

@bp.post('/api/cyber/phase12/db-lab/run')
def phase12_db_run():
    data = request.get_json(silent=True) or {}
    return jsonify(phase12.db_lab_run_demo(data.get('sql', '')))

@bp.get('/api/cyber/phase12/xp')
def phase12_xp():
    return jsonify(phase12.xp_info(int(request.args.get('xp') or 0)))

@bp.get('/api/cyber/phase12/challenges')
def phase12_challenges():
    return jsonify({'challenges': phase12.list_extra_challenges(request.args.get('tipo'))})

@bp.get('/api/cyber/phase12/game-source/<gid>')
def phase12_game_source(gid):
    return jsonify(phase12.game_source(gid))

@bp.get('/api/cyber/phase12/templates')
def phase12_templates():
    return jsonify({'templates': phase12.project_templates()})

@bp.get('/api/cyber/phase12/search')
def phase12_search():
    return jsonify(phase12.search_all(request.args.get('q', '')))

@bp.get('/api/cyber/phase12/professor-prompts')
def phase12_professor_prompts():
    return jsonify({'prompts': phase12.professor_prompts()})

@bp.post('/api/cyber/phase12/certificates/issue')
def phase12_cert_issue():
    data = request.get_json(silent=True) or {}
    uid = session.get('tf_uid') or session.get('user_id') or ''
    result = phase12.issue_certificate(
        user_name=data.get('nome') or data.get('name') or session.get('tf_name') or 'Estudante',
        track_id=data.get('trilha_id') or data.get('track_id') or '',
        modules_done=data.get('modulos') or data.get('modules'),
        project_name=data.get('projeto') or data.get('project'),
        user_id=str(uid),
    )
    status = 200 if result.get('ok') else 400
    return jsonify(result), status

@bp.get('/api/cyber/phase12/certificates')
def phase12_cert_list():
    uid = session.get('tf_uid') or session.get('user_id') or None
    return jsonify({'certificates': phase12.list_certificates(str(uid) if uid else None)})

@bp.get('/api/cyber/phase12/certificates/verify/<code>')
def phase12_cert_verify(code):
    return jsonify(phase12.verify_certificate(code))

@bp.get('/api/cyber/phase12/notes')
def phase12_notes_list():
    uid = str(session.get('tf_uid') or session.get('user_id') or 'anon')
    return jsonify({'notes': phase12.get_notes(uid)})

@bp.post('/api/cyber/phase12/notes')
def phase12_notes_save():
    uid = str(session.get('tf_uid') or session.get('user_id') or 'anon')
    data = request.get_json(silent=True) or {}
    return jsonify(phase12.save_note(uid, data))

@bp.delete('/api/cyber/phase12/notes/<nid>')
def phase12_notes_delete(nid):
    uid = str(session.get('tf_uid') or session.get('user_id') or 'anon')
    ok = phase12.delete_note(uid, nid)
    return jsonify({'ok': ok}), (200 if ok else 404)

@bp.get('/api/cyber/phase12/health')
def phase12_health():
    return jsonify(phase12.health_check())

# ---------------------------------------------------------------------------
# Phase 13.0 — Video Engine helpers, tools central, search, intelligence
# ---------------------------------------------------------------------------
from services import phase13

@bp.get('/api/cyber/phase13/overview')
def phase13_overview():
    return jsonify(phase13.overview_phase13())

@bp.get('/api/cyber/phase13/health')
def phase13_health():
    return jsonify(phase13.health_hints())

@bp.post('/api/cyber/phase13/intent')
def phase13_intent():
    data = request.get_json(silent=True) or {}
    return jsonify(phase13.detect_intent(data.get('text') or data.get('q') or ''))

@bp.get('/api/cyber/phase13/tools-central')
def phase13_tools_central():
    try:
        from services import tool_registry
        tools = [t.public() for t in tool_registry.REGISTRY.all()]
    except Exception:
        tools = []
    return jsonify(phase13.tools_central_index(tools))

@bp.get('/api/cyber/phase13/guided-projects')
def phase13_guided_projects():
    return jsonify({'projects': phase13.guided_projects()})

@bp.get('/api/cyber/phase13/learning-path')
def phase13_learning_path():
    return jsonify(phase13.learning_path_template())

@bp.get('/api/cyber/phase13/search')
def phase13_search():
    q = request.args.get('q') or ''
    try:
        vids = phase11.videos()
    except Exception:
        vids = []
    try:
        from services import tool_registry
        tools = [t.public() for t in tool_registry.REGISTRY.all()]
    except Exception:
        tools = []
    try:
        from services import game_lab
        games = game_lab.overview('anon').get('games') or []
    except Exception:
        games = []
    return jsonify(phase13.global_search(q, videos=vids, tools=tools, games=games))

@bp.post('/api/cyber/phase13/analyze-project')
def phase13_analyze_project():
    data = request.get_json(silent=True) or {}
    tree = data.get('files') or data.get('tree') or []
    deps = data.get('deps') or data.get('dependencies') or []
    return jsonify(phase13.analyze_project_tree(tree, deps))

@bp.get('/api/cyber/phase13/algo-extras')
def phase13_algo_extras():
    return jsonify({'algorithms': phase13.algo_extras()})

# ---------------------------------------------------------------------------
# Game Studio 5.0
# ---------------------------------------------------------------------------
from services import game_studio

@bp.get('/api/cyber/game-studio/overview')
def game_studio_overview():
    return jsonify(game_studio.studio_overview(_uid()))

@bp.post('/api/cyber/game-studio/projects')
def game_studio_create():
    try:
        return jsonify(game_studio.create_studio_project(_uid(), _json() or {})), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.get('/api/cyber/game-studio/projects/<pid>')
def game_studio_get(pid):
    p = game_lab.project(_uid(), pid)
    if not p:
        return jsonify({'error': 'not found'}), 404
    return jsonify(p)

@bp.put('/api/cyber/game-studio/projects/<pid>')
def game_studio_save(pid):
    try:
        return jsonify(game_studio.save_studio_project(_uid(), pid, _json() or {}))
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.get('/api/cyber/game-studio/projects/<pid>/versions')
def game_studio_versions(pid):
    return jsonify({'versions': game_studio.list_versions(_uid(), pid)})

@bp.post('/api/cyber/game-studio/projects/<pid>/restore/<int:version>')
def game_studio_restore(pid, version):
    try:
        return jsonify(game_studio.restore_version(_uid(), pid, version))
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.post('/api/cyber/game-studio/projects/<pid>/publish')
def game_studio_publish(pid):
    try:
        return jsonify(game_studio.publish_project(_uid(), pid))
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.post('/api/cyber/game-studio/projects/<pid>/coder')
def game_studio_coder(pid):
    try:
        data = _json() or {}
        return jsonify(game_studio.apply_coder_patch(_uid(), pid, data.get('instruction') or ''))
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.post('/api/cyber/game-studio/check')
def game_studio_check():
    data = (_json() or {}).get('data') or {}
    return jsonify(game_studio.game_check(data))

@bp.post('/api/cyber/game-studio/test-platformer')
def game_studio_test_platformer():
    try:
        return jsonify(game_studio.ensure_test_platformer(_uid()))
    except Exception as e:
        return jsonify({'error': str(e)}), 400
