"""Port/Service Inventory: TCP connect em lista pequena de portas comuns,
SOMENTE em alvo autorizado. Sem varredura agressiva nem exploração."""
import socket
from concurrent.futures import ThreadPoolExecutor

from services import scope
from services.evidence import make_finding as F

COMMON = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 80: "http", 110: "pop3",
    143: "imap", 443: "https", 445: "smb", 993: "imaps", 995: "pop3s", 1433: "mssql",
    3306: "mysql", 3389: "rdp", 5432: "postgres", 5900: "vnc", 6379: "redis",
    8080: "http-alt", 8443: "https-alt", 9200: "elasticsearch", 27017: "mongodb",
}
RISKY = {
    23: ("high", "Telnet transmite tudo em texto puro.", "Desative Telnet; use SSH."),
    21: ("medium", "FTP transmite credenciais em texto puro.", "Use SFTP/FTPS."),
    445: ("high", "SMB exposto aumenta superfície de ataque.", "Restrinja por firewall/VPN."),
    3389: ("high", "RDP exposto é alvo comum de força bruta.", "Coloque atrás de VPN/NLA."),
    5900: ("high", "VNC costuma ter autenticação fraca.", "Restrinja por VPN."),
    1433: ("high", "Banco de dados acessível pela rede.", "Restrinja ao segmento da aplicação."),
    3306: ("high", "Banco de dados acessível pela rede.", "Restrinja ao segmento da aplicação."),
    5432: ("high", "Banco de dados acessível pela rede.", "Restrinja ao segmento da aplicação."),
    6379: ("critical", "Redis exposto geralmente sem autenticação.", "Bind em localhost + requirepass."),
    27017: ("critical", "MongoDB exposto pode não exigir autenticação.", "Habilite auth e restrinja a rede."),
    9200: ("high", "Elasticsearch exposto costuma vazar dados.", "Restrinja e habilite autenticação."),
}


def _probe(host, port, timeout=1.5, ips=None):
    try:
        with scope.create_connection(host, port, timeout=timeout, mode="lab", ips=ips,
                                     context="port_scan") as s:
            s.settimeout(1.0)
            banner = ""
            try:
                if port in (80, 8080):
                    s.sendall(b"HEAD / HTTP/1.0\r\n\r\n")
                banner = s.recv(120).decode(errors="replace").strip().split("\n")[0][:100]
            except Exception:
                pass
            return port, True, banner
    except Exception:
        return port, False, ""


def run_port_inventory(target, ports=None):
    host = (target or "").strip().replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    ips = scope.check_host(host)   # resolve/valida UMA vez; todas as sondas usam esses IPs
    ports = [p for p in (ports or COMMON) if isinstance(p, int) and 0 < p < 65536][:64]
    with ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(lambda p: _probe(host, p, ips=ips), ports))
    open_ports = [{"port": p, "service": COMMON.get(p, "desconhecido"), "banner": b}
                  for p, ok, b in results if ok]
    findings = []
    for o in open_ports:
        if o["port"] in RISKY:
            sev, impact, fix = RISKY[o["port"]]
            findings.append(F(f"ports.risky.{o['port']}", f"Porta {o['port']} ({o['service']}) exposta", sev,
                              evidence=f"{host}:{o['port']} aberta. {o['banner']}", impact=impact,
                              fix=fix, where=f"port:{o['port']}"))
    return {"findings": findings, "raw": {"host": host, "open": open_ports, "tested": len(ports)}}
