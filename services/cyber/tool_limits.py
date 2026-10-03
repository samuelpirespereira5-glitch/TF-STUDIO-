"""Limites de segurança por ferramenta e por usuário — JARVIS Cyber Lab.

Todas as ferramentas defensivas devem consultar este módulo antes de
executar. Valores são conservadores por padrão e podem ser ajustados
pelo administrador via data/tool_limits.json (se existir).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
LIMITS_FILE = DATA_DIR / "tool_limits.json"
_lock = threading.Lock()
_rate_buckets: dict[str, list[float]] = {}

# Limites padrão (por execução / por janela)
DEFAULT_LIMITS = {
    "port_scanner": {
        "max_ports": 64,
        "max_concurrency": 8,
        "timeout_sec": 8.0,
        "rate_per_min": 6,
        "requires_authorized_target": True,
        "active": True,
        "description": "Varredura de portas em alvos autorizados",
    },
    "dns_lookup": {
        "max_queries": 20,
        "rate_per_min": 30,
        "timeout_sec": 5.0,
        "requires_authorized_target": False,
        "active": False,
        "description": "Consultas DNS passivas",
    },
    "subdomain_enum": {
        "max_queries": 50,
        "rate_per_min": 10,
        "timeout_sec": 10.0,
        "requires_authorized_target": True,
        "active": False,
        "description": "Enumeração de subdomínios em domínio autorizado",
    },
    "http_scanner": {
        "max_urls": 10,
        "max_response_bytes": 512_000,
        "rate_per_min": 20,
        "timeout_sec": 12.0,
        "requires_authorized_target": True,
        "active": True,
        "description": "Análise HTTP/HTTPS de URLs autorizadas",
    },
    "header_analyzer": {
        "max_urls": 5,
        "max_response_bytes": 256_000,
        "rate_per_min": 30,
        "timeout_sec": 10.0,
        "requires_authorized_target": True,
        "active": False,
        "description": "Análise passiva de headers HTTP",
    },
    "ssl_tls_analyzer": {
        "rate_per_min": 10,
        "timeout_sec": 15.0,
        "requires_authorized_target": True,
        "active": False,
        "description": "Análise de configuração SSL/TLS (sem exploração)",
    },
    "api_tester": {
        "max_endpoints": 5,
        "rate_per_min": 15,
        "timeout_sec": 12.0,
        "max_response_bytes": 256_000,
        "requires_authorized_target": True,
        "active": True,
        "description": "Testes de API apenas em endpoints autorizados",
    },
    "hash_analyzer": {
        "max_file_bytes": 5_000_000,
        "rate_per_min": 40,
        "timeout_sec": 20.0,
        "requires_authorized_target": False,
        "active": False,
        "description": "Cálculo e identificação de hashes",
    },
    "file_analyzer": {
        "max_file_bytes": 8_000_000,
        "rate_per_min": 20,
        "timeout_sec": 25.0,
        "block_executables": True,
        "requires_authorized_target": False,
        "active": False,
        "description": "Análise de metadados e estrutura de arquivos",
    },
    "log_analyzer": {
        "max_file_bytes": 10_000_000,
        "max_lines": 50_000,
        "rate_per_min": 15,
        "timeout_sec": 30.0,
        "requires_authorized_target": False,
        "active": False,
        "description": "Análise de logs com sanitização de dados sensíveis",
    },
    "dependency_scanner": {
        "max_file_bytes": 2_000_000,
        "rate_per_min": 10,
        "timeout_sec": 20.0,
        "requires_authorized_target": False,
        "active": False,
        "description": "Identificação de dependências e versões vulneráveis",
    },
    "code_scanner": {
        "max_file_bytes": 2_000_000,
        "max_lines": 20_000,
        "rate_per_min": 20,
        "timeout_sec": 25.0,
        "requires_authorized_target": False,
        "active": False,
        "description": "Análise estática de código (sem execução)",
    },
    "secrets_scanner": {
        "max_file_bytes": 2_000_000,
        "max_lines": 20_000,
        "rate_per_min": 15,
        "timeout_sec": 20.0,
        "requires_authorized_target": False,
        "active": False,
        "description": "Detecção de possíveis secrets em arquivos fornecidos",
    },
    "ip_analyzer": {
        "rate_per_min": 30,
        "timeout_sec": 8.0,
        "requires_authorized_target": False,
        "active": False,
        "description": "Classificação e reputação básica de IPs (fontes públicas)",
    },
    "malware_sandbox": {
        "max_file_bytes": 5_000_000,
        "timeout_sec": 30.0,
        "cpu_limit": True,
        "network_disabled": True,
        "rate_per_min": 5,
        "requires_authorized_target": False,
        "active": False,
        "description": "Sandbox isolado (sem rede por padrão)",
    },
    "osint_public": {
        "rate_per_min": 20,
        "timeout_sec": 12.0,
        "requires_authorized_target": False,
        "active": False,
        "description": "OSINT apenas em fontes públicas/autorizadas",
    },
}

# Multiplicadores por role (owner tem mais margem)
ROLE_MULTIPLIER = {
    "owner": 2.0,
    "admin": 1.0,
    "user": 0.5,
    "guest": 0.25,
    "researcher": 1.25,
    "moderator": 1.5,
}


def _load_overrides() -> dict:
    if not LIMITS_FILE.exists():
        return {}
    try:
        with open(LIMITS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_limits(tool_id: str) -> dict:
    base = dict(DEFAULT_LIMITS.get(tool_id, {
        "rate_per_min": 10,
        "timeout_sec": 10.0,
        "requires_authorized_target": True,
        "active": False,
        "description": "Ferramenta genérica",
    }))
    overrides = _load_overrides().get(tool_id, {})
    if isinstance(overrides, dict):
        base.update(overrides)
    return base


def get_all_limits() -> dict:
    out = {}
    for k in DEFAULT_LIMITS:
        out[k] = get_limits(k)
    overrides = _load_overrides()
    for k, v in overrides.items():
        if k not in out and isinstance(v, dict):
            out[k] = v
    return out


def check_rate_limit(tool_id: str, user_key: str, role: str = "user") -> tuple[bool, str]:
    """Retorna (ok, mensagem). Bloqueia se taxa excedida."""
    limits = get_limits(tool_id)
    rate = float(limits.get("rate_per_min", 10))
    mult = ROLE_MULTIPLIER.get(role, 1.0)
    rate = max(1.0, rate * mult)
    key = f"{tool_id}:{user_key}"
    now = time.time()
    window = 60.0
    with _lock:
        bucket = _rate_buckets.setdefault(key, [])
        bucket[:] = [t for t in bucket if now - t < window]
        if len(bucket) >= rate:
            return False, "Limite de requisições atingido. Aguarde antes de tentar novamente."
        bucket.append(now)
    return True, ""


def enforce_size(tool_id: str, size_bytes: int) -> tuple[bool, str]:
    limits = get_limits(tool_id)
    max_b = int(limits.get("max_file_bytes") or limits.get("max_response_bytes") or 0)
    if max_b and size_bytes > max_b:
        return False, f"Entrada inválida: tamanho máximo permitido é {max_b} bytes."
    return True, ""


def is_active_tool(tool_id: str) -> bool:
    return bool(get_limits(tool_id).get("active", False))


def requires_authorized_target(tool_id: str) -> bool:
    return bool(get_limits(tool_id).get("requires_authorized_target", True))


def policy_snapshot(role: str = "user") -> dict:
    """Snapshot para a página de Políticas de Segurança."""
    tools = {}
    for tid, base in DEFAULT_LIMITS.items():
        lim = get_limits(tid)
        tools[tid] = {
            "description": lim.get("description", ""),
            "active": lim.get("active", False),
            "requires_authorized_target": lim.get("requires_authorized_target", True),
            "rate_per_min": lim.get("rate_per_min"),
            "timeout_sec": lim.get("timeout_sec"),
            "max_ports": lim.get("max_ports"),
            "max_urls": lim.get("max_urls"),
            "max_file_bytes": lim.get("max_file_bytes") or lim.get("max_response_bytes"),
            "max_concurrency": lim.get("max_concurrency"),
            "network_disabled": lim.get("network_disabled"),
            "role_multiplier": ROLE_MULTIPLIER.get(role, 1.0),
        }
    return {
        "role": role,
        "role_multipliers": ROLE_MULTIPLIER,
        "tools": tools,
        "messages": {
            "unauthorized_target": "Alvo não autorizado",
            "rate_limited": "Limite de requisições atingido",
            "invalid_input": "Entrada inválida",
            "blocked_policy": "Operação bloqueada pela política de segurança",
            "tool_unavailable": "Ferramenta não disponível neste ambiente",
        },
    }
