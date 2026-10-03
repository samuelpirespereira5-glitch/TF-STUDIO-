"""Central reusable developer/diagnostic tools for Tristan Thorne.

Local tools never execute user code. Network tools always revalidate the
Cyber Lab authorization scope before making a request.
"""
import base64
import hashlib
import ipaddress
import json
import re
import socket
import ssl
import time
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urlparse

from services import scope
from services.cyber import dns as dns_service, local, ports, web
from services.evidence import make_finding as F

MAX_TEXT = 400_000
MAX_HTTP_BODY = 200_000


def _text(value):
    return str(value or "")[:MAX_TEXT]


def _finding_summary(findings):
    return f"{len(findings)} achado(s)"


def code_analyzer(p, ctx):
    text = _text(p.get("text"))
    if not text.strip():
        raise ValueError("Cole o código que deseja analisar.")
    result = local.scan_code(text, p.get("filename", ""))
    secret = local.scan_secrets(text, p.get("filename", ""))
    findings = result.get("findings", []) + secret.get("findings", [])
    return {"findings": findings, "raw": {"lines": len(text.splitlines()), "language": p.get("language", "auto")},
            "summary": _finding_summary(findings)}


def _balance(text):
    pairs = {"}": "{", ")": "(", "]": "["}
    opening = {"{": 0, "(": 0, "[": 0}
    stack = []
    quote = None
    line_comment = block_comment = False
    i = 0
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if c == "\n": line_comment = False
        elif block_comment:
            if c == "*" and n == "/": block_comment = False; i += 1
        elif quote:
            if c == "\\": i += 1
            elif c == quote: quote = None
        else:
            if c == "/" and n == "/": line_comment = True; i += 1
            elif c == "/" and n == "*": block_comment = True; i += 1
            elif c in "'\"`": quote = c
            elif c in opening:
                opening[c] += 1; stack.append(c)
            elif c in pairs:
                opening[pairs[c]] -= 1
                if not stack or stack[-1] != pairs[c]:
                    return {"ok": False, "problem": f"Símbolo '{c}' sem abertura correspondente.", "depth": opening}
                stack.pop()
        i += 1
    if quote:
        return {"ok": False, "problem": "String aparentemente não fechada.", "depth": opening}
    if block_comment:
        return {"ok": False, "problem": "Comentário de bloco não fechado.", "depth": opening}
    if any(v != 0 for v in opening.values()):
        return {"ok": False, "problem": "Chaves/parênteses/colchetes desbalanceados.", "depth": opening}
    return {"ok": True, "problem": "Nenhum desequilíbrio estrutural encontrado.", "depth": opening}


def debugger(p, ctx):
    code = _text(p.get("code"))
    error = _text(p.get("error"))
    findings = []
    if not error and not code:
        raise ValueError("Informe o erro e/ou cole o código.")
    if error:
        low = error.lower()
        patterns = [
            (r"modulenotfounderror|no module named", "Dependência/módulo ausente", "Verifique o ambiente e instale a dependência correta."),
            (r"nameerror", "Nome/variável não definido", "Confira grafia, escopo e inicialização da variável."),
            (r"typeerror", "Tipos incompatíveis", "Confira os tipos dos argumentos e o retorno da função."),
            (r"keyerror", "Chave inexistente", "Use validação de chave ou dict.get() quando apropriado."),
            (r"indexerror", "Índice fora dos limites", "Confira o tamanho da coleção antes de acessar o índice."),
            (r"attributeerror", "Atributo/método inexistente", "Confira o tipo real do objeto e o nome do atributo."),
            (r"syntaxerror", "Erro de sintaxe", "Revise a linha indicada, parênteses, dois-pontos, aspas e indentação."),
            (r"connection(refused|reset)|timeout", "Falha de conexão", "Confira host, porta, serviço, firewall e timeout."),
        ]
        for pat, title, fix in patterns:
            if re.search(pat, low):
                findings.append(F("debug." + re.sub(r"[^a-z]+", "_", title.lower()).strip("_"), title, "medium",
                                  evidence=error[:400], impact="A execução encontrou a condição indicada pela mensagem.", fix=fix, where="error"))
                break
        m = re.search(r"(?:line|linha)\s+(\d+)", error, re.I)
        if m:
            findings.append(F("debug.line", f"Linha indicada: {m.group(1)}", "info", evidence=m.group(0),
                              impact="A mensagem aponta o local provável do erro.", fix="Abra a linha indicada e confira o contexto imediato.", where=f"line:{m.group(1)}"))
    if code:
        b = _balance(code)
        if not b["ok"]:
            findings.append(F("debug.structure", "Possível problema estrutural no código", "medium", evidence=b["problem"],
                              impact="Um delimitador ou string não fechado pode impedir o parser de interpretar o arquivo.",
                              fix="Revise os delimitadores e strings próximos ao ponto da edição.", where="source"))
    return {"findings": findings, "raw": {"error": error[:1000], "structure": _balance(code) if code else None},
            "summary": "Nenhum padrão de erro encontrado." if not findings else _finding_summary(findings)}


def _parse_headers(raw):
    if not raw:
        return {}
    try:
        obj = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(obj, dict): raise ValueError("Headers devem ser um objeto JSON.")
        return {str(k): str(v) for k, v in obj.items()}
    except json.JSONDecodeError as e:
        raise ValueError(f"Headers inválidos: {e}")


def _request(p, ctx):
    url = (p.get("url") or "").strip()
    if not url:
        raise ValueError("Informe a URL.")
    if "://" not in url: url = "https://" + url
    scope.check_url(url)
    method = (p.get("method") or "GET").upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}:
        raise ValueError("Método HTTP não suportado.")
    headers = _parse_headers(p.get("headers", ""))
    body = p.get("body", "")
    if isinstance(body, (dict, list)):
        body = json.dumps(body, ensure_ascii=False)
    body = _text(body)
    if body and "content-type" not in {k.lower() for k in headers}:
        headers["Content-Type"] = "application/json" if body.lstrip().startswith(("{", "[")) else "text/plain"
    start = time.perf_counter()
    resp, chain = web.safe_get(url, headers=headers, timeout=10, method=method)
    elapsed = round((time.perf_counter() - start) * 1000)
    body_text = resp.text[:MAX_HTTP_BODY] if method != "HEAD" else ""
    return {"raw": {"status": resp.status_code, "method": method, "url": chain[-1]["url"],
                     "elapsed_ms": elapsed, "headers": dict(resp.headers.items()),
                     "body": body_text, "redirects": chain},
            "summary": f"HTTP {resp.status_code} · {elapsed} ms · {len(body_text)} bytes"}


def api_tester(p, ctx):
    return _request(p, ctx)


def http_request_tester(p, ctx):
    return _request(p, ctx)


def json_validator(p, ctx):
    text = _text(p.get("text"))
    if not text.strip(): raise ValueError("Cole um JSON.")
    try:
        obj = json.loads(text)
        return {"raw": {"valid": True, "type": type(obj).__name__, "pretty": json.dumps(obj, ensure_ascii=False, indent=2)},
                "summary": f"JSON válido · tipo {type(obj).__name__}"}
    except json.JSONDecodeError as e:
        return {"raw": {"valid": False, "line": e.lineno, "column": e.colno, "position": e.pos},
                "findings": [F("json.invalid", "JSON inválido", "medium", evidence=str(e), impact="O parser não consegue interpretar o documento.", fix="Corrija a sintaxe perto da linha/coluna indicadas.", where=f"{e.lineno}:{e.colno}")],
                "summary": f"JSON inválido · linha {e.lineno}, coluna {e.colno}"}


def regex_tester(p, ctx):
    pattern = _text(p.get("pattern")); text = _text(p.get("text"))
    if not pattern: raise ValueError("Informe a expressão regular.")
    try:
        flags = 0
        for flag in (p.get("flags") or ""):
            flags |= {"i": re.I, "m": re.M, "s": re.S}.get(flag, 0)
        rx = re.compile(pattern, flags)
        matches = [{"match": m.group(0), "start": m.start(), "end": m.end(), "groups": m.groups()} for m in rx.finditer(text)]
        return {"raw": {"matches": matches[:200], "count": len(matches)}, "summary": f"{len(matches)} correspondência(s)"}
    except re.error as e:
        return {"raw": {"valid": False}, "findings": [F("regex.invalid", "Expressão regular inválida", "medium", evidence=str(e), impact="A expressão não pode ser compilada.", fix="Revise a sintaxe da expressão.", where="pattern")], "summary": "Regex inválida"}


def dns_lookup(p, ctx):
    domain = p.get("domain") or p.get("target")
    r = dns_service.run_dns_analysis(domain)
    return {"findings": r["findings"], "raw": r["raw"], "summary": f"DNS consultado · {len(r['findings'])} achado(s)"}


def port_checker(p, ctx):
    target = p.get("target") or ""
    ips = scope.check_host(target.split(":")[0].split("/")[0])
    try: port = int(p.get("port"))
    except (TypeError, ValueError): raise ValueError("Informe uma porta válida.")
    if not 1 <= port <= 65535: raise ValueError("A porta deve estar entre 1 e 65535.")
    host = target.split(":")[0].split("/")[0]
    started = time.perf_counter()
    try:
        with scope.create_connection(host, port, timeout=2.0, mode="lab", ips=ips, context="port_checker") as s:
            s.settimeout(0.5)
            try: banner = s.recv(160).decode(errors="replace").strip()[:120]
            except Exception: banner = ""
        opened = True
    except Exception:
        opened = False; banner = ""
    ms = round((time.perf_counter() - started) * 1000)
    return {"raw": {"host": host, "port": port, "open": opened, "banner": banner, "elapsed_ms": ms},
            "summary": f"{host}:{port} {'aberta' if opened else 'fechada/filtrada'} · {ms} ms"}


def log_analyzer(p, ctx):
    r = local.analyze_logs(_text(p.get("text")))
    return {"findings": r["findings"], "raw": r["raw"], "summary": f"{r['raw']['lines']} linha(s) · {len(r['findings'])} achado(s)"}


def website_health(p, ctx):
    url = (p.get("url") or "").strip()
    if "://" not in url: url = "https://" + url
    scope.check_url(url)
    start = time.perf_counter()
    resp, chain = web.safe_get(url, timeout=10)
    ms = round((time.perf_counter() - start) * 1000)
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.I | re.S)
    if m: title = re.sub(r"\s+", " ", m.group(1)).strip()[:200]
    findings = []
    if resp.status_code >= 500:
        findings.append(F("health.http_5xx", f"Servidor respondeu HTTP {resp.status_code}", "high", evidence=str(resp.status_code), impact="A aplicação está devolvendo erro de servidor.", fix="Confira logs da aplicação e infraestrutura.", where="http"))
    elif resp.status_code >= 400:
        findings.append(F("health.http_4xx", f"Servidor respondeu HTTP {resp.status_code}", "medium", evidence=str(resp.status_code), impact="A URL consultada não está disponível normalmente.", fix="Confira rota, autenticação e configuração do servidor.", where="http"))
    if ms > 3000:
        findings.append(F("health.slow", "Resposta HTTP lenta", "low", evidence=f"{ms} ms", impact="Tempo alto pode degradar a experiência.", fix="Verifique backend, banco, cache e rede.", where="latency"))
    return {"findings": findings, "raw": {"status": resp.status_code, "elapsed_ms": ms, "title": title,
                     "final_url": chain[-1]["url"], "content_type": resp.headers.get("content-type", ""),
                     "content_length": len(resp.content), "redirects": chain},
            "summary": f"HTTP {resp.status_code} · {ms} ms · {len(findings)} problema(s)"}


class _HTMLValidator(HTMLParser):
    void = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    def __init__(self):
        super().__init__(convert_charrefs=True); self.stack=[]; self.errors=[]
    def handle_starttag(self, tag, attrs):
        if tag not in self.void: self.stack.append(tag)
    def handle_startendtag(self, tag, attrs): pass
    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack:
                x=self.stack.pop()
                if x == tag: break
        else: self.errors.append(f"</{tag}> sem abertura correspondente")
    def close(self):
        super().close(); self.errors += [f"<{x}> não fechada" for x in reversed(self.stack)]


def html_css_js_validator(p, ctx):
    kind = (p.get("kind") or "html").lower()
    text = _text(p.get("text"))
    if not text.strip(): raise ValueError("Cole o conteúdo para validar.")
    errors=[]
    if kind == "html":
        parser=_HTMLValidator()
        try: parser.feed(text); parser.close(); errors=parser.errors
        except Exception as e: errors=[str(e)]
    elif kind == "css":
        b=_balance(text.replace("/*", "").replace("*/", ""))
        if not b["ok"]: errors.append(b["problem"])
        if re.search(r"@[a-z-]+[^;{]*$", text, re.M): errors.append("Possível at-rule CSS sem bloco/terminador.")
    elif kind == "js":
        b=_balance(text)
        if not b["ok"]: errors.append(b["problem"])
    else:
        raise ValueError("Tipo deve ser html, css ou js.")
    findings=[F(f"validate.{kind}", "Problema de validação", "medium", evidence=e, impact="O conteúdo pode falhar no parser/navegador.", fix="Revise a estrutura apontada.", where=kind) for e in errors[:50]]
    return {"findings": findings, "raw": {"kind": kind, "valid": not errors, "errors": errors[:50]}, "summary": f"{kind.upper()}: {'válido' if not errors else str(len(errors)) + ' problema(s)'}"}


def base64_tool(p, ctx):
    text=_text(p.get("text")); action=(p.get("action") or "encode").lower()
    if action == "encode":
        out=base64.b64encode(text.encode()).decode()
    elif action == "decode":
        try: out=base64.b64decode(text, validate=True).decode("utf-8")
        except Exception as e: raise ValueError(f"Base64 inválido: {e}")
    else: raise ValueError("Ação deve ser encode ou decode.")
    return {"raw": {"action": action, "result": out}, "text": out, "summary": f"Base64 {action} concluído"}


def hash_generator(p, ctx):
    text=_text(p.get("text")); algo=(p.get("algorithm") or "sha256").lower().replace("-", "")
    aliases={"sha256":"sha256", "sha1":"sha1", "sha512":"sha512", "md5":"md5", "sha384":"sha384", "sha224":"sha224"}
    if algo not in aliases: raise ValueError("Algoritmo: md5, sha1, sha224, sha256, sha384 ou sha512.")
    digest=hashlib.new(aliases[algo], text.encode()).hexdigest()
    return {"raw": {"algorithm": algo, "digest": digest}, "text": digest, "summary": f"Hash {algo} gerado"}


def jwt_analyzer(p, ctx):
    token=_text(p.get("token")).strip()
    parts=token.split(".")
    if len(parts)!=3: raise ValueError("JWT deve ter header.payload.signature.")
    def dec(s): return json.loads(base64.urlsafe_b64decode(s + "=" * (-len(s)%4)).decode())
    try: header=dec(parts[0]); payload=dec(parts[1])
    except Exception as e: raise ValueError(f"JWT inválido: {e}")
    return {"raw": {"header": header, "payload": payload, "signature_present": bool(parts[2]), "verified": False},
            "text": json.dumps({"header":header,"payload":payload,"signature_present":bool(parts[2]),"verified":False}, ensure_ascii=False, indent=2),
            "summary": f"JWT analisado · alg={header.get('alg', '?')} · assinatura NÃO validada"}


def file_analyzer(p, ctx):
    text=_text(p.get("text")); name=(p.get("filename") or "arquivo").strip()
    raw=text.encode("utf-8", errors="replace")
    sha256=hashlib.sha256(raw).hexdigest(); md5=hashlib.md5(raw).hexdigest()
    lines=text.count("\n") + (1 if text else 0)
    ext=name.rsplit(".",1)[-1].lower() if "." in name else ""
    json_valid=None
    if ext == "json" or text.lstrip().startswith(("{", "[")):
        try: json.loads(text); json_valid=True
        except Exception: json_valid=False
    binary_ratio=sum(1 for b in raw if b == 0 or b < 9)/max(1,len(raw))
    return {"raw": {"filename":name,"extension":ext,"bytes":len(raw),"lines":lines,"sha256":sha256,"md5":md5,"json_valid":json_valid,"binary_like":binary_ratio>0.01},
            "summary": f"{name} · {len(raw)} bytes · SHA-256 {sha256[:16]}…"}


def network_diagnostics(p, ctx):
    host=(p.get("host") or "").strip()
    if not host: raise ValueError("Informe um host ou IP.")
    started=time.perf_counter(); ips=scope.check_host(host); dns_ms=round((time.perf_counter()-started)*1000)
    probes=[]
    for port in (80,443):
        t=time.perf_counter()
        try:
            with scope.create_connection(host,port,timeout=2,mode="lab",ips=ips,context="network_diagnostics"): ok=True
        except Exception: ok=False
        probes.append({"port":port,"open":ok,"ms":round((time.perf_counter()-t)*1000)})
    return {"raw": {"host":host,"ips":[str(i) for i in ips],"dns_ms":dns_ms,"tcp":probes},
            "summary": f"{host} → {', '.join(map(str,ips))} · DNS {dns_ms} ms · 80={'open' if probes[0]['open'] else 'closed'} · 443={'open' if probes[1]['open'] else 'closed'}"}
