"""TLS/HTTPS Analyzer: certificado, validade, protocolo, hostname."""
import socket
import ssl
from datetime import datetime, timezone

from services import scope
from services.evidence import make_finding as F


def _handshake(host, port, min_v=None, max_v=None, verify=True):
    ctx = ssl.create_default_context() if verify else ssl._create_unverified_context()
    if min_v is not None:
        ctx.minimum_version = min_v
    if max_v is not None:
        ctx.maximum_version = max_v
    with scope.create_connection(host, port, timeout=8, mode="lab", context="tls") as s:
        with ctx.wrap_socket(s, server_hostname=host) as ss:
            return ss.version(), ss.cipher(), ss.getpeercert()


def run_tls_analysis(target, port=443):
    host = (target or "").strip().replace("https://", "").replace("http://", "").split("/")[0]
    host = host.split(":")[0]
    scope.check_host(host)
    findings, raw = [], {"host": host, "port": port}
    try:
        version, cipher, cert = _handshake(host, port)
    except ssl.SSLCertVerificationError as e:
        findings.append(F("tls.cert_invalid", "Certificado TLS inválido", "high",
                          evidence=str(e)[:200],
                          impact="Navegadores mostram alerta; conexão pode ser interceptada.",
                          fix="Instale um certificado válido, com cadeia completa e nome correto.",
                          where="cert"))
        try:
            version, cipher, cert = _handshake(host, port, verify=False)
            cert = cert or {}
        except Exception as e2:
            raw["error"] = str(e2)
            return {"findings": findings, "raw": raw}
    except Exception as e:
        raw["error"] = str(e)
        findings.append(F("tls.unavailable", f"TLS indisponível na porta {port}", "medium",
                          evidence=str(e)[:200], impact="O serviço não oferece HTTPS.",
                          fix="Habilite HTTPS.", where=f"port:{port}"))
        return {"findings": findings, "raw": raw}

    raw.update({"protocol": version, "cipher": cipher[0] if cipher else None})
    if cert:
        not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days = (not_after - datetime.now(timezone.utc)).days
        issuer = dict(x[0] for x in cert.get("issuer", []))
        subject = dict(x[0] for x in cert.get("subject", []))
        sans = [v for k, v in cert.get("subjectAltName", []) if k == "DNS"]
        raw.update({"expires": not_after.isoformat(), "days_left": days,
                    "issuer": issuer.get("organizationName", issuer.get("commonName")),
                    "subject": subject.get("commonName"), "san": sans})
        if issuer == subject:
            findings.append(F("tls.self_signed", "Certificado autoassinado", "high",
                              evidence=f"Issuer == Subject ({subject.get('commonName')}).",
                              impact="Navegadores e clientes HTTP não confiam nele por padrão; "
                                     "facilita ataques MITM se o usuário aprender a ignorar o alerta.",
                              fix="Use um certificado de uma CA confiável (Let's Encrypt é gratuito e automatizável).",
                              where="cert.issuer"))
        if days < 0:
            findings.append(F("tls.expired", "Certificado expirado", "critical",
                              evidence=f"Expirou há {-days} dias.", impact="Conexões falham/alertam.",
                              fix="Renove o certificado (Let's Encrypt/ACME automatiza).", where="cert"))
        elif days < 14:
            findings.append(F("tls.expiring", "Certificado expira em breve", "high",
                              evidence=f"Faltam {days} dias.", impact="Risco de indisponibilidade.",
                              fix="Renove agora e automatize a renovação.", where="cert"))
        elif days < 30:
            findings.append(F("tls.expiring_soon", "Certificado expira em menos de 30 dias", "low",
                              evidence=f"Faltam {days} dias.", impact="Renovação deve ser planejada.",
                              fix="Automatize a renovação.", where="cert"))
    if version in ("TLSv1", "TLSv1.1"):
        findings.append(F("tls.old_protocol", f"Protocolo obsoleto negociado ({version})", "high",
                          evidence=version, impact="Vulnerável a ataques conhecidos.",
                          fix="Desative TLS 1.0/1.1; exija TLS 1.2+.", where="protocol"))
    # o servidor ainda aceita TLS 1.0/1.1 se forçarmos?
    legacy = []
    for label, v in (("TLSv1.0", ssl.TLSVersion.TLSv1), ("TLSv1.1", ssl.TLSVersion.TLSv1_1)):
        try:
            _handshake(host, port, min_v=v, max_v=v, verify=False)
            legacy.append(label)
        except Exception:
            pass  # recusado (bom) ou cliente local sem suporte (inconclusivo)
    raw["legacy_accepted"] = legacy
    if legacy:
        findings.append(F("tls.legacy_accepted", "Servidor aceita protocolos TLS legados", "medium",
                          evidence=", ".join(legacy), impact="Permite downgrade para versões fracas.",
                          fix="Configure ssl_protocols TLSv1.2 TLSv1.3 (ou equivalente).",
                          where="protocol:legacy"))
    # cifra negociada é fraca/exportável/nula?
    cipher_name = (cipher[0] if cipher else "") or ""
    weak_markers = ("RC4", "DES", "3DES", "NULL", "EXPORT", "MD5", "anon")
    hit = [m for m in weak_markers if m in cipher_name.upper()]
    if hit:
        findings.append(F("tls.weak_cipher", f"Cifra fraca negociada ({cipher_name})", "high",
                          evidence=cipher_name, impact="Cifra vulnerável a quebra/ataques conhecidos.",
                          fix="Desative suítes fracas no servidor (RC4/DES/3DES/NULL/export/MD5).",
                          where="cipher"))
    return {"findings": findings, "raw": raw}
