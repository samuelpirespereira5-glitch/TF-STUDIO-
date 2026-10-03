"""Ferramentas da Terceira Fase — somente análise defensiva."""
from services.tool_registry import Registry
from services import phase3

def register(reg: Registry):
    TXT={"text":{"type":"string","required":True,"description":"Texto/headers/código fornecido ao laboratório"},
         "filename":{"type":"string","description":"Nome do arquivo (opcional)"}}
    def local(fn):
        def h(p,ctx):
            return fn(p.get("text",""),p.get("filename",""))
        return h
    specs=[
      ("security_headers_analyzer","Security Headers Analyzer","web-security","Analisa headers fornecidos e identifica controles ausentes.","headers",phase3.analyze_security_headers),
      ("cookie_security_analyzer","Cookie Security Analyzer","web-security","Analisa Set-Cookie fornecido sem armazenar cookies reais.","cookies",phase3.analyze_cookies),
      ("cors_analyzer","CORS Analyzer","web-security","Identifica políticas CORS permissivas em headers fornecidos.","cors",phase3.analyze_cors),
      ("http_response_analyzer","HTTP Response Analyzer","web-security","Analisa uma resposta HTTP fornecida, sem executar payloads.","response",phase3.analyze_security_headers),
      ("api_security_checker","API Security Checker","secure-coding","Checklist heurístico para código de endpoints de API.","api",phase3.analyze_api_security),
      ("secrets_detector","Secrets Detection","secure-coding","Detecta padrões de segredos no texto sem devolver o segredo encontrado.","secret",phase3.detect_secrets),
      ("dependency_security_auditor","Dependency Security Checker","blue-team","Audita dependências fornecidas e sinaliza versões não fixadas; não inventa CVEs.","deps",phase3.analyze_dependencies),
      ("file_hash_analyzer","File Hash Analyzer","blue-team","Calcula SHA-256 do conteúdo fornecido e pode comparar com hash esperado.","hash",phase3.analyze_file_integrity),
      ("log_security_analyzer","Security Event / Log Analyzer","blue-team","Procura rajadas de falhas de autenticação em logs fornecidos.","logs",phase3.analyze_logs),
      ("metadata_analyzer","Metadata Analyzer","forensics","Revisa o tipo/nome de arquivo fornecido e recomenda saneamento de metadados.","metadata",phase3.analyze_metadata),
    ]
    for tid,name,cat,desc,kw,fn in specs:
        reg.register(id=tid,name=name,category=cat,description=desc,cap="cyber",
                     params=TXT,handler=local(fn),keywords=[kw,name.lower()])
    reg.register(id="dns_analyzer",name="DNS Analyzer",category="network",
                 description="Consulta DNS/dominio usando o guard público existente.",
                 cap="cyber",needs_target=True,params={"target":{"required":True,"description":"domínio autorizado"}},
                 handler=lambda p,c: phase3.dns_analyzer(p["target"]),
                 keywords=["dns","dns analyzer"])
    reg.register(id="tls_ssl_analyzer",name="TLS/SSL Analyzer",category="web-security",
                 description="Inspeciona certificado TLS de um domínio autorizado com o guard de rede existente.",
                 cap="cyber",needs_target=True,params={"target":{"required":True,"description":"domínio autorizado"}},
                 handler=lambda p,c: phase3.tls_analyzer(p["target"]),
                 keywords=["tls","ssl","certificado"])
    reg.register(id="ip_information",name="IP Information",category="network",
                 description="Classifica um IP/hostname e mostra propriedades de rede sem exploração.",
                 cap="cyber",params={"target":{"required":True}},handler=lambda p,c: phase3.ip_information(p["target"]),
                 keywords=["ip","ip information","endereço ip"])
    for tid,name,desc,fn,kw in [
      ("network_config_analyzer","Network Configuration Analyzer","Analisa configuração de rede fornecida.",phase3.network_config,"network config"),
      ("packet_log_analyzer","Packet/Log Analyzer","Analisa logs/capturas textuais fornecidas sem executar tráfego.",phase3.packet_log_analyzer,"packet log"),
      ("robots_sitemap_analyzer","robots.txt / sitemap Analyzer","Analisa robots.txt e referências a sitemap.",phase3.robots_sitemap_analyzer,"robots sitemap"),
      ("authentication_config_checker","Authentication Configuration Checker","Analisa configuração textual de autenticação.",phase3.auth_config_analyzer,"authentication config")
    ]:
        reg.register(id=tid,name=name,category="blue-team" if "log" in tid else "web-security",
                     description=desc,cap="cyber",params=TXT,handler=local(fn),keywords=[kw])
    reg.register(id="subnet_calculator_phase3",name="Subnet Calculator",category="network",
                 description="Calcula rede, broadcast e hosts para um CIDR informado.",
                 cap="cyber",params={"cidr":{"required":True,"description":"ex.: 192.168.1.0/24"}},
                 handler=lambda p,c: _cidr(p["cidr"]),keywords=["subnet","cidr","rede"])

def _cidr(value):
    import ipaddress
    net=ipaddress.ip_network(str(value).strip(),strict=False)
    return {"raw":{"network":str(net.network_address),"broadcast":str(net.broadcast_address),
                   "prefix":net.prefixlen,"version":net.version,
                   "hosts":max(0,net.num_addresses-2) if net.version==4 and net.prefixlen<31 else net.num_addresses},
            "summary":f"{net} · broadcast {net.broadcast_address} · prefix /{net.prefixlen}"}
