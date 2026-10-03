"""Tool Adapter / Tool Manager — integração real com ferramentas externas.

Este módulo NUNCA finge que uma ferramenta está instalada. Para cada
ferramenta ele:
  1. detecta se o binário existe no PATH (shutil.which);
  2. se existir, roda `--version` (ou equivalente) pra pegar a versão real;
  3. se não existir, devolve status "not_installed" + instruções de como
     instalar, e a ferramenta correspondente no Tool Registry recusa a
     execução em vez de simular um resultado.

Execução real só acontece:
  * contra um host que já esteja em services.scope (alvo autorizado);
  * com timeout curto e argumentos fixos (sem shell=True, sem concatenar
    input do usuário em string de shell);
  * capturando stdout/stderr e devolvendo tanto o raw output quanto uma
    lista de findings já no formato do Evidence Center.
"""
import re
import shutil
import subprocess
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from services import scope, evidence

# ---------------------------------------------------------------- execução isolada
def _safe_env():
    env = {}
    path = os.getenv("PATH", "")
    if path:
        env["PATH"] = path
    for key in ("HOME", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP"):
        if os.getenv(key):
            env[key] = os.getenv(key)
    return env

def _run_external(argv, timeout=60, **kwargs):
    """Executa binário sem shell, em diretório temporário e com limites POSIX."""
    if not isinstance(argv, (list, tuple)) or not argv or any(not isinstance(x, str) for x in argv):
        raise ValueError("Argumentos inválidos para ferramenta externa.")
    run_kwargs = dict(kwargs)
    run_kwargs.setdefault("capture_output", True)
    run_kwargs.setdefault("text", True)
    run_kwargs["timeout"] = min(max(int(timeout), 1), 180)
    run_kwargs["shell"] = False
    run_kwargs["env"] = _safe_env()
    run_kwargs["start_new_session"] = True
    with tempfile.TemporaryDirectory(prefix="tf-tool-") as cwd:
        run_kwargs["cwd"] = cwd
        if os.name == "posix":
            try:
                import resource
                def _limits():
                    resource.setrlimit(resource.RLIMIT_CPU, (min(run_kwargs["timeout"], 120), min(run_kwargs["timeout"] + 5, 125)))
                    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
                    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
                run_kwargs["preexec_fn"] = _limits
            except Exception:
                pass
        return subprocess.run(list(argv), **run_kwargs)

# ---------------------------------------------------------------- catálogo
# Cada entrada descreve como detectar a ferramenta e como rodá-la.
TOOLS = {
    "nmap": {
        "label": "Nmap",
        "bin": "nmap",
        "version_args": ["-V"],
        "version_re": r"Nmap version (\S+)",
        "install_hint": "Debian/Ubuntu: sudo apt install nmap  ·  macOS: brew install nmap",
        "docs": "https://nmap.org/book/inst-linux.html",
        "desc": "Escaneia portas e serviços abertos de um alvo de rede — a base de qualquer reconhecimento em pentest.",
        "category": "Network", "scope": "network (alvo autorizado)",
    },
    "gobuster": {
        "label": "Gobuster",
        "bin": "gobuster",
        "version_args": ["version"],
        "version_re": r"gobuster\s+(?:version\s+)?v?(\S+)",
        "install_hint": "go install github.com/OJ/gobuster/v3@latest  ·  ou baixe um binário em github.com/OJ/gobuster/releases",
        "docs": "https://github.com/OJ/gobuster",
        "desc": "Força bruta de diretórios/arquivos/subdomínios escondidos em um site — acha caminhos que não estão linkados em lugar nenhum.",
        "category": "Web Security", "scope": "network (alvo autorizado)",
    },
    "nikto": {
        "label": "Nikto",
        "bin": "nikto",
        "version_args": ["-Version"],
        "version_re": r"Nikto\s+v?(\S+)",
        "install_hint": "Debian/Ubuntu: sudo apt install nikto  ·  ou git clone https://github.com/sullo/nikto",
        "docs": "https://github.com/sullo/nikto",
        "desc": "Varre um servidor web procurando arquivos perigosos, configs expostas e versões desatualizadas conhecidas.",
        "category": "Web Security", "scope": "network (alvo autorizado)",
    },
    "wireshark": {
        "label": "Wireshark (tshark)",
        "bin": "tshark",
        "version_args": ["--version"],
        "version_re": r"TShark \(Wireshark\)\s+(\S+)",
        "install_hint": "Debian/Ubuntu: sudo apt install tshark  ·  macOS: brew install wireshark",
        "docs": "https://www.wireshark.org/download.html",
        "no_scan": "Captura de pacotes exige acesso à interface de rede e não roda por chat; "
                   "use a versão desktop do Wireshark localmente.",
        "desc": "Captura e inspeciona pacotes de rede em tempo real — permite ver exatamente o que trafega entre dois pontos.",
        "category": "Network", "scope": "host local (interface de rede)",
    },
    "burpsuite": {
        "label": "Burp Suite",
        "bin": "burpsuite",
        "version_args": ["--version"],
        "version_re": r"(\d+\.\d+(?:\.\d+)?)",
        "install_hint": "Baixe em portswigger.net/burp — não tem instalação via apt/brew padrão.",
        "docs": "https://portswigger.net/burp",
        "no_scan": "Burp Suite é uma ferramenta gráfica/proxy; não há automação segura via chat aqui — "
                   "use-o manualmente e cole o output para eu interpretar.",
        "desc": "Proxy que intercepta requisições HTTP para você inspecionar/alterar antes de enviar — o canivete suíço de teste de app web.",
        "category": "Web Security", "scope": "network (alvo autorizado, via proxy manual)",
    },
    "zap": {
        "label": "OWASP ZAP",
        "bin": "zap.sh",
        "version_args": ["-version"],
        "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "sudo snap install zaproxy --classic  ·  ou baixe em zaproxy.org/download",
        "docs": "https://www.zaproxy.org/download/",
        "no_scan": "ZAP tem API própria (daemon); ainda não conectado aqui — detecção de instalação apenas.",
        "desc": "Scanner automatizado de vulnerabilidades web (XSS, SQLi, headers, etc.), alternativa open-source ao Burp.",
        "category": "Web Security", "scope": "network (alvo autorizado)",
    },
    "sqlmap": {
        "label": "SQLMap",
        "bin": "sqlmap",
        "version_args": ["--version"],
        "version_re": r"(\d+\.\d+(?:\.\d+)?(?:#\S+)?)",
        "install_hint": "pip install sqlmap  ·  ou git clone https://github.com/sqlmapproject/sqlmap",
        "docs": "https://github.com/sqlmapproject/sqlmap",
        "no_scan": "Ferramenta de exploração ativa de SQL Injection (detecta E extrai dados). Por decisão do "
                   "produto (ver SECURITY_POLICY.md) o Tristan Thorne não dispara exploração automatizada por chat "
                   "— aqui só detectamos se está instalado. Rode manualmente, na sua máquina, só contra alvo "
                   "que você tenha autorização explícita para testar. Para uma varredura heurística e NÃO "
                   "destrutiva de candidatos a SQLi, use 'OWASP Top 10 Scanner' já existente no Cyber Lab.",
        "desc": "Detecta e explora automaticamente SQL Injection, podendo extrair dados de um banco vulnerável.",
        "category": "Web Security", "scope": "network (alvo autorizado, execução manual fora do chat)",
    },
    "ffuf": {
        "label": "ffuf",
        "bin": "ffuf",
        "version_args": ["-V"],
        "version_re": r"ffuf version:\s*(\S+)",
        "install_hint": "go install github.com/ffuf/ffuf/v2@latest  ·  ou baixe em github.com/ffuf/ffuf/releases",
        "docs": "https://github.com/ffuf/ffuf",
        "desc": "Fuzzer de caminhos/parâmetros HTTP rápido — parecido com o Gobuster, mas mais flexível (headers, POST, filtros).",
        "category": "Web Security", "scope": "network (alvo autorizado)",
    },
    "whatweb": {
        "label": "WhatWeb",
        "bin": "whatweb",
        "version_args": ["--version"],
        "version_re": r"WhatWeb version (\S+)",
        "install_hint": "Debian/Ubuntu: sudo apt install whatweb  ·  ou git clone https://github.com/urbanadventurer/WhatWeb",
        "docs": "https://github.com/urbanadventurer/WhatWeb",
        "desc": "Identifica tecnologias de um site (CMS, framework, servidor, analytics) por assinaturas — reconhecimento passivo.",
        "category": "OSINT/Recon", "scope": "network (alvo autorizado)",
    },
    "testssl": {
        "label": "testssl.sh",
        "bin": "testssl.sh",
        "version_args": ["--version"],
        "version_re": r"testssl\.sh\s+(\S+)",
        "install_hint": "git clone --depth 1 https://github.com/drwetter/testssl.sh  ·  brew install testssl",
        "docs": "https://testssl.sh/",
        "desc": "Audita TLS/SSL em profundidade: protocolos legados, cifras fracas, certificado, Heartbleed e outras CVEs conhecidas de TLS.",
        "category": "Network", "scope": "network (alvo autorizado)",
    },
    "lynis": {
        "label": "Lynis",
        "bin": "lynis",
        "version_args": ["--version"],
        "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "Debian/Ubuntu: sudo apt install lynis  ·  git clone https://github.com/CISOfy/lynis",
        "docs": "https://cisofy.com/lynis/",
        "no_scan": "Auditoria de hardening do PRÓPRIO sistema operacional local (não de um alvo de rede); "
                   "rode `lynis audit system` diretamente no host que você quer avaliar.",
        "desc": "Audita a configuração/hardening de um sistema Linux/Unix local e dá uma nota de segurança com recomendações.",
        "category": "Vulnerability Assessment", "scope": "host local (auditoria do próprio sistema)",
    },
    "ghidra": {
        "label": "Ghidra",
        "bin": "ghidraRun",
        "version_args": ["-version"],
        "version_re": r"(\d+\.\d+(?:\.\d+)?)",
        "install_hint": "Baixe em ghidra-sre.org (NSA) — extraia e rode ghidraRun; requer JDK 17+.",
        "docs": "https://ghidra-sre.org/",
        "no_scan": "Engenharia reversa é interativa e gráfica (desmontagem, decompilação); não roda em lote via chat. "
                   "Abra o binário localmente no Ghidra.",
        "desc": "Suíte de engenharia reversa (desmontador/decompilador) para analisar binários — usado em análise de malware e CTF de reverse.",
        "category": "Reverse Engineering", "scope": "arquivo local (binário)",
    },
    "autopsy": {
        "label": "Autopsy",
        "bin": "autopsy",
        "version_args": ["-v"],
        "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "Baixe em sleuthkit.org/autopsy (inclui The Sleuth Kit)",
        "docs": "https://www.sleuthkit.org/autopsy/",
        "no_scan": "Plataforma forense gráfica para analisar imagens de disco; abra a imagem localmente no Autopsy, "
                   "não há automação por chat aqui.",
        "desc": "Interface forense sobre o The Sleuth Kit — analisa imagens de disco em busca de arquivos apagados, timeline e artefatos.",
        "category": "Forensics", "scope": "arquivo local (imagem de disco)",
    },
    "openvas": {
        "label": "OpenVAS / Greenbone (GVM)",
        "bin": "gvm-cli",
        "version_args": ["--version"],
        "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "Debian/Ubuntu: sudo apt install gvm  ·  docs.greenbone.net (setup do GVM completo)",
        "docs": "https://www.greenbone.net/en/community-edition/",
        "no_scan": "Scanner de vulnerabilidades de rede completo com manager/feed próprios (GVM); configure e rode "
                   "scans pela interface web do Greenbone — aqui só detectamos o cliente `gvm-cli`.",
        "desc": "Scanner de vulnerabilidades de rede open-source com base de CVEs própria e feed atualizado (NVT).",
        "category": "Vulnerability Assessment", "scope": "network (alvo autorizado, via console GVM próprio)",
    },
    "nessus": {
        "label": "Nessus",
        "bin": "nessuscli",
        "version_args": ["--version"],
        "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "Produto comercial (Tenable) — baixe em tenable.com/downloads, precisa de licença.",
        "docs": "https://www.tenable.com/products/nessus",
        "no_scan": "Scanner de vulnerabilidades comercial com daemon/UI própria; configure e rode scans pelo "
                   "painel web do Nessus — aqui só detectamos o CLI `nessuscli`, se instalado.",
        "desc": "Scanner de vulnerabilidades comercial (Tenable), muito usado em auditorias corporativas formais.",
        "category": "Vulnerability Assessment", "scope": "network (alvo autorizado, via console Nessus próprio)",
    },

    # -------------------------------------------------- Blue Team / SOC / DFIR
    # (só detecção + orientação: são agentes/plataformas de servidor —
    #  nunca fazem sentido "rodar contra um alvo" disparados pelo chat)
    "zeek": {
        "label": "Zeek", "bin": "zeek",
        "version_args": ["--version"], "version_re": r"zeek version (\S+)",
        "install_hint": "Debian/Ubuntu: sudo apt install zeek  ·  docs.zeek.org/en/stable/install.html",
        "docs": "https://zeek.org/",
        "no_scan": "Zeek monitora tráfego ao vivo numa interface de rede; configure e rode como serviço, "
                   "não via chat. Aqui só detectamos se está instalado.",
        "desc": "Monitora tráfego de rede ao vivo e gera logs estruturados (conexões, DNS, HTTP) para detectar comportamento anômalo.",
        "category": "Network", "scope": "host local (serviço de monitoramento)",
    },
    "suricata": {
        "label": "Suricata", "bin": "suricata",
        "version_args": ["-V"], "version_re": r"Suricata version (\S+)",
        "install_hint": "Debian/Ubuntu: sudo apt install suricata  ·  suricata.io/download",
        "docs": "https://suricata.io/",
        "no_scan": "IDS/IPS de rede — roda como serviço com regras próprias, fora do escopo de execução via chat.",
        "desc": "Sistema de detecção/prevenção de intrusão (IDS/IPS) — compara tráfego contra regras de ataques conhecidos.",
        "category": "Network", "scope": "host local (serviço IDS/IPS)",
    },
    "wazuh": {
        "label": "Wazuh (agent)", "bin": "wazuh-agentd",
        "version_args": ["-V"], "version_re": r"Wazuh v(\S+)",
        "install_hint": "documentation.wazuh.com/current/installation-guide (manager + agent)",
        "docs": "https://wazuh.com/",
        "no_scan": "SIEM/HIDS com manager próprio; detecção de instalação do agente local apenas.",
        "desc": "Agente de SIEM/HIDS: coleta logs e eventos do host e manda para um painel central correlacionar.",
        "category": "Blue Team", "scope": "host local (agente) / manager dedicado",
    },
    "osquery": {
        "label": "osquery", "bin": "osqueryi",
        "version_args": ["--version"], "version_re": r"osqueryi version (\S+)",
        "install_hint": "Debian/Ubuntu: consulte osquery.io/downloads  ·  brew install osquery",
        "docs": "https://osquery.io/",
        "no_scan": "Consultas SQL sobre o próprio endpoint; use o osqueryi local — não expomos shell arbitrário via chat.",
        "desc": "Permite rodar consultas tipo SQL sobre o próprio sistema operacional (processos, arquivos, usuários) para investigação.",
        "category": "Blue Team", "scope": "host local (endpoint)",
    },
    "yara": {
        "label": "YARA", "bin": "yara",
        "version_args": ["--version"], "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "Debian/Ubuntu: sudo apt install yara  ·  pip install yara-python",
        "docs": "https://virustotal.github.io/yara/",
        "no_scan": "Motor de regras de detecção de malware; use suas regras .yar contra arquivos locais fora do chat. "
                   "Para triagem rápida de texto colado, use a ferramenta 'Scanner de Padrões de Malware' já existente no Cyber Lab.",
        "desc": "Motor de regras para identificar malware por padrões binários/textuais — muito usado em resposta a incidente.",
        "category": "Forensics", "scope": "arquivo/host local",
    },
    "sigma": {
        "label": "Sigma (sigma-cli)", "bin": "sigma",
        "version_args": ["--version"], "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "pip install sigma-cli",
        "docs": "https://github.com/SigmaHQ/sigma",
        "no_scan": "Conversor de regras de detecção para SIEM (ex.: para consultas do seu SIEM); rode localmente "
                   "sobre suas regras — não há SIEM real conectado aqui.",
        "desc": "Converte regras de detecção num formato único que dá pra usar em vários SIEMs diferentes.",
        "category": "Blue Team", "scope": "arquivo/host local",
    },
    "volatility": {
        "label": "Volatility 3", "bin": "vol",
        "version_args": ["--version"], "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "pip install volatility3",
        "docs": "https://volatilityfoundation.org/",
        "no_scan": "Análise de dumps de memória (.mem/.raw) locais; rode manualmente sobre o dump — "
                   "não fazemos upload/captura de memória de terceiros por aqui.",
        "desc": "Analisa um dump de memória RAM para achar processos, conexões e artefatos que só existem 'ao vivo', não em disco.",
        "category": "Forensics", "scope": "arquivo local (dump de memória)",
    },
    "thehive": {
        "label": "TheHive (thehive4py)", "bin": "thehive4py",
        "version_args": ["--version"], "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "pip install thehive4py  ·  servidor: docs.strangebee.com",
        "docs": "https://strangebee.com/thehive/",
        "no_scan": "Plataforma de gestão de incidentes (case management); precisa de um servidor TheHive próprio — "
                   "aqui só detectamos o cliente Python, se instalado.",
        "desc": "Plataforma de gestão de casos/incidentes de segurança (ticket, evidência, timeline) para um time de SOC.",
        "category": "Blue Team", "scope": "serviço dedicado (case management)",
    },
    "misp": {
        "label": "MISP (pymisp)", "bin": "pymisp",
        "version_args": ["--version"], "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "pip install pymisp  ·  servidor: misp-project.org/download",
        "docs": "https://www.misp-project.org/",
        "no_scan": "Plataforma de threat intel compartilhada; precisa de instância MISP própria — "
                   "aqui só detectamos o cliente Python, se instalado.",
        "desc": "Plataforma de compartilhamento de inteligência de ameaças (IOCs, indicadores) entre organizações.",
        "category": "OSINT/Recon", "scope": "serviço dedicado (threat intel)",
    },

    # -------------------------------------------------- Secure Coding
    "semgrep": {
        "label": "Semgrep", "bin": "semgrep",
        "version_args": ["--version"], "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "pip install semgrep  ·  brew install semgrep",
        "docs": "https://semgrep.dev/",
        "no_scan": "SAST de código-fonte; para uma revisão já integrada ao chat use a ferramenta "
                   "'Source Code Security Analyzer' do Cyber Lab. Rode o CLI localmente para o projeto inteiro.",
        "desc": "SAST: lê o código-fonte e aponta padrões perigosos (injeção, segredo hardcoded, lógica insegura) sem executar nada.",
        "category": "Vulnerability Assessment", "scope": "código local (repositório)",
    },
    "trivy": {
        "label": "Trivy", "bin": "trivy",
        "version_args": ["--version"], "version_re": r"Version:\s*(\S+)",
        "install_hint": "sudo apt install trivy  ·  brew install trivy  ·  aquasecurity.github.io/trivy",
        "docs": "https://aquasecurity.github.io/trivy/",
        "no_scan": "Scanner de vulnerabilidades em imagens de container e dependências; rode localmente contra "
                   "sua imagem/projeto — não construímos/baixamos imagens de terceiros por aqui.",
        "desc": "Procura vulnerabilidades conhecidas (CVEs) em imagens de container e nas dependências do projeto.",
        "category": "Vulnerability Assessment", "scope": "imagem/dependências locais",
    },
    "checkov": {
        "label": "Checkov", "bin": "checkov",
        "version_args": ["--version"], "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "pip install checkov",
        "docs": "https://www.checkov.io/",
        "no_scan": "Análise estática de Infra-as-Code (Terraform, CloudFormation, k8s); rode localmente "
                   "sobre seus arquivos de IaC.",
        "desc": "Audita arquivos de infraestrutura como código (Terraform, Kubernetes) procurando configuração insegura.",
        "category": "Vulnerability Assessment", "scope": "código local (IaC)",
    },
    "dependency-check": {
        "label": "OWASP Dependency-Check", "bin": "dependency-check.sh",
        "version_args": ["--version"], "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "owasp.org/www-project-dependency-check (binário) ou brew install dependency-check",
        "docs": "https://owasp.org/www-project-dependency-check/",
        "no_scan": "Identifica dependências com CVEs conhecidos; para dependências declaradas (requirements.txt/"
                   "package.json) use já a ferramenta 'Dependency Analyzer' do Cyber Lab, ou rode o CLI localmente.",
        "desc": "Cruza as dependências declaradas do projeto com bancos de vulnerabilidades conhecidas (CVE).",
        "category": "Vulnerability Assessment", "scope": "código local (dependências)",
    },
    "exiftool": {
        "label": "ExifTool", "bin": "exiftool", "version_args": ["-ver"],
        "version_re": r"(\d+(?:\.\d+)+)",
        "install_hint": "Debian/Ubuntu: sudo apt install libimage-exiftool-perl  ·  macOS: brew install exiftool",
        "docs": "https://exiftool.org/",
        "no_scan": "Ferramenta local de metadados; use-a manualmente sobre arquivos do seu laboratório.",
        "desc": "Extrai e inspeciona metadados de imagens, documentos e outros arquivos.",
        "category": "Forensics", "scope": "arquivo local",
    },
    "strings": {
        "label": "strings", "bin": "strings", "version_args": ["--version"],
        "version_re": r"GNU strings|strings \(GNU",
        "install_hint": "Linux: normalmente vem com binutils  ·  macOS: xcode-select --install",
        "docs": "https://sourceware.org/binutils/",
        "no_scan": "Utilitário local para inspeção estática; use-o sobre arquivos do seu laboratório.",
        "desc": "Extrai sequências legíveis de um arquivo para triagem estática.",
        "category": "Reverse Engineering", "scope": "arquivo local",
    },
    "objdump": {
        "label": "objdump", "bin": "objdump", "version_args": ["--version"],
        "version_re": r"GNU objdump|objdump \(GNU",
        "install_hint": "Linux: sudo apt install binutils  ·  macOS: brew install binutils",
        "docs": "https://sourceware.org/binutils/",
        "no_scan": "Utilitário local para inspeção/disassembly; use-o sobre arquivos do seu laboratório.",
        "desc": "Inspeciona cabeçalhos e desmonta partes de binários para análise estática.",
        "category": "Reverse Engineering", "scope": "arquivo local",
    },

    # -------------------------------------------------- Network (novas)
    "masscan": {
        "label": "Masscan", "bin": "masscan",
        "version_args": ["--version"], "version_re": r"Masscan version (\S+)",
        "install_hint": "Debian/Ubuntu: sudo apt install masscan  ·  git clone https://github.com/robertdavidgraham/masscan",
        "docs": "https://github.com/robertdavidgraham/masscan",
        "no_scan": "Scanner de portas de altíssima velocidade, feito para varrer faixas inteiras de IP; por poder "
                   "gerar tráfego agressivo mesmo contra um único alvo autorizado, aqui é só detecção. Para "
                   "varredura de portas via chat use o Nmap já integrado.",
        "desc": "Varre milhões de portas/IPs por segundo — a versão 'industrial' de um port scanner.",
        "category": "Network", "scope": "network (alvo autorizado, execução manual fora do chat)",
    },
    "tcpdump": {
        "label": "tcpdump", "bin": "tcpdump",
        "version_args": ["--version"], "version_re": r"tcpdump version (\S+)",
        "install_hint": "Debian/Ubuntu: sudo apt install tcpdump  ·  macOS: já vem instalado",
        "docs": "https://www.tcpdump.org/",
        "no_scan": "Captura de pacotes exige acesso à interface de rede e privilégio elevado; rode localmente "
                   "no host, não via chat.",
        "desc": "Captura pacotes de rede em modo texto direto do terminal — a versão CLI do que o Wireshark mostra na GUI.",
        "category": "Network", "scope": "host local (interface de rede)",
    },
    "sslyze": {
        "label": "SSLyze", "bin": "sslyze",
        "version_args": ["--version"], "version_re": r"(\d+\.\d+(?:\.\d+)?)",
        "install_hint": "pip install sslyze",
        "docs": "https://github.com/nabla-c0d3/sslyze",
        "no_scan": "Auditoria de TLS alternativa; para uma auditoria já integrada ao chat use o testssl.sh, "
                   "já suportado com execução real no Cyber Lab.",
        "desc": "Analisa a configuração TLS/SSL de um servidor (protocolos, cifras, certificado) de forma rápida.",
        "category": "Network", "scope": "network (alvo autorizado, execução manual fora do chat)",
    },
    "aircrack-ng": {
        "label": "Aircrack-ng", "bin": "aircrack-ng",
        "version_args": ["--help"], "version_re": r"Aircrack-ng (\S+)",
        "install_hint": "Debian/Ubuntu: sudo apt install aircrack-ng  ·  aircrack-ng.org",
        "docs": "https://www.aircrack-ng.org/",
        "no_scan": "Suíte de auditoria de redes Wi-Fi (captura de handshake, deauth, quebra de senha). Exige "
                   "adaptador em modo monitor e, em muitas jurisdições, autorização explícita por escrito do dono "
                   "da rede — o Tristan Thorne não automatiza nada disso por chat, só detecta a instalação. Use apenas "
                   "em laboratório próprio (sua própria rede/AP de teste).",
        "desc": "Suíte para auditar a segurança de redes Wi-Fi: captura tráfego, handshakes WPA/WPA2 e testa a força da senha.",
        "category": "Network", "scope": "adaptador Wi-Fi local (modo monitor, rede própria)",
    },

    # -------------------------------------------------- Web Security (novas)
    "wapiti": {
        "label": "Wapiti", "bin": "wapiti",
        "version_args": ["--version"], "version_re": r"Wapiti (\S+)",
        "install_hint": "pip install wapiti3",
        "docs": "https://wapiti-scanner.github.io/",
        "no_scan": "Scanner de vulnerabilidades web com fuzzing ativo (SQLi, XSS, SSRF etc.); mesma política do "
                   "ZAP/SQLMap aqui — só detecção. Para heurística não destrutiva já integrada, use o "
                   "'OWASP Top 10 Scanner' do Cyber Lab.",
        "desc": "Varre um site injetando payloads de teste em formulários e parâmetros para achar vulnerabilidades web comuns.",
        "category": "Web Security", "scope": "network (alvo autorizado, execução manual fora do chat)",
    },

    # -------------------------------------------------- OSINT/Recon (novas)
    "theharvester": {
        "label": "theHarvester", "bin": "theHarvester",
        "version_args": ["--help"], "version_re": r"theHarvester (\S+)",
        "install_hint": "pip install theHarvester  ·  git clone https://github.com/laramies/theHarvester",
        "docs": "https://github.com/laramies/theHarvester",
        "no_scan": "Coleta e-mails, subdomínios e nomes via mecanismos de busca/APIs de terceiros; execução real "
                   "dependeria de chaves de API de serviços externos que o Tristan Thorne não gerencia. Para WHOIS "
                   "básico já integrado, use a ferramenta 'WHOIS / OSINT' do Cyber Lab.",
        "desc": "Coleta e-mails, subdomínios e funcionários públicos de uma organização a partir de fontes abertas (OSINT).",
        "category": "OSINT/Recon", "scope": "consulta a serviços externos (alvo autorizado)",
    },
    "amass": {
        "label": "OWASP Amass", "bin": "amass",
        "version_args": ["-version"], "version_re": r"v?(\d+\.\d+\.\d+)",
        "install_hint": "go install -v github.com/owasp-amass/amass/v4/...@master  ·  snap install amass",
        "docs": "https://github.com/owasp-amass/amass",
        "no_scan": "Enumeração de subdomínios em larga escala (DNS, certificate transparency, scraping); pode "
                   "gerar muitas consultas a serviços de terceiros, então aqui é só detecção. Rode localmente "
                   "contra domínio autorizado.",
        "desc": "Mapeia a superfície de ataque externa de um domínio: subdomínios, ASNs e infraestrutura relacionada.",
        "category": "OSINT/Recon", "scope": "network (alvo autorizado, execução manual fora do chat)",
    },

    # ------------------------------------------ Vulnerability Assessment (novas)
    "nuclei": {
        "label": "Nuclei", "bin": "nuclei",
        "version_args": ["-version"], "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
        "docs": "https://github.com/projectdiscovery/nuclei",
        "no_scan": "Scanner baseado em templates da comunidade; muitos templates incluem checagens ativas de "
                   "exploração conhecida, então aqui é só detecção — rode manualmente com templates revisados "
                   "por você, só contra alvo autorizado.",
        "desc": "Roda milhares de templates de detecção de vulnerabilidades conhecidas contra um alvo, de forma automatizada.",
        "category": "Vulnerability Assessment", "scope": "network (alvo autorizado, execução manual fora do chat)",
    },
    "hashcat": {
        "label": "Hashcat", "bin": "hashcat",
        "version_args": ["--version"], "version_re": r"v?(\d+\.\d+\.\d+)",
        "install_hint": "Debian/Ubuntu: sudo apt install hashcat  ·  hashcat.net/hashcat",
        "docs": "https://hashcat.net/hashcat/",
        "no_scan": "Quebra de senha por GPU (dicionário/força bruta contra hashes). Ferramenta de exploração "
                   "ativa — mesma linha de política do SQLMap: só detectamos a instalação, nunca disparamos "
                   "quebra de hash por chat. Use apenas sobre hashes que você tem autorização de testar (ex.: "
                   "auditoria da própria base de senhas). Para identificar o tipo de um hash sem quebrá-lo, use "
                   "o 'Identificador de Hash' já existente.",
        "desc": "Quebra hashes de senha usando GPU (dicionário, força bruta, regras) — o cracker de senhas mais usado hoje.",
        "category": "Vulnerability Assessment", "scope": "arquivo local (hash), execução manual fora do chat",
    },
    "john": {
        "label": "John the Ripper", "bin": "john",
        "version_args": ["--version"], "version_re": r"John the Ripper (\S+)",
        "install_hint": "Debian/Ubuntu: sudo apt install john  ·  openwall.com/john",
        "docs": "https://www.openwall.com/john/",
        "no_scan": "Mesma política do Hashcat: ferramenta de quebra de senha por dicionário/força bruta — só "
                   "detecção aqui, execução manual e apenas sobre hashes com autorização explícita.",
        "desc": "Cracker de senhas clássico (CPU), com detecção automática de vários formatos de hash.",
        "category": "Vulnerability Assessment", "scope": "arquivo local (hash), execução manual fora do chat",
    },
    "hydra": {
        "label": "THC-Hydra", "bin": "hydra",
        "version_args": ["-h"], "version_re": r"Hydra v(\S+)",
        "install_hint": "Debian/Ubuntu: sudo apt install hydra  ·  github.com/vanhauser-thc/thc-hydra",
        "docs": "https://github.com/vanhauser-thc/thc-hydra",
        "no_scan": "Força bruta de login contra serviços de rede (SSH, FTP, formulários web etc.). É uma "
                   "ferramenta de ataque ativo por definição — o Tristan Thorne não automatiza login em massa por "
                   "chat contra nenhum alvo, mesmo autorizado (risco real de lockout/DoS). Só detecção aqui. Use "
                   "manualmente, com throttling responsável, e apenas em ambiente de laboratório próprio.",
        "desc": "Testa força bruta de credenciais contra dezenas de protocolos/serviços de rede (SSH, FTP, HTTP, etc.).",
        "category": "Vulnerability Assessment", "scope": "network (alvo autorizado, execução manual fora do chat)",
    },
    "metasploit": {
        "label": "Metasploit Framework", "bin": "msfconsole",
        "version_args": ["-v"], "version_re": r"Framework Version:\s*(\S+)",
        "install_hint": "Debian/Ubuntu: curl https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb | sudo bash  ·  rapid7.com/products/metasploit",
        "docs": "https://www.metasploit.com/",
        "no_scan": "Framework de exploração completo (exploits, payloads, pós-exploração). Está fora de qualquer "
                   "automação por chat aqui — nem detecção habilita execução: abra o console manualmente, só em "
                   "ambiente de laboratório isolado e autorizado (ex.: VM própria, HackTheBox/TryHackMe).",
        "desc": "Framework de exploração mais usado em pentest: catálogo de exploits, payloads e módulos de pós-exploração.",
        "category": "Vulnerability Assessment", "scope": "laboratório isolado próprio, execução manual fora do chat",
    },

    # -------------------------------------------------- Reverse Engineering (novas)
    "radare2": {
        "label": "radare2", "bin": "r2",
        "version_args": ["-v"], "version_re": r"radare2 (\S+)",
        "install_hint": "Debian/Ubuntu: sudo apt install radare2  ·  git clone https://github.com/radareorg/radare2",
        "docs": "https://rada.re/n/",
        "no_scan": "Framework de engenharia reversa interativo (desmontagem, depuração, scripting); use o "
                   "console `r2` localmente sobre o binário do seu laboratório — não roda em lote via chat.",
        "desc": "Framework livre de engenharia reversa e forense de binários, com desmontador e depurador embutidos.",
        "category": "Reverse Engineering", "scope": "arquivo local (binário)",
    },

    # -------------------------------------------------- OSINT/Recon (ProjectDiscovery, execução real)
    # Passivas/pouco invasivas o suficiente para seguir o mesmo padrão de
    # nmap/gobuster/whatweb: alvo tem que estar em escopo autorizado,
    # timeout curto, sem shell=True.
    "subfinder": {
        "label": "Subfinder", "bin": "subfinder",
        "version_args": ["-version"], "version_re": r"(?:Current Version:\s*)?v?(\d+\.\d+\.\d+)",
        "install_hint": "go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest",
        "docs": "https://github.com/projectdiscovery/subfinder",
        "desc": "Enumera subdomínios de um domínio usando só fontes passivas (certificate transparency, APIs públicas) — não toca no alvo.",
        "category": "OSINT/Recon", "scope": "network (alvo autorizado, fontes passivas)",
    },
    "httpx": {
        "label": "httpx (ProjectDiscovery)", "bin": "httpx",
        "version_args": ["-version"], "version_re": r"(?:Current Version:\s*)?v?(\d+\.\d+\.\d+)",
        "install_hint": "go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest",
        "docs": "https://github.com/projectdiscovery/httpx",
        "desc": "Sonda hosts HTTP(S) em massa e devolve status, título, tecnologia e cabeçalhos — triagem rápida de um host ou lista de hosts.",
        "category": "OSINT/Recon", "scope": "network (alvo autorizado)",
    },
    "dnsx": {
        "label": "dnsx (ProjectDiscovery)", "bin": "dnsx",
        "version_args": ["-version"], "version_re": r"(?:Current Version:\s*)?v?(\d+\.\d+\.\d+)",
        "install_hint": "go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest",
        "docs": "https://github.com/projectdiscovery/dnsx",
        "desc": "Resolve e valida registros DNS (A/AAAA/CNAME/MX/TXT etc.) em massa — útil para confirmar quais subdomínios encontrados respondem de verdade.",
        "category": "OSINT/Recon", "scope": "network (alvo autorizado)",
    },
    "naabu": {
        "label": "Naabu (ProjectDiscovery)", "bin": "naabu",
        "version_args": ["-version"], "version_re": r"(?:Current Version:\s*)?v?(\d+\.\d+\.\d+)",
        "install_hint": "go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest (precisa de libpcap-dev)",
        "docs": "https://github.com/projectdiscovery/naabu",
        "desc": "Scanner de portas rápido, pensado para alimentar outras ferramentas de recon — alternativa leve ao Nmap para descoberta inicial.",
        "category": "Network", "scope": "network (alvo autorizado)",
    },

    # -------------------------------------------------- Password Attacks / Post-Exploitation / Sniffing (só detecção)
    # Ferramentas de ataque ativo contra autenticação/Active Directory ou de
    # interceptação de rede: mesma política de sempre (sqlmap/hydra/hashcat/
    # metasploit acima) — detectamos se está instalado e explicamos o porquê
    # de não automatizar, nunca executamos.
    "crackmapexec": {
        "label": "CrackMapExec / NetExec", "bin": "crackmapexec",
        "version_args": ["--version"], "version_re": r"(\d+\.\d+(?:\.\d+)?)",
        "install_hint": "pipx install crackmapexec  ·  sucessor mantido: pipx install netexec (bin `nxc`)",
        "docs": "https://www.netexec.wiki/",
        "no_scan": "Ferramenta de pós-exploração e auditoria de credenciais em redes Windows/AD (valida senhas em "
                   "massa contra vários hosts, movimentação lateral). Mesma política do Hydra: só detecção, "
                   "execução manual e apenas em ambiente/escopo com autorização explícita.",
        "desc": "Audita credenciais e permissões em redes Windows/Active Directory, host a host — canivete suíço de pós-exploração em AD.",
        "category": "Vulnerability Assessment", "scope": "network (alvo autorizado, execução manual fora do chat)",
    },
    "bettercap": {
        "label": "Bettercap", "bin": "bettercap",
        "version_args": ["-version"], "version_re": r"(\d+\.\d+\.\d+)",
        "install_hint": "Debian/Ubuntu: sudo apt install bettercap  ·  github.com/bettercap/bettercap",
        "docs": "https://www.bettercap.org/",
        "no_scan": "Framework de ataques de rede (MITM, spoofing, sniffing wireless/BLE). Interceptar tráfego de "
                   "terceiros sem autorização explícita é crime na maioria das jurisdições — só detecção aqui, "
                   "console interativo roda localmente na sua própria rede/laboratório.",
        "desc": "Framework de MITM, spoofing e reconhecimento de rede (incluindo wireless/BLE) — muito usado em testes de rede local.",
        "category": "Vulnerability Assessment", "scope": "host local (rede própria/laboratório), execução manual fora do chat",
    },
    "responder": {
        "label": "Responder", "bin": "responder",
        "version_args": ["--version"], "version_re": r"(\d+\.\d+(?:\.\d+)?)",
        "install_hint": "git clone https://github.com/lgandx/Responder",
        "docs": "https://github.com/lgandx/Responder",
        "no_scan": "Captura credenciais via spoofing de LLMNR/NBT-NS/mDNS — ferramenta de ataque ativo contra uma "
                   "rede inteira (afeta todo mundo nela, não só um alvo escolhido). Só detecção; rode manualmente "
                   "e só na sua própria rede de laboratório.",
        "desc": "Envenena respostas LLMNR/NBT-NS/mDNS numa rede local para capturar hashes de credenciais — clássico em testes de rede interna.",
        "category": "Vulnerability Assessment", "scope": "host local (rede própria/laboratório), execução manual fora do chat",
    },
    "impacket": {
        "label": "Impacket", "bin": "impacket-secretsdump",
        "version_args": ["-h"], "version_re": r"[Ii]mpacket v(\S+)",
        "install_hint": "pipx install impacket  ·  pip install impacket --break-system-packages",
        "docs": "https://github.com/fortra/impacket",
        "no_scan": "Conjunto de scripts Python para protocolos Windows/AD, usado sobretudo em pós-exploração "
                   "(dump de credenciais, movimentação lateral, etc.). Só detecção do pacote — cada script é "
                   "executado manualmente, no seu laboratório, contra alvo autorizado.",
        "desc": "Biblioteca/scripts Python para manipular protocolos de rede Windows (SMB, Kerberos, DCOM) — base de muitas ferramentas de pós-exploração em AD.",
        "category": "Vulnerability Assessment", "scope": "network (alvo autorizado, execução manual fora do chat)",
    },
    "bloodhound": {
        "label": "BloodHound", "bin": "bloodhound-python",
        "version_args": ["--version"], "version_re": r"(\d+\.\d+(?:\.\d+)?)",
        "install_hint": "pipx install bloodhound  ·  interface gráfica: github.com/SpecterOps/BloodHound",
        "docs": "https://github.com/SpecterOps/BloodHound",
        "no_scan": "Mapeia caminhos de ataque dentro de um Active Directory (coleta dados e mostra em grafo quem "
                   "pode virar Domain Admin). Coleta e visualização rodam localmente, fora do chat — só detecção "
                   "do coletor Python aqui.",
        "desc": "Coleta a estrutura de um Active Directory e mostra em grafo os caminhos de privilégio escalável — essencial em pentest de AD.",
        "category": "Vulnerability Assessment", "scope": "network (alvo autorizado, execução manual fora do chat)",
    },
    "searchsploit": {
        "label": "SearchSploit (Exploit-DB)", "bin": "searchsploit",
        "version_args": ["-h"], "version_re": r"(\d+\.\d+(?:\.\d+)?)",
        "install_hint": "Debian/Ubuntu: sudo apt install exploitdb  ·  git clone https://github.com/offensive-security/exploitdb",
        "docs": "https://www.exploit-db.com/searchsploit",
        "no_scan": "Busca local no espelho do Exploit-DB por nome/versão de software. Devolver exploits prontos "
                   "por chat foge do propósito defensivo/educacional desta plataforma (ver SECURITY_POLICY.md) — "
                   "aqui só confirmamos que a base está instalada; a consulta roda localmente.",
        "desc": "Pesquisa offline na base do Exploit-DB por exploits conhecidos de um software/versão específico — útil para saber se algo tem CVE pública com PoC.",
        "category": "Vulnerability Assessment", "scope": "arquivo local (base offline), execução manual fora do chat",
    },
}


def _detect(entry):
    path = shutil.which(entry["bin"])
    if not path:
        return {"installed": False, "path": None, "version": None}
    version = None
    try:
        p = _run_external([path, *entry["version_args"]], timeout=8)
        out = (p.stdout or "") + (p.stderr or "")
        m = re.search(entry["version_re"], out)
        version = m.group(1) if m else out.strip().splitlines()[0][:60] if out.strip() else "desconhecida"
    except Exception:
        version = "desconhecida (falhou ao rodar --version)"
    return {"installed": True, "path": path, "version": version}


_STATUS_CACHE = {"ts": 0.0, "value": None}
_STATUS_CACHE_TTL = 8.0

def _status_item(item):
    tid, entry = item
    d = _detect(entry)
    return {
        "id": tid, "label": entry["label"], **d,
        "install_hint": entry["install_hint"], "docs": entry["docs"],
        "category": entry.get("category", "—"), "scope": entry.get("scope", "—"),
        "desc": entry.get("desc", ""),
        "runnable": d["installed"] and "no_scan" not in entry,
        "status": "not_installed" if not d["installed"] else ("config_required" if entry.get("no_scan") else "installed"),
        "note": entry.get("no_scan"),
    }

def status_all():
    """Status real das ferramentas, com probes de versão em paralelo.

    A detecção continua sendo real e sem simulação; apenas evita que ~30
    chamadas de --version sejam feitas uma após outra. Um cache curtíssimo
    reduz cliques repetidos sem esconder mudanças de instalação por muito tempo.
    """
    now = time.monotonic()
    if _STATUS_CACHE["value"] is not None and now - _STATUS_CACHE["ts"] < _STATUS_CACHE_TTL:
        return [dict(x) for x in _STATUS_CACHE["value"]]
    items = list(TOOLS.items())
    workers = min(8, max(1, len(items)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="tool-status") as pool:
        out = list(pool.map(_status_item, items))
    _STATUS_CACHE.update({"ts": now, "value": out})
    return [dict(x) for x in out]


def status_one(tool_id):
    entry = TOOLS.get(tool_id)
    if not entry:
        return None
    d = _detect(entry)
    return {"id": tool_id, "label": entry["label"], **d,
            "install_hint": entry["install_hint"], "docs": entry["docs"],
            "category": entry.get("category", "—"), "scope": entry.get("scope", "—"),
            "desc": entry.get("desc", ""),
            "runnable": d["installed"] and "no_scan" not in entry,
            "status": "not_installed" if not d["installed"] else ("config_required" if entry.get("no_scan") else "installed"),
            "note": entry.get("no_scan")}


class NotInstalledError(Exception):
    def __init__(self, tool_id, hint):
        self.tool_id, self.hint = tool_id, hint
        super().__init__(f"'{tool_id}' não está instalado neste servidor. {hint}")


class NotRunnableError(Exception):
    pass


def _require_scope(target):
    """Valida o alvo no SSRF Guard e devolve o HOST (string).
    (Antes devolvia a lista de IPs de check_host, o que quebrava os comandos.)"""
    t = (target or "").strip()
    if "://" in t:
        # recusa formas ambíguas/credenciais embutidas antes de extrair o host
        host = urlparse(scope.canonical_url(t, context="tool_adapter")).hostname
    else:
        host = t
    scope.check_host(host, context="tool_adapter")  # levanta ScopeError se não autorizado
    return host


def _scoped_url(target, host):
    """URL entregue ao binário externo: reconstruída a partir do que foi
    validado, nunca a string crua do usuário (evita divergência de parser)."""
    if "://" in (target or ""):
        return scope.canonical_url(target, context="tool_adapter")
    return f"http://[{host}]" if ":" in host else f"http://{host}"


# ------------------------------------------------------------ execuções
def run_nmap(target, ports="top1000"):
    entry = TOOLS["nmap"]
    d = _detect(entry)
    if not d["installed"]:
        raise NotInstalledError("nmap", entry["install_hint"])
    host = _require_scope(target)
    # nmap recebe o IP já validado (sem nova resolução DNS => sem rebinding)
    ips = scope.check_host(host, context="nmap")
    args = [d["path"], "-Pn", "-sT", "--top-ports", "200", "-T4"]
    if ips[0].version == 6:
        args.append("-6")
    args.append(str(ips[0]))
    t0 = time.perf_counter()
    p = _run_external(args, timeout=90)
    ms = round((time.perf_counter() - t0) * 1000)
    findings = _parse_nmap(p.stdout, host)
    return {"raw": {"stdout": p.stdout[-8000:], "stderr": p.stderr[-2000:], "cmd": " ".join(args)},
            "findings": findings, "duration_ms": ms,
            "summary": f"Nmap: {len(findings)} porta(s)/achado(s) em {host}"}


def _parse_nmap(stdout, host):
    findings = []
    for line in stdout.splitlines():
        m = re.match(r"(\d+)/(tcp|udp)\s+(\S+)\s+(\S+)", line.strip())
        if m:
            port, proto, state, service = m.groups()
            sev = "medium" if state == "open" else "info"
            findings.append(evidence.make_finding(
                rule="nmap.port", title=f"Porta {port}/{proto} {state} ({service})",
                severity=sev, evidence=line.strip(),
                impact="Serviço exposto pode ampliar a superfície de ataque." if state == "open" else "",
                fix="Feche portas/serviços desnecessários e restrinja por firewall." if state == "open" else "",
                where=f"{host}:{port}/{proto}"))
    return findings


def run_gobuster(target, wordlist_size="small"):
    entry = TOOLS["gobuster"]
    d = _detect(entry)
    if not d["installed"]:
        raise NotInstalledError("gobuster", entry["install_hint"])
    host = _require_scope(target)
    url = _scoped_url(target, host)
    wl = _mini_wordlist()
    t0 = time.perf_counter()
    p = _run_external([d["path"], "dir", "-u", url, "-w", wl, "-q", "-t", "10", "--timeout", "5s"], timeout=60)
    ms = round((time.perf_counter() - t0) * 1000)
    findings = []
    for line in p.stdout.splitlines():
        m = re.match(r"(/\S+)\s+\(Status:\s*(\d+)\)", line.strip())
        if m:
            path_, code = m.groups()
            sev = "low" if code.startswith(("2", "3")) else "info"
            findings.append(evidence.make_finding(
                rule="gobuster.path", title=f"Caminho encontrado: {path_} ({code})",
                severity=sev, evidence=line.strip(),
                impact="Endpoint/diretório acessível pode expor funcionalidade não destinada ao público.",
                fix="Revise se o caminho deveria estar acessível; restrinja ou remova se não deveria.",
                where=f"{url}{path_}"))
    return {"raw": {"stdout": p.stdout[-8000:], "stderr": p.stderr[-2000:]}, "findings": findings,
            "duration_ms": ms, "summary": f"Gobuster: {len(findings)} caminho(s) em {url}"}


def _mini_wordlist():
    import tempfile
    words = ["admin", "login", "api", "config", ".env", "backup", "test", "wp-admin",
             "dashboard", ".git", "uploads", "static", "assets", "debug", ".well-known"]
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    f.write("\n".join(words))
    f.close()
    return f.name


def run_nikto(target):
    entry = TOOLS["nikto"]
    d = _detect(entry)
    if not d["installed"]:
        raise NotInstalledError("nikto", entry["install_hint"])
    host = _require_scope(target)
    url = _scoped_url(target, host)
    t0 = time.perf_counter()
    p = _run_external([d["path"], "-h", url, "-Tuning", "1,2,3", "-maxtime", "45s", "-nointeractive"], timeout=70)
    ms = round((time.perf_counter() - t0) * 1000)
    findings = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if line.startswith("+ ") and len(line) > 5:
            findings.append(evidence.make_finding(
                rule="nikto.finding", title=line[2:120], severity="low",
                evidence=line, impact="Possível fraqueza de configuração web.",
                fix="Avalie a linha do Nikto e corrija a configuração indicada.",
                where=url))
    return {"raw": {"stdout": p.stdout[-8000:], "stderr": p.stderr[-2000:]}, "findings": findings,
            "duration_ms": ms, "summary": f"Nikto: {len(findings)} achado(s) em {url}"}


def run_ffuf(target):
    entry = TOOLS["ffuf"]
    d = _detect(entry)
    if not d["installed"]:
        raise NotInstalledError("ffuf", entry["install_hint"])
    host = _require_scope(target)
    url = _scoped_url(target, host)
    base = url.rstrip("/") + "/FUZZ"
    wl = _mini_wordlist()
    t0 = time.perf_counter()
    p = _run_external([d["path"], "-u", base, "-w", wl, "-t", "10", "-timeout", "5",
                        "-mc", "200,204,301,302,307,401,403", "-s"], timeout=60)
    ms = round((time.perf_counter() - t0) * 1000)
    findings = []
    for line in p.stdout.splitlines():
        path_ = line.strip()
        if not path_:
            continue
        findings.append(evidence.make_finding(
            rule="ffuf.path", title=f"Caminho encontrado: /{path_}",
            severity="low", evidence=path_,
            impact="Endpoint/diretório acessível pode expor funcionalidade não destinada ao público.",
            fix="Revise se o caminho deveria estar acessível; restrinja ou remova se não deveria.",
            where=f"{url.rstrip('/')}/{path_}"))
    return {"raw": {"stdout": p.stdout[-8000:], "stderr": p.stderr[-2000:]}, "findings": findings,
            "duration_ms": ms, "summary": f"ffuf: {len(findings)} caminho(s) em {url}"}


def run_whatweb(target):
    entry = TOOLS["whatweb"]
    d = _detect(entry)
    if not d["installed"]:
        raise NotInstalledError("whatweb", entry["install_hint"])
    host = _require_scope(target)
    url = _scoped_url(target, host)
    t0 = time.perf_counter()
    p = _run_external([d["path"], "--color=never", "-a", "1", url], timeout=30)
    ms = round((time.perf_counter() - t0) * 1000)
    findings = []
    out = (p.stdout or "").strip()
    # formato típico: "http://alvo [200 OK] Apache[2.4.41], Country[...], IP[...]"
    after_status = re.split(r"\]\s+", out, maxsplit=1)
    tail = after_status[1] if len(after_status) > 1 else out
    for token in tail.split(", "):
        m = re.match(r"([A-Za-z0-9._ -]+?)(?:\[([^\]]*)\])?$", token.strip())
        if not m:
            continue
        name, detail = m.group(1).strip(), (m.group(2) or "").strip()
        if not name or name.lower() in ("http", "https"):
            continue
        findings.append(evidence.make_finding(
            rule="whatweb.tech", title=f"Tecnologia detectada: {name}" + (f" ({detail})" if detail else ""),
            severity="info", evidence=token.strip(),
            impact="Tecnologias/versões expostas ajudam um atacante a mirar CVEs conhecidas.",
            fix="Oculte banners/versões desnecessários quando possível.", where=url))
    return {"raw": {"stdout": p.stdout[-8000:], "stderr": p.stderr[-2000:]}, "findings": findings[:20],
            "duration_ms": ms, "summary": f"WhatWeb: {len(findings[:20])} tecnologia(s) em {url}"}


def run_testssl(target):
    entry = TOOLS["testssl"]
    d = _detect(entry)
    if not d["installed"]:
        raise NotInstalledError("testssl", entry["install_hint"])
    host = _require_scope(target)
    t0 = time.perf_counter()
    p = _run_external([d["path"], "--quiet", "--color", "0", "--fast", host], timeout=120)
    ms = round((time.perf_counter() - t0) * 1000)
    findings = []
    for line in p.stdout.splitlines():
        line = line.strip()
        m = re.match(r"(SSLv2|SSLv3|TLS 1(?:\.0|\.1)?)\s+(offered|not offered)", line, re.I)
        if m and m.group(2).lower() == "offered":
            findings.append(evidence.make_finding(
                rule="testssl.legacy_protocol", title=f"Protocolo legado habilitado: {m.group(1)}",
                severity="high", evidence=line,
                impact="Protocolos TLS/SSL antigos têm vulnerabilidades conhecidas (ex.: POODLE, BEAST).",
                fix="Desabilite SSLv2/SSLv3/TLS 1.0/1.1 no servidor; use TLS 1.2+.", where=host))
        if re.search(r"VULNERABLE", line, re.I) and "not vulnerable" not in line.lower():
            findings.append(evidence.make_finding(
                rule="testssl.cve", title=line[:120], severity="critical",
                evidence=line, impact="Vulnerabilidade conhecida de TLS/SSL detectada.",
                fix="Atualize a stack TLS do servidor e reconfigure conforme a recomendação do testssl.sh.",
                where=host))
    return {"raw": {"stdout": p.stdout[-8000:], "stderr": p.stderr[-2000:]}, "findings": findings,
            "duration_ms": ms, "summary": f"testssl.sh: {len(findings)} achado(s) em {host}"}


def run_subfinder(target):
    entry = TOOLS["subfinder"]
    d = _detect(entry)
    if not d["installed"]:
        raise NotInstalledError("subfinder", entry["install_hint"])
    host = _require_scope(target)
    t0 = time.perf_counter()
    p = _run_external([d["path"], "-d", host, "-silent", "-timeout", "15"], timeout=45)
    ms = round((time.perf_counter() - t0) * 1000)
    findings = []
    for line in p.stdout.splitlines():
        sub = line.strip()
        if not sub:
            continue
        findings.append(evidence.make_finding(
            rule="subfinder.subdomain", title=f"Subdomínio encontrado: {sub}",
            severity="info", evidence=sub,
            impact="Cada subdomínio exposto aumenta a superfície de ataque (apps esquecidos, staging, etc.).",
            fix="Confirme se todo subdomínio encontrado deveria estar público; desative/restrinja os que não deveriam.",
            where=sub))
    return {"raw": {"stdout": p.stdout[-8000:], "stderr": p.stderr[-2000:]}, "findings": findings[:50],
            "duration_ms": ms, "summary": f"Subfinder: {len(findings)} subdomínio(s) de {host} (fontes passivas)"}


def run_httpx(target):
    entry = TOOLS["httpx"]
    d = _detect(entry)
    if not d["installed"]:
        raise NotInstalledError("httpx", entry["install_hint"])
    host = _require_scope(target)
    url = _scoped_url(target, host)
    t0 = time.perf_counter()
    p = _run_external([d["path"], "-u", url, "-silent", "-status-code", "-title", "-tech-detect", "-timeout", "10"], timeout=30)
    ms = round((time.perf_counter() - t0) * 1000)
    findings = []
    out = (p.stdout or "").strip()
    if out:
        findings.append(evidence.make_finding(
            rule="httpx.probe", title="Resposta HTTP sondada", severity="info",
            evidence=out, impact="Confirma que o host está ativo e expõe informações de título/tecnologia.",
            fix="", where=url))
    return {"raw": {"stdout": p.stdout[-8000:], "stderr": p.stderr[-2000:]}, "findings": findings,
            "duration_ms": ms, "summary": f"httpx: {'host respondeu' if out else 'sem resposta'} em {url}"}


def run_dnsx(target):
    entry = TOOLS["dnsx"]
    d = _detect(entry)
    if not d["installed"]:
        raise NotInstalledError("dnsx", entry["install_hint"])
    host = _require_scope(target)
    t0 = time.perf_counter()
    p = _run_external([d["path"], "-d", host, "-silent", "-resp", "-a", "-aaaa", "-cname", "-timeout", "10"], timeout=30)
    ms = round((time.perf_counter() - t0) * 1000)
    findings = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        findings.append(evidence.make_finding(
            rule="dnsx.record", title=f"Registro DNS: {line}", severity="info",
            evidence=line, impact="Confirma a resolução DNS real do host (evita falso-positivo de subdomínio morto).",
            fix="", where=host))
    return {"raw": {"stdout": p.stdout[-8000:], "stderr": p.stderr[-2000:]}, "findings": findings,
            "duration_ms": ms, "summary": f"dnsx: {len(findings)} registro(s) para {host}"}


def run_naabu(target):
    entry = TOOLS["naabu"]
    d = _detect(entry)
    if not d["installed"]:
        raise NotInstalledError("naabu", entry["install_hint"])
    host = _require_scope(target)
    ips = scope.check_host(host, context="naabu")
    t0 = time.perf_counter()
    p = _run_external([d["path"], "-host", str(ips[0]), "-silent", "-top-ports", "100", "-timeout", "5000"], timeout=60)
    ms = round((time.perf_counter() - t0) * 1000)
    findings = []
    for line in p.stdout.splitlines():
        line = line.strip()
        m = re.match(r"(?:\S+:)?(\d+)$", line)
        port = m.group(1) if m else (line.split(":")[-1] if ":" in line else line)
        if not port or not port.isdigit():
            continue
        findings.append(evidence.make_finding(
            rule="naabu.port", title=f"Porta {port}/tcp aberta", severity="medium",
            evidence=line, impact="Serviço exposto pode ampliar a superfície de ataque.",
            fix="Feche portas/serviços desnecessários e restrinja por firewall.",
            where=f"{host}:{port}"))
    return {"raw": {"stdout": p.stdout[-8000:], "stderr": p.stderr[-2000:]}, "findings": findings,
            "duration_ms": ms, "summary": f"Naabu: {len(findings)} porta(s) aberta(s) em {host}"}


RUNNERS = {"nmap": run_nmap, "gobuster": run_gobuster, "nikto": run_nikto,
           "ffuf": run_ffuf, "whatweb": run_whatweb, "testssl": run_testssl,
           "subfinder": run_subfinder, "httpx": run_httpx, "dnsx": run_dnsx, "naabu": run_naabu}


def run(tool_id, target, **kw):
    entry = TOOLS.get(tool_id)
    if not entry:
        raise NotRunnableError(f"Ferramenta externa desconhecida: {tool_id}")
    if entry.get("no_scan"):
        raise NotRunnableError(entry["no_scan"])
    runner = RUNNERS.get(tool_id)
    if not runner:
        raise NotRunnableError(f"'{tool_id}' ainda não tem execução automatizada implementada.")
    return runner(target, **kw)
