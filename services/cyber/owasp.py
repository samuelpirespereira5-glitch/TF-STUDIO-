"""OWASP Top 10 — verificações heurísticas e NÃO destrutivas.

Filosofia: isto é um detector de sinais, não um exploit. Cada teste manda
no máximo alguns requests extras com marcadores inofensivos e observa a
resposta (reflexo, erro de banco, redirect para host controlado, etc.).
Nunca tenta extrair dados reais, nunca escreve, nunca faz brute force.
Tudo passa por services.scope (alvo autorizado) antes de qualquer request.
"""
import re
import time
import uuid
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from services import scope
from services.evidence import make_finding as F
from services.cyber.web import safe_get, normalize_url

SQL_ERROR_PATTERNS = [
    r"you have an error in your sql syntax", r"warning: mysqli?", r"unclosed quotation mark",
    r"quoted string not properly terminated", r"pg_query\(\)", r"sqlstate\[", r"ora-\d{5}",
    r"sqlite3\.OperationalError", r"syntax error at or near",
]
LFI_MARKERS = [r"root:.*:0:0:", r"\[extensions\]", r"\[boot loader\]"]


def _params_from_url(url):
    parts = urlsplit(url)
    return parts, parse_qsl(parts.query, keep_blank_values=True)


def _build(parts, params):
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))


def scan_owasp(target, max_requests=12):
    """Roda os testes heurísticos que fazem sentido para o alvo (URL com
    query string testa parâmetros; sem query string, testa só o que não
    depende de parâmetro: cabeçalhos de segurança relacionados a SSRF/CORS
    já ficam no web_analyzer — aqui focamos no que é específico do OWASP)."""
    url = normalize_url(target)
    scope.check_host(urlsplit(url).hostname)
    findings = []
    budget = {"n": 0}

    parts, params = _params_from_url(url)
    if params:
        findings += _test_sqli(parts, params, budget, max_requests)
        findings += _test_xss(parts, params, budget, max_requests)
        findings += _test_lfi(parts, params, budget, max_requests)
        findings += _test_ssrf_param(parts, params, budget, max_requests)
    else:
        findings.append(F("owasp.no_params", "URL sem parâmetros de query",
                          "info", evidence=url,
                          impact="Testes de SQLi/XSS/LFI/SSRF por parâmetro não se aplicam sem parâmetros.",
                          fix="Para testar esses vetores, informe uma URL com ?param=valor (ex.: uma busca "
                              "ou filtro do próprio alvo).", where=url))
    findings += _test_idor_hint(parts, params)
    return {"findings": findings, "raw": {"url": url, "params_tested": [p for p, _ in params],
                                          "requests_used": budget["n"]}}


def _get(url, budget, max_requests, timeout=8):
    if budget["n"] >= max_requests:
        return None
    budget["n"] += 1
    try:
        resp, _chain = safe_get(url, timeout=timeout)
        return resp
    except Exception:
        return None


def _test_sqli(parts, params, budget, max_requests):
    """Error-based: injeta uma aspa simples inofensiva e procura mensagens
    de erro de banco de dados conhecidas. Não usa boolean/time-based (mais
    invasivo) nem tenta extrair dados."""
    out = []
    for i, (k, v) in enumerate(params):
        p2 = list(params)
        p2[i] = (k, v + "'")
        r = _get(_build(parts, p2), budget, max_requests)
        if not r:
            continue
        body = (r.text or "").lower()
        for pat in SQL_ERROR_PATTERNS:
            if re.search(pat, body, re.I):
                out.append(F("owasp.sqli_error_based", f"Possível SQL Injection no parâmetro '{k}'",
                             "critical", evidence=f"Padrão de erro SQL detectado ao injetar aspa em '{k}'.",
                             impact="Pode permitir leitura/alteração não autorizada do banco de dados.",
                             fix="Use queries parametrizadas/prepared statements; nunca concatene input em SQL.",
                             where=f"param:{k}"))
                break
    return out


def _test_xss(parts, params, budget, max_requests):
    """Reflected XSS: injeta um marcador único e verifica se volta
    SEM escapar no HTML da resposta."""
    out = []
    for i, (k, v) in enumerate(params):
        marker = f"tfxss{uuid.uuid4().hex[:8]}"
        payload = f"<{marker}>"
        p2 = list(params)
        p2[i] = (k, v + payload)
        r = _get(_build(parts, p2), budget, max_requests)
        if not r:
            continue
        if payload in (r.text or ""):
            out.append(F("owasp.reflected_xss", f"Possível XSS refletido no parâmetro '{k}'", "high",
                         evidence=f"Marcador '{payload}' voltou sem escapar no HTML.",
                         impact="Um atacante pode executar JavaScript no navegador da vítima.",
                         fix="Faça escape de saída (HTML-encode) e considere uma CSP restritiva.",
                         where=f"param:{k}"))
    return out


def _test_lfi(parts, params, budget, max_requests):
    """Local File Inclusion: tenta path traversal para um arquivo público
    e inofensivo de ler (não escreve, não executa comando)."""
    out = []
    candidates = ["../../../../etc/passwd", "..\\..\\..\\..\\windows\\win.ini"]
    for i, (k, v) in enumerate(params):
        if not re.search(r"\.(php|asp|jsp|py|rb)?$", k, re.I) and not any(
                h in k.lower() for h in ("file", "path", "page", "doc", "include", "template")):
            continue
        for cand in candidates:
            p2 = list(params)
            p2[i] = (k, cand)
            r = _get(_build(parts, p2), budget, max_requests)
            if not r:
                continue
            body = r.text or ""
            if any(re.search(pat, body, re.I) for pat in LFI_MARKERS):
                out.append(F("owasp.lfi", f"Possível Local File Inclusion no parâmetro '{k}'", "critical",
                             evidence=f"Conteúdo de arquivo de sistema detectado ao injetar path traversal em '{k}'.",
                             impact="Pode expor arquivos sensíveis do servidor.",
                             fix="Valide/normalize paths; use allowlist de arquivos permitidos, nunca input direto.",
                             where=f"param:{k}"))
                break
    return out


def _test_ssrf_param(parts, params, budget, max_requests):
    """SSRF: apenas HEURÍSTICA por nome de parâmetro — não faz um request
    real para um servidor de callback externo (isso seria ativo demais
    para um scanner automático genérico); sinaliza parâmetros suspeitos
    para revisão manual."""
    out = []
    suspicious = ("url", "uri", "link", "callback", "redirect", "target", "dest", "src", "fetch", "proxy")
    for k, v in params:
        if k.lower() in suspicious and re.match(r"^https?://", v, re.I):
            out.append(F("owasp.ssrf_candidate", f"Parâmetro '{k}' aceita URL — candidato a SSRF", "medium",
                         evidence=f"{k}={v}",
                         impact="Se o servidor busca essa URL internamente, pode ser abusado para acessar "
                                "rede interna/metadata.",
                         fix="Valide contra allowlist de hosts, bloqueie IPs privados/metadata no backend.",
                         where=f"param:{k}"))
    return out


def _test_idor_hint(parts, params):
    """BOLA/IDOR: heurística — identifica parâmetros numéricos sequenciais
    típicos de referência direta a objeto, para revisão manual (testar
    IDOR de forma automática exigiria duas contas de teste, fora de escopo
    de um scanner sem credenciais)."""
    out = []
    for k, v in params:
        if re.match(r"^\d+$", v) and any(h in k.lower() for h in ("id", "user", "conta", "account", "order", "invoice")):
            out.append(F("owasp.idor_candidate", f"Parâmetro '{k}={v}' parece referência direta a objeto",
                         "low", evidence=f"{k}={v}",
                         impact="Se a autorização não for checada no backend, outro usuário pode acessar "
                                "trocando o valor (BOLA/IDOR).",
                         fix="Sempre valide no backend se o usuário autenticado tem permissão sobre o "
                             "objeto pedido, nunca confie apenas no ID da URL.",
                         where=f"param:{k}"))
    return out
