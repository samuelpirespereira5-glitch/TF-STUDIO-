"""Tool Router do Jarvis.

1. `plan(text, role)`  → entende a frase, extrai alvo/parâmetros e escolhe
   ferramenta(s) — combinando várias quando faz sentido.
2. `run_plan(plan, role)` → executa passo a passo (gerador de eventos:
   explicação, progresso, resultado) com AUTO-DIAGNÓSTICO:
   erro → causa provável → correção segura → novo teste → resultado.
"""
import re
import time
from urllib.parse import urlparse

from services import permissions
from services.tool_registry import REGISTRY, execute

URL_RE = re.compile(r"(https?://[^\s\"'<>]+)", re.I)
DOMAIN_RE = re.compile(r"\b((?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,24})\b", re.I)
IP_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")
FILE_LIKE = {"py", "js", "ts", "json", "txt", "md", "html", "css", "env", "log", "yml", "yaml", "conf", "php"}

# frases que disparam a investigação completa (playbook)
INVESTIGATE_HINTS = ["audite", "auditar", "auditoria", "investigue", "investigar", "análise completa",
                     "analise completa", "análise de segurança", "analise de segurança", "teste de segurança",
                     "pentest", "security investigator", "verifique a segurança", "segurança do meu site",
                     "seguranca do meu site", "check-up", "checkup"]


def extract_target(text):
    m = URL_RE.search(text)
    if m:
        return m.group(1).rstrip(".,);")
    m = IP_RE.search(text)
    if m:
        return m.group(1)
    for m in DOMAIN_RE.finditer(text):
        d = m.group(1)
        if d.rsplit(".", 1)[-1].lower() not in FILE_LIKE:
            return d
    return None


def _score(tool, low):
    s = 0
    for k in tool.keywords:
        if not k:
            continue
        if re.search(r"(?<![\w])" + re.escape(k) + r"(?![\w])", low):
            s += 2 if " " in k or len(k) > 5 else 1
    return s


def plan(text, role, session_id=""):
    """Devolve {"mode": "investigate"|"tools"|"none"|"denied", "steps": [...], "explain": "..."}"""
    low = (text or "").lower()
    target = extract_target(text or "")

    if any(h in low for h in INVESTIGATE_HINTS) and target:
        if not permissions.has_cap("cyber", role):
            return {"mode": "denied", "capability": "cyber", "steps": [],
                    "explain": "Investigações de segurança exigem papel owner/admin."}
        return {"mode": "investigate", "target": target,
                "steps": [{"tool": "security_investigator", "params": {"target": target}}],
                "explain": f"Vou executar o Security Investigator em {target}: escopo → reconhecimento → "
                           f"análise → evidência → gravidade → correção → reteste → relatório."}

    scored = []
    for t in REGISTRY.tools.values():
        if t.kind == "ui" and t.id == "hologram_scene":
            continue
        sc = _score(t, low)
        if sc:
            scored.append((sc, t))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return {"mode": "none", "steps": [], "explain": ""}

    top = scored[0][0]
    chosen = [t for sc, t in scored if sc >= max(2, top - 1)][:4]
    denied = [t for t in chosen if not permissions.has_cap(t.cap, role)]
    chosen = [t for t in chosen if permissions.has_cap(t.cap, role)]
    if not chosen and denied:
        return {"mode": "denied", "capability": denied[0].cap, "steps": [],
                "explain": f"'{denied[0].name}' exige papel com acesso a '{denied[0].cap}'."}

    steps = []
    for t in chosen:
        params = {}
        for pname in t.params:
            if pname in ("target", "url", "domain") and target:
                params[pname] = target
            if pname == "subject":
                params["subject"] = _hologram_subject(text)
            if pname == "text":
                params["text"] = ctx_text(text)
        steps.append({"tool": t.id, "params": params})

    # ferramenta sem alvo/conteúdo obrigatório NÃO sequestra a conversa:
    # "meu site está lento" vira bate-papo normal, não um erro de parâmetro.
    def _complete(step):
        spec = REGISTRY.get(step["tool"]).params
        return all(step["params"].get(k) for k, v in spec.items() if v.get("required"))
    steps = [s for s in steps if _complete(s)]
    if not steps:
        return {"mode": "none", "steps": [], "explain": ""}

    names = ", ".join(REGISTRY.get(s["tool"]).name for s in steps)
    explain = (f"Vou usar: {names}." if len(steps) == 1 else
               f"Vou combinar {len(steps)} ferramentas: {names}.")
    if denied:
        explain += f" (Ignorei {', '.join(d.name for d in denied)}: seu papel não tem acesso.)"
    return {"mode": "tools", "target": target, "steps": steps, "explain": explain}


def _hologram_subject(text):
    m = re.search(r"(?:holograma|hologram|mostre|mostra|exiba|exibir)\s+(?:de\s+|do\s+|da\s+|um\s+|uma\s+)*(.+)$",
                  text, re.I)
    return (m.group(1) if m else text).strip(" .!?")[:80]


def ctx_text(text):
    """Texto colado após ``` ou ':' vira conteúdo a analisar."""
    m = re.search(r"```(?:\w+)?\n?(.*?)```", text, re.S)
    if m:
        return m.group(1)
    return text.split(":", 1)[1].strip() if ":" in text and len(text.split(":", 1)[1]) > 20 else ""


# ------------------------------------------------------------- diagnóstico
def diagnose(error, error_type, tool_id, params):
    """Mapeia erro → causa provável → correção segura (ou None)."""
    e = (error or "").lower()
    if error_type == "PermissionDenied":
        return {"cause": "Seu papel não tem esta permissão.", "fix": None,
                "advice": "Peça a um owner para conceder acesso admin."}
    if error_type == "ScopeError" or "autorizado" in e or "autorize" in e:
        return {"cause": "O alvo não está na lista de alvos autorizados (ou resolve para rede interna).",
                "fix": None, "advice": "Um owner deve adicionar o alvo em Cyber Lab › Alvos autorizados, "
                                        "confirmando que é seu ou que há autorização."}
    if error_type == "MissingParams":
        return {"cause": "Faltou informar o alvo/conteúdo.", "fix": None,
                "advice": "Diga o domínio/URL, ou cole o conteúdo entre ``` ```."}
    if "timed out" in e or "timeout" in e or error_type in ("ConnectTimeout", "ReadTimeout", "TimeoutError"):
        return {"cause": "O alvo demorou demais para responder (rede lenta ou porta filtrada).",
                "fix": {"action": "retry", "params": params}, "advice": "Tentando novamente uma vez."}
    if "name or service not known" in e or "nodename nor servname" in e or "não consegui resolver" in e or "gaierror" in e:
        tgt = params.get("target") or params.get("domain") or ""
        if tgt and not tgt.startswith("www.") and "." in tgt and "://" not in tgt:
            p2 = {**params}
            for k in ("target", "domain"):
                if k in p2:
                    p2[k] = "www." + tgt
            return {"cause": "O nome não resolveu no DNS; pode ser que só exista com 'www.'.",
                    "fix": {"action": "retry", "params": p2}, "advice": "Tentando com www."}
        return {"cause": "O nome não resolve no DNS (digitação errada ou domínio inexistente).",
                "fix": None, "advice": "Confira a grafia do domínio."}
    if "certificate" in e or "ssl" in e:
        return {"cause": "Falha na verificação TLS do alvo (certificado inválido/expirado ou protocolo incompatível).",
                "fix": None, "advice": "Rode o TLS Analyzer para detalhes; não desativo a verificação automaticamente."}
    if "refused" in e or "recusada" in e:
        return {"cause": "A porta/serviço não está aceitando conexões.", "fix": None,
                "advice": "Confirme que o serviço está no ar e a porta correta."}
    if "api key" in e or "chave" in e or "nenhuma chave" in e:
        return {"cause": "Nenhum provedor de IA configurado.", "fix": None,
                "advice": "Configure uma chave em Configurações (owner)."}
    return {"cause": "Erro não catalogado.", "fix": None, "advice": "Veja os detalhes técnicos; se persistir, rode o diagnóstico do sistema."}


def run_plan(pl, role, session_id=""):
    """Gerador de eventos. Cada evento é um dict serializável (NDJSON/SSE)."""
    t0 = time.perf_counter()
    yield {"event": "plan", "mode": pl["mode"], "explain": pl["explain"],
           "steps": [{"tool": s["tool"], "name": (REGISTRY.get(s["tool"]).name if REGISTRY.get(s["tool"]) else s["tool"])}
                     for s in pl["steps"]] or []}
    if pl["mode"] in ("none", "denied"):
        yield {"event": "done", "ok": pl["mode"] == "none", "denied": pl["mode"] == "denied",
               "duration_ms": 0}
        return

    if pl["mode"] == "investigate":
        from services.investigator import investigate
        final = None
        for ev in investigate(pl["target"], role, session_id):
            yield ev
            if ev["event"] == "done":
                final = ev
        yield {"event": "done", "ok": final is not None, "duration_ms": round((time.perf_counter() - t0) * 1000)}
        return

    results, ok_all = [], True
    total = len(pl["steps"])
    for i, step in enumerate(pl["steps"], 1):
        tool = REGISTRY.get(step["tool"])
        yield {"event": "step_start", "index": i, "total": total, "tool": tool.id, "name": tool.name,
               "explain": tool.explain, "progress": round((i - 1) / total * 100)}
        res = execute(tool.id, step["params"], role, {"session_id": session_id, "target": pl.get("target")})
        if not res["ok"]:
            d = diagnose(res["error"], res.get("error_type", ""), tool.id, step["params"])
            yield {"event": "diagnostic", "tool": tool.id, "error": res["error"], "cause": d["cause"],
                   "advice": d["advice"], "auto_fix": bool(d["fix"])}
            if d["fix"]:
                time.sleep(0.4)
                yield {"event": "retry", "tool": tool.id, "message": d["advice"]}
                res2 = execute(tool.id, d["fix"]["params"], role, {"session_id": session_id, "target": pl.get("target")})
                if res2["ok"]:
                    res2["recovered"] = True
                    res = res2
                    yield {"event": "diagnostic_resolved", "tool": tool.id,
                           "message": "Correção segura aplicada e teste passou."}
                else:
                    yield {"event": "diagnostic_failed", "tool": tool.id, "error": res2["error"],
                           "message": "A correção automática não resolveu."}
        if res["ok"]:
            results.append(res)
            yield {"event": "step_result", "index": i, "total": total, **res, "progress": round(i / total * 100)}
            if "ui_action" in res:
                yield {"event": "ui_action", **res["ui_action"]}
        else:
            ok_all = False
            yield {"event": "step_result", "index": i, "total": total, **res, "progress": round(i / total * 100)}
    allf = [f for r in results for f in r.get("findings", [])]
    yield {"event": "done", "ok": ok_all, "duration_ms": round((time.perf_counter() - t0) * 1000),
           "findings_total": len(allf)}
