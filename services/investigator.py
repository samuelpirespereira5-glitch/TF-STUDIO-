"""SECURITY INVESTIGATOR

ALVO AUTORIZADO → RECONHECIMENTO → ANÁLISE → EVIDÊNCIA → PROBLEMA →
GRAVIDADE → IMPACTO → CORREÇÃO → RETESTE → RELATÓRIO

`investigate()` é um gerador de eventos (para streaming/progresso no
Jarvis). Toda etapa executa ferramentas reais via registry.
"""
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from services import scope, evidence
from services.tool_registry import execute

STAGES = ["ALVO AUTORIZADO", "RECONHECIMENTO", "ANÁLISE", "EVIDÊNCIA", "PROBLEMA",
          "GRAVIDADE", "IMPACTO", "CORREÇÃO", "RETESTE", "RELATÓRIO"]
SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _host_of(target):
    t = target.strip()
    if "://" not in t:
        t = "https://" + t
    return urlparse(t).hostname or t


def build_scene(target, raw_by_tool, findings):
    """Cena 3D simples e real: servidor central, serviços/portas, endpoints e
    achados destacados por gravidade. O Hologram Engine só renderiza."""
    host = _host_of(target)
    nodes = [{"id": "server", "type": "server", "label": host, "severity": None}]
    links = []
    for p in (raw_by_tool.get("port_inventory") or {}).get("open", []):
        nid = f"port{p['port']}"
        nodes.append({"id": nid, "type": "service", "label": f"{p['port']}/{p['service']}"})
        links.append(["server", nid])
    web = raw_by_tool.get("web_analyzer") or {}
    for i, hop in enumerate(web.get("redirect_chain", [])):
        nid = f"ep{i}"
        nodes.append({"id": nid, "type": "endpoint", "label": urlparse(hop["url"]).path or "/", "status": hop["status"]})
        links.append(["server", nid])
    for i, t in enumerate(web.get("technologies", [])[:6]):
        nid = f"tech{i}"
        nodes.append({"id": nid, "type": "tech", "label": t})
        links.append(["server", nid])
    for f in sorted(findings, key=lambda x: SEV_ORDER[x["severity"]])[:14]:
        nid = "f_" + f["id"]
        nodes.append({"id": nid, "type": "finding", "label": f["title"], "severity": f["severity"]})
        # liga achado ao nó mais relacionado
        anchor = "server"
        if f["where"].startswith("port:"):
            anchor = "port" + f["where"].split(":")[1]
        links.append([anchor if any(n["id"] == anchor for n in nodes) else "server", nid])
    return {"title": f"Investigação · {host}", "nodes": nodes, "links": links}


def investigate(target, role, session_id="", do_ports=True, do_subdomains=False):
    t_start = time.perf_counter()
    all_findings, raws = [], {}
    tool_ids = []

    yield {"event": "stage", "stage": STAGES[0], "index": 0, "message": f"Validando escopo de {target}…"}
    host = _host_of(target)
    tkey = evidence.normalize_target(target)
    try:
        ips = scope.check_host(host)
    except scope.ScopeError as e:
        yield {"event": "error", "stage": STAGES[0], "error": str(e),
               "hint": "Peça ao owner para adicionar o alvo em Cyber Lab › Alvos autorizados."}
        return
    yield {"event": "stage_done", "stage": STAGES[0], "index": 0, "message": f"{host} autorizado ({', '.join(map(str, ips))})"}

    import ipaddress
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        is_ip = False
    parsed = urlparse(target if "://" in target else "https://" + target)
    explicit_http = parsed.scheme == "http" and (parsed.port or 80) != 443
    plan = []
    if is_ip:
        yield {"event": "stage", "stage": STAGES[1], "index": 1,
               "message": "Alvo é um IP: análise de DNS não se aplica (pulada)."}
    else:
        plan.append(("dns_analyzer", "RECONHECIMENTO", "Consultando DNS (SPF, DMARC, CAA)…"))
    if do_subdomains:
        plan.append(("subdomain_discovery", "RECONHECIMENTO", "Descobrindo subdomínios por dicionário…"))
    if do_ports:
        plan.append(("port_inventory", "RECONHECIMENTO", "Inventariando portas/serviços comuns…"))
    plan.append(("web_analyzer", "ANÁLISE", "Analisando HTTP, headers, cookies, CSP e CORS…"))
    if explicit_http:
        yield {"event": "stage", "stage": STAGES[2], "index": 2,
               "message": "Alvo informado em HTTP puro: TLS pulado (o achado 'HTTP sem TLS' cobre isso)."}
    else:
        plan.append(("tls_analyzer", "ANÁLISE", "Analisando certificado e protocolos TLS…"))
    plan.append(("link_checker", "ANÁLISE", "Verificando links e conteúdo misto…"))

    scan_ids = {}
    for tool_id, stage, msg in plan:
        idx = STAGES.index(stage)
        yield {"event": "stage", "stage": stage, "index": idx, "tool": tool_id, "message": msg}
        params = {"target": target}
        if tool_id == "port_inventory" and parsed.port:
            params["extra_ports"] = [parsed.port]  # inclui a porta do próprio alvo
        res = execute(tool_id, params, role, {"session_id": session_id, "target": tkey})
        if not res["ok"]:
            yield {"event": "tool_error", "stage": stage, "tool": tool_id, "error": res["error"],
                   "error_type": res.get("error_type")}
            continue
        tool_ids.append(tool_id)
        all_findings += res.get("findings", [])
        raws[tool_id] = res.get("raw")
        scan_ids[tool_id] = res.get("scan_id")
        yield {"event": "tool_done", "stage": stage, "tool": tool_id, "summary": res["summary"],
               "duration_ms": res["duration_ms"], "findings": len(res.get("findings", []))}

    # dedup por id estável
    uniq = {f["id"]: f for f in all_findings}
    findings = sorted(uniq.values(), key=lambda f: (SEV_ORDER[f["severity"]], f["title"]))

    yield {"event": "stage", "stage": STAGES[3], "index": 3, "message": f"{len(scan_ids)} scans salvos no Evidence Center"}
    yield {"event": "stage", "stage": STAGES[4], "index": 4, "message": f"{len(findings)} problema(s) encontrado(s)"}
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in evidence.SEVERITIES}
    score = evidence.risk_score(findings)
    yield {"event": "stage", "stage": STAGES[5], "index": 5,
           "message": f"Risco {evidence.risk_label(score)} ({score}/100)", "counts": counts}
    yield {"event": "stage", "stage": STAGES[6], "index": 6,
           "message": "Impacto e correção descritos por achado"}
    yield {"event": "stage", "stage": STAGES[7], "index": 7,
           "message": "Correções priorizadas por gravidade"}

    # RETESTE: compara com o scan anterior do mesmo alvo, se houver
    comparisons = []
    for tool_id, sid in scan_ids.items():
        rows = evidence.history(target=tkey, tool=tool_id, limit=2)
        if len(rows) == 2:
            comparisons.append({"tool": tool_id, **evidence.compare(rows[1], rows[0])})
    yield {"event": "stage", "stage": STAGES[8], "index": 8,
           "message": (f"Comparado com scan anterior em {len(comparisons)} ferramenta(s)"
                       if comparisons else "Primeira investigação deste alvo — sem base para comparar"),
           "comparisons": comparisons}

    report_md = build_report(tkey, findings, raws, comparisons, score)
    yield {"event": "stage", "stage": STAGES[9], "index": 9, "message": "Relatório gerado"}
    yield {"event": "done", "target": tkey, "score": score, "risk": evidence.risk_label(score),
           "counts": counts, "findings": findings, "comparisons": comparisons,
           "scene": build_scene(target, raws, findings), "report_md": report_md,
           "scan_ids": scan_ids, "duration_ms": round((time.perf_counter() - t_start) * 1000),
           "tools": tool_ids}


def build_report(host, findings, raws, comparisons=None, score=None):
    score = evidence.risk_score(findings) if score is None else score
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in evidence.SEVERITIES}
    L = [f"# Relatório de Segurança — {host}", "",
         f"_Gerado em {now} pelo Tristan Thorne Cyber Lab. Análise em alvo autorizado._", "",
         "## Resumo executivo", "",
         f"- **Risco geral:** {evidence.risk_label(score).upper()} ({score}/100)",
         f"- **Achados:** {len(findings)} — " + ", ".join(f"{n} {s}" for s, n in counts.items() if n) if findings
         else "- **Achados:** nenhum problema encontrado pelas verificações executadas.", ""]
    web = raws.get("web_analyzer") or {}
    if web:
        L += ["## Reconhecimento", "",
              f"- URL final: `{web.get('final_url')}` (HTTP {web.get('status')}, {web.get('response_ms')} ms)",
              f"- Tecnologias: {', '.join(web.get('technologies', [])) or 'não identificadas'}"]
    ports = (raws.get("port_inventory") or {}).get("open")
    if ports is not None:
        L.append("- Portas abertas: " + (", ".join(f"{p['port']}/{p['service']}" for p in ports) or "nenhuma das testadas"))
    L.append("")
    if comparisons:
        L += ["## Reteste (antes × depois)", ""]
        for c in comparisons:
            L.append(f"- `{c['tool']}`: {c['verdict']} — score {c['before']['score']} → {c['after']['score']}; "
                     f"{len(c['resolved'])} resolvido(s), {len(c['new'])} novo(s), {len(c['persistent'])} persistente(s)")
        L.append("")
    L += ["## Achados", ""]
    if not findings:
        L.append("Nenhum achado.")
    for i, f in enumerate(findings, 1):
        L += [f"### {i}. [{f['severity'].upper()}] {f['title']}", "",
              f"- **Evidência:** {f['evidence']}", f"- **Impacto:** {f['impact']}",
              f"- **Correção:** {f['fix']}", f"- **Local:** `{f['where']}`", ""]
    L += ["## Limitações", "",
          "Verificações não invasivas, restritas ao escopo autorizado. A ausência de achados não prova ausência de vulnerabilidades."]
    return "\n".join(L)
