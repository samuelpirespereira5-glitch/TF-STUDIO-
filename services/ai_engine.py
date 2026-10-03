from openai import OpenAI
import httpx
import json
import re
import time

from .config import (
    get_api_key, get_model,
    get_groq_api_key, get_google_api_key, get_cerebras_api_key,
    get_github_api_key, get_huggingface_api_key,
    get_cohere_api_key, get_sambanova_api_key,
    get_custom_provider, get_custom_api_key, get_custom_base_url, get_custom_model,
    has_custom_ai_provider,
)
from .countries import country_info
from .utils import extract_html

APP_NAME = "TRISTAN THORNE"

# Alguns modelos gratuitos da OpenRouter são modelos de "raciocínio" e, por
# padrão, devolvem o pensamento interno junto da resposta (às vezes até no
# lugar da resposta, se o raciocínio consumir todo o limite de tokens).
# Pedimos à OpenRouter para excluir esse raciocínio da resposta e, por
# segurança, removemos qualquer bloco desse tipo que ainda vier.
NO_REASONING = {"reasoning": {"exclude": True}}
THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)

# Modelos gratuitos usados como reserva quando o modelo configurado nas
# Configurações falhar, demorar demais ou devolver uma resposta vazia (o
# principal motivo do erro "A IA não retornou conteúdo."). Tentamos o
# modelo escolhido pelo usuário primeiro e só caímos para esta lista se
# ele realmente não funcionar — assim a criação de site e o Jarvis não
# ficam reféns de um único modelo instável.
#
# IMPORTANTE: os slugs ":free" da OpenRouter mudam com frequência (modelos
# saem do plano grátis ou são descontinuados, o que gera erros 404 tipo
# "This model is unavailable for free"). Por isso "openrouter/free" — o
# roteador automático da própria OpenRouter, que sempre escolhe um modelo
# grátis disponível na hora — vem primeiro na lista de reserva: ele não
# fica desatualizado. Os demais são só reforço extra caso o roteador
# automático esteja fora do ar.
FALLBACK_FREE_MODELS = [
    "openrouter/free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "z-ai/glm-5.2:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "deepseek/deepseek-r1:free",
    "meta-llama/llama-3.1-70b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
]

# ------------------------------------------------------------------
# Descoberta "ao vivo" de modelos grátis
# ------------------------------------------------------------------
# Os slugs ":free" da lista acima também podem ficar desatualizados com
# o tempo (é exatamente isso que causa o erro 404 "This model is
# unavailable for free"). Como reforço extra, consultamos a própria
# lista de modelos da OpenRouter e guardamos em cache por algumas horas
# quais modelos estão com preço $0 agora — assim, mesmo que toda a lista
# fixa acima fique obsoleta, o app ainda encontra sozinho um modelo
# grátis que está funcionando de verdade naquele momento.
_MODELS_ENDPOINT = "https://openrouter.ai/api/v1/models"
_live_free_models_cache = {"models": [], "fetched_at": 0.0}
_LIVE_CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 horas


def _fetch_live_free_models():
    try:
        resp = httpx.get(_MODELS_ENDPOINT, timeout=8)
        resp.raise_for_status()
        entries = resp.json().get("data", [])
    except Exception:
        return []

    free_ids = []
    for entry in entries:
        model_id = entry.get("id") or ""
        if not model_id.endswith(":free"):
            continue
        pricing = entry.get("pricing") or {}
        try:
            prompt_price = float(pricing.get("prompt") or 0)
            completion_price = float(pricing.get("completion") or 0)
        except (TypeError, ValueError):
            continue
        if prompt_price == 0 and completion_price == 0:
            free_ids.append(model_id)
    return free_ids


def _live_free_models():
    now = time.time()
    cache = _live_free_models_cache
    if cache["models"] and (now - cache["fetched_at"]) < _LIVE_CACHE_TTL_SECONDS:
        return cache["models"]

    fetched = _fetch_live_free_models()
    if fetched:
        cache["models"] = fetched
        cache["fetched_at"] = now
        return fetched
    # Se a consulta falhar (sem internet, OpenRouter fora do ar etc.),
    # mantemos o que já estava em cache (mesmo vencido) em vez de nada.
    return cache["models"]


def _clean_reasoning(text: str) -> str:
    if not text:
        return text
    text = THINK_BLOCK_RE.sub("", text)
    return text.strip()


# ------------------------------------------------------------------
# Deixa a fala do Jarvis "falada", sem símbolos de formatação de texto
# (markdown), já que ele é lido em voz alta e exibido como texto puro.
# ------------------------------------------------------------------

_MD_BOLD_ITALIC_RE = re.compile(r"(\*\*\*|\*\*|\*|___|__|_)(.+?)\1")
_MD_HEADER_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s*")
_MD_BULLET_RE = re.compile(r"(?m)^\s*[\*\-•]\s+")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
_MD_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def humanize_reply(text: str) -> str:
    """Remove marcações de markdown (asteriscos, hashtags, listas com
    traço, links, blocos de código) para o Jarvis soar como uma
    conversa falada normal, e não como um texto formatado."""

    if not text:
        return text

    text = _MD_CODE_FENCE_RE.sub("", text)
    text = text.replace("`", "")
    text = _MD_HEADER_RE.sub("", text)
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _MD_BULLET_RE.sub("", text)
    text = _MD_BOLD_ITALIC_RE.sub(r"\2", text)
    # Sobras soltas de asterisco/hashtag que não vieram em pares
    text = text.replace("*", "").replace("#", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


# Tempo máximo de espera por CADA tentativa de modelo antes de desistir
# e passar pro próximo. Isso era 180s — praticamente 3 minutos de espera
# num modelo travado antes de sequer tentar a reserva — e era a maior
# causa do "atraso" percebido no Jarvis. 25s é tempo de sobra pra
# qualquer modelo rápido responder, e libera o fallback bem mais cedo
# quando um provedor está lento ou fora do ar.
REQUEST_TIMEOUT_SECONDS = 12


def _openrouter_client():
    api_key = get_api_key()
    if not api_key:
        return None
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=1)


# ------------------------------------------------------------------
# Provedor de IA genérico e configurável (AI_PROVIDER/AI_API_KEY/
# AI_BASE_URL/AI_MODEL)
# ------------------------------------------------------------------
# Diferente das camadas grátis abaixo, este NÃO tem uma lista fixa de
# modelos: o usuário aponta pra qualquer endpoint compatível com o
# formato de API da OpenAI (OpenAI, Azure OpenAI, Anthropic via
# endpoint compatível, Together, Fireworks, DeepSeek, um servidor
# próprio com vLLM/Ollama etc.) e diz explicitamente qual modelo usar.
# Ele entra PRIMEIRO em _build_attempts() — na frente até da
# OpenRouter — porque, se a pessoa configurou a própria chave (paga ou
# não), é razoável assumir que ela quer aquele provedor priorizado, e
# não tratado como só mais uma camada de reserva grátis.
def _custom_client():
    api_key = get_custom_api_key()
    base_url = get_custom_base_url()
    if not api_key or not base_url:
        return None
    return OpenAI(base_url=base_url, api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=1)


# ------------------------------------------------------------------
# Camadas extra 100% grátis (sem cartão de crédito)
# ------------------------------------------------------------------
# A cota grátis da OpenRouter é curta (~50 mensagens/dia sem créditos).
# Para quem não pode/quer pagar nada, Groq, Google AI Studio e Cerebras
# oferecem chaves de API totalmente grátis, com cotas diárias bem mais
# generosas, e falam o mesmo "idioma" da OpenAI — então dá pra usá-las
# aqui do mesmo jeito. Cada uma é 100% opcional: o app só entra nelas
# se o usuário colar a respectiva chave em Configurações (ou definir a
# variável de ambiente). Quando a OpenRouter estiver com a cota
# esgotada, o Jarvis passa para a próxima camada sozinho, sem o usuário
# precisar fazer nada.
def _groq_client():
    api_key = get_groq_api_key()
    if not api_key:
        return None
    return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=1)


def _google_client():
    api_key = get_google_api_key()
    if not api_key:
        return None
    return OpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=1,
    )


def _cerebras_client():
    api_key = get_cerebras_api_key()
    if not api_key:
        return None
    return OpenAI(base_url="https://api.cerebras.ai/v1", api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=1)


# GitHub Models: catálogo de modelos (GPT-4o, Llama, Phi, Mistral...)
# liberado de graça pra qualquer conta do GitHub, sem cartão — só criar
# um Personal Access Token (nem precisa de permissão especial) em
# github.com/settings/tokens e colar aqui. Fala o mesmo formato OpenAI.
def _github_client():
    api_key = get_github_api_key()
    if not api_key:
        return None
    return OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=1,
    )


# Hugging Face Inference Providers: roteador grátis (com token de leitura
# gratuito, sem cartão) na frente de vários provedores de inferência que
# hospedam modelos abertos. Também fala o formato OpenAI.
def _huggingface_client():
    api_key = get_huggingface_api_key()
    if not api_key:
        return None
    return OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=1,
    )


# Cohere: plano de avaliação (trial key) gratuito e permanente, sem
# cartão de crédito, com um limite de chamadas por minuto — ótimo como
# mais uma camada de reserva. Fala o formato OpenAI na rota /compatibility.
def _cohere_client():
    api_key = get_cohere_api_key()
    if not api_key:
        return None
    return OpenAI(
        base_url="https://api.cohere.ai/compatibility/v1",
        api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=1,
    )


# SambaNova Cloud: cota diária grátis generosa, sem cartão de crédito,
# rodando modelos abertos em hardware próprio (bem rápida). Também fala
# o formato OpenAI.
def _sambanova_client():
    api_key = get_sambanova_api_key()
    if not api_key:
        return None
    return OpenAI(
        base_url="https://api.sambanova.ai/v1",
        api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=1,
    )


# Modelos grátis conhecidos de cada camada extra (sinal de reforço: se
# algum desses slugs também mudar no futuro, o app simplesmente pula
# para o próximo, do mesmo jeito que já faz com a OpenRouter).
GROQ_FREE_MODELS = [
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
]
GOOGLE_FREE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]
CEREBRAS_FREE_MODELS = [
    "llama-3.3-70b",
    "llama3.1-8b",
]
GITHUB_FREE_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "Meta-Llama-3.1-70B-Instruct",
    "Phi-3.5-MoE-instruct",
    "Mistral-Nemo",
]
HUGGINGFACE_FREE_MODELS = [
    "meta-llama/Llama-3.3-70B-Instruct:fireworks-ai",
    "Qwen/Qwen2.5-72B-Instruct:fireworks-ai",
    "mistralai/Mistral-Nemo-Instruct-2407:novita",
]
COHERE_FREE_MODELS = [
    "command-r-plus-08-2024",
    "command-r-08-2024",
]
SAMBANOVA_FREE_MODELS = [
    "Meta-Llama-3.3-70B-Instruct",
    "Meta-Llama-3.1-8B-Instruct",
]

# (provedor, função que monta o cliente, lista de modelos fixos)
# A OpenRouter é tratada à parte porque a lista dela é dinâmica
# (modelo escolhido pelo usuário + reservas + descoberta ao vivo).
EXTRA_PROVIDERS = [
    ("groq", _groq_client, GROQ_FREE_MODELS),
    ("google", _google_client, GOOGLE_FREE_MODELS),
    ("cerebras", _cerebras_client, CEREBRAS_FREE_MODELS),
    ("github", _github_client, GITHUB_FREE_MODELS),
    ("huggingface", _huggingface_client, HUGGINGFACE_FREE_MODELS),
    ("cohere", _cohere_client, COHERE_FREE_MODELS),
    ("sambanova", _sambanova_client, SAMBANOVA_FREE_MODELS),
]


# Modelos gratuitos da OpenRouter com suporte real a análise de imagem
# (multimodal). Usados só quando o usuário anexa uma foto no Jarvis —
# nem todo modelo grátis entende o bloco "image_url", então esse
# caminho fica separado da lista de texto acima em vez de misturado
# nela (evita gastar tentativas em modelos que vão simplesmente
# ignorar ou rejeitar a imagem).
VISION_FREE_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "qwen/qwen2.5-vl-72b-instruct:free",
    "meta-llama/llama-3.2-11b-vision-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
]


def _models_to_try(vision_only=False):
    if vision_only:
        models = list(VISION_FREE_MODELS)
        configured = get_model()
        if configured and configured not in models:
            models.append(configured)
        return models

    configured = get_model()
    models = [configured]

    for m in FALLBACK_FREE_MODELS:
        if m not in models:
            models.append(m)

    # Última linha de defesa: alguns modelos grátis que estão realmente
    # disponíveis agora na OpenRouter, segundo a própria API deles.
    for m in _live_free_models()[:6]:
        if m not in models:
            models.append(m)

    return models


def _short_error(e):
    """Reduz a exceção a uma linha curta e legível, em vez do dump
    gigante de JSON que a biblioteca da OpenRouter às vezes devolve
    (isso é o que fazia a mensagem de erro tomar a tela inteira)."""
    text = str(e)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 180:
        text = text[:177] + "..."
    return text


# ------------------------------------------------------------------
# Limite de taxa ("rate limit") de cada provedor
# ------------------------------------------------------------------
# Um erro 429 ("Rate limit exceeded") é uma cota da CONTA/CHAVE daquele
# provedor como um todo (não de um modelo específico dele) — por isso,
# ao bater nele, pulamos direto para o PRÓXIMO PROVEDOR configurado em
# vez de continuar testando outros modelos do mesmo provedor à toa.
# Guardamos um pequeno "tempo de espera" por provedor em memória para
# as próximas mensagens já pularem esse provedor de cara, sem nem
# chamar a API dele de novo, até o tempo passar.
RATE_LIMIT_COOLDOWN_SECONDS = 45
_provider_rate_limited_until = {}


def _is_rate_limit_error(e) -> bool:
    text = str(e).lower()
    return "429" in text or "rate limit" in text or "rate-limit" in text or "rate_limit" in text


def _build_attempts(vision_only=False):
    """Monta a lista de tentativas (provedor, cliente, modelo) na ordem
    em que devem ser testadas: primeiro a OpenRouter (se tiver chave),
    com o modelo escolhido pelo usuário e as reservas grátis; depois
    Groq, Google AI Studio e Cerebras — cada uma só entra se o usuário
    tiver colado a respectiva chave grátis em Configurações. Provedores
    ainda "esfriando" de um rate limit recente são pulados sem nem
    tentar.

    Quando vision_only=True (o usuário anexou uma foto no Jarvis), só
    tentamos a OpenRouter com os modelos com visão de VISION_FREE_MODELS
    — os outros provedores grátis configurados aqui não têm um modelo
    de visão definido, então entrar neles só gastaria tempo com um erro
    certo."""

    now = time.time()
    attempts = []

    # Provedor personalizado primeiro (se configurado) — tanto no modo
    # texto quanto no modo visão, já que não há como saber de antemão
    # se o modelo que o usuário apontou suporta imagem ou não; se não
    # suportar, ele simplesmente falha e a cadeia cai pro próximo.
    if now >= _provider_rate_limited_until.get("custom", 0):
        custom_client = _custom_client()
        if custom_client is not None:
            model = get_custom_model()
            if model:
                attempts.append(("custom", custom_client, model))

    if now >= _provider_rate_limited_until.get("openrouter", 0):
        or_client = _openrouter_client()
        if or_client is not None:
            for model in _models_to_try(vision_only=vision_only):
                attempts.append(("openrouter", or_client, model))

    if vision_only:
        return attempts

    for name, client_fn, model_list in EXTRA_PROVIDERS:
        if now < _provider_rate_limited_until.get(name, 0):
            continue
        client = client_fn()
        if client is None:
            continue
        for model in model_list:
            attempts.append((name, client, model))

    return attempts


def _no_key_configured_message():
    return (
        "Nenhuma chave de IA foi configurada ainda. Abra 'Configurações' e "
        "cole a chave de um provedor: pode ser o SEU provedor pago/próprio "
        "(qualquer serviço compatível com a API da OpenAI — OpenAI, Azure, "
        "Anthropic, Together, um servidor próprio etc.) no card 'Provedor de "
        "IA personalizado', ou, se preferir não pagar nada, uma chave grátis "
        "da OpenRouter (openrouter.ai/keys), Groq (console.groq.com/keys), "
        "Google AI Studio (aistudio.google.com/apikey), Cerebras "
        "(cloud.cerebras.ai), GitHub Models (github.com/settings/tokens), "
        "Hugging Face (huggingface.co/settings/tokens), Cohere "
        "(dashboard.cohere.com/api-keys) ou SambaNova (cloud.sambanova.ai/apis)."
    )


def _rate_limit_message():
    return (
        "Todos os provedores de IA configurados bateram no limite de "
        "mensagens grátis por agora. Esse limite é da conta/chave (não "
        "de um modelo só). Espere 1 ou 2 minutos e tente de novo. Se "
        "isso acontecer com frequência, considere configurar mais de um "
        "provedor grátis em Configurações (OpenRouter + Groq + Google "
        "AI Studio + GitHub Models + Hugging Face, por exemplo) — cada "
        "um tem uma cota diária separada, então quando um esgota o app "
        "passa pro próximo sozinho, sem custar nada."
    )


def _complete(messages, max_tokens, temperature=0.7, validator=None, return_finish_reason=False, vision=False):
    """Faz a chamada à IA tentando, em ordem, todos os provedores/
    modelos grátis configurados, até um deles devolver conteúdo de
    verdade. É isto que evita o erro 'A IA não retornou conteúdo.':
    em vez de desistir na primeira falha/resposta vazia/rate limit,
    tenta o próximo modelo — e, se preciso, o próximo provedor —
    automaticamente.

    Se `validator` for passado, o conteúdo só é aceito se
    `validator(content)` for verdadeiro — usado por exemplo para exigir
    que a resposta contenha HTML de verdade na criação/edição de sites,
    já que alguns modelos grátis às vezes devolvem só um comentário em
    vez do código pedido.

    Se `vision=True` (mensagem com uma imagem anexada), só tentamos os
    modelos grátis com suporte real a imagem (ver VISION_FREE_MODELS),
    em vez da lista normal de texto."""

    attempts = _build_attempts(vision_only=vision)
    if not attempts:
        if vision:
            raise RuntimeError(
                "A análise de imagem precisa de uma chave da OpenRouter "
                "configurada em Configurações (é o único provedor grátis "
                "com modelo de visão disponível aqui) — cole uma chave "
                "grátis de openrouter.ai/keys e tente de novo."
            )
        raise RuntimeError(_no_key_configured_message())

    last_error = None
    any_success_attempted = False
    skip_providers = set()

    # Orçamento de tempo total: hospedagens grátis (Render, PythonAnywhere,
    # Railway etc.) costumam ter um limite de ~25-30s antes de o próprio
    # servidor/proxy devolver uma página de erro em HTML no lugar da
    # resposta do Flask — e é exatamente essa página HTML chegando no
    # navegador que quebrava o "res.json()" no Jarvis com o erro
    # "Unexpected token '<'". Com muitos modelos grátis pra testar (cada
    # um até 12s), a soma podia passar bem desse limite. Paramos de
    # tentar mais modelos depois desse teto, e devolvemos um erro nosso,
    # em JSON de verdade, dentro do tempo que o proxy aceita.
    start_time = time.time()
    MAX_TOTAL_SECONDS = 20

    for provider, client, model in attempts:
        if provider in skip_providers:
            continue
        if time.time() - start_time > MAX_TOTAL_SECONDS:
            break
        any_success_attempted = True
        try:
            kwargs = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature)
            if provider == "openrouter":
                kwargs["extra_headers"] = {"X-Title": APP_NAME}
                kwargs["extra_body"] = NO_REASONING
            response = client.chat.completions.create(**kwargs)
        except Exception as e:
            last_error = e
            if _is_rate_limit_error(e):
                _provider_rate_limited_until[provider] = time.time() + RATE_LIMIT_COOLDOWN_SECONDS
                skip_providers.add(provider)
            continue

        content = _clean_reasoning(response.choices[0].message.content)
        finish_reason = getattr(response.choices[0], "finish_reason", None)

        if not content:
            last_error = RuntimeError("resposta vazia")
            continue

        if validator and not validator(content):
            last_error = RuntimeError("resposta em formato inesperado")
            continue

        return (content, finish_reason) if return_finish_reason else content

    if not any_success_attempted:
        # Todos os provedores configurados estavam esfriando de um rate
        # limit recente — nem chegamos a chamar nenhuma API de novo.
        raise RuntimeError(_rate_limit_message())

    if last_error is not None and _is_rate_limit_error(last_error) and len(skip_providers) >= len({p for p, _, _ in attempts}):
        raise RuntimeError(_rate_limit_message())

    detail = _short_error(last_error) if last_error else "motivo desconhecido"
    raise RuntimeError(
        f"A IA não conseguiu responder depois de tentar alguns "
        "modelos grátis dentro do tempo limite. Tente de novo — às "
        "vezes o próximo modelo da fila responde rápido. Verifique "
        f"também sua internet ou suas chaves em Configurações. Último "
        f"erro: {detail}"
    )


def ai_request(prompt, system=None, max_tokens=7000, validator=None):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    return _complete(messages, max_tokens=max_tokens, validator=validator)


def _tidy_whitespace(text: str) -> str:
    """Só limpa espaçamento excessivo, sem tocar em nenhuma marcação
    markdown — diferente de humanize_reply(), que existia para uma época
    em que o Jarvis não podia usar formatação nenhuma."""
    if not text:
        return text
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def ai_chat(messages, max_tokens=3072, temperature=0.7, max_continuations=3, vision=False):
    """Conversa do Jarvis. Se a resposta for cortada por ter batido no
    limite de tokens (finish_reason == 'length'), pede automaticamente
    para o modelo continuar de onde parou e concatena tudo — assim o
    usuário nunca recebe uma resposta pela metade, mesmo em respostas
    bem longas e detalhadas.

    `vision=True` quando a última mensagem do usuário inclui uma
    imagem anexada (ver services/live_data e app._apply_attachment) —
    restringe as tentativas aos modelos grátis com suporte a imagem."""
    working_messages = list(messages)
    full_reply = ""

    for attempt in range(max_continuations + 1):
        content, finish_reason = _complete(
            working_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            return_finish_reason=True,
            vision=vision,
        )
        full_reply += content

        if finish_reason != "length" or attempt == max_continuations:
            break

        working_messages = working_messages + [
            {"role": "assistant", "content": content},
            {
                "role": "user",
                "content": (
                    "Sua resposta foi cortada por limite de tamanho. "
                    "Continue exatamente de onde parou — sem repetir "
                    "nada do que já foi escrito, sem reiniciar a "
                    "resposta e sem dizer que estava cortada — só "
                    "continue o texto naturalmente."
                ),
            },
        ]

    return _tidy_whitespace(full_reply)


# ------------------------------------------------------------------
# Geração de site
# ------------------------------------------------------------------

def build_site_prompt(data, has_logo, has_cover, gallery_count):
    sections = ", ".join(data["sections"])

    images_info_lines = []
    if has_logo:
        images_info_lines.append(
            "- Existe um LOGO. Use exatamente o texto ASSET_LOGO como valor "
            "do atributo src de uma tag <img> no cabeçalho (e no rodapé, se "
            "fizer sentido). Não troque, não invente outro nome de arquivo."
        )
    if has_cover:
        images_info_lines.append(
            "- Existe uma imagem de CAPA. Use exatamente o texto ASSET_COVER "
            "como src de uma <img> (ou background-image: url('ASSET_COVER') "
            "em CSS) na seção inicial/hero. Não troque, não invente outro nome."
        )
    if gallery_count:
        tokens = ", ".join(f"ASSET_GALLERY_{i}" for i in range(1, gallery_count + 1))
        images_info_lines.append(
            f"- Existem {gallery_count} imagens de GALERIA. Use exatamente "
            f"estes textos, um por imagem, como src de tags <img> na seção "
            f"de galeria: {tokens}. Não troque, não invente outros nomes."
        )
    if not images_info_lines:
        images_info_lines.append(
            "- Não há imagens enviadas pelo usuário. NÃO use tags <img> com "
            "URLs externas ou inventadas; se precisar de elementos visuais, "
            "use apenas CSS (formas, gradientes, ícones em texto/emoji)."
        )
    images_info = "\n".join(images_info_lines)

    country_name, language_name, currency = country_info(data.get("country", "Brasil"))

    accent = (data.get("accent") or "").strip()
    accent_line = (
        f"Cor de destaque/terciária: {accent} (use com moderação, só para "
        "pequenos detalhes/realces, sem competir com a principal e a secundária)."
        if accent else
        "Não há cor de destaque extra — use só a principal e a secundária."
    )

    font_name = (data.get("font") or "Padrão do sistema").strip()
    if font_name and font_name != "Padrão do sistema":
        font_clean = font_name.split(" (")[0].strip()
        font_line = (
            f"Fonte: use a fonte '{font_clean}' do Google Fonts. Importe-a "
            f"com uma tag <link> para fonts.googleapis.com (e preconnect "
            f"para fonts.gstatic.com), com um fallback genérico adequado "
            f"(sans-serif ou serif) caso não carregue."
        )
    else:
        font_line = "Fonte: use uma fonte de sistema (sans-serif nativa), sem importar fontes externas."

    extras = data.get("extras") or []
    extras_lines = []
    if "whatsapp_float" in extras and data.get("whatsapp"):
        extras_lines.append(
            "- Inclua um botão flutuante circular do WhatsApp fixo no canto "
            "inferior direito da tela (position: fixed), sempre visível "
            "durante a rolagem, com o mesmo link wa.me do restante do site."
        )
    if "cookie_banner" in extras:
        extras_lines.append(
            "- Inclua um banner de cookies simples (LGPD) fixo na parte "
            "inferior da tela, com um botão 'Aceitar' que o esconde e "
            "lembra a escolha em localStorage."
        )
    if "scroll_animations" in extras:
        extras_lines.append(
            "- Adicione animações discretas de entrada (fade/slide) nos "
            "elementos conforme o usuário rola a página, usando "
            "IntersectionObserver em JavaScript puro."
        )
    if "back_to_top" in extras:
        extras_lines.append(
            "- Inclua um botão flutuante de 'voltar ao topo' que aparece "
            "após rolar um pouco a página."
        )
    extras_block = ("\nRECURSOS EXTRAS PEDIDOS PELO USUÁRIO:\n" + "\n".join(extras_lines)) if extras_lines else ""

    futurista = "futurista" in data["style"].lower() or "cyberpunk" in data["style"].lower()
    estilo_extra = (
        "\nComo o estilo escolhido é FUTURISTA/CYBERPUNK, capriche em: "
        "fundo escuro com gradientes em neon, linhas/grades sutis, "
        "brilhos (glow) discretos em botões e títulos com CSS "
        "(box-shadow/text-shadow), bordas com leve efeito neon, e uma "
        "sensação de painel de tecnologia — mas sem perder a legibilidade "
        "nem exagerar a ponto de cansar os olhos."
        if futurista else ""
    )

    prompt = f"""
Crie um site profissional COMPLETO em um único arquivo HTML.

PAÍS-ALVO / IDIOMA (muito importante):
- País-alvo: {country_name}
- Escreva ABSOLUTAMENTE TODO o texto do site (menus, títulos, botões,
  descrições, rodapé, mensagens do WhatsApp, meta tags) em: {language_name}.
- Se algum preço aparecer no site, use o símbolo de moeda: {currency}.
- Adapte referências culturais ao público de {country_name}, sem inventar
  informações que o usuário não passou.

DADOS:
Nome: {data["name"]}
Tipo: {data["type"]}
WhatsApp: {data["whatsapp"]}
Cidade/região: {data["city"]}
Instagram: {data["instagram"]}
TikTok: {data["tiktok"]}
Email: {data["email"]}
Endereço/Maps: {data["maps"]}
Slogan: {data["slogan"]}
Descrição: {data["description"]}

Estilo: {data["style"]}{estilo_extra}
Tema: {data["theme"]}
Cor principal: {data["primary"]}
Cor secundária: {data["secondary"]}
{accent_line}
{font_line}

IMAGENS DISPONÍVEIS (muito importante, leia com atenção):
{images_info}

SEÇÕES SELECIONADAS:
{sections}
{extras_block}

REGRAS OBRIGATÓRIAS:
1. Retorne SOMENTE HTML.
2. Comece com <!DOCTYPE html>.
3. Termine com </html>.
4. CSS dentro de <style>.
5. JavaScript dentro de <script>.
6. Não use frameworks nem bibliotecas externas (exceto a fonte do Google
   Fonts, se indicada acima).
7. O site precisa ser responsivo (mobile-first) e funcionar mesmo sem a
   fonte externa carregar.
8. Design moderno e profissional, menu responsivo, botões modernos,
   animações CSS discretas, HTML semântico.
9. Inclua SEO: viewport, title, meta description, Open Graph.
10. Não invente informações, avaliações, preços, clientes, certificações
    ou números. Se algum dado estiver vazio, simplesmente não mostre.
11. Se WhatsApp existir, crie um botão de destaque "Fale conosco" que
    abra https://wa.me/NUMERO (apenas dígitos, com código do país) com
    mensagem pré-preenchida cordial mencionando o nome do negócio,
    ESCRITA EM {language_name}, url-encoded no parâmetro ?text=.
12. Se Instagram/TikTok/email/endereço existirem, crie os respectivos
    links (incluindo mailto para email).
13. Use as seções selecionadas.
14. As cores principal ({data["primary"]}) e secundária ({data["secondary"]})
    devem ser variáveis CSS (:root {{ --primary: ...; --secondary: ...; }})
    usadas de forma consistente. Siga a orientação sobre cor de destaque
    acima.
15. Siga rigorosamente as instruções de IMAGENS DISPONÍVEIS acima.
16. Crie um footer bonito.
17. Não escreva explicações fora do HTML.

QUALIDADE VISUAL — MUITO IMPORTANTE (o site NÃO PODE parecer "feito por IA"):
Evite os clichês mais comuns de sites gerados por IA, que fazem o resultado
parecer genérico mesmo quando o código funciona:
- Não use o "kit de cards": tudo em cards idênticos com o mesmo
  border-radius, a mesma sombra cinza suave e ícone+título+texto
  repetido em série. Varie os layouts das seções (uma pode ser
  assimétrica, outra em duas colunas desiguais, outra em faixa cheia).
- Não use o padrão fundo cor de creme (#F4F1EA) com serifada e um
  acento terracota, nem o padrão fundo quase preto com um único acento
  neon/verde-ácido — a menos que o estilo escolhido acima realmente
  peça algo nessa linha.
- Não coloque um rótulo em CAIXA ALTA acima de cada título nem
  metadados separados por "·" nem setas "→" no final de botões/links —
  isso é enchimento de template, não conteúdo real.
- Não use marcadores numerados tipo "01 / 02 / 03" a menos que o
  conteúdo realmente seja uma sequência/processo passo a passo.
- Não anime tudo igual (fade+slide para cima em cada seção, o mesmo
  hover em cada card) — se for usar uma animação de entrada, escolha
  UM momento de destaque em vez de repetir a mesma em tudo.
- Escreva os textos como se fosse um dono de negócio real descrevendo o
  próprio negócio, específico ao que foi informado nos DADOS acima —
  nunca frases genéricas de propaganda tipo "Bem-vindo ao nosso
  incrível [tipo de negócio]" ou "Qualidade e excelência em cada
  detalhe" sem nenhuma informação real por trás.
- Escolha UM elemento para ser o protagonista visual da página (pode
  ser o hero, uma foto grande, um número de destaque) e deixe o resto
  mais discreto ao redor dele, em vez de todo elemento competindo por
  atenção com o mesmo peso visual.

O resultado precisa parecer um site comercial real e bem acabado.
"""
    system = (
        "Você é um especialista em desenvolvimento frontend. Sua função é "
        "criar páginas HTML completas, bonitas, responsivas e funcionais. "
        "Nunca invente informações fornecidas pelo usuário."
    )
    return prompt, system


def generate_site_html(data, has_logo, has_cover, gallery_count):
    prompt, system = build_site_prompt(data, has_logo, has_cover, gallery_count)
    result = ai_request(
        prompt, system=system, max_tokens=10000,
        validator=lambda t: "<html" in extract_html(t).lower(),
    )
    html = extract_html(result)
    if "<html" not in html.lower():
        raise RuntimeError("A IA não retornou um HTML válido.")
    return html


def edit_site_html(current_html, instruction):
    prompt = f"""
Você vai editar um site HTML existente.

ALTERAÇÃO PEDIDA PELO USUÁRIO:
{instruction}

REGRAS:
- Retorne somente o HTML completo.
- Preserve as informações reais existentes.
- Não remova conteúdo sem necessidade.
- Não invente informações.
- Mantenha o site responsivo.
- Preserve funcionalidades existentes e imagens locais.
- CSS dentro de style, JavaScript dentro de script.
- Não use Markdown.

HTML ATUAL:
{current_html}
"""
    result = ai_request(
        prompt,
        system="Você é um desenvolvedor frontend especialista em editar sites HTML.",
        max_tokens=12000,
        validator=lambda t: "<html" in extract_html(t).lower(),
    )
    html = extract_html(result)
    if "<html" not in html.lower():
        raise RuntimeError("A IA não retornou HTML válido.")
    return html


def auto_improve_site_html(current_html):
    """Deixa a própria IA decidir o que melhorar no site, sem o usuário
    precisar escrever uma instrução. Ela analisa o HTML atual e aplica
    correções de bugs, responsividade, acessibilidade, performance e
    acabamento visual, preservando o conteúdo e as funcionalidades reais.
    """
    prompt = f"""
Você vai revisar e melhorar um site HTML existente por conta própria,
sem receber uma instrução específica do usuário.

Analise o HTML abaixo e aplique melhorias reais, por exemplo:
- corrigir bugs visuais, de layout ou de JavaScript;
- melhorar a responsividade em celular e tablet;
- melhorar contraste, espaçamento, tipografia e hierarquia visual;
- corrigir acessibilidade (alt em imagens, contraste, foco em botões);
- remover código morto ou duplicado;
- pequenos ajustes de performance (evitar CSS/JS redundante).

Evite deixar o site com cara de "template de IA" (cards idênticos com a
mesma sombra genérica em tudo, cores/gradientes clichê, textos de
propaganda genéricos) — se for mexer no visual, prefira reforçar a
identidade que o site já tem em vez de substituí-la por um padrão
genérico.

REGRAS:
- Retorne somente o HTML completo.
- Preserve todas as informações reais existentes (textos, produtos, contato).
- Não invente conteúdo novo nem remova seções existentes.
- Não mude a estrutura de identidade do negócio (nome, imagens, links).
- Mantenha o site responsivo.
- Preserve funcionalidades existentes e imagens locais.
- CSS dentro de style, JavaScript dentro de script.
- Não use Markdown.

HTML ATUAL:
{current_html}
"""
    result = ai_request(
        prompt,
        system=(
            "Você é um desenvolvedor frontend sênior revisando o próprio "
            "trabalho: encontra problemas reais e os corrige com cuidado, "
            "sem quebrar nada que já funciona."
        ),
        max_tokens=12000,
        validator=lambda t: "<html" in extract_html(t).lower(),
    )
    html = extract_html(result)
    if "<html" not in html.lower():
        raise RuntimeError("A IA não retornou HTML válido.")
    return html


def fix_site_issues(current_html, issues_text):
    """Corrige APENAS os problemas encontrados pela análise estática
    (services/debugger_service.py), sem sair reescrevendo o site
    inteiro por conta própria."""
    prompt = f"""
Um analisador estático encontrou os problemas abaixo neste site HTML.
Corrija ESPECIFICAMENTE esses problemas, um por um. Não faça nenhuma
outra alteração de design, texto ou funcionalidade além do necessário
para corrigi-los.

PROBLEMAS ENCONTRADOS:
{issues_text}

REGRAS:
- Retorne somente o HTML completo.
- Corrija só os problemas listados acima.
- Não remova conteúdo real do site.
- Se um problema for "imagem quebrada", troque o src por um caminho de
  imagem que já existe em assets/ (veja o HTML) ou remova a tag <img>
  se não houver substituto razoável — nunca invente um caminho novo.
- Não use Markdown.

HTML ATUAL:
{current_html}
"""
    result = ai_request(
        prompt,
        system="Você é um desenvolvedor frontend corrigindo bugs específicos, com cuidado para não quebrar mais nada.",
        max_tokens=12000,
        validator=lambda t: "<html" in extract_html(t).lower(),
    )
    html = extract_html(result)
    if "<html" not in html.lower():
        raise RuntimeError("A IA não retornou HTML válido.")
    return html


def translate_site_html(html, target_country_name):
    _, language_name, _ = country_info(target_country_name)
    prompt = f"""
Traduza para {language_name} TODO o texto visível para o usuário no HTML
abaixo (títulos, parágrafos, botões, menus, rodapé, placeholders, alt de
imagens, meta description e title).

REGRAS OBRIGATÓRIAS:
1. Retorne SOMENTE o HTML completo, começando com <!DOCTYPE html> e
   terminando com </html>.
2. NÃO traduza nomes próprios (nome do negócio), telefones/WhatsApp,
   links (href/src), e-mails, nomes de arquivos (ASSET_LOGO, ASSET_COVER,
   ASSET_GALLERY_1, etc.) ou nomes de arquivos já usados em assets/.
3. NÃO altere a estrutura HTML, classes, ids, CSS ou JavaScript — apenas
   o texto visível deve mudar de idioma.
4. Se algum texto já estiver em {language_name}, apenas mantenha.
5. Adapte o símbolo de moeda apenas se já existir um preço explícito.
6. Não escreva nenhuma explicação fora do HTML.

HTML ORIGINAL:
{html}
"""
    result = ai_request(
        prompt,
        system=(
            "Você é um tradutor profissional especializado em sites. Você "
            "preserva 100% da estrutura técnica do HTML e traduz apenas o "
            "conteúdo visível ao usuário."
        ),
        max_tokens=10000,
        validator=lambda t: "<html" in extract_html(t).lower(),
    )
    translated = extract_html(result)
    if "<html" not in translated.lower():
        raise RuntimeError("A IA não retornou um HTML válido na tradução.")
    return translated


# ------------------------------------------------------------------
# Pequenas ferramentas de IA (texto genérico, SEO, legendas sociais...)
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# Entendimento do comando de holograma em linguagem natural
# ------------------------------------------------------------------
# O front-end (static/js/jarvis.js) já detecta a maioria dos pedidos de
# holograma com expressões regulares, sem gastar nenhuma chamada de IA
# (rápido e de graça). Mas frases bem desorganizadas ou muito
# diferentes dos padrões esperados podem escapar disso. Para esses
# casos, esta função usa a própria IA (que já entende linguagem
# natural de verdade) só para decidir "isso é ou não um pedido de
# holograma, e sobre o quê" — como uma segunda camada, mais lenta mas
# muito mais flexível, chamada apenas quando o atalho local não
# resolveu.
def detect_hologram_intent(user_text):
    """Pede pra IA classificar se a mensagem é um pedido para criar um
    holograma e, se for, extrair o assunto e se é modo 'lugar real'
    (OpenStreetMap) ou procedural. Devolve um dict:
    {"quer_holograma": bool, "modo": "real"|"procedural", "assunto": str}
    Levanta RuntimeError se nenhum provedor de IA responder — quem
    chama deve tratar isso como "não deu pra confirmar agora" e não
    quebrar a conversa por causa disso."""
    prompt = f"""Mensagem do usuário para um assistente que tem um projetor de holograma 3D embutido no chat:
\"\"\"{user_text}\"\"\"

A pessoa está pedindo, de alguma forma (mesmo que a frase seja bagunçada, incompleta ou informal), para CRIAR/PROJETAR/MOSTRAR um holograma agora? Responda SOMENTE com um JSON puro, sem markdown, sem crases, no formato exato:
{{"quer_holograma": true ou false, "modo": "real" ou "procedural", "assunto": "string curta"}}

Regras:
- "quer_holograma": true apenas se há intenção clara de criar/ver um holograma AGORA (não conte reclamações, bugs, ou pedidos de melhoria no app/Jarvis como isso).
- "modo": "real" se a pessoa quer um LUGAR de verdade (cidade, endereço, ponto turístico, "de verdade", "real", "mapa real"); "procedural" para objetos, conceitos ou quando não ficar claro.
- "assunto": o que a pessoa quer ver no holograma, bem resumido (poucas palavras, sem verbos de pedido como "cria"/"mostra"/"quero"). Se não der pra identificar um assunto, use "".
- Se quer_holograma for false, "assunto" deve ser "".
"""
    raw = ai_request(
        prompt,
        system="Você responde SOMENTE com JSON válido, nada mais.",
        max_tokens=150,
        validator=lambda t: "{" in t and "}" in t,
    ).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError("A IA não retornou um formato válido.")
    parsed = json.loads(raw[start:end + 1])
    return {
        "quer_holograma": bool(parsed.get("quer_holograma")),
        "modo": "real" if parsed.get("modo") == "real" else "procedural",
        "assunto": str(parsed.get("assunto") or "").strip(),
    }


def analyze_photo_for_hologram(image_data_url):
    """Usa um modelo grátis com visão (ver VISION_FREE_MODELS) para
    olhar a foto que o usuário mandou pro holograma e devolver uma
    legenda curta em português e um tipo de cena — usado só para
    rotular o holograma de profundidade que o front-end já montou
    localmente a partir dos pixels da própria foto (ver
    static/js/hologram.js: buildFromPhoto()). Levanta RuntimeError se
    nenhum provedor com visão responder; quem chama trata isso como
    "sem legenda desta vez", nunca como "sem holograma"."""
    messages = [
        {
            "role": "system",
            "content": (
                "Você responde SOMENTE com JSON válido, sem markdown, sem "
                "crases, no formato exato: "
                '{"legenda": "string curta", "tipo": "retrato|paisagem|objeto|cidade|outro"}. '
                "\"legenda\": no máximo 8 palavras, em português do Brasil, "
                "num tom de rótulo de holograma futurista (ex: "
                "\"RETRATO — pessoa sorrindo ao ar livre\", "
                "\"OBJETO — caneca de cerâmica azul\"). "
                "\"tipo\": a categoria que melhor descreve a cena."
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Analise esta foto para um holograma 3D."},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        },
    ]
    raw = ai_chat(messages, max_tokens=120, max_continuations=0, vision=True).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError("A IA não retornou um formato válido.")
    parsed = json.loads(raw[start:end + 1])
    tipo = str(parsed.get("tipo") or "outro").strip().lower()
    if tipo not in ("retrato", "paisagem", "objeto", "cidade", "outro"):
        tipo = "outro"
    return {
        "legenda": str(parsed.get("legenda") or "").strip()[:120],
        "tipo": tipo,
    }


def generic_ai_text(instruction, context=""):
    prompt = instruction if not context else f"{instruction}\n\nContexto:\n{context}"
    return ai_request(
        prompt,
        system="Você é um assistente de escrita objetivo e útil, responde em português do Brasil salvo instrução contrária.",
        max_tokens=1200,
    ).strip()


# ------------------------------------------------------------------
# Cyber Lab / Security (educacional) — item 15-21 do briefing.
#
# Importante: nada aqui EXECUTA comando nenhum, escaneia rede alheia ou
# controla uma VM de verdade — isso exigiria infraestrutura de
# isolamento (containers/VMs por usuário) que não existe neste projeto
# e que seria perigoso fingir dentro do mesmo processo do Flask. O que
# estas funções fazem é só usar o mesmo motor de IA do resto do app
# (ai_request) para ENSINAR, ANALISAR CÓDIGO/SAÍDA que o próprio
# usuário cola aqui, e nunca gerar comandos prontos contra um alvo de
# terceiros — sempre no contexto de localhost/CTF/laboratório próprio.
# ------------------------------------------------------------------

def analyze_code_security(code, filename=""):
    """Security Analyzer (item 21): revisão estática de código feita
    pela IA, sempre no formato VULNERABILIDADE/SEVERIDADE/LOCALIZAÇÃO/
    EXPLICAÇÃO/CORREÇÃO por achado, para poder ser exibida em cards."""
    alvo = f' do arquivo "{filename}"' if filename else ""
    prompt = f"""Você é um analista de segurança (SAST) revisando o código{alvo} abaixo.

Aponte só problemas REAIS de segurança (não estilo/formatação/nomenclatura). Para CADA problema encontrado, use exatamente este formato, um bloco por problema:

VULNERABILIDADE: <nome curto>
SEVERIDADE: <Crítica|Alta|Média|Baixa|Informativa>
LOCALIZAÇÃO: <linha, trecho ou função aproximada>
EXPLICAÇÃO: <por que é um problema, em 1-3 frases>
CORREÇÃO: <como corrigir, com um trecho de código quando fizer sentido>

Considere, quando aplicável: injeção (SQL/comando/template/NoSQL), XSS, CSRF, quebra de autenticação/autorização, segredos ou chaves hardcoded, criptografia fraca ou mal aplicada, deserialização insegura, path traversal, SSRF, uso de dependências/funções conhecidas por vulnerabilidades, headers de segurança ausentes, validação de entrada insuficiente, exposição de dados sensíveis em logs/erros.

Se não encontrar nenhum problema real, responda exatamente:
"Nenhuma vulnerabilidade evidente encontrada nesta revisão — lembrando que revisão automática não substitui um pentest ou revisão humana completa."

CÓDIGO A ANALISAR:
{code[:12000]}
"""
    return ai_request(
        prompt,
        system="Você é um analista de segurança de aplicações sênior, direto e técnico, responde em português do Brasil.",
        max_tokens=2200,
    ).strip()


def explain_security_tool(query, output_pasted=""):
    """Kali/Ubuntu tutor (itens 16, 17, 20): explica uma ferramenta,
    comando ou conceito, e interpreta uma saída que o usuário cola —
    nunca gera um ataque pronto contra um alvo de verdade."""
    ctx = f"\n\nSaída/resultado que o usuário colou para você interpretar:\n{output_pasted[:6000]}" if output_pasted else ""
    prompt = f"""Contexto: uso educacional, sempre em localhost, laboratório próprio, CTF público (TryHackMe/HackTheBox) ou ambiente explicitamente autorizado pelo usuário — nunca contra terceiros.

Pedido do usuário: "{query}"{ctx}

Responda de forma didática, cobrindo o que for aplicável:
1. Objetivo da ferramenta/comando/conceito
2. Sintaxe e principais parâmetros (se for uma ferramenta/comando)
3. Interpretação da saída colada acima, linha a linha quando fizer sentido (se houver saída)
4. Como se defender/mitigar (lado azul)

Regra inegociável: nunca produza um comando ou sequência de ataque pronta para ser usada contra um alvo específico de produção ou de terceiros — ensine o raciocínio e a sintaxe, deixando claro que só deve ser usado em ambiente autorizado."""
    return ai_request(
        prompt,
        system="Você é um instrutor de cybersecurity (ofensiva e defensiva) focado só em ensino ético, redes/Linux (Kali e Ubuntu) e ambientes autorizados. Responde em português do Brasil.",
        max_tokens=1800,
    ).strip()


TRYHACKME_STUDY_MODES = {
    "aula": "Dê uma aula estruturada e progressiva sobre o assunto, do básico ao intermediário, com exemplos práticos.",
    "dica": "Dê só uma dica direcionadora que ajude a pensar no próximo passo — não entregue a resposta pronta.",
    "explicacao": "Explique o conceito em profundidade, com analogias, sem se preocupar em ser breve.",
    "laboratorio": "Sugira um mini-laboratório PRÁTICO e seguro (localhost, CTF público ou ferramenta própria) para praticar esse conceito, passo a passo.",
    "revisao": "Faça uma revisão em tópicos-resumo (tipo checklist/flashcard) do que já se estuda sobre o assunto.",
}


def tryhackme_study(topic, mode="aula"):
    """TryHackMe Study Mode (item 18): Jarvis como professor/parceiro
    de estudo, nos 5 sub-modos do briefing (aula/dica/explicação/
    laboratório/revisão) — nunca entrega a flag/resposta literal de um
    desafio específico, só ensina o caminho até ela."""
    instr = TRYHACKME_STUDY_MODES.get(mode, TRYHACKME_STUDY_MODES["aula"])
    prompt = f"""O usuário está estudando cybersecurity (TryHackMe ou trilha equivalente) e descreveu o seguinte tópico/situação:
"{topic}"

{instr}

Não entregue a resposta literal (flag) de um desafio/sala específica — o objetivo é o usuário aprender o caminho, não só copiar a solução."""
    return ai_request(
        prompt,
        system="Você é um professor de cybersecurity paciente, usa método socrático quando fizer sentido, e responde em português do Brasil.",
        max_tokens=1800,
    ).strip()


def seo_suggestions(business_name, business_type, description):
    prompt = f"""
Gere sugestões de SEO para este negócio, em português do Brasil.
Nome: {business_name}
Tipo: {business_type}
Descrição: {description}

Retorne:
1. Um <title> ideal (até 60 caracteres)
2. Uma meta description ideal (até 155 caracteres)
3. 10 palavras-chave relevantes
Formate em texto simples, com esses 3 títulos.
"""
    return ai_request(prompt, max_tokens=500).strip()


def social_caption(topic, tone, platform):
    prompt = (
        f"Escreva 3 legendas para {platform} sobre: {topic}. "
        f"Tom: {tone}. Inclua emojis e 5 hashtags relevantes ao final de cada "
        "legenda. Numere as 3 opções."
    )
    return ai_request(prompt, max_tokens=600).strip()


def generate_business_name(description):
    prompt = (
        "Sugira 8 nomes criativos e curtos para um negócio com esta "
        f"descrição: {description}\nListe apenas os nomes, um por linha, "
        "sem numeração nem explicações."
    )
    return ai_request(prompt, max_tokens=200).strip()


def generate_slogan(name, description):
    prompt = (
        f"Sugira 8 slogans curtos e impactantes para o negócio '{name}'. "
        f"Descrição: {description}\nListe apenas os slogans, um por linha."
    )
    return ai_request(prompt, max_tokens=200).strip()


def improve_description(text):
    prompt = f"Reescreva e melhore este texto de apresentação de negócio, mantendo os fatos, deixando mais persuasivo e profissional:\n\n{text}"
    return ai_request(prompt, max_tokens=400).strip()


def parse_business_chat(text, sections, styles, extras_keys):
    """Recebe uma descrição livre do negócio (modo 'conversa' do criador
    de sites) e devolve um dicionário já pronto pra preencher o
    formulário: nome, tipo, cidade, slogan, descrição, estilo, seções,
    extras e cores. É o que dá a sensação de 'IA de verdade' no criador,
    sem abrir mão do formulário — a IA só chuta os campos, o usuário
    revisa e ajusta antes de gerar o site."""
    sections_list = ", ".join(sections)
    styles_list = ", ".join(styles)
    extras_list = ", ".join(extras_keys)
    prompt = f"""
O usuário descreveu o negócio dele em texto livre, em português do Brasil:
\"\"\"{text}\"\"\"

Extraia um JSON com exatamente estas chaves (use "" ou [] quando não der
pra descobrir — nunca invente contato, endereço ou WhatsApp que não
foram citados):
- name: nome do negócio (se não for citado, sugira um nome curto e coerente)
- type: tipo de negócio
- city: cidade/região, se mencionada
- slogan: um slogan curto sugerido
- description: descrição de 2 a 3 frases, profissional e persuasiva
- style: um destes valores, o que combinar melhor: {styles_list}
- sections: lista com 4 a 7 itens dentre exatamente estes valores: {sections_list}
- extras: lista com os que fizerem sentido dentre exatamente estas chaves: {extras_list}
- primary: cor hex (#rrggbb) que combine com o tipo de negócio
- secondary: segunda cor hex (#rrggbb) que combine com a primeira

Responda SOMENTE com o JSON puro, sem markdown, sem crases, sem texto antes ou depois.
"""

    def _looks_like_json(content):
        return "{" in content and "}" in content

    raw = ai_request(prompt, max_tokens=700, validator=_looks_like_json).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError("A IA não retornou um formato válido. Tente descrever de novo.")

    parsed = json.loads(raw[start:end + 1])
    parsed["sections"] = [s for s in parsed.get("sections", []) if s in sections] or sections[:5]
    parsed["extras"] = [e for e in parsed.get("extras", []) if e in extras_keys]
    if parsed.get("style") not in styles:
        parsed["style"] = styles[0]
    for key in ("name", "type", "city", "slogan", "description", "primary", "secondary"):
        parsed.setdefault(key, "")
    return parsed
