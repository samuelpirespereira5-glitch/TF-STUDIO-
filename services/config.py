import json
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config.json"


def _load_dotenv(path):
    """Carrega um arquivo .env local (desenvolvimento) sem depender de pacote
    extra. NÃO sobrescreve variáveis que já existam no ambiente real — em
    produção, o que a hospedagem define sempre vence. Formato: CHAVE=valor,
    linhas com # são comentário, aspas ao redor do valor são removidas."""
    try:
        if not path.is_file():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip().removeprefix("export ").strip()
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            if key and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


# tem de rodar ANTES de qualquer outro módulo ler os.getenv
_load_dotenv(BASE_DIR / ".env")

# Campos secretos (nunca renderizados no HTML) -> variável de ambiente que os substitui.
ENV_NAMES = {
    "openrouter_api_key": "OPENROUTER_API_KEY",
    "groq_api_key": "GROQ_API_KEY",
    "google_api_key": "GOOGLE_API_KEY",
    "cerebras_api_key": "CEREBRAS_API_KEY",
    "github_api_key": "GITHUB_API_KEY",
    "huggingface_api_key": "HUGGINGFACE_API_KEY",
    "cohere_api_key": "COHERE_API_KEY",
    "sambanova_api_key": "SAMBANOVA_API_KEY",
    "ai_api_key": "AI_API_KEY",
    "google_maps_api_key": "GOOGLE_MAPS_API_KEY",
}
SECRET_FIELDS = tuple(ENV_NAMES)
PLAIN_FIELDS = ("openrouter_model", "ai_provider", "ai_base_url", "ai_model")

DEFAULT_CONFIG = {
    "openrouter_api_key": "",
    "openrouter_model": "openrouter/free",
    # Camadas extra 100% grátis (sem cartão de crédito), usadas
    # automaticamente quando a cota diária/por minuto da OpenRouter
    # estiver esgotada. Cada uma é opcional — o app só usa a que tiver
    # chave preenchida.
    "groq_api_key": "",
    "google_api_key": "",
    "cerebras_api_key": "",
    "github_api_key": "",
    "huggingface_api_key": "",
    "cohere_api_key": "",
    "sambanova_api_key": "",
    # Provedor de IA genérico e configurável — para quem quer usar a
    # própria chave (paga ou não) de QUALQUER serviço compatível com o
    # formato de API da OpenAI (OpenAI, Azure OpenAI, Anthropic via
    # endpoint compatível, Together, Fireworks, DeepSeek, um servidor
    # próprio com vLLM/Ollama etc.), sem depender dos provedores
    # gratuitos acima. Tem prioridade sobre eles quando configurado
    # (ver services/ai_engine.py:_build_attempts). Nunca é exposto no
    # front-end — só existe aqui no backend/config.
    "ai_provider": "",
    "ai_api_key": "",
    "ai_base_url": "",
    "ai_model": "",
    # Campo mantido por compatibilidade com configurações antigas, mas
    # sem uso: o holograma de "lugar real" agora roda 100% em cima do
    # OpenStreetMap (Nominatim + Open-Meteo Elevation + tiles OSM), que
    # não precisa de chave nenhuma. Veja services/maps_service.py.
    "google_maps_api_key": "",
}


def load_config():
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {**DEFAULT_CONFIG, **data}
    except Exception:
        pass
    return DEFAULT_CONFIG.copy()


CONFIG = load_config()


def save_config():
    """Gravação atômica e com permissão 600 (o arquivo guarda chaves de API)."""
    try:
        tmp = CONFIG_FILE.with_suffix(".json.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(CONFIG, ensure_ascii=False, indent=2))
        os.replace(tmp, CONFIG_FILE)
        return True
    except Exception:
        return False


def _tighten_permissions():
    """Corrige arquivos de segredo criados por versões antigas (644 -> 600)."""
    if os.name != "posix":
        return
    for f in (CONFIG_FILE, BASE_DIR / "auth.json", BASE_DIR / ".env"):
        try:
            if f.is_file() and (f.stat().st_mode & 0o077):
                f.chmod(0o600)
        except Exception:
            pass


_tighten_permissions()


def get_api_key():
    env_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if env_key:
        return env_key
    return CONFIG.get("openrouter_api_key", "").strip()


def get_model():
    return CONFIG.get("openrouter_model", "openrouter/free").strip() or "openrouter/free"


def get_groq_api_key():
    env_key = os.getenv("GROQ_API_KEY", "").strip()
    if env_key:
        return env_key
    return CONFIG.get("groq_api_key", "").strip()


def get_google_api_key():
    env_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if env_key:
        return env_key
    return CONFIG.get("google_api_key", "").strip()


def get_cerebras_api_key():
    env_key = os.getenv("CEREBRAS_API_KEY", "").strip()
    if env_key:
        return env_key
    return CONFIG.get("cerebras_api_key", "").strip()


def get_github_api_key():
    env_key = os.getenv("GITHUB_API_KEY", "").strip()
    if env_key:
        return env_key
    return CONFIG.get("github_api_key", "").strip()


def get_huggingface_api_key():
    env_key = os.getenv("HUGGINGFACE_API_KEY", "").strip()
    if env_key:
        return env_key
    return CONFIG.get("huggingface_api_key", "").strip()


def get_cohere_api_key():
    env_key = os.getenv("COHERE_API_KEY", "").strip()
    if env_key:
        return env_key
    return CONFIG.get("cohere_api_key", "").strip()


def get_sambanova_api_key():
    env_key = os.getenv("SAMBANOVA_API_KEY", "").strip()
    if env_key:
        return env_key
    return CONFIG.get("sambanova_api_key", "").strip()


def get_custom_provider():
    """Nome livre do provedor personalizado (só rótulo, não afeta a
    chamada em si) — ex: 'openai', 'anthropic', 'azure', 'together',
    'meu-servidor'. Lido de AI_PROVIDER (env) ou Configurações."""
    env_val = os.getenv("AI_PROVIDER", "").strip()
    if env_val:
        return env_val
    return CONFIG.get("ai_provider", "").strip()


def get_custom_api_key():
    env_key = os.getenv("AI_API_KEY", "").strip()
    if env_key:
        return env_key
    return CONFIG.get("ai_api_key", "").strip()


def get_custom_base_url():
    env_val = os.getenv("AI_BASE_URL", "").strip()
    if env_val:
        return env_val
    return CONFIG.get("ai_base_url", "").strip()


def get_custom_model():
    env_val = os.getenv("AI_MODEL", "").strip()
    if env_val:
        return env_val
    return CONFIG.get("ai_model", "").strip()


def has_custom_ai_provider():
    """True só quando há o mínimo pra fazer uma chamada de verdade:
    endpoint + chave + modelo. Diferente dos provedores grátis fixos
    acima, aqui não há como adivinhar o modelo certo de um serviço
    arbitrário, então os três campos são obrigatórios."""
    return bool(get_custom_api_key() and get_custom_base_url() and get_custom_model())


def get_google_maps_api_key():
    env_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if env_key:
        return env_key
    return CONFIG.get("google_maps_api_key", "").strip()


def has_any_ai_key():
    """True se pelo menos um provedor de IA (o personalizado configurável
    via AI_PROVIDER/AI_API_KEY/AI_BASE_URL/AI_MODEL, ou algum dos
    grátis: OpenRouter, Groq, Google AI Studio, Cerebras, GitHub Models,
    Hugging Face, Cohere ou SambaNova) tiver uma chave configurada —
    usado para decidir se mostramos o aviso de 'nenhuma chave
    configurada', já que o app funciona com qualquer um deles, sozinho
    ou combinado."""
    return bool(
        has_custom_ai_provider()
        or get_api_key() or get_groq_api_key() or get_google_api_key()
        or get_cerebras_api_key() or get_github_api_key() or get_huggingface_api_key()
        or get_cohere_api_key() or get_sambanova_api_key()
    )


# ------------------------------------------------------------------
# Proteção de segredos: máscara para a UI, redação em respostas e auditoria
# ------------------------------------------------------------------
def _secret_value(field):
    env = os.getenv(ENV_NAMES[field], "").strip()
    return env or str(CONFIG.get(field, "") or "").strip()


def mask_secret(value):
    """'sk-or-v1-abcdef123456' -> '••••3456' (nunca revela mais que 4 chars)."""
    value = (value or "").strip()
    if not value:
        return ""
    return "••••" + value[-4:] if len(value) >= 12 else "••••"


def secret_hints():
    """Dicas seguras para a tela de Configurações: só últimos 4 caracteres e a
    origem (ambiente ou arquivo). O valor completo NUNCA vai para o HTML."""
    hints = {}
    for field, env_name in ENV_NAMES.items():
        env = os.getenv(env_name, "").strip()
        if env:
            hints[field] = f"{mask_secret(env)} (ambiente)"
        elif str(CONFIG.get(field, "") or "").strip():
            hints[field] = f"{mask_secret(CONFIG[field])} (arquivo)"
    return hints


_EXTRA_SECRET_ENVS = ("SECRET_KEY", "MASTER_PASSWORD", "MASTER_PASSWOR", "MASTER_PASSWORD_HASH",
                      "HIBP_API_KEY", "NETLIFY_AUTH_TOKEN")


def redact_secrets(text):
    """Troca por [oculto] qualquer valor de segredo configurado que apareça em
    `text` (ex.: mensagem de erro de um provedor que ecoou a chave). Só
    valores exatos com 8+ caracteres — não mexe em conteúdo comum."""
    if not text:
        return text
    values = {_secret_value(f) for f in SECRET_FIELDS}
    values.update(os.getenv(n, "").strip() for n in _EXTRA_SECRET_ENVS)
    for v in sorted((v for v in values if len(v) >= 8), key=len, reverse=True):
        if v in text:
            text = text.replace(v, "[oculto]")
    return text


def secret_audit():
    """Checagens rápidas de higiene de segredos. Retorna [(nível, texto)],
    nível em 'ok' | 'warn' | 'bad'."""
    out = []
    in_file = [f for f in SECRET_FIELDS
               if str(CONFIG.get(f, "") or "").strip() and not os.getenv(ENV_NAMES[f], "").strip()]
    if in_file:
        out.append(("warn", f"{len(in_file)} chave(s) só no arquivo config.json (texto puro): "
                            f"{', '.join(in_file)}. Prefira variáveis de ambiente."))
    else:
        out.append(("ok", "Nenhuma chave de API depende do arquivo config.json."))
    if os.name == "posix":
        for f in (CONFIG_FILE, BASE_DIR / "auth.json", BASE_DIR / ".env"):
            try:
                if f.is_file() and (f.stat().st_mode & 0o077):
                    out.append(("bad", f"{f.name} legível por outros usuários do servidor "
                                       f"(permissão {oct(f.stat().st_mode & 0o777)[2:]}). Rode: chmod 600 {f.name}"))
            except Exception:
                pass
    if not os.getenv("SECRET_KEY", "").strip():
        out.append(("warn", "SECRET_KEY não definida: as sessões caem a cada reinício e divergem se "
                            "houver mais de 1 worker. Gere uma: python -c \"import secrets;print(secrets.token_hex(32))\""))
    master_plain = (os.getenv("MASTER_PASSWORD", "") or os.getenv("MASTER_PASSWOR", "")).strip()
    master_hash = os.getenv("MASTER_PASSWORD_HASH", "").strip()
    if master_plain and master_hash:
        out.append(("warn", "MASTER_PASSWORD e MASTER_PASSWORD_HASH estão definidos. A MASTER_PASSWORD está ativa para compatibilidade; prefira o hash quando possível."))
    elif master_plain:
        out.append(("warn", "MASTER_PASSWORD está ativa. Funciona em produção para compatibilidade, mas o hash continua sendo a opção mais segura."))
    elif master_hash:
        out.append(("ok", "Senha mestre configurada por MASTER_PASSWORD_HASH."))
    gi = BASE_DIR / ".gitignore"
    try:
        ignored = gi.read_text(encoding="utf-8") if gi.is_file() else ""
    except Exception:
        ignored = ""
    missing = [n for n in ("config.json", "auth.json", ".env", "data/") if n not in ignored]
    if missing:
        out.append(("bad", f".gitignore não cobre: {', '.join(missing)} — risco de subir segredos para o Git."))
    else:
        out.append(("ok", ".gitignore cobre config.json, auth.json, .env e data/."))
    return out
