"""DNS Analyzer (resolvedor UDP em stdlib, sem dependências extras).
Registros A/AAAA/NS/MX/TXT/CNAME + SPF, DMARC, CAA e wildcard."""
import os
import random
import socket
import struct

from services import scope
from services.evidence import make_finding as F

QTYPES = {"A": 1, "NS": 2, "CNAME": 5, "MX": 15, "TXT": 16, "AAAA": 28, "CAA": 257}


def _system_resolver():
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                if line.startswith("nameserver"):
                    return line.split()[1]
    except Exception:
        pass
    return os.getenv("DNS_RESOLVER", "1.1.1.1")


def _encode(name):
    out = b""
    for label in name.strip(".").split("."):
        out += bytes([len(label)]) + label.encode()
    return out + b"\x00"


def _read_name(buf, off):
    labels, jumped, end = [], False, off
    while True:
        ln = buf[off]
        if ln == 0:
            off += 1
            break
        if ln & 0xC0 == 0xC0:
            ptr = ((ln & 0x3F) << 8) | buf[off + 1]
            if not jumped:
                end = off + 2
            off, jumped = ptr, True
            continue
        off += 1
        labels.append(buf[off:off + ln].decode(errors="replace"))
        off += ln
    return ".".join(labels), (end if jumped else off)


def query(name, qtype, server=None, timeout=4):
    server = server or _system_resolver()
    tid = random.randint(0, 65535)
    pkt = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0) + _encode(name) + struct.pack(">HH", QTYPES[qtype], 1)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(pkt, (server, 53))
        data, _ = s.recvfrom(4096)
    finally:
        s.close()
    _, flags, qd, an, _, _ = struct.unpack(">HHHHHH", data[:12])
    rcode = flags & 0xF
    off = 12
    for _ in range(qd):
        _, off = _read_name(data, off)
        off += 4
    answers = []
    for _ in range(an):
        _, off = _read_name(data, off)
        rtype, _, ttl, rdlen = struct.unpack(">HHIH", data[off:off + 10])
        off += 10
        rd = data[off:off + rdlen]
        val = None
        if rtype == 1 and rdlen == 4:
            val = socket.inet_ntoa(rd)
        elif rtype == 28 and rdlen == 16:
            val = socket.inet_ntop(socket.AF_INET6, rd)
        elif rtype in (2, 5):
            val, _ = _read_name(data, off)
        elif rtype == 15:
            pref = struct.unpack(">H", rd[:2])[0]
            n, _ = _read_name(data, off + 2)
            val = f"{pref} {n}"
        elif rtype == 16:
            parts, i = [], 0
            while i < len(rd):
                l = rd[i]; parts.append(rd[i + 1:i + 1 + l].decode(errors="replace")); i += 1 + l
            val = "".join(parts)
        elif rtype == 257 and rdlen >= 2:
            tl = rd[1]
            val = f"{rd[0]} {rd[2:2+tl].decode(errors='replace')} {rd[2+tl:].decode(errors='replace')}"
        if val is not None:
            answers.append({"type": rtype, "value": val, "ttl": ttl})
        off += rdlen
    return rcode, answers


def run_dns_analysis(target):
    domain = (target or "").strip().lower().replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    scope.check_name_only(domain)
    records, findings = {}, []
    for t in ("A", "AAAA", "NS", "MX", "TXT", "CAA", "CNAME"):
        try:
            _, ans = query(domain, t)
            records[t] = [a["value"] for a in ans if a["type"] == QTYPES[t]]
        except Exception as e:
            records[t] = []
            records.setdefault("_errors", {})[t] = str(e)[:80]
    txt = records.get("TXT", [])
    spf = [t for t in txt if t.lower().startswith("v=spf1")]
    if records.get("MX") and not spf:
        findings.append(F("dns.no_spf", "Domínio com e-mail (MX) sem SPF", "medium",
                          evidence=f"MX: {records['MX']}", impact="Facilita falsificação de remetente (spoofing).",
                          fix='Publique TXT "v=spf1 include:<provedor> -all".', where="txt:spf"))
    elif spf and spf[0].rstrip().endswith("+all"):
        findings.append(F("dns.spf_pass_all", "SPF permite qualquer remetente (+all)", "high",
                          evidence=spf[0], impact="SPF não protege contra spoofing.",
                          fix="Troque +all por -all (ou ~all durante a transição).", where="txt:spf"))
    try:
        _, dm = query("_dmarc." + domain, "TXT")
        dmarc = [a["value"] for a in dm if a["type"] == 16 and a["value"].lower().startswith("v=dmarc1")]
    except Exception:
        dmarc = []
    records["DMARC"] = dmarc
    if records.get("MX") and not dmarc:
        findings.append(F("dns.no_dmarc", "Sem política DMARC", "medium",
                          evidence=f"_dmarc.{domain} não tem registro DMARC.",
                          impact="Sem DMARC, spoofing do domínio não é rejeitado/monitorado.",
                          fix='Publique _dmarc TXT "v=DMARC1; p=none; rua=mailto:..." e evolua para quarantine/reject.',
                          where="txt:dmarc"))
    elif dmarc and "p=none" in dmarc[0].replace(" ", "").lower():
        findings.append(F("dns.dmarc_none", "DMARC em modo monitoramento (p=none)", "low",
                          evidence=dmarc[0], impact="Não bloqueia e-mails falsificados.",
                          fix="Evolua para p=quarantine e depois p=reject.", where="txt:dmarc"))
    if not records.get("CAA") and records.get("A"):
        findings.append(F("dns.no_caa", "Sem registro CAA", "info",
                          evidence="Nenhum CAA encontrado.", impact="Qualquer CA pode emitir certificado.",
                          fix='Adicione CAA restringindo as CAs (ex: 0 issue "letsencrypt.org").', where="caa"))
    if len(records.get("NS", [])) == 1:
        findings.append(F("dns.single_ns", "Apenas um servidor de nomes", "low",
                          evidence=str(records["NS"]), impact="Ponto único de falha.",
                          fix="Use pelo menos 2 NS em redes distintas.", where="ns"))
    try:
        _, wild = query("tfstudio-nao-existe-" + str(random.randint(10**6, 10**7)) + "." + domain, "A")
        records["wildcard"] = bool(wild)
        if wild:
            findings.append(F("dns.wildcard", "DNS wildcard ativo", "info",
                              evidence="Subdomínio inexistente resolveu.",
                              impact="Dificulta detectar subdomínios órfãos.", fix="Confirme que é intencional.",
                              where="wildcard"))
    except Exception:
        records["wildcard"] = None
    return {"findings": findings, "raw": records}


COMMON_SUBS = ["www", "mail", "api", "dev", "staging", "test", "admin", "app", "cdn", "static",
               "blog", "shop", "portal", "vpn", "git", "ftp", "smtp", "ns1", "ns2"]


def discover_subdomains(target, wordlist=None):
    """Descoberta por dicionário — só em domínio autorizado."""
    domain = (target or "").strip().lower().split("/")[0]
    scope.check_name_only(domain)
    found = []
    for sub in (wordlist or COMMON_SUBS)[:200]:
        fq = f"{sub}.{domain}"
        try:
            _, ans = query(fq, "A")
            ips = [a["value"] for a in ans if a["type"] == 1]
            cn = [a["value"] for a in ans if a["type"] == 5]
            if ips or cn:
                found.append({"name": fq, "ips": ips, "cname": cn})
        except Exception:
            continue
    findings = []
    for f in found:
        if any(k in f["name"].split(".")[0] for k in ("dev", "staging", "test", "admin", "git")):
            findings.append(F("subdomain.sensitive", f"Subdomínio sensível exposto: {f['name']}", "low",
                              evidence=f"{f['name']} → {f['ips'] or f['cname']}",
                              impact="Ambientes internos/de teste costumam ter menos proteção.",
                              fix="Restrinja por VPN/IP allowlist ou remova do DNS público.", where=f["name"]))
    return {"findings": findings, "raw": {"subdomains": found, "tested": len(wordlist or COMMON_SUBS)}}
