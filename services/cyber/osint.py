"""OSINT & Reconhecimento.

* WHOIS real via socket cru na porta 43 (sem dependência externa, sem API
  paga) — segue a cadeia de referral (whois.iana.org -> whois do TLD).
* Verificação de vazamento de e-mail: usa a API pública HaveIBeenPwned se
  (e só se) uma chave estiver configurada em Configurações/env
  (HIBP_API_KEY). Sem chave, o resultado diz claramente que não está
  configurado — nunca finge um resultado.
* Fingerprint de tecnologias: reaproveita services.cyber.web (não duplica).
"""
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

from services import scope
from services.evidence import make_finding as F

IANA_WHOIS = "whois.iana.org"


def _whois_query(server, query, timeout=6):
    with scope.create_connection(server, 43, timeout=timeout, mode="public", context="whois") as s:
        s.sendall((query + "\r\n").encode())
        chunks = []
        while True:
            data = s.recv(4096)
            if not data:
                break
            chunks.append(data)
        return b"".join(chunks).decode(errors="replace")


def whois_lookup(domain):
    domain = (domain or "").strip().lower().strip(".")
    scope.check_name_only(domain)
    referred = None
    try:
        iana = _whois_query(IANA_WHOIS, domain)
        m = re.search(r"refer:\s*(\S+)", iana, re.I)
        referred = m.group(1) if m else None
    except Exception:
        iana = ""
    server = referred or f"whois.{domain.rsplit('.', 1)[-1]}"
    try:
        raw = _whois_query(server, domain)
    except Exception as e:
        return {"findings": [], "raw": {"domain": domain, "server": server, "error": str(e), "iana": iana[:2000]}}

    fields = {}
    for key, pat in [
        ("registrar", r"Registrar:\s*(.+)"),
        ("created", r"Creation Date:\s*(.+)"),
        ("expires", r"Registry Expiry Date:\s*(.+)"),
        ("updated", r"Updated Date:\s*(.+)"),
        ("status", r"Domain Status:\s*(.+)"),
        ("nameservers", r"Name Server:\s*(.+)"),
    ]:
        vals = re.findall(pat, raw, re.I)
        if vals:
            fields[key] = vals if key in ("status", "nameservers") else vals[0].strip()

    findings = []
    if fields.get("expires"):
        findings.append(F("osint.whois_expiry", "Data de expiração do domínio identificada", "info",
                          evidence=fields["expires"], impact="Domínio não renovado pode ser sequestrado.",
                          fix="Garanta renovação automática e alertas de vencimento.", where=domain))
    if "clientTransferProhibited".lower() not in json.dumps(fields.get("status", [])).lower() and fields.get("status"):
        findings.append(F("osint.whois_no_transfer_lock", "Sem trava de transferência (clientTransferProhibited) evidente",
                          "low", evidence=str(fields.get("status")),
                          impact="Facilita domain hijacking via transferência não autorizada.",
                          fix="Ative clientTransferProhibited no registrador.", where=domain))
    return {"findings": findings, "raw": {"domain": domain, "server": server, "fields": fields, "raw_excerpt": raw[:4000]}}


def check_email_breach(email):
    """HaveIBeenPwned — só executa de verdade se houver chave configurada."""
    email = (email or "").strip()
    api_key = os.getenv("HIBP_API_KEY", "").strip()
    if not api_key:
        return {"findings": [], "raw": {"configured": False},
                "summary": "HIBP_API_KEY não configurada — verificação de vazamento desativada "
                           "(não simulado). Configure a chave em Configurações/variáveis de ambiente "
                           "para habilitar (haveibeenpwned.com/API/Key)."}
    req = urllib.request.Request(
        f"https://haveibeenpwned.com/api/v3/breachedaccount/{urllib.parse.quote(email)}",
        headers={"hibp-api-key": api_key, "User-Agent": "TF-Studio-CyberLab"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            breaches = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"findings": [], "raw": {"configured": True, "breaches": []},
                    "summary": f"Nenhum vazamento conhecido para {email}."}
        return {"findings": [], "raw": {"configured": True, "error": str(e)}, "summary": f"Erro HIBP: {e}"}
    names = [b.get("Name") for b in breaches]
    findings = [F("osint.email_breach", f"E-mail encontrado em vazamento: {n}", "medium",
                  evidence=n, impact="Credenciais/dados associados podem estar comprometidos.",
                  fix="Troque a senha usada nesse serviço e ative 2FA.", where=email)
                for n in names]
    return {"findings": findings, "raw": {"configured": True, "breaches": names},
            "summary": f"{len(names)} vazamento(s) encontrado(s) para {email}."}
