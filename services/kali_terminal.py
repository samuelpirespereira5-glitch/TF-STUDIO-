"""Terminal web do Kali: interface de comandos limitada ao Tool Registry.

Não existe shell arbitrário aqui. Cada comando é traduzido para uma ferramenta
já registrada no projeto, mantendo permissões, escopo autorizado, SSRF Guard,
timeouts e sandbox do Tool Adapter.
"""
import shlex
from services.tool_registry import execute
from services import permissions, tool_adapter

COMMANDS = {
    "nmap": {"tool": "external_nmap", "param": "target", "help": "nmap <alvo-autorizado>"},
    "gobuster": {"tool": "external_gobuster", "param": "target", "help": "gobuster <url-autorizada>"},
    "nikto": {"tool": "external_nikto", "param": "target", "help": "nikto <url-autorizada>"},
    "ffuf": {"tool": "external_ffuf", "param": "target", "help": "ffuf <url-autorizada>"},
    "whatweb": {"tool": "external_whatweb", "param": "target", "help": "whatweb <alvo-autorizado>"},
    "testssl": {"tool": "external_testssl", "param": "target", "help": "testssl <host-autorizado>"},
    "dns": {"tool": "dns_analyzer", "param": "target", "help": "dns <dominio-autorizado>"},
    "tls": {"tool": "tls_analyzer", "param": "target", "help": "tls <host-autorizado>"},
    "ports": {"tool": "port_inventory", "param": "target", "help": "ports <host-autorizado>"},
    "whois": {"tool": "osint_whois", "param": "domain", "help": "whois <dominio-autorizado>"},
    "web": {"tool": "web_analyzer", "param": "target", "help": "web <url-autorizada>"},
    "subdomains": {"tool": "subdomain_discovery", "param": "target", "help": "subdomains <dominio-autorizado>"},
    "links": {"tool": "link_checker", "param": "target", "help": "links <url-autorizada>"},
    "secrets": {"tool": "secret_scanner", "param": "text", "help": "secrets <texto-ou-codigo>"},
    "code": {"tool": "code_analyzer", "param": "text", "help": "code <codigo>"},
    "deps": {"tool": "dependency_analyzer", "param": "text", "help": "deps <requirements-ou-package-json>"},
    "malware": {"tool": "malware_pattern_scan", "param": "text", "help": "malware <texto-ou-arquivo>"},
    "mitre": {"tool": "mitre_lookup", "param": "query", "help": "mitre <tecnica-ou-palavra-chave>"},
    "hash": {"tool": "hash_identifier", "param": "value", "help": "hash <hash>"},
    "cidr": {"tool": "cidr_calculator", "param": "cidr", "help": "cidr <rede/CIDR>"},
    "headers": {"tool": "headers_audit", "param": "text", "help": "headers <cabecalhos-HTTP>"},
    "csp": {"tool": "csp_audit", "param": "text", "help": "csp <politica-CSP>"},
    "cookies": {"tool": "cookie_security_audit", "param": "text", "help": "cookies <set-cookie-ou-headers>"},
    "docker": {"tool": "dockerfile_audit", "param": "text", "help": "docker <Dockerfile>"},
    "ci": {"tool": "ci_security_audit", "param": "text", "help": "ci <workflow-GitHub-Actions>"},
    "api-audit": {"tool": "api_security_audit", "param": "text", "help": "api-audit <trecho-da-API>"},
}


def help_text():
    lines = [
        "TRISTAN THORNE / KALI LAB TERMINAL",
        "Modo seguro: somente ferramentas registradas e alvos autorizados.",
        "",
        "Comandos:",
        "  help                 mostra esta ajuda",
        "  clear                limpa o terminal",
        "  status               mostra ferramentas externas detectadas",
        "  tools                lista comandos disponíveis",
    ]
    lines.extend(f"  {v['help']}" for v in COMMANDS.values())
    lines.append("")
    lines.append("Shell arbitrário, apt, bash, python e comandos fora da allowlist não são executados pelo servidor.")
    return "\n".join(lines)


def _result_text(result):
    if not result.get("ok"):
        return f"[ERRO] {result.get('error', 'falha desconhecida')}"
    parts = [f"[OK] {result.get('name', result.get('tool', 'tool'))}", result.get("summary", "execução concluída")]
    risk = result.get("risk")
    if risk:
        parts.append(f"Risco: {risk}")
    findings = result.get("findings") or []
    if findings:
        parts.append(f"Achados: {len(findings)}")
        for f in findings[:20]:
            sev = str(f.get("severity", "info")).upper()
            title = str(f.get("title", "achado"))[:180]
            parts.append(f"  [{sev}] {title}")
    raw = result.get("raw") or {}
    stdout = str(raw.get("stdout", "")).strip()
    if stdout:
        parts.append("\n" + stdout[-6000:])
    text = "\n".join(parts)
    return text[:10000]


def run(command, role, session_id=""):
    if not permissions.has_cap("cyber_advanced", role):
        return {"ok": False, "error": "Terminal Kali exige a capacidade cyber_advanced."}
    command = (command or "").strip()
    if not command:
        return {"ok": True, "text": help_text()}
    try:
        argv = shlex.split(command, posix=True)
    except ValueError as exc:
        return {"ok": False, "error": f"Comando inválido: {exc}"}
    if len(argv) > 4:
        return {"ok": False, "error": "Comando excede o formato permitido. Use help."}
    name = argv[0].lower()
    if name == "help":
        return {"ok": True, "text": help_text()}
    if name == "clear":
        return {"ok": True, "clear": True, "text": ""}
    if name == "tools":
        return {"ok": True, "text": "\n".join(f"{k:10} → {v['tool']}" for k, v in COMMANDS.items())}
    if name == "status":
        st = tool_adapter.status_all()
        rows = []
        for item in st:
            mark = "OK" if item.get("installed") else "--"
            version = item.get("version") or "não instalado"
            rows.append(f"[{mark}] {item['label']}: {version}")
        return {"ok": True, "text": "\n".join(rows)}
    spec = COMMANDS.get(name)
    if not spec:
        return {"ok": False, "error": f"Comando não permitido: {name}. Use help."}
    if len(argv) != 2 or not argv[1].strip():
        return {"ok": False, "error": f"Uso: {spec['help']}"}
    target = argv[1].strip()
    if len(target) > 253:
        return {"ok": False, "error": "Alvo muito longo."}
    params = {spec["param"]: target}
    result = execute(spec["tool"], params, role, {"session_id": session_id, "target": target})
    return {**result, "text": _result_text(result)}
