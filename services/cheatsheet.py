"""Base de conhecimento / Cheatsheet — conteúdo estático de referência
rápida. Isto é documentação (não executa nada); a execução real (quando
disponível) passa pelo Tool Adapter em services/tool_adapter.py.
"""

CHEATSHEET = [
    {
        "tool": "Nmap",
        "commands": [
            {"cmd": "nmap -sV -sC -p- <alvo>", "desc": "Varredura completa de portas com detecção de versão e scripts padrão."},
            {"cmd": "nmap -Pn -sT --top-ports 1000 <alvo>", "desc": "Top 1000 portas TCP, sem ping prévio (útil quando ICMP é bloqueado)."},
            {"cmd": "nmap -A <alvo>", "desc": "Detecção agressiva: SO, versão, scripts e traceroute."},
            {"cmd": "nmap -sU --top-ports 20 <alvo>", "desc": "Varredura básica de portas UDP."},
        ],
    },
    {
        "tool": "Gobuster",
        "commands": [
            {"cmd": "gobuster dir -u http://<alvo> -w wordlist.txt", "desc": "Enumeração de diretórios/arquivos."},
            {"cmd": "gobuster dns -d <dominio> -w subdomains.txt", "desc": "Enumeração de subdomínios via DNS."},
            {"cmd": "gobuster vhost -u http://<alvo> -w vhosts.txt", "desc": "Enumeração de virtual hosts."},
        ],
    },
    {
        "tool": "SQLmap",
        "commands": [
            {"cmd": "sqlmap -u \"http://<alvo>/?id=1\" --batch --level=2", "desc": "Teste automatizado de SQL Injection num parâmetro de URL."},
            {"cmd": "sqlmap -u \"http://<alvo>/login\" --data=\"user=a&pass=b\" --batch", "desc": "Teste em requisição POST."},
            {"cmd": "sqlmap -u \"http://<alvo>/?id=1\" --dbs", "desc": "Lista bancos de dados (só em ambiente autorizado!)."},
        ],
    },
    {
        "tool": "Wireshark / tshark",
        "commands": [
            {"cmd": "tshark -i eth0 -f \"tcp port 80\"", "desc": "Captura ao vivo de tráfego HTTP na interface eth0."},
            {"cmd": "tshark -r captura.pcap -Y \"http.request\"", "desc": "Filtra requisições HTTP num arquivo de captura já salvo."},
            {"cmd": "tshark -r captura.pcap -q -z conv,tcp", "desc": "Resumo de conversas TCP num pcap."},
        ],
    },
    {
        "tool": "Metasploit",
        "commands": [
            {"cmd": "msfconsole -q", "desc": "Abre o console do Metasploit."},
            {"cmd": "search type:exploit <nome>", "desc": "Busca módulos de exploit por nome/CVE."},
            {"cmd": "use <modulo>; show options", "desc": "Seleciona um módulo e mostra as opções configuráveis."},
        ],
    },
    {
        "tool": "Nikto",
        "commands": [
            {"cmd": "nikto -h http://<alvo>", "desc": "Varredura padrão de configurações/vulnerabilidades web conhecidas."},
            {"cmd": "nikto -h http://<alvo> -Tuning 1,2,3", "desc": "Restringe a varredura a categorias específicas (mais rápido)."},
        ],
    },
    {
        "tool": "OWASP ZAP",
        "commands": [
            {"cmd": "zap.sh -cmd -quickurl http://<alvo> -quickout report.html", "desc": "Varredura rápida via CLI, exporta relatório HTML."},
        ],
    },
    {
        "tool": "Hydra",
        "commands": [
            {"cmd": "hydra -l admin -P wordlist.txt <alvo> ssh", "desc": "Força-bruta de login SSH com usuário fixo e lista de senhas."},
            {"cmd": "hydra -L users.txt -P wordlist.txt <alvo> http-post-form \"/login:user=^USER^&pass=^PASS^:F=incorrect\"", "desc": "Força-bruta num formulário HTTP POST (login web)."},
            {"cmd": "hydra -l admin -P wordlist.txt -t 4 <alvo> ftp", "desc": "Login FTP limitando a 4 threads paralelas."},
        ],
    },
    {
        "tool": "FFUF",
        "commands": [
            {"cmd": "ffuf -u http://<alvo>/FUZZ -w wordlist.txt", "desc": "Fuzzing de diretórios/arquivos numa URL."},
            {"cmd": "ffuf -u http://<alvo> -H \"Host: FUZZ.<dominio>\" -w subdomains.txt", "desc": "Fuzzing de subdomínios via cabeçalho Host (vhosts)."},
            {"cmd": "ffuf -u http://<alvo>/api/FUZZ -w wordlist.txt -mc 200,204,301,302,401,403", "desc": "Fuzzing de endpoints de API, filtrando por códigos de status relevantes."},
        ],
    },
    {
        "tool": "Burp Suite",
        "commands": [
            {"cmd": "Proxy > Intercept on", "desc": "Intercepta requisições do browser para inspeção/edição manual."},
            {"cmd": "Repeater (Ctrl+R)", "desc": "Reenvia e edita uma requisição capturada para testar variações manualmente."},
            {"cmd": "Intruder > Sniper", "desc": "Automatiza testes de um único parâmetro com uma lista de payloads."},
        ],
    },
    {
        "tool": "GTFOBins / LOLBAS (escalada de privilégio)",
        "commands": [
            {"cmd": "sudo -l", "desc": "Lista comandos que o usuário atual pode rodar como root — ponto de partida clássico em Linux."},
            {"cmd": "find / -perm -4000 -type f 2>/dev/null", "desc": "Procura binários com bit SUID definido (possíveis vetores de escalada)."},
            {"cmd": "gtfobins.github.io/<binario>", "desc": "Consulte o binário SUID/sudo encontrado no site GTFOBins para a técnica de escalada correspondente."},
            {"cmd": "whoami /priv (Windows)", "desc": "Lista privilégios do token atual no Windows (ex.: SeImpersonatePrivilege → técnicas de potato)."},
            {"cmd": "lolbas-project.github.io/<binario>", "desc": "Consulte binários nativos do Windows (LOLBAS) que podem ser abusados para execução/persistência."},
        ],
    },
    {
        "tool": "Headers de defesa (referência rápida)",
        "commands": [
            {"cmd": "Cross-Origin-Opener-Policy: same-origin", "desc": "Isola a janela: outra origem não mantém referência via window.opener."},
            {"cmd": "Cross-Origin-Resource-Policy: same-site", "desc": "Impede que outros sites embutam/leiam este recurso via <script>/<img>."},
            {"cmd": '<script src="..." integrity="sha384-..." crossorigin="anonymous">', "desc": "Subresource Integrity: o navegador recusa o script se o CDN servir algo diferente do hash."},
            {"cmd": "Set-Cookie: __Host-session=...; Path=/; Secure; HttpOnly; SameSite=Lax", "desc": "Prefixo __Host- é reforçado pelo próprio navegador (exige Secure, HTTPS, sem Domain)."},
        ],
    },
    {
        "tool": "cURL (recon manual)",
        "commands": [
            {"cmd": "curl -I https://<alvo>", "desc": "Mostra apenas os headers da resposta (rápido para checar security headers)."},
            {"cmd": "curl -s -o /dev/null -w \"%{http_code}\\n\" https://<alvo>", "desc": "Só o status HTTP."},
        ],
    },
]
