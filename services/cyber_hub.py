"""Hub de Cybersecurity/Pentest — catálogo por categoria.

Não duplica nada do Cyber Lab: é uma camada de REFERÊNCIA (o que é cada
categoria/ferramenta de mercado, para que serve, link oficial) que aponta
para as ferramentas que JÁ existem no `tool_registry` (REGISTRY) quando
elas cobrem aquele item, e mostra "não integrado — referência" quando é
uma ferramenta comercial/externa que não roda embutida no app.

Tudo aqui é 100% educacional/referência: nenhum link ou item deste
catálogo executa nada sozinho. Execução real acontece só através das
ferramentas já registradas no Cyber Lab (com escopo autorizado).
"""

# tool_id: liga o card a uma ferramenta já registrada em builtin_tools.py
# (o link "Abrir no Cyber Lab" só aparece quando o id existe no REGISTRY).
CATALOG = {
    "Pentest / Offensive": [
        {"name": "Nmap", "desc": "Varredura de portas e serviços de rede.",
         "url": "https://nmap.org/", "tool_id": "external_nmap"},
        {"name": "Wireshark", "desc": "Captura e análise de tráfego de rede (pacotes).",
         "url": "https://www.wireshark.org/", "tool_id": "external_wireshark"},
        {"name": "Burp Suite", "desc": "Proxy de interceptação e testes de segurança web.",
         "url": "https://portswigger.net/burp", "tool_id": "external_burpsuite"},
        {"name": "OWASP ZAP", "desc": "Scanner de vulnerabilidades web open-source.",
         "url": "https://www.zaproxy.org/", "tool_id": "external_zap"},
        {"name": "Gobuster", "desc": "Brute-force de diretórios, DNS e vhosts.",
         "url": "https://github.com/OJ/gobuster", "tool_id": "external_gobuster"},
        {"name": "Nikto", "desc": "Scanner de vulnerabilidades em servidores web.",
         "url": "https://cirt.net/Nikto2", "tool_id": "external_nikto"},
        {"name": "Nessus", "desc": "Scanner de vulnerabilidades comercial (Tenable).",
         "url": "https://www.tenable.com/products/nessus"},
        {"name": "OpenVAS / Greenbone", "desc": "Scanner de vulnerabilidades open-source.",
         "url": "https://www.openvas.org/"},
        {"name": "Ghidra", "desc": "Engenharia reversa e análise de binários (NSA).",
         "url": "https://ghidra-sre.org/"},
        {"name": "Autopsy", "desc": "Plataforma de forense digital (baseada no Sleuth Kit).",
         "url": "https://www.autopsy.com/"},
        {"name": "OSINT / WHOIS", "desc": "Coleta de informações públicas sobre alvo/domínio.",
         "url": "https://www.kali.org/tools/whois/", "tool_id": "osint_whois"},
        {"name": "Subdomain Discovery", "desc": "Descoberta de subdomínios de um alvo autorizado.",
         "tool_id": "subdomain_discovery"},
    ],
    "SOC / Defense": [
        {"name": "SIEM", "desc": "Security Information and Event Management — correlação de logs/eventos.",
         "url": "https://en.wikipedia.org/wiki/Security_information_and_event_management"},
        {"name": "SOAR", "desc": "Security Orchestration, Automation and Response.",
         "url": "https://en.wikipedia.org/wiki/Security_orchestration"},
        {"name": "EDR", "desc": "Endpoint Detection and Response.",
         "url": "https://en.wikipedia.org/wiki/Endpoint_detection_and_response"},
        {"name": "XDR", "desc": "Extended Detection and Response (multi-fonte)."},
        {"name": "NDR", "desc": "Network Detection and Response."},
        {"name": "IDS", "desc": "Intrusion Detection System."},
        {"name": "IPS", "desc": "Intrusion Prevention System."},
        {"name": "HIDS", "desc": "Host-based Intrusion Detection System."},
        {"name": "NIDS", "desc": "Network-based Intrusion Detection System."},
        {"name": "WAF", "desc": "Web Application Firewall.", "tool_id": "waf_generate"},
        {"name": "UEBA", "desc": "User and Entity Behavior Analytics."},
        {"name": "TIP", "desc": "Threat Intelligence Platform.", "tool_id": "mitre_lookup"},
        {"name": "DRP", "desc": "Digital Risk Protection."},
        {"name": "BCDR", "desc": "Business Continuity & Disaster Recovery.",
         "tool_id": "ir_playbook"},
    ],
    "Application Security": [
        {"name": "SAST", "desc": "Static Application Security Testing (análise de código-fonte).",
         "tool_id": "code_analyzer"},
        {"name": "DAST", "desc": "Dynamic Application Security Testing (app em execução).",
         "tool_id": "web_analyzer"},
        {"name": "IAST", "desc": "Interactive Application Security Testing (SAST+DAST em runtime)."},
        {"name": "RASP", "desc": "Runtime Application Self-Protection."},
    ],
    "Cloud": [
        {"name": "CSPM", "desc": "Cloud Security Posture Management."},
        {"name": "CWPP", "desc": "Cloud Workload Protection Platform."},
        {"name": "CIEM", "desc": "Cloud Infrastructure Entitlement Management."},
        {"name": "CNAPP", "desc": "Cloud-Native Application Protection Platform."},
        {"name": "CASB", "desc": "Cloud Access Security Broker."},
        {"name": "DLP", "desc": "Data Loss Prevention.", "tool_id": "secret_scanner"},
        {"name": "SPCM", "desc": "Security Posture & Compliance Management."},
    ],
    "Identity / Access": [
        {"name": "IAM", "desc": "Identity and Access Management."},
        {"name": "PAM", "desc": "Privileged Access Management."},
        {"name": "MFA", "desc": "Multi-Factor Authentication."},
        {"name": "NAC", "desc": "Network Access Control."},
        {"name": "VPN", "desc": "Virtual Private Network."},
        {"name": "ZTNA", "desc": "Zero Trust Network Access."},
    ],
    "Network": [
        {"name": "UTM", "desc": "Unified Threat Management."},
        {"name": "NGFW", "desc": "Next-Generation Firewall."},
        {"name": "NTA", "desc": "Network Traffic Analysis."},
        {"name": "SASE", "desc": "Secure Access Service Edge."},
        {"name": "SSE", "desc": "Security Service Edge."},
        {"name": "DNS Analyzer", "desc": "Análise de registros DNS de um alvo autorizado.",
         "tool_id": "dns_analyzer"},
        {"name": "Port/Service Inventory", "desc": "Inventário de portas e serviços expostos.",
         "tool_id": "port_inventory"},
        {"name": "TLS/HTTPS Analyzer", "desc": "Auditoria de certificado e configuração TLS.",
         "tool_id": "tls_analyzer"},
    ],
    "Endpoint": [
        {"name": "AV", "desc": "Antivírus / anti-malware."},
        {"name": "EMM", "desc": "Enterprise Mobility Management."},
        {"name": "MDM", "desc": "Mobile Device Management."},
    ],
    "Outras áreas": [
        {"name": "Linux", "desc": "Fundamentos e hardening de sistemas Linux.",
         "tool_id": "config_auditor"},
        {"name": "Windows", "desc": "Fundamentos e hardening de sistemas Windows."},
        {"name": "Criptografia", "desc": "Hashes, cifragem, identificação de algoritmos.",
         "tool_id": "hash_identifier"},
        {"name": "Malware Analysis", "desc": "Identificação de padrões maliciosos em código/arquivos.",
         "tool_id": "malware_pattern_scan"},
        {"name": "Digital Forensics", "desc": "Análise de logs e evidências.",
         "tool_id": "log_analyzer"},
        {"name": "CTF", "desc": "Desafios práticos de secure coding.",
         "tool_id": "ctf_challenge"},
        {"name": "Engenharia Reversa", "desc": "Ghidra e ferramentas de análise binária.",
         "url": "https://ghidra-sre.org/"},
        {"name": "Vulnerabilidades / OWASP Top 10", "desc": "Scanner e guia OWASP Top 10.",
         "tool_id": "owasp_scanner"},
        {"name": "Segurança Web", "desc": "Headers, CORS, CSP, cookies.", "tool_id": "web_analyzer"},
    ],
}


def all_tool_ids():
    return {item["tool_id"] for items in CATALOG.values() for item in items if item.get("tool_id")}


def catalog_public(registry):
    """Retorna o catálogo já anotado com se o tool_id existe de fato no registry."""
    out = {}
    for cat, items in CATALOG.items():
        out[cat] = [
            {**it, "integrated": bool(it.get("tool_id") and registry.get(it["tool_id"]))}
            for it in items
        ]
    # Central de Ferramentas (categorias oficiais v34)
    try:
        from services.cyber.central_categories import hub_catalog, list_categories
        central = hub_catalog()
        central_cats = {}
        for c in list_categories():
            tools = []
            for tid in c["tool_ids"]:
                t = registry.get(tid) if registry else None
                tools.append({
                    "name": t.name if t else tid,
                    "desc": (t.description if t else "Ferramenta planejada / em expansão"),
                    "tool_id": tid,
                    "integrated": bool(t),
                })
            central_cats[f"{c['icon']} {c['name']}"] = tools
        out = {**central_cats, **out}
        out["_meta"] = {
            "policy_notes": central.get("policy_notes", []),
            "central_categories": list_categories(),
        }
    except Exception:
        pass
    return out
