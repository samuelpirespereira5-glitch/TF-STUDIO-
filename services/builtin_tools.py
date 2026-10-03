"""Registra as ferramentas embutidas. Cada handler chama código REAL
(nenhuma ferramenta finge executar)."""
from services import basic_net, tool_adapter, central_tools
from services.cyber import web, tls, dns, ports, local, owasp, osint, payloads
from services.tool_registry import REGISTRY as R

T = {"target": {"type": "string", "required": True, "description": "URL, domínio ou IP autorizado"}}
TXT = {"text": {"type": "string", "required": True, "description": "Conteúdo a analisar"},
       "filename": {"type": "string", "description": "Nome do arquivo (opcional)"}}


def _web(p, ctx):
    r = web.run_web_analysis(p["target"])
    raw = r["raw"]
    r["summary"] = (f"HTTP {raw['status']} em {raw['response_ms']} ms · {len(r['findings'])} achado(s) · "
                    f"tecnologias: {', '.join(raw['technologies']) or 'nenhuma identificada'}")
    return r


def _tls(p, ctx):
    r = tls.run_tls_analysis(p["target"])
    raw = r["raw"]
    if raw.get("protocol"):
        r["summary"] = (f"{raw['protocol']} · expira em {raw.get('days_left', '?')} dias · "
                        f"{len(r['findings'])} achado(s)")
    else:
        r["summary"] = f"sem TLS utilizável ({raw.get('error', 'erro')[:60]}) · {len(r['findings'])} achado(s)"
    return r


def _dns(p, ctx):
    r = dns.run_dns_analysis(p["target"])
    r["summary"] = f"{len(r['raw'].get('A', []))} IPv4, {len(r['raw'].get('MX', []))} MX · {len(r['findings'])} achado(s)"
    return r


def _subs(p, ctx):
    r = dns.discover_subdomains(p["target"])
    r["summary"] = f"{len(r['raw']['subdomains'])} subdomínio(s) encontrado(s) de {r['raw']['tested']} testados"
    return r


def _ports(p, ctx):
    extra = [x for x in p.get("extra_ports", []) if isinstance(x, int)]
    r = ports.run_port_inventory(p["target"], ports=(list(ports.COMMON) + extra) if extra else None)
    r["summary"] = f"{len(r['raw']['open'])} porta(s) aberta(s) de {r['raw']['tested']} testadas"
    return r


def _links(p, ctx):
    r = web.check_links(p["target"])
    r["summary"] = f"{len(r['raw']['checked'])} link(s) verificado(s) · {len(r['findings'])} problema(s)"
    return r


def _local(fn):
    def h(p, ctx):
        r = fn(p["text"], p.get("filename", "")) if fn is not local.analyze_logs and fn is not local.audit_config \
            else fn(p["text"])
        r["summary"] = f"{len(r['findings'])} achado(s)"
        return r
    return h


def _deps(p, ctx):
    r = local.scan_dependencies(p["text"], p.get("filename", ""), check_osv=bool(p.get("check_osv")))
    r["summary"] = f"{len(r['raw']['dependencies'])} dependência(s) · {len(r['findings'])} achado(s)"
    return r


def _cfg(p, ctx):
    r = local.audit_config(p["text"], p.get("kind", "auto"))
    r["summary"] = f"config {r['raw']['kind']} · {len(r['findings'])} achado(s)"
    return r


def _ai_wrap(fn, label):
    def h(p, ctx):
        return {"text": fn(p), "summary": label}
    return h


def _ai_review(p, ctx):
    from services import ai_engine  # import tardio: Cyber Lab não depende de IA
    return {"text": ai_engine.analyze_code_security(p["text"], p.get("filename", "")),
            "summary": "revisão concluída"}


def _investigator(p, ctx):
    """Versão não-streaming (o front usa /api/cyber/investigate para progresso)."""
    from services.investigator import investigate
    final, err = None, None
    for ev in investigate(p["target"], ctx.get("role", "owner"), ctx.get("session_id", "")):
        if ev["event"] == "done":
            final = ev
        elif ev["event"] == "error":
            err = ev
    if err:
        raise PermissionError(err["error"])
    return {"findings": final["findings"], "raw": {"score": final["score"], "scan_ids": final["scan_ids"]},
            "scene": final["scene"], "text": final["report_md"],
            "summary": f"risco {final['risk']} ({final['score']}/100) · {len(final['findings'])} achado(s)"}


def _holo(p, ctx):
    subject = (p.get("subject") or "").strip()
    return {"ui_action": {"type": "HOLOGRAM_SHOW", "subject": subject,
                          "camera": p.get("camera"), "wireframe": bool(p.get("wireframe"))},
            "summary": f"Exibindo holograma: {subject}"}


def _holo_scene(p, ctx):
    return {"ui_action": {"type": "HOLOGRAM_SCENE", "scene": p.get("scene")}, "summary": "Cena 3D enviada ao holograma"}


def _external(tool_id):
    def handler(p, ctx):
        try:
            return tool_adapter.run(tool_id, p["target"])
        except tool_adapter.NotInstalledError as e:
            return {"summary": f"'{tool_id}' não está instalado neste servidor.",
                    "text": f"{e}\n\nDocumentação: {tool_adapter.TOOLS[tool_id]['docs']}",
                    "raw": {"installed": False, "install_hint": e.hint}}
        except tool_adapter.NotRunnableError as e:
            return {"summary": str(e), "raw": {"runnable": False}}
    return handler


def _tools_status(p, ctx):
    st = tool_adapter.status_all()
    installed = [s for s in st if s["installed"]]
    return {"raw": {"tools": st},
            "summary": f"{len(installed)}/{len(st)} ferramentas externas instaladas neste servidor."}


def register_all():
    # ------- Pentest avançado (OWNER apenas — cap cyber_advanced) -------
    R.register(id="owasp_scanner", name="OWASP Top 10 Scanner", category="pentest",
               description="Testes heurísticos NÃO destrutivos para SQLi, XSS refletido, LFI, candidatos "
                           "a SSRF e BOLA/IDOR, a partir de uma URL com parâmetros.",
               cap="cyber_advanced", needs_target=True, persist=True, params=T,
               handler=lambda p, ctx: owasp.scan_owasp(p["target"]),
               keywords=["owasp", "sqli", "sql injection", "xss", "lfi", "rfi", "ssrf", "idor", "bola",
                         "top 10", "vulnerabilidade web", "injeção"])
    R.register(id="osint_whois", name="WHOIS / OSINT", category="pentest",
               description="Consulta WHOIS real (registrador, datas, status, nameservers) do domínio.",
               cap="cyber_advanced", needs_target=True, persist=True,
               params={"domain": {"required": True, "description": "Domínio (sem http://)"}},
               handler=lambda p, ctx: osint.whois_lookup(p["domain"]),
               keywords=["whois", "osint", "registrador", "dono do domínio", "reconhecimento"])
    R.register(id="osint_email_breach", name="Verificação de vazamento de e-mail", category="pentest",
               description="Verifica se um e-mail aparece em vazamentos conhecidos (via HaveIBeenPwned, "
                           "se HIBP_API_KEY estiver configurada).",
               cap="cyber_advanced",
               params={"email": {"required": True}},
               handler=lambda p, ctx: osint.check_email_breach(p["email"]),
               keywords=["vazamento", "leak", "email vazado", "breach", "haveibeenpwned", "hibp"])
    # ------- Payloads & Encoders (OWNER apenas) -------
    R.register(id="encoder", name="Encoder/Decoder (Base64/URL/Hex)", category="pentest",
               description="Codifica ou decodifica texto em Base64, URL ou Hex.",
               cap="cyber_advanced",
               params={"text": {"required": True}, "encoding": {"required": True, "description": "base64|url|hex"},
                       "action": {"required": True, "description": "encode|decode"}},
               handler=lambda p, ctx: payloads.run_encoder(p["text"], p["encoding"], p["action"]),
               keywords=["base64", "encode", "decode", "url encode", "hex"])
    R.register(id="jwt_decoder", name="JWT Decoder", category="pentest",
               description="Decodifica header e payload de um JWT (sem validar assinatura).",
               cap="cyber_advanced", params={"token": {"required": True}},
               handler=lambda p, ctx: payloads.decode_jwt(p["token"]),
               keywords=["jwt", "json web token", "decodificar token", "bearer"])
    R.register(id="hash_identifier", name="Identificador de Hash", category="pentest",
               description="Identifica o tipo provável de um hash (MD5, SHA-1/256/512, bcrypt, etc.).",
               cap="cyber_advanced", params={"value": {"required": True}},
               handler=lambda p, ctx: payloads.identify_hash(p["value"]),
               keywords=["hash", "md5", "sha1", "sha256", "bcrypt", "identificar hash"])
    R.register(id="cidr_calculator", name="Calculadora CIDR", category="pentest",
               description="Calcula rede, broadcast, máscara e hosts utilizáveis de uma sub-rede CIDR.",
               cap="cyber_advanced", params={"cidr": {"required": True, "description": "ex: 192.168.0.0/24"}},
               handler=lambda p, ctx: payloads.cidr_calc(p["cidr"]),
               keywords=["cidr", "sub-rede", "subnet", "máscara de rede", "netmask"])
    R.register(id="test_payloads", name="Gerador de Payloads de Teste", category="pentest",
               description="Gera payloads de teste inofensivos (XSS/SQLi/LFI/SSRF/CMDi) para colar "
                           "manualmente em campos de um ambiente autorizado.",
               cap="cyber_advanced",
               params={"kind": {"required": True, "description": "xss|sqli|lfi|ssrf|cmdi"}},
               handler=lambda p, ctx: payloads.generate_test_payloads(p["kind"]),
               keywords=["payload", "gerar payload", "teste de injeção"])

    # ------- Ferramentas externas (Tool Adapter — nunca simula) -------
    R.register(id="tools_status", name="Status das ferramentas externas", category="external",
               description="Verifica quais ferramentas externas de Network, Web Security, Blue Team, "
                           "Forensics, Vulnerability Assessment, Reverse Engineering e OSINT/Recon (Nmap, "
                           "Gobuster, Nikto, ffuf, WhatWeb, testssl.sh, Wireshark, Burp Suite, ZAP, SQLMap, "
                           "Zeek, Suricata, Wazuh, osquery, YARA, Volatility, Ghidra, Autopsy, OpenVAS, "
                           "Nessus, Trivy, Semgrep, Lynis etc.) estão instaladas neste servidor, com versão "
                           "e instruções de instalação.",
               cap="cyber", handler=_tools_status,
               keywords=["ferramentas externas", "nmap instalado", "status das ferramentas", "tool status",
                         "quais ferramentas", "gobuster instalado", "nikto instalado"])
    R.register(id="external_nmap", name="Nmap (externo)", category="external",
               description="Executa Nmap real (top portas TCP) contra um alvo autorizado, se instalado.",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_external("nmap"),
               keywords=["nmap"])
    R.register(id="external_gobuster", name="Gobuster (externo)", category="external",
               description="Executa Gobuster real (dir busting) contra um alvo autorizado, se instalado.",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_external("gobuster"),
               keywords=["gobuster", "dir busting", "diretórios ocultos"])
    R.register(id="external_nikto", name="Nikto (externo)", category="external",
               description="Executa Nikto real (varredura web) contra um alvo autorizado, se instalado.",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_external("nikto"),
               keywords=["nikto"])
    R.register(id="external_wireshark", name="Wireshark/tshark (status)", category="external",
               description="Verifica instalação do Wireshark/tshark e explica por que a captura não roda por chat.",
               cap="cyber", needs_target=True, params=T, handler=_external("wireshark"),
               keywords=["wireshark", "tshark", "captura de pacotes"])
    R.register(id="external_burpsuite", name="Burp Suite (status)", category="external",
               description="Verifica instalação do Burp Suite e explica o fluxo manual recomendado.",
               cap="cyber", needs_target=True, params=T, handler=_external("burpsuite"),
               keywords=["burp", "burp suite"])
    R.register(id="external_zap", name="OWASP ZAP (status)", category="external",
               description="Verifica instalação do OWASP ZAP.",
               cap="cyber", needs_target=True, params=T, handler=_external("zap"),
               keywords=["zap", "owasp zap"])
    R.register(id="external_sqlmap", name="SQLMap (status)", category="external",
               description="Verifica instalação do SQLMap e explica por que a exploração não roda por chat.",
               cap="cyber", needs_target=True, params=T, handler=_external("sqlmap"),
               keywords=["sqlmap", "sql injection automatizado"])
    R.register(id="external_ffuf", name="ffuf (externo)", category="external",
               description="Executa ffuf real (fuzzing de caminhos) contra um alvo autorizado, se instalado.",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_external("ffuf"),
               keywords=["ffuf", "fuzzing", "fuzzer"])
    R.register(id="external_whatweb", name="WhatWeb (externo)", category="external",
               description="Executa WhatWeb real (fingerprint de tecnologias) contra um alvo autorizado, se instalado.",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_external("whatweb"),
               keywords=["whatweb", "fingerprint de tecnologia"])
    R.register(id="external_testssl", name="testssl.sh (externo)", category="external",
               description="Executa testssl.sh real (auditoria TLS profunda) contra um alvo autorizado, se instalado.",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_external("testssl"),
               keywords=["testssl", "tls profundo", "cifras fracas"])
    R.register(id="external_lynis", name="Lynis (status)", category="external",
               description="Verifica instalação do Lynis e explica como auditar o próprio host local.",
               cap="cyber", needs_target=True, params=T, handler=_external("lynis"),
               keywords=["lynis", "hardening", "auditoria de sistema"])
    R.register(id="external_ghidra", name="Ghidra (status)", category="external",
               description="Verifica instalação do Ghidra.",
               cap="cyber", needs_target=True, params=T, handler=_external("ghidra"),
               keywords=["ghidra", "engenharia reversa", "reverse engineering", "decompilador"])
    R.register(id="external_autopsy", name="Autopsy (status)", category="external",
               description="Verifica instalação do Autopsy.",
               cap="cyber", needs_target=True, params=T, handler=_external("autopsy"),
               keywords=["autopsy", "forense", "imagem de disco", "sleuth kit"])
    R.register(id="external_openvas", name="OpenVAS / Greenbone (status)", category="external",
               description="Verifica instalação do cliente GVM (OpenVAS/Greenbone).",
               cap="cyber", needs_target=True, params=T, handler=_external("openvas"),
               keywords=["openvas", "greenbone", "gvm"])
    R.register(id="external_nessus", name="Nessus (status)", category="external",
               description="Verifica instalação do Nessus (nessuscli).",
               cap="cyber", needs_target=True, params=T, handler=_external("nessus"),
               keywords=["nessus", "tenable"])
    R.register(id="external_masscan", name="Masscan (status)", category="external",
               description="Verifica instalação do Masscan e explica por que a varredura em massa não roda por chat.",
               cap="cyber", needs_target=True, params=T, handler=_external("masscan"),
               keywords=["masscan", "varredura em massa", "scanner de portas rápido"])
    R.register(id="external_tcpdump", name="tcpdump (status)", category="external",
               description="Verifica instalação do tcpdump.",
               cap="cyber", needs_target=True, params=T, handler=_external("tcpdump"),
               keywords=["tcpdump", "captura de pacotes"])
    R.register(id="external_sslyze", name="SSLyze (status)", category="external",
               description="Verifica instalação do SSLyze.",
               cap="cyber", needs_target=True, params=T, handler=_external("sslyze"),
               keywords=["sslyze", "auditoria tls"])
    R.register(id="external_aircrackng", name="Aircrack-ng (status)", category="external",
               description="Verifica instalação do Aircrack-ng e explica os limites legais/técnicos de uso.",
               cap="cyber", needs_target=True, params=T, handler=_external("aircrack-ng"),
               keywords=["aircrack", "aircrack-ng", "wifi", "wi-fi", "wpa2", "handshake"])
    R.register(id="external_wapiti", name="Wapiti (status)", category="external",
               description="Verifica instalação do Wapiti.",
               cap="cyber", needs_target=True, params=T, handler=_external("wapiti"),
               keywords=["wapiti", "scanner web"])
    R.register(id="external_theharvester", name="theHarvester (status)", category="external",
               description="Verifica instalação do theHarvester.",
               cap="cyber", needs_target=True, params=T, handler=_external("theharvester"),
               keywords=["theharvester", "harvester", "osint de e-mail"])
    R.register(id="external_amass", name="OWASP Amass (status)", category="external",
               description="Verifica instalação do OWASP Amass.",
               cap="cyber", needs_target=True, params=T, handler=_external("amass"),
               keywords=["amass", "enumeração de subdomínio", "subdomínios"])
    R.register(id="external_nuclei", name="Nuclei (status)", category="external",
               description="Verifica instalação do Nuclei e explica por que templates ativos não rodam por chat.",
               cap="cyber", needs_target=True, params=T, handler=_external("nuclei"),
               keywords=["nuclei", "templates de vulnerabilidade"])
    R.register(id="external_hashcat", name="Hashcat (status)", category="external",
               description="Verifica instalação do Hashcat e explica a política de não quebrar hash por chat.",
               cap="cyber", needs_target=True, params=T, handler=_external("hashcat"),
               keywords=["hashcat", "quebrar hash", "crackear senha"])
    R.register(id="external_john", name="John the Ripper (status)", category="external",
               description="Verifica instalação do John the Ripper.",
               cap="cyber", needs_target=True, params=T, handler=_external("john"),
               keywords=["john the ripper", "john", "crackear senha"])
    R.register(id="external_hydra", name="THC-Hydra (status)", category="external",
               description="Verifica instalação do Hydra e explica por que força bruta de login não roda por chat.",
               cap="cyber", needs_target=True, params=T, handler=_external("hydra"),
               keywords=["hydra", "thc-hydra", "força bruta de login", "brute force"])
    R.register(id="external_metasploit", name="Metasploit (status)", category="external",
               description="Verifica instalação do Metasploit Framework.",
               cap="cyber", needs_target=True, params=T, handler=_external("metasploit"),
               keywords=["metasploit", "msfconsole", "framework de exploração"])
    R.register(id="external_radare2", name="radare2 (status)", category="external",
               description="Verifica instalação do radare2.",
               cap="cyber", needs_target=True, params=T, handler=_external("radare2"),
               keywords=["radare2", "r2", "engenharia reversa"])
    R.register(id="external_subfinder", name="Subfinder (externo)", category="external",
               description="Executa Subfinder real (enumeração passiva de subdomínios) contra um domínio autorizado, se instalado.",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_external("subfinder"),
               keywords=["subfinder", "subdomínio", "enumeração de subdomínio", "projectdiscovery"])
    R.register(id="external_httpx", name="httpx (externo)", category="external",
               description="Executa httpx real (sonda status/título/tecnologia HTTP) contra um alvo autorizado, se instalado.",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_external("httpx"),
               keywords=["httpx", "probe http", "sondar host"])
    R.register(id="external_dnsx", name="dnsx (externo)", category="external",
               description="Executa dnsx real (resolução/validação de registros DNS) contra um alvo autorizado, se instalado.",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_external("dnsx"),
               keywords=["dnsx", "resolver dns", "registros dns"])
    R.register(id="external_naabu", name="Naabu (externo)", category="external",
               description="Executa Naabu real (varredura de portas rápida) contra um alvo autorizado, se instalado.",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_external("naabu"),
               keywords=["naabu", "varredura de portas rápida", "port scan"])
    R.register(id="external_crackmapexec", name="CrackMapExec / NetExec (status)", category="external",
               description="Verifica instalação do CrackMapExec/NetExec e explica por que não roda por chat.",
               cap="cyber", needs_target=True, params=T, handler=_external("crackmapexec"),
               keywords=["crackmapexec", "netexec", "cme", "nxc", "active directory", "pós-exploração"])
    R.register(id="external_bettercap", name="Bettercap (status)", category="external",
               description="Verifica instalação do Bettercap e explica os limites legais/técnicos de uso.",
               cap="cyber", needs_target=True, params=T, handler=_external("bettercap"),
               keywords=["bettercap", "mitm", "spoofing", "sniffing"])
    R.register(id="external_responder", name="Responder (status)", category="external",
               description="Verifica instalação do Responder e explica os limites legais/técnicos de uso.",
               cap="cyber", needs_target=True, params=T, handler=_external("responder"),
               keywords=["responder", "llmnr", "nbt-ns", "captura de hash"])
    R.register(id="external_impacket", name="Impacket (status)", category="external",
               description="Verifica instalação do Impacket.",
               cap="cyber", needs_target=True, params=T, handler=_external("impacket"),
               keywords=["impacket", "secretsdump", "smb", "kerberos"])
    R.register(id="external_bloodhound", name="BloodHound (status)", category="external",
               description="Verifica instalação do coletor BloodHound.",
               cap="cyber", needs_target=True, params=T, handler=_external("bloodhound"),
               keywords=["bloodhound", "active directory", "caminho de ataque", "privilege escalation"])
    R.register(id="external_searchsploit", name="SearchSploit (status)", category="external",
               description="Verifica instalação do SearchSploit (Exploit-DB) e explica por que não devolvemos exploits por chat.",
               cap="cyber", needs_target=True, params=T, handler=_external("searchsploit"),
               keywords=["searchsploit", "exploit-db", "exploitdb", "cve com exploit"])
    # ------- Cyber Lab (alvo autorizado) -------
    R.register(id="web_analyzer", name="HTTP/Headers/Cookies/CSP/CORS Analyzer", category="cyber",
               description="Análise HTTP completa: security headers, cookies, CSP, CORS e fingerprint.",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_web,
               keywords=["http", "header", "cabeçalho", "cabecalho", "cookie", "csp", "cors", "fingerprint",
                         "tecnologia", "site", "web", "clickjacking", "hsts", "security headers"])
    R.register(id="tls_analyzer", name="HTTPS/TLS Analyzer", category="cyber",
               description="Certificado, validade, versão do protocolo TLS e protocolos legados.",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_tls,
               keywords=["tls", "ssl", "https", "certificado", "certificate", "cifra", "criptografia"])
    R.register(id="dns_analyzer", name="DNS Analyzer", category="cyber",
               description="Registros A/AAAA/NS/MX/TXT/CAA, SPF, DMARC e wildcard.",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_dns,
               keywords=["dns", "spf", "dmarc", "mx", "registro", "nameserver", "ns", "email spoof", "caa"])
    R.register(id="subdomain_discovery", name="Subdomain Discovery", category="cyber",
               description="Descoberta de subdomínios por dicionário (apenas domínio autorizado).",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_subs,
               keywords=["subdomínio", "subdominio", "subdomain", "subdomains"])
    R.register(id="port_inventory", name="Port/Service Inventory", category="cyber",
               description="Inventário de portas TCP comuns e serviços expostos (sem exploração).",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_ports,
               keywords=["porta", "portas", "port", "ports", "nmap", "serviço", "servico", "servicos", "exposto", "scan de portas"])
    R.register(id="link_checker", name="Link Checker", category="cyber",
               description="Verifica links quebrados e conteúdo misto na página inicial.",
               cap="cyber", needs_target=True, persist=True, params=T, handler=_links,
               keywords=["link", "links", "quebrado", "quebrados", "broken", "conteúdo misto"])
    # ------- Análise local (sem rede) -------
    R.register(id="secret_scanner", name="Secret/Credential Exposure Detector", category="cyber",
               description="Detecta chaves, tokens e senhas expostos em código/arquivos colados.",
               cap="cyber", persist=True, params=TXT, handler=_local(local.scan_secrets),
               keywords=["segredo", "segredos", "secret", "credencial", "credenciais", "token exposto", "chave exposta", "senha no código", "vazamento"])
    R.register(id="code_analyzer", name="Source Code Security Analyzer", category="cyber",
               description="Regras de segurança em código (injeção, desserialização, crypto fraca, auth).",
               cap="cyber", persist=True, params=TXT, handler=_local(local.scan_code),
               keywords=["código", "codigo", "code", "sast", "vulnerabilidade no código", "injeção", "sql injection", "xss", "auth", "autenticação", "autorização"])
    R.register(id="dependency_analyzer", name="Dependency Analyzer", category="cyber",
               description="Analisa requirements.txt/package.json (versões fixas + OSV.dev opcional).",
               cap="cyber", persist=True, handler=_deps,
               params={**TXT, "check_osv": {"type": "boolean", "description": "Consultar OSV.dev (requer internet)"}},
               keywords=["dependência", "dependencia", "dependências", "requirements", "package.json", "cve", "biblioteca desatualizada", "pip", "npm"])
    R.register(id="log_analyzer", name="Log Analyzer", category="cyber",
               description="Analisa logs de acesso web e auth (força bruta SSH, SQLi/XSS, varreduras).",
               cap="cyber", persist=True, params={"text": TXT["text"]}, handler=_local(local.analyze_logs),
               keywords=["log", "logs", "access.log", "auth.log", "força bruta", "forca bruta", "brute force", "tentativas de login"])
    R.register(id="config_auditor", name="Configuration Auditor", category="cyber",
               description="Audita sshd_config, nginx e .env.",
               cap="cyber", persist=True,
               params={"text": TXT["text"], "kind": {"type": "string", "description": "auto|sshd|nginx|env"}},
               handler=_cfg, keywords=["configuração", "configuracao", "config", "sshd", "nginx", ".env", "hardening"])
    R.register(id="security_investigator", name="Security Investigator", category="cyber",
               description="Fluxo completo: escopo → reconhecimento → análise → evidência → gravidade → "
                           "correção → reteste → relatório, com cena 3D dos achados.",
               cap="cyber", needs_target=True, params=T, handler=_investigator,
               keywords=["security investigator", "investigador de segurança"])
    # ------- Central de Ferramentas Reutilizáveis -------
    CENTRAL_TEXT = {"text": {"type": "string", "required": True, "description": "Conteúdo a analisar"},
                    "filename": {"type": "string", "description": "Nome do arquivo (opcional)"}}
    R.register(id="central_code_analyzer", name="Code Analyzer", category="central",
               description="Analisa código estaticamente em busca de padrões de segurança e segredos expostos; não executa o código.",
               cap="tools_advanced", params={**CENTRAL_TEXT, "language": {"description": "python|javascript|java|php|auto"}},
               handler=central_tools.code_analyzer, keywords=["code analyzer", "analisador de código", "analisar código", "sast"])
    R.register(id="central_debugger", name="Debugger", category="central",
               description="Analisa mensagem de erro e código sem executar o programa, apontando causas prováveis e próximos passos.",
               cap="tools_advanced", params={"error": {"description": "Mensagem/traceback"}, "code": {"description": "Código relacionado"}},
               handler=central_tools.debugger, keywords=["debugger", "debug", "depurar", "corrigir erro", "traceback"])
    API_PARAMS={"url": {"type":"string", "required":True, "description":"URL do alvo autorizado"},
                "method": {"description":"GET|POST|PUT|PATCH|DELETE|HEAD"},
                "headers": {"description":"Objeto JSON com headers"}, "body": {"description":"Corpo da requisição"}}
    R.register(id="central_api_tester", name="API Tester", category="central",
               description="Envia requisições HTTP para uma URL autorizada e mostra status, headers, tempo e corpo.",
               cap="tools_advanced", needs_target=True, params=API_PARAMS, handler=central_tools.api_tester,
               keywords=["api tester", "testar api", "teste de api", "rest api"])
    R.register(id="central_json_validator", name="JSON Validator", category="central",
               description="Valida JSON e informa linha/coluna do erro quando a sintaxe é inválida.",
               cap="tools_advanced", params={"text":{"required":True}}, handler=central_tools.json_validator,
               keywords=["json validator", "validar json", "json inválido", "json invalido"])
    R.register(id="central_regex_tester", name="Regex Tester", category="central",
               description="Compila uma expressão regular e mostra as correspondências encontradas no texto.",
               cap="tools_advanced", params={"pattern":{"required":True},"text":{"required":True},"flags":{}},
               handler=central_tools.regex_tester, keywords=["regex tester", "regex", "expressão regular", "expressao regular"])
    R.register(id="central_http_request", name="HTTP Request Tester", category="central",
               description="Testa uma requisição HTTP para alvo autorizado com método, headers e corpo opcionais.",
               cap="tools_advanced", needs_target=True, params=API_PARAMS, handler=central_tools.http_request_tester,
               keywords=["http request tester", "http request", "requisição http", "requisicao http"])
    R.register(id="central_dns_lookup", name="DNS Lookup", category="central",
               description="Consulta registros DNS de um domínio autorizado.", cap="tools_advanced", needs_target=True,
               params={"domain":{"required":True}}, handler=central_tools.dns_lookup,
               keywords=["dns lookup", "consulta dns", "lookup dns"])
    R.register(id="central_port_checker", name="Port Checker", category="central",
               description="Verifica uma porta TCP específica em alvo autorizado.", cap="tools_advanced", needs_target=True,
               params={"target":{"required":True},"port":{"required":True}}, handler=central_tools.port_checker,
               keywords=["port checker", "verificar porta", "porta tcp"])
    R.register(id="central_log_analyzer", name="Log Analyzer", category="central",
               description="Analisa logs de acesso e autenticação em busca de padrões suspeitos.", cap="tools_advanced",
               params={"text":{"required":True}}, handler=central_tools.log_analyzer,
               keywords=["log analyzer", "analisar logs", "logs de segurança"])
    R.register(id="central_website_health", name="Website Health Checker", category="central",
               description="Verifica disponibilidade, status HTTP, tempo de resposta, redirects e título de um site autorizado.",
               cap="tools_advanced", needs_target=True, params={"url":{"required":True}}, handler=central_tools.website_health,
               keywords=["website health checker", "site está fora", "saúde do site", "health check"])
    R.register(id="central_markup_validator", name="HTML/CSS/JS Validator", category="central",
               description="Valida a estrutura básica de HTML, CSS ou JavaScript sem executar o conteúdo.", cap="tools_advanced",
               params={"text":{"required":True},"kind":{"required":True,"description":"html|css|js"}}, handler=central_tools.html_css_js_validator,
               keywords=["html validator", "css validator", "js validator", "validar html", "validar css", "validar javascript"])
    R.register(id="central_base64", name="Base64 Encoder/Decoder", category="central",
               description="Codifica ou decodifica Base64 usando UTF-8.", cap="tools_advanced",
               params={"text":{"required":True},"action":{"required":True,"description":"encode|decode"}}, handler=central_tools.base64_tool,
               keywords=["base64 encoder", "base64 decoder", "codificar base64", "decodificar base64"])
    R.register(id="central_hash", name="Hash Generator", category="central",
               description="Gera hashes MD5, SHA-1, SHA-224, SHA-256, SHA-384 ou SHA-512 do texto fornecido.", cap="tools_advanced",
               params={"text":{"required":True},"algorithm":{"required":True}}, handler=central_tools.hash_generator,
               keywords=["hash generator", "gerar hash", "sha256", "sha-256", "md5"])
    R.register(id="central_jwt", name="JWT Analyzer", category="central",
               description="Decodifica header e payload de JWT e deixa explícito que a assinatura não é validada.", cap="tools_advanced",
               params={"token":{"required":True}}, handler=central_tools.jwt_analyzer,
               keywords=["jwt analyzer", "analisar jwt", "jwt decoder", "json web token"])
    R.register(id="central_file_analyzer", name="File Analyzer", category="central",
               description="Analisa um arquivo/texto fornecido: tamanho, linhas, extensão, hashes e formato JSON quando aplicável.", cap="tools_advanced",
               params={"text":{"required":True},"filename":{}}, handler=central_tools.file_analyzer,
               keywords=["file analyzer", "analisar arquivo", "analisador de arquivo", "sha256 arquivo"])
    R.register(id="central_network_diagnostics", name="Network Diagnostics", category="central",
               description="Diagnóstico básico de DNS e conectividade TCP em alvo autorizado.", cap="tools_advanced", needs_target=True,
               params={"host":{"required":True}}, handler=central_tools.network_diagnostics,
               keywords=["network diagnostics", "diagnóstico de rede", "diagnostico de rede", "rede lenta"])

    # ------- Ferramentas básicas (já existiam; usuário comum pode usar) -------
    R.register(id="latency", name="Latência HTTP", category="basic", description="Mede o tempo de resposta de um site público.",
               cap="tools_basic", params={"url": {"required": True}},
               handler=lambda p, c: {**(r := basic_net.latency_check(p["url"])), "raw": r,
                                     "summary": f"HTTP {r['status']} em {r['elapsed_ms']} ms"},
               keywords=["latência", "latencia", "lento", "tempo de resposta", "ping"])
    R.register(id="robots", name="robots.txt", category="basic", description="Mostra o robots.txt de um site público.",
               cap="tools_basic", params={"domain": {"required": True}},
               handler=lambda p, c: {"raw": (r := basic_net.robots_check(p["domain"])), "summary": f"HTTP {r['status']}", "text": r["content"]},
               keywords=["robots", "robots.txt"])
    R.register(id="domain_resolves", name="Domínio resolve?", category="basic", description="Verifica se um domínio resolve no DNS.",
               cap="tools_basic", params={"domain": {"required": True}},
               handler=lambda p, c: {"raw": (r := basic_net.domain_check(p["domain"])), "summary": "resolve" if r["resolves"] else "não resolve"},
               keywords=["domínio existe", "dominio existe", "resolve"])
    # ------- IA -------
    R.register(id="ai_code_review", name="Revisão de segurança por IA", category="ai",
               description="A IA revisa um trecho de código em busca de falhas.",
               cap="cyber", kind="ai", params=TXT,
               handler=_ai_review,
               keywords=["revisar código com ia", "explique a falha", "review de segurança"])
    # ------- Comando de interface (Jarvis controla hologramas) -------
    R.register(id="hologram_show", name="Mostrar holograma", category="ui", kind="ui",
               description="Exibe um holograma 3D (DNA, cérebro, planeta, servidor, cidade…).",
               cap="chat", params={"subject": {"required": True}, "camera": {}, "wireframe": {"type": "boolean"}},
               handler=_holo,
               keywords=["holograma", "hologram", "mostre", "mostra", "exiba", "3d", "dna", "átomo", "molécula", "cérebro", "planeta", "sistema solar"])
    R.register(id="hologram_scene", name="Cena 3D de resultado", category="ui", kind="ui",
               description="Envia uma cena 3D (servidor/endpoints/achados) ao Hologram Engine.",
               cap="chat", params={"scene": {"required": True}}, handler=_holo_scene, keywords=[])

    # ------- Blue Team / Threat Intel / Forense (services/cyber/blue.py) -------
    from services.cyber import blue as blue_service

    def _mitre(p, ctx):
        r = blue_service.mitre_lookup(p.get("query", ""))
        return {"raw": {"tactics": r}, "summary": f"{len(r)} tática(s) MITRE ATT&CK encontrada(s)"}

    R.register(id="mitre_lookup", name="Consultar MITRE ATT&CK", category="cyber",
               description="Consulta táticas/técnicas de ataque (MITRE ATT&CK) com estratégias de detecção e mitigação.",
               cap="cyber", params={"query": {"description": "tática, técnica ou palavra-chave (opcional)"}},
               handler=_mitre, keywords=["mitre", "att&ck", "tática", "tatica", "técnica de ataque"])

    def _waf(p, ctx):
        r = blue_service.generate_waf_rules(p.get("engine", "nginx"), p.get("patterns", []))
        return {"raw": r, "text": r.get("rules", ""), "summary": f"Regras {r.get('engine')} geradas"}

    R.register(id="waf_generate", name="Gerar regras de WAF/Firewall", category="cyber",
               description="Gera regras defensivas (nginx, ModSecurity ou iptables) para bloquear padrões de ataque conhecidos.",
               cap="cyber", params={"engine": {"description": "nginx|modsecurity|iptables"},
                                    "patterns": {"description": "lista: sqli, xss, traversal, scanner"}},
               handler=_waf, keywords=["waf", "firewall", "regra de bloqueio", "modsecurity", "iptables"])

    def _headers(p, ctx):
        r = blue_service.audit_http_headers(p["text"])
        r["summary"] = f"{len(r['findings'])} cabeçalho(s) de segurança ausente(s)"
        return r

    R.register(id="headers_audit", name="Auditar cabeçalhos HTTP", category="cyber",
               description="Analisa cabeçalhos HTTP colados (ex.: saída de curl -I) e aponta CSP/HSTS/X-Frame-Options ausentes.",
               cap="cyber", params=TXT, handler=_headers,
               keywords=["cabeçalhos http", "headers http", "csp", "hsts", "x-frame-options"])

    def _email(p, ctx):
        r = blue_service.analyze_email_headers(p["text"])
        r["summary"] = f"SPF={r['raw']['spf']} DKIM={r['raw']['dkim']} DMARC={r['raw']['dmarc']}"
        return r

    R.register(id="email_headers_analyze", name="Analisar cabeçalhos de e-mail (anti-phishing)", category="cyber",
               description="Analisa cabeçalhos brutos de e-mail: SPF, DKIM, DMARC e Reply-To suspeito.",
               cap="cyber", params=TXT, handler=_email,
               keywords=["phishing", "cabeçalho de email", "spf", "dkim", "dmarc"])

    def _ir(p, ctx):
        pb = blue_service.get_ir_playbook(p.get("key", ""))
        if not pb:
            return {"raw": {"playbooks": blue_service.list_ir_playbooks()}, "summary": "Playbooks disponíveis"}
        return {"raw": pb, "text": "\n".join(f"**{s['phase']}**: {s['text']}" for s in pb["steps"]),
                "summary": pb["title"]}

    R.register(id="ir_playbook", name="Playbook de Resposta a Incidentes", category="cyber",
               description="Guia passo a passo (contenção/erradicação/recuperação) para tipos comuns de incidente.",
               cap="cyber", params={"key": {"description": "web_compromise|credential_leak|bruteforce_detected|phishing_reported"}},
               handler=_ir, keywords=["resposta a incidente", "playbook", "incident response", "ir"])

    def _sectests(p, ctx):
        r = blue_service.generate_security_tests(p.get("language", "python"), p.get("endpoints", []))
        return {"raw": r, "text": r["code"], "summary": f"Testes gerados em {r['language']}"}

    R.register(id="security_tests_generate", name="Gerar testes de segurança", category="cyber",
               description="Gera testes automatizados (pytest ou Jest) que verificam validação de entrada dos seus endpoints.",
               cap="cyber", params={"language": {"description": "python|javascript"}, "endpoints": {}},
               handler=_sectests, keywords=["gerar testes", "pytest", "jest", "unit test de segurança"])

    def _ctf(p, ctx):
        cid = p.get("id")
        if not cid:
            return {"raw": {"challenges": blue_service.list_ctf_challenges()}, "summary": "Desafios CTF disponíveis"}
        c = blue_service.get_ctf_challenge(cid, reveal_fix=bool(p.get("reveal")))
        return {"raw": c, "text": c["vulnerable_code"] if c else "", "summary": c["title"] if c else "não encontrado"}

    R.register(id="ctf_challenge", name="Desafio de Secure Coding (CTF)", category="cyber",
               description="Mostra um trecho de código intencionalmente vulnerável para o usuário identificar/corrigir a falha.",
               cap="cyber", params={"id": {"description": "ctf1..ctf5 (vazio lista todos)"}, "reveal": {"type": "boolean"}},
               handler=_ctf, keywords=["ctf", "desafio de segurança", "código vulnerável"])

    def _audit_report(p, ctx):
        target = p.get("target", "aplicação")
        findings = p.get("findings") or []
        report = blue_service.generate_audit_report(findings, fmt=p.get("format", "markdown"), target=target)
        score = blue_service.compute_security_score(findings)
        return {"raw": {"security_score": score}, "text": report,
                "summary": f"Score {score['score']}/100 (risco {score['risk']})"}

    R.register(id="audit_report_generate", name="Gerar Relatório de Auditoria", category="cyber",
               description="Consolida achados em relatório (Markdown/JSON) com Security Score global.",
               cap="cyber", params={"target": {}, "format": {"description": "markdown|json"}, "findings": {}},
               handler=_audit_report, keywords=["relatório de auditoria", "security score", "relatorio de seguranca"])

    def _pwd(p, ctx):
        r = blue_service.analyze_password_strength(p.get("password", ""))
        return {"raw": r, "summary": f"Força: {r['label']} ({r['score']}/100)"}

    R.register(id="password_strength", name="Analisador de Força de Senha", category="cyber",
               description="Avalia força de uma senha (entropia, variedade, padrões comuns) — educacional, não armazena a senha.",
               cap="cyber", params={"password": {"required": True}},
               handler=_pwd, keywords=["força de senha", "senha forte", "password strength"])

    def _malware(p, ctx):
        r = blue_service.scan_malware_patterns(p["text"], p.get("filename", ""))
        r["summary"] = f"{len(r['findings'])} padrão(ões) suspeito(s) de malware/backdoor"
        return r

    R.register(id="malware_pattern_scan", name="Scanner de Padrões de Malware (forense)", category="cyber",
               description="Procura padrões conhecidos de webshell, JS ofuscado, comandos de download+execução e cryptominer em texto/logs.",
               cap="cyber", params=TXT, handler=_malware,
               keywords=["malware", "webshell", "backdoor", "yara", "forense"])


    # ------- V29: analisadores defensivos adicionais, reutilizando o Blue Team -------
    def _csp(p, ctx):
        r = blue_service.analyze_csp_policy(p["text"])
        r["summary"] = f"{len(r['findings'])} ponto(s) de revisão na CSP"
        return r
    R.register(id="csp_audit", name="CSP Deep Audit", category="cyber",
               description="Audita uma Content-Security-Policy procurando unsafe-inline, unsafe-eval, wildcards e diretivas ausentes.",
               cap="cyber", params=TXT, handler=_csp,
               keywords=["csp audit", "auditar csp", "content security policy", "unsafe-inline", "unsafe-eval"])

    def _cookies(p, ctx):
        r = blue_service.analyze_cookie_headers(p["text"])
        r["summary"] = f"{r['raw']['cookies']} cookie(s) analisado(s) · {len(r['findings'])} achado(s)"
        return r
    R.register(id="cookie_security_audit", name="Cookie Security Audit", category="cyber",
               description="Analisa Set-Cookie e verifica Secure, HttpOnly e SameSite sem fazer requisições.",
               cap="cyber", params=TXT, handler=_cookies,
               keywords=["cookie audit", "auditar cookie", "secure httponly samesite"])

    def _docker(p, ctx):
        r = blue_service.audit_dockerfile(p["text"])
        r["summary"] = f"Dockerfile: {len(r['findings'])} ponto(s) de revisão"
        return r
    R.register(id="dockerfile_audit", name="Dockerfile Security Audit", category="cyber",
               description="Analisa Dockerfile em busca de latest, execução como root, ADD e modo privilegiado.",
               cap="cyber", params=TXT, handler=_docker,
               keywords=["docker security", "dockerfile", "container hardening", "root container"])

    def _gha(p, ctx):
        r = blue_service.audit_github_actions(p["text"])
        r["summary"] = f"Workflow CI: {len(r['findings'])} ponto(s) de revisão"
        return r
    R.register(id="ci_security_audit", name="CI/CD Security Audit", category="cyber",
               description="Audita workflows GitHub Actions em busca de permissões excessivas e padrões perigosos de secrets.",
               cap="cyber", params=TXT, handler=_gha,
               keywords=["github actions", "ci cd", "workflow security", "pipeline security"])

    def _api_sec(p, ctx):
        r = blue_service.analyze_api_security_text(p["text"])
        r["summary"] = f"API checklist: {len(r['findings'])} ponto(s) para revisão"
        return r
    R.register(id="api_security_audit", name="API Security Checklist", category="cyber",
               description="Checklist estático de autenticação, autorização, rate limit, validação e tratamento de erros em trechos de API.",
               cap="cyber", params=TXT, handler=_api_sec,
               keywords=["api security", "segurança de api", "api audit", "authorization", "rate limit"])

    from services.cyber import vulndoctor as vulndoctor_service

    def _vulndoctor(p, ctx):
        r = vulndoctor_service.diagnose(p["text"], p.get("filename", ""))
        return {"findings": r["findings"], "raw": {"kind": r["kind"]}, "summary": r["summary"]}

    R.register(id="vuln_doctor", name="Vulnerability Doctor", category="cyber",
               description="Acha vulnerabilidades em código/HTML/config/dependências e mostra como corrigir (antes/depois).",
               cap="cyber", params=TXT, handler=_vulndoctor,
               keywords=["vulnerabilidade", "vulnerabilidades", "ajeitar falha", "corrigir falha", "doutor de segurança"])

    def _vulndoctor_site(p, ctx):
        r = vulndoctor_service.diagnose_site(p["slug"])
        return {"findings": r["findings"], "raw": {"site": r["site"]}, "summary": r["summary"]}

    R.register(id="vuln_doctor_site", name="Vulnerability Doctor (site gerado)", category="cyber",
               description="Analisa o index.html de um site criado pelo app e mostra como corrigir cada falha.",
               cap="cyber", params={"slug": {"type": "string", "required": True, "description": "slug do site"}},
               handler=_vulndoctor_site, keywords=["site está seguro", "site seguro", "analisar meu site"])


register_all()
from services.cyber import extra_tools as _extra_tools  # v33: utilitários locais extras
_extra_tools.register(R)
# v34 expand: ferramentas defensivas + validação rigorosa + Central de Ferramentas
try:
    from services.cyber.defensive_tools import register_defensive_tools
    register_defensive_tools(R)
except Exception as _def_err:  # nunca derruba o boot
    import logging
    logging.getLogger("jarvis").warning("defensive_tools register failed: %s", _def_err)
try:
    from services.cyber.defensive_tools_extra import register_defensive_extra
    register_defensive_extra(R)
except Exception as _def_err2:
    import logging
    logging.getLogger("jarvis").warning("defensive_tools_extra register failed: %s", _def_err2)
R.load_plugins()
