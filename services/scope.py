"""Escopo do Cyber Lab + SSRF Guard centralizado.

Este módulo é o ÚNICO ponto de decisão sobre "para onde o servidor pode
conectar". Todas as ferramentas que fazem requisição HTTP/DNS/TCP ou
analisam alvos passam por aqui (nenhuma tem lista própria de bloqueio).

Regras:
  * Toda ferramenta do Cyber Lab exige que o host esteja na lista de
    alvos autorizados (services/scope -> data/authorized_targets.json).
  * Faixas SEMPRE bloqueadas, mesmo se alguém tentar autorizar: metadata
    de nuvem (169.254.169.254, fd00:ec2::254, 100.100.100.200,
    192.0.0.192, 168.63.129.16), link-local, multicast, 0.0.0.0/8,
    broadcast, IPv6 não especificado e nomes de metadata.
  * Loopback/rede privada/reservada/CGNAT (IPv4 e IPv6, incluindo IPv4
    embutido em IPv6: ::ffff:a.b.c.d, ::a.b.c.d, NAT64, 6to4, Teredo) só
    passam no modo laboratório, se o IP/CIDR estiver explicitamente
    autorizado (ex.: "127.0.0.1", "192.168.0.0/24").
  * Ferramentas públicas (modo "public") nunca alcançam rede interna.
  * O host é resolvido UMA vez, validado, e a conexão é feita direto no
    IP validado (create_connection / PinnedHTTP*Connection): não há segunda
    resolução DNS, então DNS rebinding não abre janela de bypass.
  * Redirects são seguidos manualmente, revalidando a cada salto.
  * Timeouts: resolução DNS e conexão têm limite (clamp_timeout).
  * Toda negativa é registrada (logger "ssrf_guard" + audit_log da
    telemetria, tool="ssrf_guard").

Limitação conhecida: binários externos (nikto, gobuster, whatweb, ffuf,
testssl) resolvem o nome por conta própria; para eles só é possível
validar imediatamente antes de executar. Para alvos hostis, rode o Cyber
Lab dentro de uma rede isolada.
"""
import http.client
import ipaddress
import json
import logging
import socket
import ssl
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TARGETS_FILE = DATA_DIR / "authorized_targets.json"
_lock = threading.Lock()
log = logging.getLogger("ssrf_guard")

# Limites de tempo (segundos)
DEFAULT_TIMEOUT = 10.0
MAX_TIMEOUT = 30.0
DNS_TIMEOUT = 5.0
MAX_HOST_LEN = 253


def _nets(*items):
    return [ipaddress.ip_network(i) for i in items]


# Faixas que NENHUMA autorização libera (metadata de nuvem e afins).
ALWAYS_BLOCKED = _nets(
    "169.254.0.0/16",        # link-local + metadata AWS/GCP/Azure/OCI (169.254.169.254, 169.254.170.2)
    "fe80::/10",             # link-local IPv6
    "fd00:ec2::/32",         # metadata AWS IPv6
    "0.0.0.0/8",             # "this network" (0.0.0.0 costuma cair no localhost)
    "224.0.0.0/4",           # multicast
    "255.255.255.255/32",    # broadcast
    "ff00::/8",              # multicast IPv6
    "::/128",                # IPv6 não especificado
    "100.100.100.200/32",    # metadata Alibaba Cloud
    "192.0.0.192/32",        # metadata Oracle Cloud (legado)
    "168.63.129.16/32",      # Azure wireserver
)

# Nomes de metadata: bloqueados antes mesmo de resolver.
BLOCKED_HOSTNAMES = frozenset({
    "metadata", "metadata.google.internal", "metadata.goog",
    "instance-data", "instance-data.ec2.internal",
})

_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_TIER_RANK = {None: 0, "internal": 1, "always": 2}


class ScopeError(Exception):
    """Alvo fora do escopo autorizado (ou bloqueado pelo SSRF Guard)."""
    kind = "escopo"


# ------------------------------------------------------------ autorizações
def _load():
    try:
        if TARGETS_FILE.exists():
            data = json.loads(TARGETS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save(items):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TARGETS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def list_targets():
    return _load()


def normalize_entry(raw):
    raw = (raw or "").strip().lower()
    if not raw:
        raise ValueError("Informe um host, IP ou CIDR.")
    if "://" in raw:
        raw = urlparse(raw).hostname or ""
    raw = raw.split("/")[0] if "/" in raw and not _is_cidr(raw) else raw
    raw = raw.strip(".")
    if not raw:
        raise ValueError("Alvo inválido.")
    return raw


def _is_cidr(s):
    try:
        ipaddress.ip_network(s, strict=False)
        return "/" in s
    except ValueError:
        return False


def _check_cidr_size(entry):
    """Um CIDR 'catch-all' (0.0.0.0/0, ::/0...) anularia a proteção de rede
    interna do modo laboratório; exigimos um bloco de laboratório de verdade."""
    if "/" not in entry:
        return
    try:
        net = ipaddress.ip_network(entry, strict=False)
    except ValueError:
        return
    minimum = 8 if net.version == 4 else 16
    if net.prefixlen < minimum:
        raise ValueError(
            f"CIDR muito amplo ({entry}). Use um bloco de laboratório específico "
            f"(prefixo /{minimum} ou mais restrito)."
        )


def add_target(raw, note="", confirm_ownership=False, added_by="owner"):
    if not confirm_ownership:
        raise ValueError(
            "Confirme que este alvo é seu ou que você tem autorização por escrito para testá-lo."
        )
    entry = normalize_entry(raw)
    _check_cidr_size(entry)
    with _lock:
        items = _load()
        if any(i["target"] == entry for i in items):
            return next(i for i in items if i["target"] == entry)
        item = {
            "target": entry,
            "note": (note or "")[:200],
            "added": datetime.now(timezone.utc).isoformat(),
            "added_by": added_by,
        }
        items.append(item)
        _save(items)
        return item


def remove_target(raw):
    entry = normalize_entry(raw)
    with _lock:
        items = _load()
        new = [i for i in items if i["target"] != entry]
        _save(new)
        return len(new) != len(items)


# ------------------------------------------------------------ registro
def _log_block(kind, host, reason, mode, context, ips=None):
    """Registra tentativa bloqueada: logger + audit_log (telemetria).
    Nunca pode derrubar a requisição."""
    shown = [str(i) for i in (ips or [])]
    log.warning("SSRF bloqueado [%s] modo=%s ctx=%s host=%r ips=%s: %s",
                kind, mode, context or "-", host, shown, reason)
    try:
        from services import telemetry
        telemetry.log("system", "", "ssrf_guard", str(host)[:200], False, 0,
                      f"[{kind}] modo={mode} ctx={context or '-'} ips={','.join(shown)} :: {reason}")
    except Exception:
        pass


def _deny(kind, message, host, mode, context, ips=None):
    _log_block(kind, host, message, mode, context, ips)
    err = ScopeError(message)
    err.kind = kind
    raise err


# ------------------------------------------------------------ classificação de IP
def _parse_ip(text):
    text = str(text).split("%")[0]          # remove zone id (fe80::1%eth0)
    return ipaddress.ip_address(text)


def normalize_ip(ip):
    """::ffff:a.b.c.d vira o IPv4 a.b.c.d (mesma regra de autorização)."""
    if isinstance(ip, str):
        ip = _parse_ip(ip)
    if ip.version == 6 and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def _embedded_ipv4(ip):
    """IPv4 escondido em IPv6: compatível (::a.b.c.d), NAT64, 6to4, Teredo."""
    if ip.version != 6:
        return []
    out, n = [], int(ip)
    if n >> 32 == 0 and n > 1:                       # ::a.b.c.d
        out.append(ipaddress.IPv4Address(n & 0xFFFFFFFF))
    if ip in _NAT64:                                 # 64:ff9b::a.b.c.d
        out.append(ipaddress.IPv4Address(n & 0xFFFFFFFF))
    if ip.sixtofour is not None:
        out.append(ip.sixtofour)
    if ip.teredo is not None:
        out.extend(ip.teredo)
    return out


def _classify_one(ip):
    for net in ALWAYS_BLOCKED:
        if ip.version == net.version and ip in net:
            return "always", f"faixa sempre bloqueada ({net})"
    if ip.is_loopback:
        return "internal", "loopback"
    if ip.is_private or ip.is_reserved or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return "internal", "rede privada/reservada"
    if not ip.is_global:                              # CGNAT, benchmarking, 192.0.0.0/24...
        return "internal", "faixa não global (compartilhada/reservada)"
    return None, ""


def classify_ip(ip):
    """(tier, motivo). tier: None (público) | 'internal' | 'always'."""
    ip = normalize_ip(ip)
    # NAT64 (64:ff9b::/96) é legítimo em rede só-IPv6: vale o veredito do IPv4 embutido.
    best = (None, "") if ip in _NAT64 else _classify_one(ip)
    if ip.version == 6 and ip.ipv4_mapped is None and ip not in _NAT64 and int(ip) >> 32 == 0 and int(ip) > 1:
        best = max(best, ("internal", "IPv4-compatível (::a.b.c.d)"), key=lambda t: _TIER_RANK[t[0]])
    for emb in _embedded_ipv4(ip):
        tier, why = _classify_one(emb)
        if _TIER_RANK[tier] > _TIER_RANK[best[0]]:
            best = (tier, f"{why}; IPv4 embutido {emb} em {ip}")
    return best


# ------------------------------------------------------------ resolução
def _clean_host(host):
    h = (host or "").strip().lower()
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    h = h.strip(".")
    if not h:
        raise ScopeError("Host vazio.")
    if (len(h) > MAX_HOST_LEN or "\\" in h or "/" in h or "@" in h
            or any(ord(c) <= 32 or ord(c) == 127 for c in h)):
        _deny("host_invalido", "Host inválido.", repr(h[:80]), "-", "")
    return h


def clamp_timeout(timeout=None):
    if timeout is None or timeout is getattr(socket, "_GLOBAL_DEFAULT_TIMEOUT", object()):
        return DEFAULT_TIMEOUT
    try:
        t = float(timeout)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT
    return max(0.1, min(t, MAX_TIMEOUT))


def _resolve(host):
    """Resolve `host` (com timeout) e devolve IPs únicos, normalizados.
    Literais IP e 'localhost' não passam pelo DNS."""
    host = _clean_host(host)
    is_local_name = host == "localhost" or host.endswith(".localhost")
    try:
        return [normalize_ip(_parse_ip(host))]
    except ValueError:
        pass
    box = {}

    def work():
        try:
            box["infos"] = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        except Exception as e:                       # noqa: BLE001
            box["err"] = e

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(DNS_TIMEOUT)
    if t.is_alive():
        raise ScopeError(f"Timeout ao resolver '{host}' (> {DNS_TIMEOUT:.0f}s).")
    err = box.get("err")
    if err is not None and is_local_name:
        return [ipaddress.ip_address("127.0.0.1")]
    if isinstance(err, socket.gaierror):
        raise ScopeError(f"Não consegui resolver '{host}': {err}")
    if err is not None:
        raise ScopeError(f"Host inválido '{host}': {err}")
    ips = []
    for info in box["infos"]:
        ip = normalize_ip(_parse_ip(info[4][0]))
        if ip not in ips:
            ips.append(ip)
    if is_local_name:
        # 'localhost' é sempre loopback: respostas de DNS fora de loopback são descartadas
        ips = [ip for ip in ips if ip.is_loopback]
        if not ips:
            ips = [ipaddress.ip_address("127.0.0.1")]
    if not ips:
        raise ScopeError(f"Não consegui resolver '{host}': sem endereços.")
    return ips


def _entry_matches_host(entry, host):
    if entry.startswith("*."):
        base = entry[2:]
        return host == base or host.endswith("." + base)
    return host == entry


def _entry_covers_ip(entry, ip):
    try:
        if "/" in entry:
            return normalize_ip(ip) in ipaddress.ip_network(entry, strict=False)
        return normalize_ip(ip) == normalize_ip(ipaddress.ip_address(entry))
    except ValueError:
        return False


def _validate(host, mode, context):
    """Núcleo do guard: resolve UMA vez e valida. Retorna os IPs validados.
    mode='lab'    -> exige autorização; rede interna só com IP/CIDR autorizado.
    mode='public' -> sem lista de autorizados, mas NUNCA rede interna."""
    host = _clean_host(host)
    if host in BLOCKED_HOSTNAMES:
        _deny("metadata", f"'{host}' é um endpoint de metadata de nuvem (sempre bloqueado).",
              host, mode, context)
    ips = _resolve(host)
    tiers = [(ip,) + classify_ip(ip) for ip in ips]
    for ip, tier, why in tiers:
        if tier == "always":
            _deny("metadata_ou_link_local",
                  f"{ip} está em faixa sempre bloqueada (metadata/link-local/multicast): {why}.",
                  host, mode, context, ips)
    if mode == "public":
        for ip, tier, why in tiers:
            if tier == "internal":
                _deny("rede_interna",
                      "Esta ferramenta pública não acessa endereços internos. "
                      f"Use o Cyber Lab com alvo autorizado. ({ip}: {why})",
                      host, mode, context, ips)
        return ips
    entries = [i["target"] for i in _load()]
    by_name = any(_entry_matches_host(e, host) for e in entries)
    by_ip = all(any(_entry_covers_ip(e, ip) for e in entries) for ip in ips)
    if not (by_name or by_ip):
        _deny("nao_autorizado",
              f"'{host}' não está na lista de alvos autorizados. Um administrador "
              f"(owner) precisa adicioná-lo antes de qualquer análise.",
              host, mode, context, ips)
    # Mesmo autorizado por nome: se o nome aponta para rede interna, exige
    # autorização explícita do IP/CIDR (evita autorizar 'meusite.com' que
    # foi apontado para 127.0.0.1/10.x para atingir serviços internos).
    for ip, tier, why in tiers:
        if tier == "internal":
            if not any(_entry_covers_ip(e, ip) for e in entries):
                _deny("rede_interna",
                      f"'{host}' resolve para {ip} (rede interna: {why}). Autorize também esse "
                      f"IP/CIDR explicitamente se for um laboratório local.",
                      host, mode, context, ips)
            log.info("SSRF Guard: acesso interno liberado por autorização de laboratório: %s -> %s", host, ip)
    return ips


def check_host(host, context=""):
    """Valida `host` contra o escopo. Retorna a lista de IPs resolvidos.
    Levanta ScopeError se não autorizado."""
    return _validate(host, "lab", context)


def check_url(url, context=""):
    _reject_ambiguous(url, "lab", context)
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        _deny("esquema", "Só http/https são permitidos.", repr((p.scheme or "")[:20]), "lab", context)
    if not p.hostname:
        raise ScopeError("URL sem host.")
    return check_host(p.hostname, context=context)


def guard_public_fetch(url, context=""):
    """Para as ferramentas simples (Ferramentas > http-headers etc.) que já
    existiam: continuam abertas para sites públicos, mas NUNCA alcançam
    rede interna/metadata. Não exige lista de autorizados."""
    _reject_ambiguous(url, "public", context)
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ScopeError("URL inválida.")
    _validate(p.hostname, "public", context)
    return True


def check_name_only(host, context=""):
    """Autorização por NOME (sem resolver IP): usada por análises de DNS,
    onde o domínio pode nem ter registro A."""
    host = _clean_host(host) if (host or "").strip() else ""
    if not host:
        raise ScopeError("Domínio vazio.")
    if host in BLOCKED_HOSTNAMES:
        _deny("metadata", f"'{host}' é um endpoint de metadata de nuvem (sempre bloqueado).",
              host, "lab", context)
    entries = [i["target"] for i in _load()]
    if not any(_entry_matches_host(e, host) for e in entries):
        _deny("nao_autorizado", f"'{host}' não está na lista de alvos autorizados.",
              host, "lab", context)
    return True


# ------------------------------------------------------------ URLs ambíguas
def _reject_ambiguous(url, mode="lab", context=""):
    """Barra formas que parsers diferentes leem de jeitos diferentes
    (barra invertida, espaços/controle): base de vários bypass de SSRF."""
    u = url or ""
    if "\\" in u or any(ord(c) <= 32 or ord(c) == 127 for c in u.strip()):
        _deny("url_ambigua", "URL com caracteres ambíguos (barra invertida/espaço/controle) recusada.",
              repr(u[:80]), mode, context)


def canonical_url(url, context=""):
    """URL reconstruída só com o que foi validado (para repassar a binários
    externos em vez da string crua do usuário)."""
    _reject_ambiguous(url, "lab", context)
    p = urlparse((url or "").strip())
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ScopeError("URL inválida (use http:// ou https://).")
    if p.username or p.password:
        raise ScopeError("URL com credenciais embutidas não é aceita nesta ferramenta.")
    try:
        port = p.port
    except ValueError:
        raise ScopeError("Porta inválida na URL.")
    netloc = f"[{p.hostname}]" if ":" in p.hostname else p.hostname
    if port:
        netloc += f":{port}"
    return urlunparse((p.scheme, netloc, p.path or "/", "", p.query, ""))


# ------------------------------------------------------------ conexão com IP fixado
def create_connection(host, port, timeout=None, mode="lab", ips=None, context="tcp"):
    """Substitui socket.create_connection((host, port)) nas ferramentas.

    Resolve e valida UMA vez e conecta direto no IP validado (nenhum novo
    DNS => sem rebinding). `ips` permite reaproveitar o resultado de um
    check_host() já feito (ex.: varredura de várias portas)."""
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise ScopeError("Porta inválida.")
    if not 0 < port < 65536:
        raise ScopeError("Porta inválida.")
    timeout = clamp_timeout(timeout)
    if ips is None:
        ips = _validate(host, mode, context)
    else:
        ips = [normalize_ip(i) for i in ips]
        for ip in ips:
            tier, why = classify_ip(ip)
            if tier == "always":
                _deny("metadata_ou_link_local", f"{ip} está em faixa sempre bloqueada: {why}.",
                      host, mode, context, ips)
    deadline = time.monotonic() + timeout
    last = None
    for ip in ips:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            sock = socket.create_connection((str(ip), port), timeout=remaining)
        except OSError as e:
            last = e
            continue
        try:
            peer = normalize_ip(_parse_ip(sock.getpeername()[0]))
        except Exception:                            # noqa: BLE001
            peer = ip
        if peer != ip:
            sock.close()
            _deny("rebinding", f"Conexão foi para {peer} e não para o IP validado {ip}.",
                  host, mode, context, ips)
        return sock
    raise last or socket.timeout("timed out")


class PinnedHTTPConnection(http.client.HTTPConnection):
    """http.client que conecta no IP validado pelo guard (sem 2ª resolução)."""

    def __init__(self, *args, mode="lab", **kwargs):
        super().__init__(*args, **kwargs)
        self._ssrf_mode = mode

    def connect(self):
        self.sock = create_connection(self.host, self.port, self.timeout,
                                      mode=self._ssrf_mode, context="http")


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Idem para HTTPS: TLS/SNI continuam usando o NOME do host."""

    def __init__(self, *args, mode="lab", **kwargs):
        super().__init__(*args, **kwargs)
        self._ssrf_mode = mode

    def connect(self):
        sock = create_connection(self.host, self.port, self.timeout,
                                 mode=self._ssrf_mode, context="https")
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise
