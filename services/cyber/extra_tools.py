"""Ferramentas extras (v33) — 100% locais: sem rede, sem alvo, sem executar nada.

Cada função recebe texto/valores e devolve o mesmo formato das outras
ferramentas: {"findings": [...], "raw": {...}, "summary": "..."}.
Servem para estudar, conferir e entender — não atacam nada.
"""
import base64
import hashlib
import ipaddress
import json
import math
import re
import secrets
import string
import urllib.parse
from datetime import datetime, timezone

from services.evidence import make_finding as F

MAX_TEXT = 100_000


def _clip(s):
    return (s or "")[:MAX_TEXT]


def _res(findings, raw, summary):
    return {"findings": findings, "raw": raw, "summary": summary}


# ------------------------------------------------------------ senhas
_COMMON = {"123456", "12345678", "password", "senha", "senha123", "qwerty", "admin", "abc123",
           "111111", "123456789", "iloveyou", "letmein", "welcome", "brasil", "123123"}


def password_strength(password):
    pw = password or ""
    pool = 0
    pool += 26 if re.search(r"[a-z]", pw) else 0
    pool += 26 if re.search(r"[A-Z]", pw) else 0
    pool += 10 if re.search(r"\d", pw) else 0
    pool += 33 if re.search(r"[^A-Za-z0-9]", pw) else 0
    bits = round(len(pw) * math.log2(pool), 1) if pool and pw else 0.0
    findings = []
    if pw.lower() in _COMMON:
        findings.append(F("pw.common", "Senha está entre as mais comuns", "critical", where="senha",
                          impact="Testada logo nas primeiras tentativas de qualquer ataque.",
                          fix="Troque por uma frase longa e única."))
    if len(pw) < 12:
        findings.append(F("pw.short", f"Senha curta ({len(pw)} caracteres)", "high" if len(pw) < 8 else "medium",
                          where="senha", impact="Comprimento é o que mais pesa contra tentativa e erro.",
                          fix="Use 12+ caracteres; uma frase com 4 palavras soltas funciona bem."))
    if re.fullmatch(r"(.)\1+", pw) or re.search(r"(0123|1234|2345|abcd|qwer)", pw.lower()):
        findings.append(F("pw.pattern", "Sequência ou repetição previsível", "medium", where="senha",
                          fix="Evite sequências de teclado, números em ordem e caracteres repetidos."))
    if pw and pw.isdigit():
        findings.append(F("pw.digits", "Senha só com números", "high", where="senha",
                          fix="Misture palavras/letras ou aumente bastante o comprimento."))
    label = ("muito fraca" if bits < 28 else "fraca" if bits < 40 else "razoável" if bits < 60
             else "forte" if bits < 80 else "muito forte")
    return _res(findings, {"length": len(pw), "estimated_bits": bits, "level": label,
                           "note": "Estimativa teórica (não lê nem guarda a senha)."},
                f"{label} · ~{bits} bits · {len(findings)} alerta(s)")


def password_generator(length=20, kind="password"):
    try:
        length = int(length)
    except (TypeError, ValueError):
        length = 20
    length = max(8, min(length, 128))
    if (kind or "").lower() == "passphrase":
        words = ["lago", "pedra", "nuvem", "cacto", "farol", "trem", "ponte", "vento", "ouro", "rio",
                 "lua", "bravo", "tinta", "vidro", "monte", "sino", "areia", "folha", "mapa", "raio",
                 "cofre", "brasa", "sol", "navio", "trigo", "coral", "pluma", "tempo", "onda", "gelo"]
        n = max(4, min(length // 4, 10))
        out = "-".join(secrets.choice(words) for _ in range(n))
        bits = round(n * math.log2(len(words)), 1)
    else:
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        out = "".join(secrets.choice(alphabet) for _ in range(length))
        bits = round(length * math.log2(len(alphabet)), 1)
    return _res([], {"value": out, "bits": bits, "note": "Gerada com o módulo secrets (aleatório seguro)."},
                f"{len(out)} caracteres · ~{bits} bits de entropia")


# ------------------------------------------------------------ hash / tempo
def hash_generator(text, algorithm="sha256"):
    algo = (algorithm or "sha256").lower().replace("-", "")
    allowed = {"md5": "md5", "sha1": "sha1", "sha256": "sha256", "sha512": "sha512",
               "blake2b": "blake2b", "sha3256": "sha3_256"}
    if algo not in allowed:
        raise ValueError("Algoritmo inválido. Use: " + ", ".join(sorted(allowed)))
    digest = hashlib.new(allowed[algo], _clip(text).encode("utf-8")).hexdigest()
    findings = []
    if algo in ("md5", "sha1"):
        findings.append(F("hash.weak", f"{algo.upper()} é fraco para segurança", "low", where=algo,
                          impact="Colisões conhecidas; não use para senhas nem assinaturas.",
                          fix="Para integridade use SHA-256+. Para senhas use bcrypt/scrypt/argon2."))
    return _res(findings, {"algorithm": algo, "hex": digest, "length": len(digest)},
                f"{algo}: {digest[:16]}…")


def timestamp_converter(value):
    v = (value or "").strip()
    if re.fullmatch(r"-?\d{9,13}", v):
        n = int(v)
        if abs(n) > 10**11:
            n = n / 1000.0
        dt = datetime.fromtimestamp(n, tz=timezone.utc)
        return _res([], {"unix": int(n), "iso_utc": dt.isoformat()}, f"{v} → {dt.isoformat()}")
    dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return _res([], {"unix": int(dt.timestamp()), "iso_utc": dt.astimezone(timezone.utc).isoformat()},
                f"{v} → {int(dt.timestamp())}")


# ------------------------------------------------------------ URL / phishing
def url_inspector(url):
    u = (url or "").strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", u, re.I):
        u = "http://" + u
    p = urllib.parse.urlsplit(u)
    host = p.hostname or ""
    findings = []
    if p.scheme == "http":
        findings.append(F("url.http", "Sem HTTPS", "medium", where=host, fix="Prefira https://."))
    if "@" in (p.netloc or ""):
        findings.append(F("url.userinfo", "Usuário@ na URL (truque de phishing)", "high", where=host,
                          impact="O que aparece antes do @ é ignorado; o destino real é depois dele."))
    try:
        ipaddress.ip_address(host)
        findings.append(F("url.ip", "Host é um IP literal", "medium", where=host,
                          impact="Sites legítimos quase sempre usam nome de domínio."))
    except ValueError:
        pass
    if host.startswith("xn--") or ".xn--" in host:
        findings.append(F("url.punycode", "Domínio com punycode (possível homógrafo)", "high", where=host,
                          impact="Letras parecidas de outros alfabetos podem imitar uma marca."))
    if host.count(".") >= 4:
        findings.append(F("url.subdomains", "Muitos subdomínios", "low", where=host,
                          impact="Pode esconder o domínio real no meio do nome."))
    if re.search(r"(login|verify|secure|account|update|confirm)", host, re.I):
        findings.append(F("url.keyword", "Palavra típica de phishing no domínio", "low", where=host))
    if len(u) > 200:
        findings.append(F("url.long", "URL muito longa", "low", where=host))
    return _res(findings, {"scheme": p.scheme, "host": host, "port": p.port, "path": p.path,
                           "query": dict(urllib.parse.parse_qsl(p.query)), "fragment": p.fragment},
                f"{host or 'sem host'} · {len(findings)} alerta(s)")


# ------------------------------------------------------------ cabeçalhos HTTP
def security_headers_text(text):
    heads = {}
    for line in _clip(text).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            heads[k.strip().lower()] = v.strip()
    rules = [
        ("strict-transport-security", "HSTS ausente", "medium", "Adicione Strict-Transport-Security: max-age=31536000; includeSubDomains"),
        ("content-security-policy", "CSP ausente", "medium", "Defina uma Content-Security-Policy restritiva."),
        ("x-content-type-options", "X-Content-Type-Options ausente", "low", "Use X-Content-Type-Options: nosniff"),
        ("referrer-policy", "Referrer-Policy ausente", "low", "Use Referrer-Policy: strict-origin-when-cross-origin"),
        ("permissions-policy", "Permissions-Policy ausente", "info", "Restrinja câmera, microfone e geolocalização."),
    ]
    findings = [F(f"hdr.{k}", t, s, where=k, fix=fx) for k, t, s, fx in rules if k not in heads]
    if "x-frame-options" not in heads and "frame-ancestors" not in heads.get("content-security-policy", ""):
        findings.append(F("hdr.clickjacking", "Sem proteção contra clickjacking", "medium", where="x-frame-options",
                          fix="Use X-Frame-Options: DENY ou CSP frame-ancestors 'none'."))
    for leak in ("server", "x-powered-by", "x-aspnet-version"):
        if leak in heads and re.search(r"\d", heads[leak]):
            findings.append(F(f"hdr.leak.{leak}", f"Cabeçalho {leak} revela versão", "low", where=leak,
                              evidence=f"{leak}: {heads[leak][:60]}", fix="Remova ou generalize esse cabeçalho."))
    return _res(findings, {"headers_found": sorted(heads)}, f"{len(heads)} cabeçalho(s) · {len(findings)} achado(s)")


def csp_analyzer(policy):
    pol = _clip(policy).strip()
    pol = re.sub(r"^content-security-policy\s*:\s*", "", pol, flags=re.I)
    directives = {}
    for part in pol.split(";"):
        bits = part.strip().split()
        if bits:
            directives[bits[0].lower()] = bits[1:]
    findings = []
    if "default-src" not in directives and "script-src" not in directives:
        findings.append(F("csp.no-default", "Sem default-src nem script-src", "high", where="csp",
                          fix="Defina default-src 'self' como base."))
    for d, vals in directives.items():
        if "'unsafe-inline'" in vals and d in ("script-src", "default-src", "script-src-elem"):
            findings.append(F("csp.unsafe-inline", f"'unsafe-inline' em {d}", "high", where=d,
                              impact="Permite scripts inline — anula boa parte da proteção contra XSS.",
                              fix="Use nonce ou hash nos scripts."))
        if "'unsafe-eval'" in vals:
            findings.append(F("csp.unsafe-eval", f"'unsafe-eval' em {d}", "medium", where=d))
        if "*" in vals:
            findings.append(F("csp.wildcard", f"Curinga * em {d}", "high", where=d,
                              fix="Liste só as origens necessárias."))
        if "data:" in vals and d in ("script-src", "default-src"):
            findings.append(F("csp.data", f"data: permitido em {d}", "medium", where=d))
    for needed in ("object-src", "base-uri", "frame-ancestors"):
        if needed not in directives and "default-src" not in directives:
            findings.append(F(f"csp.{needed}", f"{needed} não definido", "low", where=needed))
    return _res(findings, {"directives": {k: v for k, v in directives.items()}},
                f"{len(directives)} diretiva(s) · {len(findings)} achado(s)")


def cookie_analyzer(text):
    findings, cookies = [], []
    for line in _clip(text).splitlines():
        line = re.sub(r"^set-cookie\s*:\s*", "", line.strip(), flags=re.I)
        if not line or "=" not in line:
            continue
        parts = [x.strip() for x in line.split(";")]
        name = parts[0].split("=", 1)[0]
        attrs = [a.lower() for a in parts[1:]]
        cookies.append(name)
        if "secure" not in attrs:
            findings.append(F("cookie.secure", f"Cookie {name} sem Secure", "medium", where=name,
                              fix="Adicione o atributo Secure (só HTTPS)."))
        if "httponly" not in attrs:
            findings.append(F("cookie.httponly", f"Cookie {name} sem HttpOnly", "medium", where=name,
                              impact="JavaScript (inclusive via XSS) consegue ler o cookie.",
                              fix="Adicione HttpOnly."))
        if not any(a.startswith("samesite") for a in attrs):
            findings.append(F("cookie.samesite", f"Cookie {name} sem SameSite", "low", where=name,
                              fix="Use SameSite=Lax (ou Strict)."))
        elif "samesite=none" in attrs and "secure" not in attrs:
            findings.append(F("cookie.samesite-none", f"Cookie {name}: SameSite=None exige Secure", "high", where=name))
    return _res(findings, {"cookies": cookies}, f"{len(cookies)} cookie(s) · {len(findings)} achado(s)")


# ------------------------------------------------------------ e-mail
def email_header_analyzer(text):
    t = _clip(text)
    low = t.lower()
    findings = []

    def verdict(name):
        m = re.search(rf"\b{name}\s*=\s*(\w+)", low)
        return m.group(1) if m else ""

    results = {k: verdict(k) for k in ("spf", "dkim", "dmarc")}
    for k, v in results.items():
        if not v:
            findings.append(F(f"mail.{k}.missing", f"Sem resultado de {k.upper()}", "low", where=k,
                              fix="Procure o cabeçalho Authentication-Results."))
        elif v != "pass":
            findings.append(F(f"mail.{k}.fail", f"{k.upper()} = {v}", "high", where=k,
                              impact="O remetente pode não ser quem diz ser."))
    frm = re.search(r"^from:.*?<?([\w.+-]+@[\w.-]+)>?", t, re.I | re.M)
    rp = re.search(r"^return-path:\s*<?([\w.+-]+@[\w.-]+)>?", t, re.I | re.M)
    if frm and rp and frm.group(1).split("@")[-1].lower() != rp.group(1).split("@")[-1].lower():
        findings.append(F("mail.mismatch", "From e Return-Path em domínios diferentes", "medium", where="from",
                          evidence=f"{frm.group(1)} vs {rp.group(1)}",
                          impact="Comum em spoofing e também em listas/ESPs legítimos — confirme o contexto."))
    hops = len(re.findall(r"^received:", t, re.I | re.M))
    return _res(findings, {**results, "from": frm.group(1) if frm else "", "return_path": rp.group(1) if rp else "",
                           "received_hops": hops}, f"SPF {results['spf'] or '?'} · DKIM {results['dkim'] or '?'} · DMARC {results['dmarc'] or '?'}")


# ------------------------------------------------------------ CVSS 3.1
_W = {"AV": {"N": .85, "A": .62, "L": .55, "P": .2}, "AC": {"L": .77, "H": .44},
      "UI": {"N": .85, "R": .62}, "CIA": {"H": .56, "L": .22, "N": 0}}


def _roundup(x):
    i = round(x * 100000)
    return i / 100000.0 if i % 10000 == 0 else (math.floor(i / 10000) + 1) / 10.0


def cvss_calculator(vector):
    m = dict(p.split(":", 1) for p in (vector or "").replace("CVSS:3.1/", "").replace("CVSS:3.0/", "").split("/") if ":" in p)
    need = ("AV", "AC", "PR", "UI", "S", "C", "I", "A")
    if any(k not in m for k in need):
        raise ValueError("Vetor incompleto. Ex.: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
    changed = m["S"] == "C"
    pr = {"N": .85, "L": .68 if changed else .62, "H": .5 if changed else .27}[m["PR"]]
    iss = 1 - (1 - _W["CIA"][m["C"]]) * (1 - _W["CIA"][m["I"]]) * (1 - _W["CIA"][m["A"]])
    impact = 7.52 * (iss - .029) - 3.25 * (iss - .02) ** 15 if changed else 6.42 * iss
    expl = 8.22 * _W["AV"][m["AV"]] * _W["AC"][m["AC"]] * pr * _W["UI"][m["UI"]]
    if impact <= 0:
        score = 0.0
    else:
        score = _roundup(min(1.08 * (impact + expl), 10)) if changed else _roundup(min(impact + expl, 10))
    sev = "crítica" if score >= 9 else "alta" if score >= 7 else "média" if score >= 4 else "baixa" if score > 0 else "nenhuma"
    return _res([], {"score": score, "severity": sev, "metrics": m}, f"CVSS 3.1 = {score} ({sev})")


# ------------------------------------------------------------ referências
PORTS = {
    20: ("FTP dados", "Sem criptografia; prefira SFTP."), 21: ("FTP", "Credenciais em texto puro."),
    22: ("SSH", "Use chaves; desative login root e senha."), 23: ("Telnet", "Inseguro; substitua por SSH."),
    25: ("SMTP", "Relay aberto é risco; exija autenticação."), 53: ("DNS", "Cuidado com transferência de zona e amplificação."),
    67: ("DHCP", "Rede local."), 80: ("HTTP", "Redirecione para HTTPS."), 110: ("POP3", "Use POP3S (995)."),
    123: ("NTP", "Amplificação DDoS se mal configurado."), 135: ("MS-RPC", "Não expor à internet."),
    139: ("NetBIOS", "Não expor."), 143: ("IMAP", "Use IMAPS (993)."), 161: ("SNMP", "Troque community padrão."),
    389: ("LDAP", "Use LDAPS/StartTLS."), 443: ("HTTPS", "Confira certificado e protocolos."),
    445: ("SMB", "Alvo clássico; nunca expor à internet."), 465: ("SMTPS", "SMTP sobre TLS."),
    587: ("SMTP submission", "Envio autenticado."), 993: ("IMAPS", "IMAP sobre TLS."), 995: ("POP3S", "POP3 sobre TLS."),
    1433: ("MSSQL", "Não expor o banco."), 3306: ("MySQL/MariaDB", "Não expor o banco."),
    3389: ("RDP", "Proteja com VPN e MFA."), 5432: ("PostgreSQL", "Não expor o banco."),
    5900: ("VNC", "Sem criptografia por padrão."), 6379: ("Redis", "Sem senha por padrão; nunca expor."),
    8080: ("HTTP alternativo", "Frequentemente painéis/proxies."), 9200: ("Elasticsearch", "Exija autenticação."),
    27017: ("MongoDB", "Exija autenticação; não expor."),
}


def port_reference(port):
    try:
        n = int(str(port).strip())
    except ValueError:
        q = str(port).strip().lower()
        hits = {p: v for p, v in PORTS.items() if q and q in v[0].lower()}
        if not hits:
            return _res([], {"matches": []}, "Nenhuma porta encontrada para essa busca")
        return _res([], {"matches": [{"port": p, "service": v[0], "tip": v[1]} for p, v in hits.items()]},
                    f"{len(hits)} porta(s) encontradas")
    if not 0 < n < 65536:
        raise ValueError("Porta deve estar entre 1 e 65535.")
    svc, tip = PORTS.get(n, ("não listada", "Porta alta/dinâmica ou serviço específico."))
    return _res([], {"port": n, "service": svc, "tip": tip, "range": "bem conhecida" if n < 1024 else "registrada" if n < 49152 else "dinâmica"},
                f"{n} → {svc}")


HTTP_CODES = {200: "OK", 201: "Criado", 204: "Sem conteúdo", 301: "Movido permanentemente", 302: "Encontrado (redirect temporário)",
              304: "Não modificado", 400: "Requisição inválida", 401: "Não autenticado", 403: "Proibido (autenticado, sem permissão)",
              404: "Não encontrado", 405: "Método não permitido", 409: "Conflito", 413: "Corpo grande demais",
              418: "Sou um bule de chá", 422: "Entidade não processável", 429: "Muitas requisições (rate limit)",
              500: "Erro interno do servidor", 502: "Bad gateway", 503: "Serviço indisponível", 504: "Gateway timeout"}


def http_status_reference(code):
    n = int(str(code).strip())
    if n not in HTTP_CODES:
        fam = {1: "informativo", 2: "sucesso", 3: "redirecionamento", 4: "erro do cliente", 5: "erro do servidor"}.get(n // 100, "desconhecido")
        return _res([], {"code": n, "meaning": "não listado", "family": fam}, f"{n}: família {fam}")
    return _res([], {"code": n, "meaning": HTTP_CODES[n]}, f"{n} = {HTTP_CODES[n]}")


def base64_inspector(text):
    raw = _clip(text).strip()
    pad = raw + "=" * (-len(raw) % 4)
    try:
        data = base64.b64decode(pad, validate=True)
    except Exception:
        raise ValueError("Não parece Base64 válido.")
    try:
        decoded = data.decode("utf-8")
        printable = True
    except UnicodeDecodeError:
        decoded, printable = data.hex(), False
    findings = []
    if printable and re.search(r"(password|passwd|secret|api[_-]?key|token)\s*[=:]", decoded, re.I):
        findings.append(F("b64.secret", "Base64 contém algo que parece segredo", "high", where="base64",
                          impact="Base64 é codificação, não criptografia.", fix="Não guarde segredos assim."))
    return _res(findings, {"bytes": len(data), "utf8": printable, "decoded": decoded[:500]},
                f"{len(data)} bytes · {'texto' if printable else 'binário (hex)'}")


# ------------------------------------------------------------ registro
def register(R):
    specs = [
        ("password_strength", "Força de senha", "Estima a força (entropia) de uma senha e aponta fraquezas. Nada é guardado.",
         {"password": {"required": True}}, lambda p, c: password_strength(p["password"]),
         ["força de senha", "senha forte", "minha senha é boa", "entropia"]),
        ("password_generator", "Gerador de senha/frase", "Gera senha aleatória segura ou frase-senha.",
         {"length": {"description": "8 a 128 (padrão 20)"}, "kind": {"description": "password|passphrase"}},
         lambda p, c: password_generator(p.get("length", 20), p.get("kind", "password")),
         ["gerar senha", "criar senha", "passphrase", "frase-senha"]),
        ("hash_generator", "Gerador de hash", "Calcula MD5, SHA-1, SHA-256, SHA-512, BLAKE2b ou SHA3-256 de um texto.",
         {"text": {"required": True}, "algorithm": {"description": "md5|sha1|sha256|sha512|blake2b|sha3-256"}},
         lambda p, c: hash_generator(p["text"], p.get("algorithm", "sha256")),
         ["gerar hash", "calcular hash", "sha256 de", "md5 de"]),
        ("timestamp_converter", "Conversor de timestamp", "Converte Unix ↔ data ISO (UTC). Útil em logs.",
         {"value": {"required": True, "description": "1700000000 ou 2026-09-30T12:00:00Z"}},
         lambda p, c: timestamp_converter(p["value"]), ["timestamp", "epoch", "unix time", "converter data"]),
        ("url_inspector", "Inspetor de URL (phishing)", "Desmonta uma URL e aponta sinais de phishing (IP, @, punycode, sem HTTPS).",
         {"url": {"required": True}}, lambda p, c: url_inspector(p["url"]),
         ["link suspeito", "url suspeita", "phishing", "inspecionar url", "esse link é seguro"]),
        ("security_headers_text", "Analisador de cabeçalhos HTTP", "Cole cabeçalhos de resposta e veja o que falta (HSTS, CSP, clickjacking...).",
         {"text": {"required": True, "description": "cabeçalhos colados"}}, lambda p, c: security_headers_text(p["text"]),
         ["cabeçalhos http", "security headers", "hsts", "clickjacking"]),
        ("csp_analyzer", "Analisador de CSP", "Avalia uma Content-Security-Policy: unsafe-inline, curingas, diretivas faltando.",
         {"policy": {"required": True}}, lambda p, c: csp_analyzer(p["policy"]),
         ["csp", "content security policy", "analisar csp"]),
        ("cookie_analyzer", "Analisador de cookies", "Confere Secure, HttpOnly e SameSite em linhas Set-Cookie.",
         {"text": {"required": True, "description": "linhas Set-Cookie"}}, lambda p, c: cookie_analyzer(p["text"]),
         ["cookie seguro", "set-cookie", "httponly", "samesite"]),
        ("email_header_analyzer", "Analisador de cabeçalho de e-mail", "Lê SPF/DKIM/DMARC e incoerências de remetente em um e-mail colado.",
         {"text": {"required": True, "description": "cabeçalho completo do e-mail"}}, lambda p, c: email_header_analyzer(p["text"]),
         ["cabeçalho de e-mail", "spf dkim dmarc", "e-mail falso", "spoofing"]),
        ("cvss_calculator", "Calculadora CVSS 3.1", "Calcula a nota CVSS 3.1 a partir do vetor.",
         {"vector": {"required": True, "description": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}},
         lambda p, c: cvss_calculator(p["vector"]), ["cvss", "nota da vulnerabilidade", "gravidade cvss"]),
        ("port_reference", "Referência de portas", "Mostra serviço e dica de segurança de uma porta (ou busca por nome).",
         {"port": {"required": True, "description": "número (445) ou nome (ssh)"}}, lambda p, c: port_reference(p["port"]),
         ["que porta é", "porta 445", "porta 22", "referência de portas"]),
        ("http_status_reference", "Referência de status HTTP", "Explica códigos HTTP (401 vs 403, 429, 502...).",
         {"code": {"required": True}}, lambda p, c: http_status_reference(p["code"]),
         ["status http", "erro 403", "erro 404", "erro 502", "código http"]),
        ("base64_inspector", "Inspetor de Base64", "Decodifica Base64 e avisa se parece conter segredo.",
         {"text": {"required": True}}, lambda p, c: base64_inspector(p["text"]),
         ["inspecionar base64", "isso é base64"]),
    ]
    for tid, name, desc, params, handler, kws in specs:
        if R.get(tid):
            continue
        R.register(id=tid, name=name, category="utilitarios", description=desc, cap="tools_basic",
                   params={k: {"type": "string", **v} for k, v in params.items()}, handler=handler, keywords=kws)
