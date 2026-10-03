"""Central de Ferramentas — categorias oficiais do JARVIS Cyber Lab.

Categorias:
  Reconhecimento, Web, Rede, Blue Team, Forense, OSINT,
  Criptografia, Malware Analysis (sandbox), Segurança de APIs, CTF/Laboratório
"""
from __future__ import annotations

CATEGORIES = {
    "reconhecimento": {
        "id": "reconhecimento",
        "name": "Reconhecimento",
        "icon": "🔍",
        "description": "Descoberta passiva e ativa controlada de ativos autorizados (DNS, subdomínios, IPs, serviços).",
        "tools": ["dns_lookup", "subdomain_enum", "ip_analyzer", "port_scanner", "service_banner"],
    },
    "web": {
        "id": "web",
        "name": "Web",
        "icon": "🌐",
        "description": "Análise defensiva de aplicações web autorizadas: headers, HTTPS, exposição, health.",
        "tools": ["header_analyzer", "http_scanner", "ssl_tls_analyzer", "website_health", "cookie_analyzer"],
    },
    "rede": {
        "id": "rede",
        "name": "Rede",
        "icon": "📡",
        "description": "Diagnóstico de rede e exposição de serviços em alvos previamente autorizados.",
        "tools": ["port_scanner", "network_diagnostics", "cidr_calculator", "service_banner"],
    },
    "blue_team": {
        "id": "blue_team",
        "name": "Blue Team",
        "icon": "🛡️",
        "description": "Defesa: logs, hardening, detecção de misconfigurações e plano de correção.",
        "tools": ["log_analyzer", "dependency_scanner", "secrets_scanner", "config_checker", "hardening_checklist"],
    },
    "forense": {
        "id": "forense",
        "name": "Forense",
        "icon": "🔬",
        "description": "Análise de arquivos, metadados e evidências sem execução de conteúdo não confiável.",
        "tools": ["file_analyzer", "hash_analyzer", "metadata_extractor", "timeline_helper"],
    },
    "osint": {
        "id": "osint",
        "name": "OSINT",
        "icon": "🌍",
        "description": "Fontes públicas e autorizadas apenas. Respeita rate limits e políticas de uso.",
        "tools": ["osint_whois", "osint_public", "ip_analyzer", "dns_lookup"],
    },
    "criptografia": {
        "id": "criptografia",
        "name": "Criptografia",
        "icon": "🔐",
        "description": "Hashes, JWT (decodificação), Base64, análise de certificados — sem cracking.",
        "tools": ["hash_analyzer", "hash_generator", "jwt_analyzer", "base64_tool", "ssl_tls_analyzer"],
    },
    "malware_sandbox": {
        "id": "malware_sandbox",
        "name": "Malware Analysis (sandbox)",
        "icon": "🧪",
        "description": "Ambiente isolado, sem acesso à rede por padrão, CPU/memória/tempo limitados.",
        "tools": ["malware_sandbox", "hash_analyzer", "file_analyzer"],
    },
    "api_security": {
        "id": "api_security",
        "name": "Segurança de APIs",
        "icon": "🔌",
        "description": "Testes controlados apenas em endpoints autorizados. Limite de requisições rigoroso.",
        "tools": ["api_tester", "http_scanner", "jwt_analyzer", "header_analyzer"],
    },
    "ctf_lab": {
        "id": "ctf_lab",
        "name": "CTF / Laboratório",
        "icon": "🏁",
        "description": "Desafios práticos isolados, alvos pré-configurados e reset automático.",
        "tools": ["ctf_challenges", "thm_lab", "local_lab"],
    },
}


def list_categories() -> list[dict]:
    return [
        {
            "id": c["id"],
            "name": c["name"],
            "icon": c["icon"],
            "description": c["description"],
            "tool_ids": list(c["tools"]),
        }
        for c in CATEGORIES.values()
    ]


def category_for_tool(tool_id: str) -> str | None:
    for cat in CATEGORIES.values():
        if tool_id in cat["tools"]:
            return cat["id"]
    return None


def hub_catalog() -> dict:
    """Catálogo para /api/cyber/hub e Central de Ferramentas."""
    return {
        "categories": list_categories(),
        "policy_notes": [
            "Todas as ferramentas ativas exigem alvo autorizado ou modo laboratório.",
            "Análise passiva não altera o alvo; análise ativa requer confirmação e allowlist.",
            "Localhost, redes privadas e metadata endpoints são bloqueados salvo autorização explícita.",
            "Senhas, tokens e cookies nunca são armazenados nos logs.",
            "Rate limits e timeouts são aplicados por ferramenta e por usuário (RBAC).",
        ],
    }
