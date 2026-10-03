"""
Dados "ao vivo" e 100% grátis (sem chave nenhuma) que o Jarvis usa como
contexto real antes de responder — assim ele para de "chutar" coisas
como clima atual ou fatos que mudam com o tempo, e passa a responder
com dado de verdade, buscado na hora. Isto é o "banco de dados ao vivo"
do Jarvis: quanto mais fontes aqui, mais perguntas do dia a dia ele
consegue responder com fato real em vez de achismo.

Fontes usadas (todas gratuitas, sem necessidade de API key):
  - Open-Meteo (geocoding + previsão do tempo) para clima/temperatura
  - Open-Meteo (geocoding, campo "timezone") + zoneinfo da própria
    biblioteca padrão do Python para horário/fuso horário atual de
    qualquer cidade do mundo
  - Wikipédia (REST API de resumo) para "o que é / quem é X"
  - Frankfurter (dados do Banco Central Europeu) para câmbio de moedas
  - CoinGecko para preço atual de criptomoedas
  - BrasilAPI para feriados nacionais do Brasil por ano
  - BrasilAPI (ViaCEP por baixo) para endereço a partir de um CEP
  - wheretheiss.at para a posição orbital atual da ISS

Isso não é "function calling" de verdade (os modelos gratuitos usados
no ai_engine nem sempre suportam isso de forma confiável) — é uma
camada mais simples e robusta: detectamos por palavra-chave o que o
usuário quer, buscamos o dado real, e injetamos como um bloco de
"DADOS EM TEMPO REAL" na conversa antes de mandar pra IA. Se nada bater
com os padrões abaixo, a conversa segue normal, sem nenhum custo extra.
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

REQUEST_TIMEOUT = 6

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
WIKIPEDIA_SUMMARY_URL = "https://pt.wikipedia.org/api/rest_v1/page/summary/{title}"
CURRENCY_URL = "https://api.frankfurter.app/latest"
CRYPTO_URL = "https://api.coingecko.com/api/v3/simple/price"
HOLIDAYS_URL = "https://brasilapi.com.br/api/feriados/v1/{year}"
CEP_URL = "https://brasilapi.com.br/api/cep/v2/{cep}"
ISS_URL = "https://api.wheretheiss.at/v1/satellites/25544"

# Nomes -> símbolos de criptomoedas mais pedidas (CoinGecko usa IDs
# próprios, não os tickers). Cobre os pedidos mais comuns em português.
_CRYPTO_IDS = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum", "ether": "ethereum",
    "solana": "solana", "sol": "solana",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "cardano": "cardano", "ada": "cardano",
    "ripple": "ripple", "xrp": "ripple",
    "binance coin": "binancecoin", "bnb": "binancecoin",
    "polkadot": "polkadot", "dot": "polkadot",
    "litecoin": "litecoin", "ltc": "litecoin",
}

_CURRENCY_ALIASES = {
    "dolar": "USD", "dólar": "USD", "dolares": "USD", "dólares": "USD", "usd": "USD",
    "euro": "EUR", "euros": "EUR", "eur": "EUR",
    "libra": "GBP", "libras": "GBP", "gbp": "GBP",
    "real": "BRL", "reais": "BRL", "brl": "BRL",
    "peso argentino": "ARS", "peso": "ARS", "ars": "ARS",
    "iene": "JPY", "ienes": "JPY", "jpy": "JPY",
    "yuan": "CNY", "cny": "CNY",
}

_WEATHER_CODES = {
    0: "céu limpo", 1: "poucas nuvens", 2: "parcialmente nublado", 3: "nublado",
    45: "névoa", 48: "névoa com geada", 51: "garoa fraca", 53: "garoa",
    55: "garoa forte", 61: "chuva fraca", 63: "chuva", 65: "chuva forte",
    71: "neve fraca", 73: "neve", 75: "neve forte", 80: "pancadas de chuva fracas",
    81: "pancadas de chuva", 82: "pancadas de chuva fortes", 95: "tempestade",
    96: "tempestade com granizo", 99: "tempestade forte com granizo",
}

_TIME_TRIGGER = re.compile(
    r"\b(?:que\s+horas?\s+[eé]\s+s[aã]o|hor[aá]rio\s+(?:atual|agora)|fuso\s+hor[aá]rio)\b"
    r".{0,15}\b(?:em|no|na|de|da)\s+([a-zà-úA-ZÀ-Ú\s\-]{2,40})",
    re.IGNORECASE,
)

_WEATHER_TRIGGER = re.compile(
    r"\b(clima|tempo|temperatura|previs[aã]o|vai chover|est[aá]\s+chovendo|graus?)\b", re.IGNORECASE
)
_WEATHER_PLACE = re.compile(
    r"(?:clima|tempo|temperatura|previs[aã]o)\s+(?:em|de|no|na|pra|para)\s+([a-zà-úA-ZÀ-Ú\s\-]{2,40})",
    re.IGNORECASE,
)

_WIKI_TRIGGER = re.compile(
    r"^(?:o que [eé]|quem [eé]|quem foi|me fale sobre|fale sobre|pesquis[ae]|"
    r"me explica sobre|explica sobre|wikipedia)\b\s*(.*)",
    re.IGNORECASE,
)

_CURRENCY_TRIGGER = re.compile(
    r"\b(c[aâ]mbio|cota[cç][aã]o|convert[ae]r?)\b.{0,40}\b"
    r"(d[oó]lar|euro|libra|real|reais|peso|iene|yuan|usd|eur|gbp|brl|ars|jpy|cny)\b"
    r"|\b(quanto\s+(?:est[aá]|vale)\s+o?\s*(d[oó]lar|euro|libra|iene|yuan))\b",
    re.IGNORECASE,
)

_CRYPTO_TRIGGER = re.compile(
    r"\b(pre[cç]o|cota[cç][aã]o|valor)\s+(?:d[oa]?\s+)?"
    r"(bitcoin|btc|ethereum|eth|ether|solana|sol|dogecoin|doge|cardano|ada|"
    r"ripple|xrp|binance coin|bnb|polkadot|dot|litecoin|ltc)\b"
    r"|\b(bitcoin|btc|ethereum)\s+(?:est[aá]|vale)\s+quanto\b",
    re.IGNORECASE,
)

_HOLIDAY_TRIGGER = re.compile(
    r"\bferiados?\b.{0,20}\b(brasil|nacion(?:al|ais))?\b|\bferiados?\s+de\s+(\d{4})\b",
    re.IGNORECASE,
)

_CEP_TRIGGER = re.compile(r"\bcep\b.{0,10}(\d{5}-?\d{3})", re.IGNORECASE)

_ISS_TRIGGER = re.compile(
    r"\b(esta[cç][aã]o espacial internacional|\biss\b).{0,20}\b(onde|posi[cç][aã]o|localiza[cç][aã]o|agora)\b"
    r"|\bonde\s+(?:est[aá]|fica)\s+a\s+iss\b",
    re.IGNORECASE,
)


def _fetch_weather(place_name):
    geo = httpx.get(
        GEOCODE_URL,
        params={"name": place_name, "count": 1, "language": "pt"},
        timeout=REQUEST_TIMEOUT,
    )
    geo.raise_for_status()
    results = geo.json().get("results") or []
    if not results:
        return None
    place = results[0]

    weather = httpx.get(
        WEATHER_URL,
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "timezone": "auto",
        },
        timeout=REQUEST_TIMEOUT,
    )
    weather.raise_for_status()
    current = weather.json().get("current") or {}
    if not current:
        return None

    code = current.get("weather_code")
    condition = _WEATHER_CODES.get(code, "condição não identificada")
    label = ", ".join(
        p for p in [place.get("name"), place.get("admin1"), place.get("country")] if p
    )
    return (
        f"Clima agora em {label}: {current.get('temperature_2m')}°C, {condition}, "
        f"umidade {current.get('relative_humidity_2m')}%, vento "
        f"{current.get('wind_speed_10m')} km/h. (fonte: Open-Meteo, dado ao vivo)"
    )


def _fetch_local_time(place_name):
    """Descobre o horário local atual de qualquer cidade do mundo. Usa
    a mesma geocodificação gratuita da Open-Meteo (que já devolve o
    nome oficial do fuso horário IANA da cidade, ex: 'Asia/Tokyo') e
    calcula a hora atual com o zoneinfo da própria biblioteca padrão do
    Python — sem precisar de mais nenhum serviço externo de horário."""
    geo = httpx.get(
        GEOCODE_URL,
        params={"name": place_name, "count": 1, "language": "pt"},
        timeout=REQUEST_TIMEOUT,
    )
    geo.raise_for_status()
    results = geo.json().get("results") or []
    if not results:
        return None
    place = results[0]
    tz_name = place.get("timezone")
    if not tz_name:
        return None

    try:
        now_there = datetime.now(ZoneInfo(tz_name))
    except Exception:
        return None

    label = ", ".join(
        p for p in [place.get("name"), place.get("admin1"), place.get("country")] if p
    )
    dias = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado", "domingo"]
    dia_semana = dias[now_there.weekday()]
    return (
        f"Horário local agora em {label} ({tz_name}): "
        f"{now_there.strftime('%H:%M')} de {dia_semana}, "
        f"{now_there.strftime('%d/%m/%Y')} (fonte: Open-Meteo + fuso "
        f"horário IANA, dado ao vivo)."
    )


def _fetch_wikipedia_summary(topic):
    title = topic.strip().replace(" ", "_")
    if not title:
        return None
    resp = httpx.get(
        WIKIPEDIA_SUMMARY_URL.format(title=title),
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "Tristan-Thorne-Jarvis/1.0"},
        follow_redirects=True,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    extract = (data.get("extract") or "").strip()
    if not extract:
        return None
    page_url = (data.get("content_urls", {}).get("desktop", {}) or {}).get("page", "")
    block = f"Resumo da Wikipédia sobre \"{data.get('title', topic)}\": {extract}"
    if page_url:
        block += f" (fonte: {page_url})"
    return block


def _fetch_currency(from_code, to_code):
    if from_code == to_code:
        return None
    resp = httpx.get(
        CURRENCY_URL,
        params={"from": from_code, "to": to_code},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    rate = (data.get("rates") or {}).get(to_code)
    if rate is None:
        return None
    return (
        f"Câmbio agora: 1 {from_code} = {rate} {to_code} (data-base: "
        f"{data.get('date', 'hoje')}, fonte: Frankfurter/Banco Central "
        f"Europeu, dado ao vivo)."
    )


def _fetch_crypto(coin_id):
    resp = httpx.get(
        CRYPTO_URL,
        params={"ids": coin_id, "vs_currencies": "usd,brl"},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json().get(coin_id)
    if not data:
        return None
    return (
        f"Preço agora de {coin_id.capitalize()}: "
        f"US$ {data.get('usd')} / R$ {data.get('brl')} "
        f"(fonte: CoinGecko, dado ao vivo)."
    )


def _fetch_holidays(year):
    resp = httpx.get(HOLIDAYS_URL.format(year=year), timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        return None
    holidays = resp.json() or []
    if not holidays:
        return None
    lines = [f"- {h.get('date')}: {h.get('name')}" for h in holidays[:20]]
    return (
        f"Feriados nacionais do Brasil em {year} (fonte: BrasilAPI, "
        f"dado ao vivo):\n" + "\n".join(lines)
    )


def _fetch_cep(cep_digits):
    resp = httpx.get(CEP_URL.format(cep=cep_digits), timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        return None
    data = resp.json()
    partes = [
        data.get("street"), data.get("neighborhood"),
        data.get("city"), data.get("state"),
    ]
    endereco = ", ".join(p for p in partes if p)
    if not endereco:
        return None
    return f"Endereço do CEP {data.get('cep', cep_digits)}: {endereco} (fonte: BrasilAPI, dado ao vivo)."


def _fetch_iss_position():
    resp = httpx.get(ISS_URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    lat, lng = data.get("latitude"), data.get("longitude")
    if lat is None or lng is None:
        return None
    return (
        f"Posição atual da Estação Espacial Internacional (ISS): "
        f"latitude {round(lat, 2)}, longitude {round(lng, 2)}, altitude "
        f"{round(data.get('altitude', 0), 1)} km, velocidade "
        f"{round(data.get('velocity', 0))} km/h "
        f"(fonte: wheretheiss.at, dado ao vivo)."
    )


def build_live_context(user_text):
    """Olha a última mensagem do usuário e, se bater com um padrão
    conhecido (clima ou pedido de informação enciclopédica), busca o
    dado real correspondente. Devolve None se não houver nada relevante
    para buscar (o caminho mais comum) ou se a busca falhar — nesse
    caso o Jarvis simplesmente responde do jeito normal, sem trava."""
    text = (user_text or "").strip()
    if not text:
        return None

    try:
        time_m = _TIME_TRIGGER.search(text)
        if time_m and time_m.group(1):
            result = _fetch_local_time(time_m.group(1).strip())
            if result:
                return result
            return None

        if _WEATHER_TRIGGER.search(text):
            m = _WEATHER_PLACE.search(text)
            place_name = m.group(1).strip() if m else None
            if place_name:
                result = _fetch_weather(place_name)
                if result:
                    return result
            return None

        if _ISS_TRIGGER.search(text):
            return _fetch_iss_position()

        cep_m = _CEP_TRIGGER.search(text)
        if cep_m:
            cep_digits = re.sub(r"\D", "", cep_m.group(1))
            if len(cep_digits) == 8:
                return _fetch_cep(cep_digits)

        holiday_m = _HOLIDAY_TRIGGER.search(text)
        if holiday_m:
            year = holiday_m.group(2)
            if not year:
                year_m = re.search(r"\b(20\d{2})\b", text)
                year = year_m.group(1) if year_m else None
            if year:
                return _fetch_holidays(year)

        crypto_m = _CRYPTO_TRIGGER.search(text)
        if crypto_m:
            coin_word = (crypto_m.group(2) or crypto_m.group(3) or "").lower()
            coin_id = _CRYPTO_IDS.get(coin_word)
            if coin_id:
                return _fetch_crypto(coin_id)

        if _CURRENCY_TRIGGER.search(text):
            words = re.findall(r"[a-zà-úA-ZÀ-Ú]+", text.lower())
            codes = []
            i = 0
            while i < len(words):
                # tenta primeiro combinações de duas palavras (ex: "peso argentino")
                two = f"{words[i]} {words[i+1]}" if i + 1 < len(words) else ""
                if two in _CURRENCY_ALIASES:
                    codes.append(_CURRENCY_ALIASES[two])
                    i += 2
                    continue
                if words[i] in _CURRENCY_ALIASES:
                    codes.append(_CURRENCY_ALIASES[words[i]])
                i += 1
            codes = list(dict.fromkeys(codes))  # remove duplicatas, mantém ordem
            if len(codes) >= 2:
                return _fetch_currency(codes[0], codes[1])
            if len(codes) == 1:
                base = "BRL" if codes[0] != "BRL" else "USD"
                return _fetch_currency(codes[0], base)
            return None

        m = _WIKI_TRIGGER.match(text)
        if m and m.group(1) and len(m.group(1).strip()) > 1:
            topic = re.sub(r"[?.!]+$", "", m.group(1).strip())
            return _fetch_wikipedia_summary(topic)
    except Exception:
        # Qualquer falha de rede/parse aqui NUNCA deve derrubar a
        # conversa do Jarvis — só significa que ele responde sem o
        # dado extra, do jeito que já respondia antes.
        return None

    return None
