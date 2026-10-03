"""Área Kali Linux — catálogo completo por categoria oficial do Kali.

Segue as mesmas categorias do menu do Kali Linux (Information Gathering,
Vulnerability Analysis, Web Application Analysis, Database Assessment,
Password Attacks, Wireless Attacks, Reverse Engineering, Exploitation
Tools, Sniffing & Spoofing, Post Exploitation, Forensics, Reporting Tools
e Social Engineering Tools).

Este módulo NUNCA finge que uma ferramenta está instalada:
- Se o `tool_id` bate com uma entrada já detectada de verdade em
  `services.tool_adapter.TOOLS`, a detecção real (shutil.which + versão)
  é reaproveitada.
- Caso contrário, se houver um `bin`, fazemos uma checagem própria com
  shutil.which (sem rodar nada).
- Sem `bin` (ferramenta puramente gráfica/comercial ou não aplicável a um
  servidor web), o item fica marcado como "referência" com o pacote apt
  oficial do Kali para quem quiser instalar localmente.

Execução real de qualquer ferramenta só acontece pelas integrações já
existentes no Cyber Lab (Tool Adapter), dentro de um alvo em escopo
autorizado. Esta página é catálogo + detecção de instalação, não um
executor genérico de comandos.
"""
import shutil

from services import tool_adapter

# cid: (nome, pacote apt no Kali, descrição curta, bin p/ checar instalação
#       localmente quando não há entrada no tool_adapter, tool_id do
#       tool_adapter quando já integrado de verdade)
CATALOG = {
    "Information Gathering": [
        ("Nmap", "nmap", "Descoberta de hosts, portas e serviços de rede.", None, "nmap"),
        ("Masscan", "masscan", "Varredura de portas em larga escala, extremamente rápida.", None, "masscan"),
        ("Naabu", "naabu", "Varredura de portas rápida, pensada para alimentar outras ferramentas de recon.", None, "naabu"),
        ("Subfinder", "subfinder", "Enumeração passiva de subdomínios (certificate transparency, APIs públicas).", None, "subfinder"),
        ("dnsx", "dnsx-toolkit", "Resolução e validação de registros DNS em massa.", None, "dnsx"),
        ("theHarvester", "theharvester", "Coleta e-mails, subdomínios e hosts de fontes públicas (OSINT).", None, "theharvester"),
        ("Amass", "amass", "Mapeamento de superfície de ataque e enumeração de subdomínios.", None, "amass"),
        ("Recon-ng", "recon-ng", "Framework modular de reconhecimento web/OSINT.", "recon-ng", None),
        ("Maltego", "maltego", "Visualização gráfica de relações OSINT entre entidades.", "maltego", None),
        ("dnsenum", "dnsenum", "Enumeração de DNS (registros, zonas, subdomínios).", "dnsenum", None),
        ("dnsrecon", "dnsrecon", "Enumeração e varredura de DNS com várias técnicas.", "dnsrecon", None),
        ("Fierce", "fierce", "Descoberta de espaço de IP e nomes de host de um domínio.", "fierce", None),
        ("WhatWeb", "whatweb", "Fingerprinting de tecnologias usadas em um site.", None, "whatweb"),
        ("Sublist3r", "sublist3r", "Enumeração rápida de subdomínios via múltiplas fontes.", "sublist3r", None),
        ("Shodan CLI", "shodan-cli", "Busca de dispositivos/serviços expostos indexados pelo Shodan.", "shodan", None),
        ("WHOIS", "whois", "Consulta de registro de domínio/IP.", "whois", None),
        ("Netdiscover", "netdiscover", "Descoberta ativa/passiva de hosts em uma rede local (ARP).", "netdiscover", None),
        ("p0f", "p0f", "Fingerprinting passivo de sistema operacional via tráfego.", "p0f", None),
        ("Nbtscan", "nbtscan", "Varredura de nomes NetBIOS em redes Windows.", "nbtscan", None),
        ("SMBmap", "smbmap", "Enumeração de compartilhamentos SMB e permissões.", "smbmap", None),
        ("enum4linux", "enum4linux", "Enumeração de informações via SMB/Samba em hosts Windows/Linux.", "enum4linux", None),
        ("SNMPwalk", "snmp", "Consulta de informações expostas via SNMP.", "snmpwalk", None),
        ("Unicornscan", "unicornscan", "Varredura de portas assíncrona e de alta performance.", "unicornscan", None),
        ("Wireless Fingerprinting (Wash)", "reaver", "Identifica pontos de acesso com WPS habilitado.", "wash", None),
        ("OSRFramework", "osrframework", "Conjunto de ferramentas OSINT para usernames/e-mails/domínios.", "usufy", None),
        ("Spiderfoot", "spiderfoot", "Automação de reconhecimento OSINT com dezenas de módulos.", "spiderfoot", None),
        ("dmitry", "dmitry", "Coleta de informações passiva/ativa sobre um host (e-mails, subdomínios, portas).", "dmitry", None),
    ],
    "Blue Team / Defense": [
        ("Zeek", "zeek", "Análise de tráfego e detecção de eventos de rede para defesa.", "zeek", None),
        ("Suricata", "suricata", "IDS/IPS e inspeção de tráfego com regras defensivas.", "suricata", None),
        ("YARA", "yara", "Identificação de padrões em arquivos para investigação e resposta.", "yara", None),
        ("ClamAV", "clamav", "Antivírus open-source para análise de arquivos suspeitos.", "clamscan", None),
        ("osquery", "osquery", "Consulta de estado e inventário de endpoints para investigação.", "osqueryi", None),
        ("Semgrep", "semgrep", "SAST para detectar padrões inseguros em código.", "semgrep", None),
        ("Gitleaks", "gitleaks", "Detecção de secrets expostos em repositórios e histórico Git.", "gitleaks", None),
        ("Trivy", "trivy", "Scanner de vulnerabilidades para imagens, dependências e IaC.", "trivy", None),
        ("Grype", "grype", "Scanner de vulnerabilidades para SBOMs e artefatos.", "grype", None),
        ("Wazuh", "wazuh", "Plataforma de SIEM/XDR para monitoramento e resposta.", "wazuh-agent", None),
        ("Velociraptor", "velociraptor", "DFIR e investigação de endpoints em ambientes autorizados.", "velociraptor", None),
        ("OpenSCAP", "openscap-scanner", "Auditoria de conformidade e hardening de sistemas.", "oscap", None),
    ],
    "Vulnerability Analysis": [
        ("Nikto", "nikto", "Varredura de vulnerabilidades e configurações em servidores web.", None, "nikto"),
        ("OpenVAS / Greenbone", "openvas", "Scanner completo de vulnerabilidades de rede.", None, "openvas"),
        ("Nuclei", "nuclei", "Varredura de vulnerabilidades baseada em templates da comunidade.", None, "nuclei"),
        ("Lynis", "lynis", "Auditoria de segurança e hardening de sistemas Linux/Unix.", None, "lynis"),
        ("Legion", "legion", "Automatiza reconhecimento e varredura de vulnerabilidades em rede.", "legion", None),
        ("SQLmap", "sqlmap", "Detecção e exploração de SQL Injection.", None, "sqlmap"),
        ("Wapiti", "wapiti", "Scanner de vulnerabilidades web caixa-preta.", None, "wapiti"),
        ("Nessus", "—", "Scanner de vulnerabilidades comercial (Tenable), licença própria.", None, "nessus"),
        ("Nikto2 plugins", "nikto", "Extensões de assinaturas para o Nikto.", "nikto", None),
        ("GVM-CLI", "gvm-tools", "Automação em linha de comando do Greenbone Vulnerability Manager.", "gvm-cli", None),
        ("Vuls", "vuls", "Scanner de vulnerabilidades agentless para servidores Linux/rede.", "vuls", None),
        ("YASAT", "yasat", "Auditoria rápida de segurança para sistemas Unix.", "yasat", None),
    ],
    "Web Application Analysis": [
        ("Burp Suite", "burpsuite", "Proxy de interceptação e testes de segurança em apps web.", None, "burpsuite"),
        ("OWASP ZAP", "zaproxy", "Scanner de vulnerabilidades web open-source.", None, "zap"),
        ("Gobuster", "gobuster", "Força bruta de diretórios, arquivos, DNS e vhosts.", None, "gobuster"),
        ("ffuf", "ffuf", "Fuzzing rápido de parâmetros, diretórios e headers HTTP.", None, "ffuf"),
        ("dirb", "dirb", "Força bruta de conteúdo web com wordlists.", "dirb", None),
        ("wfuzz", "wfuzz", "Fuzzing de aplicações web (parâmetros, forms, headers).", "wfuzz", None),
        ("Wappalyzer CLI", "wappalyzer-cli", "Identifica tecnologias/frameworks usados em um site.", "wappalyzer", None),
        ("XSStrike", "xsstrike", "Detecção e fuzzing avançado de XSS.", "xsstrike", None),
        ("Commix", "commix", "Detecção e exploração de command injection.", "commix", None),
        ("WPScan", "wpscan", "Auditoria de segurança para sites WordPress.", "wpscan", None),
        ("JoomScan", "joomscan", "Auditoria de segurança para sites Joomla.", "joomscan", None),
        ("Arachni", "arachni", "Framework de varredura de segurança para aplicações web.", "arachni", None),
        ("testssl.sh", "testssl.sh", "Auditoria de TLS/SSL (protocolos, cifras, certificados).", None, "testssl"),
        ("dirbuster", "dirbuster", "Força bruta de diretórios/arquivos com interface gráfica.", "dirbuster", None),
        ("Skipfish", "skipfish", "Scanner de segurança web ativo e de alta performance.", "skipfish", None),
        ("XSSer", "xsser", "Framework automatizado de detecção/exploração de XSS.", "xsser", None),
        ("Sqlsus", "sqlsus", "Ferramenta de injeção e exploração de MySQL.", "sqlsus", None),
        ("CMSmap", "cmsmap", "Varredura de vulnerabilidades em CMS (WordPress, Joomla, Drupal).", "cmsmap", None),
        ("droopescan", "droopescan", "Varredura de vulnerabilidades em Drupal e outros CMS.", "droopescan", None),
        ("Uniscan", "uniscan", "Scanner de vulnerabilidades web simples e rápido.", "uniscan", None),
    ],
    "Database Assessment": [
        ("SQLmap", "sqlmap", "Também cobre exploração automatizada de bancos via SQLi.", None, "sqlmap"),
        ("sqlninja", "sqlninja", "Exploração de SQL Injection em ambientes Microsoft SQL Server.", "sqlninja", None),
        ("NoSQLMap", "nosqlmap", "Testes de injeção e má configuração em bancos NoSQL.", "nosqlmap", None),
        ("jsql-injection", "jsql-injection", "Cliente gráfico para automatizar detecção de SQL Injection.", "jsql-injection", None),
        ("Oscanner", "oscanner", "Auditoria de segurança em bancos Oracle.", "oscanner", None),
        ("SidGuesser", "oscanner", "Descoberta de SIDs válidos em instâncias Oracle.", "sidguess", None),
        ("Tnscmd10g", "oscanner", "Envia comandos ao TNS Listener do Oracle para reconhecimento.", "tnscmd10g", None),
    ],
    "Password Attacks": [
        ("Hydra", "hydra", "Força bruta de autenticação em dezenas de protocolos/serviços.", None, "hydra"),
        ("John the Ripper", "john", "Quebra de hashes de senha offline.", None, "john"),
        ("Hashcat", "hashcat", "Quebra de hashes acelerada por GPU.", None, "hashcat"),
        ("Medusa", "medusa", "Força bruta paralela de autenticação em rede.", "medusa", None),
        ("CrackMapExec", "crackmapexec", "Pós-exploração e auditoria de credenciais em redes Windows/AD.", "crackmapexec", "crackmapexec"),
        ("Hash-identifier", "hash-identifier", "Identifica o tipo/algoritmo de um hash.", "hash-identifier", None),
        ("CeWL", "cewl", "Gera wordlists customizadas a partir do conteúdo de um site.", "cewl", None),
        ("Crunch", "crunch", "Gerador de wordlists por padrão/charset.", "crunch", None),
        ("Hydra-gtk", "hydra-gtk", "Interface gráfica para o Hydra.", "xhydra", None),
        ("Ophcrack", "ophcrack", "Quebra de senhas Windows via rainbow tables.", "ophcrack", None),
        ("Patator", "patator", "Força bruta multiuso e modular para diversos protocolos.", "patator", None),
        ("THC-pptp-bruter", "thc-pptp-bruter", "Força bruta contra VPNs PPTP.", "thc-pptp-bruter", None),
        ("RSMangler", "rsmangler", "Gera variações de wordlists a partir de palavras-base.", "rsmangler", None),
        ("Wordlists (rockyou etc.)", "wordlists", "Conjunto de wordlists padrão do Kali para ataques de dicionário.", None, None),
    ],
    "Wireless Attacks": [
        ("Aircrack-ng", "aircrack-ng", "Suite completa de auditoria de redes Wi-Fi (captura, WPA/WEP).", None, "aircrack-ng"),
        ("Kismet", "kismet", "Detecção e sniffing de redes sem fio (Wi-Fi, Bluetooth).", "kismet", None),
        ("Reaver", "reaver", "Ataque de força bruta contra WPS.", "reaver", None),
        ("Wifite", "wifite", "Automação de auditoria de redes Wi-Fi usando a suite Aircrack-ng.", "wifite", None),
        ("Fern Wifi Cracker", "fern-wifi-cracker", "Interface gráfica para auditoria de redes Wi-Fi.", "fern-wifi-cracker", None),
        ("Bettercap", "bettercap", "Framework de ataques de rede/MITM e reconhecimento wireless/BLE.", "bettercap", "bettercap"),
        ("Bully", "bully", "Ataque de força bruta contra WPS (alternativa ao Reaver).", "bully", None),
        ("PixieWPS", "pixiewps", "Ataque offline Pixie Dust contra WPS.", "pixiewps", None),
        ("Wash", "reaver", "Detecta pontos de acesso com WPS habilitado.", "wash", None),
        ("MDK4", "mdk4", "Testes de estresse e ataques em redes IEEE 802.11.", "mdk4", None),
        ("Cowpatty", "cowpatty", "Ataque offline contra handshakes WPA-PSK.", "cowpatty", None),
    ],
    "Reverse Engineering": [
        ("Ghidra", "ghidra", "Engenharia reversa e análise de binários (NSA, open-source).", None, "ghidra"),
        ("radare2", "radare2", "Framework de engenharia reversa via linha de comando.", None, "radare2"),
        ("objdump", "binutils", "Desmontagem e inspeção de binários/objetos.", None, "objdump"),
        ("strings", "binutils", "Extrai texto legível de arquivos binários.", None, "strings"),
        ("GDB", "gdb", "Depurador para análise dinâmica de binários.", "gdb", None),
        ("edb-debugger", "edb-debugger", "Depurador com interface gráfica para Linux.", "edb", None),
        ("Cutter", "cutter", "Interface gráfica construída sobre o radare2.", "cutter", None),
        ("PEDA/GEF/pwndbg", "gdb", "Extensões do GDB voltadas a exploração/CTF.", "gdb-peda", None),
        ("Apktool", "apktool", "Engenharia reversa de aplicativos Android (APK).", "apktool", None),
        ("jadx", "jadx", "Descompilador de código Android (DEX para Java legível).", "jadx", None),
        ("Frida", "frida-tools", "Instrumentação dinâmica de binários e apps em tempo real.", "frida", None),
    ],
    "Exploitation Tools": [
        ("Metasploit Framework", "metasploit-framework", "Framework de desenvolvimento e execução de exploits em laboratório.", None, "metasploit"),
        ("SearchSploit", "exploitdb", "Busca offline na base do Exploit-DB.", "searchsploit", "searchsploit"),
        ("BeEF", "beef-xss", "Framework de exploração focado no navegador (XSS/engenharia social).", "beef-xss", None),
        ("SET (Social-Engineer Toolkit)", "set", "Framework de vetores de ataque de engenharia social.", "setoolkit", None),
        ("Armitage", "armitage", "Interface gráfica de colaboração para o Metasploit.", "armitage", None),
        ("MSFvenom", "metasploit-framework", "Geração de payloads para uso em laboratório com o Metasploit.", "msfvenom", None),
        ("RouterSploit", "routersploit", "Framework de exploração voltado a dispositivos embarcados/roteadores.", "routersploit", None),
        ("Social Engineering Toolkit (Fasttrack)", "set", "Automação de exploração combinada a vetores de engenharia social.", "fasttrack", None),
    ],
    "Sniffing & Spoofing": [
        ("Wireshark / tshark", "wireshark", "Captura e inspeção de pacotes de rede em tempo real.", None, "wireshark"),
        ("tcpdump", "tcpdump", "Captura de pacotes via linha de comando.", None, "tcpdump"),
        ("Ettercap", "ettercap-graphical", "Ataques MITM, sniffing e injeção em redes locais.", "ettercap", None),
        ("Bettercap", "bettercap", "MITM moderno, sniffing e manipulação de tráfego.", "bettercap", "bettercap"),
        ("dsniff", "dsniff", "Conjunto de ferramentas clássicas de sniffing de credenciais.", "dsniff", None),
        ("macchanger", "macchanger", "Altera o endereço MAC de uma interface de rede.", "macchanger", None),
        ("Responder", "responder", "Captura de credenciais via spoofing de LLMNR/NBT-NS/mDNS.", "responder", "responder"),
        ("Wireshark CLI (tcpick)", "tcpick", "Reconstrução de streams TCP a partir de captura de tráfego.", "tcpick", None),
        ("dnschef", "dnschef", "Servidor DNS falso configurável para laboratório/testes.", "dnschef", None),
        ("SIPVicious (svmap)", "sipvicious", "Auditoria de segurança em redes VoIP/SIP.", "svmap", None),
    ],
    "Post Exploitation": [
        ("CrackMapExec", "crackmapexec", "Movimentação lateral e auditoria pós-exploração em redes Windows.", "crackmapexec", "crackmapexec"),
        ("Empire", "powershell-empire", "Framework de pós-exploração e C2 para Windows/Linux/macOS.", "powershell-empire", None),
        ("Mimikatz (via Wine)", "mimikatz", "Extração de credenciais em memória no Windows (uso em laboratório).", "mimikatz", None),
        ("Weevely", "weevely", "Web shell em PHP para pós-exploração de servidores web.", "weevely", None),
        ("PowerSploit", "powersploit", "Coleção de módulos PowerShell para pós-exploração.", None, None),
        ("Impacket", "python3-impacket", "Conjunto de scripts Python para protocolos Windows/AD (pós-exploração).", "impacket-scripts", "impacket"),
        ("BloodHound", "bloodhound", "Mapeamento gráfico de caminhos de ataque em Active Directory.", "bloodhound", "bloodhound"),
        ("Evil-WinRM", "evil-winrm", "Shell remoto sobre WinRM para pós-exploração em Windows.", "evil-winrm", None),
    ],
    "Forensics": [
        ("Autopsy", "autopsy", "Plataforma de forense digital (baseada no Sleuth Kit).", None, "autopsy"),
        ("The Sleuth Kit", "sleuthkit", "Ferramentas de linha de comando para análise forense de discos.", "tsk_recover", None),
        ("Volatility 3", "volatility3", "Análise forense de memória (RAM).", None, "volatility"),
        ("ExifTool", "libimage-exiftool-perl", "Leitura/edição de metadados em arquivos e imagens.", None, "exiftool"),
        ("Foremost", "foremost", "Recuperação de arquivos por assinatura (data carving).", "foremost", None),
        ("Binwalk", "binwalk", "Análise e extração de conteúdo embutido em firmwares/binários.", "binwalk", None),
        ("Bulk Extractor", "bulk-extractor", "Extração em massa de artefatos forenses de imagens de disco.", "bulk_extractor", None),
        ("YARA", "yara", "Regras de identificação/classificação de malware e artefatos.", None, "yara"),
        ("Guymager", "guymager", "Aquisição forense de imagens de disco.", "guymager", None),
        ("Chkrootkit", "chkrootkit", "Detecção de rootkits conhecidos em sistemas Linux.", "chkrootkit", None),
        ("rkhunter", "rkhunter", "Auditoria de rootkits, backdoors e exploits locais.", "rkhunter", None),
        ("PDF Parser / peepdf", "peepdf", "Análise de PDFs potencialmente maliciosos.", "peepdf", None),
    ],
    "Reporting Tools": [
        ("Dradis", "dradis", "Colaboração e geração de relatórios de pentest.", "dradis", None),
        ("Faraday", "faraday", "Plataforma colaborativa de gestão de vulnerabilidades e relatórios.", "faraday-server", None),
        ("CutyCapt", "cutycapt", "Captura de tela de páginas web para evidências.", "cutycapt", None),
        ("MagicTree", "magictree", "Consolidação de dados de varredura para relatórios.", "magictree", None),
        ("EyeWitness", "eyewitness", "Captura de tela em massa e relatório de hosts web/RDP/VNC.", "eyewitness", None),
    ],
    "Social Engineering Tools": [
        ("SET (Social-Engineer Toolkit)", "set", "Vetores de ataque de engenharia social (phishing, clonagem de site).", "setoolkit", None),
        ("Gophish", "gophish", "Plataforma de simulação de phishing para treinamento/conscientização.", "gophish", None),
        ("King Phisher", "king-phisher", "Simulação de campanhas de phishing para times de segurança.", "king-phisher", None),
        ("BeEF", "beef-xss", "Exploração do navegador da vítima após engenharia social.", "beef-xss", None),
        ("Evilginx2", "evilginx2", "Proxy reverso para simulações avançadas de phishing/MFA (uso em laboratório).", "evilginx", None),
    ],
    "Cloud / Container / Supply Chain": [
        ("Prowler", "prowler", "Auditoria de postura de segurança em AWS/Azure/GCP.", "prowler", None),
        ("ScoutSuite", "scoutsuite", "Auditoria de configuração de ambientes cloud.", "scout", None),
        ("kube-bench", "kube-bench", "Verifica configurações Kubernetes contra benchmarks CIS.", "kube-bench", None),
        ("kube-hunter", "kube-hunter", "Identifica exposições de segurança em clusters Kubernetes de laboratório.", "kube-hunter", None),
        ("Kubescape", "kubescape", "Análise de risco e conformidade para Kubernetes.", "kubescape", None),
        ("Falco", "falco", "Detecção de comportamento anômalo em hosts e containers.", "falco", None),
        ("Syft", "syft", "Gera SBOM de imagens e diretórios para inventário de componentes.", "syft", None),
        ("Grype", "grype", "Identifica vulnerabilidades conhecidas em SBOMs/imagens.", "grype", None),
        ("Cosign", "cosign", "Verificação e assinatura de artefatos de software.", "cosign", None),
        ("TruffleHog", "trufflehog", "Busca de possíveis secrets expostos em código e repositórios.", "trufflehog", None),
        ("Checkov", "checkov", "Auditoria de segurança de Infrastructure as Code.", "checkov", None),
        ("SOPS", "sops", "Gerenciamento seguro de arquivos de configuração criptografados.", "sops", None),
    ],
 }


# Expansão de catálogo: referências e utilitários adicionais para o laboratório.
# Itens sem integração continuam como referência/detecção local; não são
# apresentados como executáveis quando o servidor não os possui.
_EXTRA_TOOLS = {
    "Web Application Analysis": [
        ("Burp Suite", "burpsuite", "Proxy e plataforma de teste de aplicações web em laboratório autorizado.", "burpsuite", None),
        ("OWASP ZAP", "zaproxy", "Proxy e scanner de segurança web para testes autorizados.", "zaproxy", None),
        ("Wapiti", "wapiti", "Scanner de aplicações web para identificar classes comuns de falhas.", "wapiti", None),
        ("WhatWeb", "whatweb", "Fingerprinting de tecnologias web.", "whatweb", None),
        ("Arjun", "arjun", "Descoberta de parâmetros HTTP para auditoria de APIs e aplicações.", "arjun", None),
        ("Dalfox", "dalfox", "Scanner focado em superfícies XSS para ambientes de teste.", "dalfox", None),
        ("HTTPx", "httpx-toolkit", "Verificação e enriquecimento de endpoints HTTP em inventários autorizados.", "httpx", "httpx"),
        ("Katana", "katana", "Crawler moderno para descoberta de rotas e recursos em aplicações autorizadas.", "katana", None),
    ],
    "Reverse Engineering": [
        ("Ghidra", "ghidra", "Engenharia reversa e análise estática de binários.", "ghidra", None),
        ("Radare2", "radare2", "Framework de engenharia reversa e análise de binários.", "r2", None),
        ("Cutter", "cutter", "Interface gráfica para análise de binários com Radare2.", "cutter", None),
        ("Rizin", "rizin", "Framework de engenharia reversa para análise de executáveis.", "rz", None),
        ("GDB", "gdb", "Depuração de programas nativos em laboratório.", "gdb", None),
        ("strace", "strace", "Observação de chamadas de sistema para diagnóstico e análise.", "strace", None),
    ],
    "Forensics": [
        ("Plaso / log2timeline", "plaso", "Construção de linhas do tempo forenses a partir de artefatos.", "log2timeline.py", None),
        ("Timesketch", "timesketch", "Investigação colaborativa de timelines forenses.", "timesketch", None),
        ("SIFT utilities", "sleuthkit", "Conjunto de utilitários de investigação forense.", "mmls", None),
        ("Lynis", "lynis", "Auditoria de hardening e configuração de sistemas Linux.", "lynis", None),
    ],
    "Database Assessment": [
        ("SQLmap", "sqlmap", "Automação de testes de SQL injection em ambientes autorizados.", "sqlmap", None),
        ("SQLiteBrowser", "sqlitebrowser", "Inspeção de bancos SQLite durante análise e desenvolvimento.", "sqlitebrowser", None),
        ("MDBTools", "mdbtools", "Leitura de bancos Microsoft Access para análise de dados.", "mdb-tables", None),
    ],
    "Password Attacks": [
        ("John the Ripper", "john", "Auditoria offline de hashes de senha em laboratório autorizado.", "john", None),
        ("Hashcat", "hashcat", "Auditoria de hashes e testes de força de senha offline.", "hashcat", None),
        ("CeWL", "cewl", "Geração de wordlists a partir de conteúdo autorizado para testes.", "cewl", None),
        ("Hydra", "hydra", "Auditoria de autenticação em serviços sob autorização.", "hydra", None),
    ],
    "Wireless Attacks": [
        ("Aircrack-ng", "aircrack-ng", "Suite de análise e auditoria de redes Wi-Fi em laboratório.", "aircrack-ng", None),
        ("Kismet", "kismet", "Detecção e monitoramento passivo de redes sem fio.", "kismet", None),
        ("Wifite", "wifite", "Automação de auditorias Wi-Fi em ambientes autorizados.", "wifite", None),
    ],
    "Exploitation Tools": [
        ("Metasploit Framework", "metasploit-framework", "Framework para validação de vulnerabilidades em laboratórios autorizados.", "msfconsole", None),
        ("SearchSploit", "exploitdb", "Pesquisa local no Exploit-DB para estudo e validação defensiva.", "searchsploit", "searchsploit"),
        ("Commix", "commix", "Ferramenta de teste de command injection em aplicações autorizadas.", "commix", None),
    ],
    "Sniffing & Spoofing": [
        ("Scapy", "python3-scapy", "Manipulação e análise de pacotes para pesquisa e laboratório.", "scapy", None),
        ("Mitmproxy", "mitmproxy", "Proxy interativo para depuração e testes de tráfego autorizados.", "mitmproxy", None),
    ],
    "Reporting Tools": [
        ("Pwndoc", "pwndoc", "Gestão e geração de relatórios de pentest.", "pwndoc", None),
        ("Serpico", "serpico", "Geração de relatórios de testes de segurança.", "serpico", None),
        ("Dradis", "dradis", "Colaboração e consolidação de achados de pentest.", "dradis", None),
        ("Faraday", "faraday", "IDE colaborativa para pentest e gestão de vulnerabilidades.", "faraday-client", None),
    ],
    "OSINT / Recon Extra": [
        ("Sherlock", "sherlock", "Busca de username em dezenas de redes sociais (OSINT).", "sherlock", None),
        ("Maigret", "maigret", "OSINT de usernames com relatórios ricos.", "maigret", None),
        ("Photon", "photon", "Crawler OSINT para extrair URLs, e-mails e arquivos.", "photon", None),
        ("Holehe", "holehe", "Verifica se um e-mail está registrado em serviços online.", "holehe", None),
        ("Social-Analyzer", "social-analyzer", "Análise de perfis e presença digital.", "social-analyzer", None),
        ("Metagoofil", "metagoofil", "Extração de metadados de documentos públicos.", "metagoofil", None),
        ("ExifTool", "libimage-exiftool-perl", "Leitura/escrita de metadados em arquivos (forense/OSINT).", "exiftool", "exiftool"),
        ("FOCA", "foca", "Análise de metadados e descoberta de informações em documentos.", "foca", None),
    ],
    "Cloud / Container Security": [
        ("ScoutSuite", "scoutsuite", "Auditoria multi-cloud de configurações de segurança.", "scout", None),
        ("Prowler", "prowler", "Avaliação de segurança e conformidade em AWS/Azure/GCP.", "prowler", None),
        ("Trivy", "trivy", "Scanner de CVEs e misconfig em imagens, FS e IaC.", "trivy", None),
        ("Grype", "grype", "Scanner de vulnerabilidades em containers e SBOMs.", "grype", None),
        ("Hadolint", "hadolint", "Linter de Dockerfiles para boas práticas de segurança.", "hadolint", None),
        ("Checkov", "checkov", "Scanner de IaC (Terraform, K8s, CloudFormation) para misconfig.", "checkov", None),
        ("Kube-hunter", "kube-hunter", "Descoberta de riscos em clusters Kubernetes (lab autorizado).", "kube-hunter", None),
        ("Kube-bench", "kube-bench", "CIS benchmark para Kubernetes.", "kube-bench", None),
    ],
    "Binary / Malware Analysis": [
        ("Volatility 3", "volatility3", "Análise de memória (RAM) para forense e malware.", "vol", None),
        ("Binwalk", "binwalk", "Análise e extração de firmware e arquivos compostos.", "binwalk", None),
        ("Foremost", "foremost", "Carving de arquivos a partir de dumps.", "foremost", None),
        ("Scalpel", "scalpel", "Carving de arquivos baseado em headers/footers.", "scalpel", None),
        ("strings", "binutils", "Extração de strings legíveis de binários.", "strings", "strings"),
        ("objdump", "binutils", "Desmontagem e inspeção de objetos ELF/PE.", "objdump", "objdump"),
        ("xxd", "xxd", "Dump hexadecimal para análise de arquivos.", "xxd", None),
        ("YARA", "yara", "Matching de regras em arquivos suspeitos.", "yara", None),
    ],
    "Network Defense Extra": [
        ("tcpdump", "tcpdump", "Captura de pacotes em linha de comando.", "tcpdump", None),
        ("tshark", "tshark", "Wireshark em CLI para análise de PCAP.", "tshark", None),
        ("ngrep", "ngrep", "grep em tráfego de rede.", "ngrep", None),
        ("iptables", "iptables", "Firewall e filtragem de pacotes no Linux.", "iptables", None),
        ("nftables", "nftables", "Firewall moderno do kernel Linux.", "nft", None),
        ("fail2ban", "fail2ban", "Banimento automático de IPs após falhas de auth.", "fail2ban-client", None),
    ],
}
for _category, _items in _EXTRA_TOOLS.items():
    CATALOG.setdefault(_category, []).extend(_items)


def _local_detect(cmd):
    path = shutil.which(cmd)
    return {"installed": bool(path), "path": path, "version": None}


def status_all():
    """Status de cada item do catálogo — detecção real, sem simulação.

    - Itens com tool_id reaproveitam o Tool Adapter (detecção + versão).
    - Itens com bin fazem apenas shutil.which local (rápido, sem exec).
    - Itens sem bin nem tool_id (ferramentas gráficas/comerciais) ficam
      como "reference" — não há como detectar de forma útil num servidor
      web headless, então nem tentamos fingir.
    """
    adapter_status = {s["id"]: s for s in tool_adapter.status_all()}
    out = {}
    for category, items in CATALOG.items():
        rows = []
        for name, pkg, desc, cmd, tool_id in items:
            if tool_id and tool_id in adapter_status:
                a = adapter_status[tool_id]
                rows.append({
                    "name": name, "package": pkg, "desc": desc, "tool_id": tool_id,
                    "installed": a["installed"], "version": a.get("version"),
                    "integrated": True, "runnable": a.get("runnable", False),
                    "status": a["status"], "install_hint": a.get("install_hint"),
                })
            elif cmd:
                d = _local_detect(cmd)
                rows.append({
                    "name": name, "package": pkg, "desc": desc, "tool_id": None,
                    "installed": d["installed"], "version": None,
                    "integrated": False, "runnable": False,
                    "status": "installed" if d["installed"] else "not_installed",
                    "install_hint": f"Debian/Ubuntu (Kali): sudo apt install {pkg}" if pkg != "—" else None,
                })
            else:
                rows.append({
                    "name": name, "package": pkg, "desc": desc, "tool_id": None,
                    "installed": None, "version": None,
                    "integrated": False, "runnable": False,
                    "status": "reference",
                    "install_hint": f"sudo apt install {pkg}" if pkg != "—" else "Licença/instalação própria do fabricante.",
                })
        out[category] = rows
    return out


def counts():
    total = sum(len(v) for v in CATALOG.values())
    integrated = sum(1 for items in CATALOG.values() for i in items if i[4])
    return {"total": total, "categories": len(CATALOG), "integrated": integrated}
