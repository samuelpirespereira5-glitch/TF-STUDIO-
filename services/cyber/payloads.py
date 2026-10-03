"""Payloads & Encoders — utilitários puramente locais (sem rede, sem
alvo), úteis durante um pentest: decodificar tokens, identificar hashes,
gerar payloads de teste seguros (não destrutivos) e calcular sub-redes.
"""
import base64
import binascii
import ipaddress
import json
import re
import urllib.parse


# --------------------------------------------------------------- encoder
def encode_decode(text, encoding, action):
    text = text or ""
    try:
        if encoding == "base64":
            return base64.b64encode(text.encode()).decode() if action == "encode" \
                else base64.b64decode(text + "=" * (-len(text) % 4)).decode(errors="replace")
        if encoding == "url":
            return urllib.parse.quote(text) if action == "encode" else urllib.parse.unquote(text)
        if encoding == "hex":
            return text.encode().hex() if action == "encode" else bytes.fromhex(text).decode(errors="replace")
        raise ValueError(f"Encoding desconhecido: {encoding}")
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"Falha ao {action} em {encoding}: {e}")


def run_encoder(text, encoding, action):
    out = encode_decode(text, encoding, action)
    return {"findings": [], "raw": {"input": text, "encoding": encoding, "action": action, "output": out},
            "summary": out[:200]}


# ------------------------------------------------------------ jwt decode
def decode_jwt(token):
    """Decodifica header/payload SEM validar assinatura (não temos a
    chave) — só para inspeção, deixa isso bem explícito no resultado."""
    parts = (token or "").strip().split(".")
    if len(parts) < 2:
        raise ValueError("Token não parece um JWT (esperado header.payload.signature).")

    def _b64d(s):
        s += "=" * (-len(s) % 4)
        return json.loads(base64.urlsafe_b64decode(s).decode())

    header = _b64d(parts[0])
    payload = _b64d(parts[1])
    findings = []
    alg = (header.get("alg") or "").lower()
    if alg == "none":
        findings.append({"id": "jwt.alg_none", "rule": "jwt.alg_none", "title": "JWT com alg=none",
                          "severity": "critical", "evidence": "header.alg == 'none'",
                          "impact": "Servidor mal configurado pode aceitar token sem assinatura.",
                          "fix": "Nunca aceite alg=none; force o algoritmo esperado no backend.",
                          "where": "header.alg", "ref": ""})
    if payload.get("exp") is None:
        findings.append({"id": "jwt.no_exp", "rule": "jwt.no_exp", "title": "JWT sem campo 'exp' (expiração)",
                          "severity": "low", "evidence": "payload sem 'exp'",
                          "impact": "Token pode nunca expirar se o backend não checar isso.",
                          "fix": "Sempre inclua e valide 'exp' no backend.", "where": "payload.exp", "ref": ""})
    return {"findings": findings,
            "raw": {"header": header, "payload": payload, "signature_present": len(parts) == 3 and bool(parts[2]),
                    "note": "Assinatura NÃO foi validada (chave secreta/pública não disponível aqui)."},
            "summary": f"alg={header.get('alg')} · claims: {', '.join(payload.keys())}"}


# ------------------------------------------------------- hash identifier
HASH_PATTERNS = [
    (r"^[a-f0-9]{32}$", ["MD5", "NTLM", "MD4"]),
    (r"^[a-f0-9]{40}$", ["SHA-1"]),
    (r"^[a-f0-9]{56}$", ["SHA-224"]),
    (r"^[a-f0-9]{64}$", ["SHA-256"]),
    (r"^[a-f0-9]{96}$", ["SHA-384"]),
    (r"^[a-f0-9]{128}$", ["SHA-512"]),
    (r"^\$2[aby]?\$\d{2}\$", ["bcrypt"]),
    (r"^\$1\$", ["MD5 crypt (Unix)"]),
    (r"^\$5\$", ["SHA-256 crypt (Unix)"]),
    (r"^\$6\$", ["SHA-512 crypt (Unix)"]),
    (r"^\$argon2(id|i|d)\$", ["Argon2"]),
    (r"^[a-f0-9]{32}:[a-f0-9]+$", ["hash:salt genérico"]),
]


def identify_hash(value):
    value = (value or "").strip()
    matches = [names for pat, names in HASH_PATTERNS if re.match(pat, value, re.I)]
    flat = [n for group in matches for n in group]
    return {"findings": [], "raw": {"value": value, "length": len(value), "candidates": flat or ["não identificado"]},
            "summary": ", ".join(flat) if flat else "Formato não reconhecido — pode não ser um hash comum."}


# ------------------------------------------------------------- cidr calc
def cidr_calc(cidr):
    net = ipaddress.ip_network(cidr, strict=False)
    return {"findings": [], "raw": {
        "network": str(net.network_address), "broadcast": str(net.broadcast_address) if net.version == 4 else None,
        "netmask": str(net.netmask), "prefix": net.prefixlen, "total_hosts": net.num_addresses,
        "usable_hosts": max(net.num_addresses - 2, 0) if net.version == 4 and net.prefixlen < 31 else net.num_addresses,
        "first_usable": str(list(net.hosts())[0]) if net.num_addresses > 2 else None,
        "last_usable": str(list(net.hosts())[-1]) if net.num_addresses > 2 else None,
        "version": net.version,
    }, "summary": f"{cidr} → {net.num_addresses} endereços"}


# --------------------------------------------------------- test payloads
"""Payloads de TESTE inofensivos: usam marcador único, não fazem nada
destrutivo (não é ransomware, não apaga dados, não executa comando real).
Servem para o pentester colar manualmente num campo e observar o
comportamento — não são disparados automaticamente por esta função."""
def generate_test_payloads(kind):
    kind = (kind or "").lower()
    bank = {
        "xss": [
            "<script>alert('tf-xss-test')</script>",
            "\"><img src=x onerror=alert('tf-xss-test')>",
            "'-alert('tf-xss-test')-'",
        ],
        "sqli": [
            "' OR '1'='1",
            "' UNION SELECT NULL-- -",
            "\" OR \"\"=\"",
        ],
        "lfi": [
            "../../../../etc/passwd",
            "..%2f..%2f..%2fetc%2fpasswd",
            "php://filter/convert.base64-encode/resource=index.php",
        ],
        "ssrf": [
            "http://127.0.0.1:80",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]:80",
        ],
        "cmdi": [
            "; id",
            "| whoami",
            "`id`",
        ],
    }
    payloads = bank.get(kind)
    if not payloads:
        raise ValueError(f"Categoria desconhecida: {kind}. Use: {', '.join(bank)}.")
    return {"findings": [], "raw": {"kind": kind, "payloads": payloads},
            "summary": f"{len(payloads)} payload(s) de teste para {kind} "
                       f"(uso manual em ambiente autorizado — não são disparados automaticamente)."}
