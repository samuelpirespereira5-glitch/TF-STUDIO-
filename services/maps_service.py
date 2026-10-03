"""
Integração com o OpenStreetMap (OSM) de verdade para o modo "lugar real"
do holograma: o usuário digita um lugar (endereço, cidade, ponto
turístico) e a gente traz coordenadas, relevo (elevação) e um mapa real
daquele ponto — para o holograma "materializar" o lugar de verdade, e
não só um terreno procedural genérico.

Stack 100% OpenStreetMap / grátis / SEM chave nenhuma (diferente da
versão antiga deste arquivo, que dependia do Google Maps Platform
pago):
  - Nominatim (nominatim.openstreetmap.org) -> geocodificação: transforma
    o texto digitado em lat/lng reais, usando a mesma base de dados
    aberta do OpenStreetMap.
  - Open-Meteo Elevation API (open-meteo.com) -> malha de altitudes reais
    ao redor do ponto (grátis, sem chave; mesma família de API que o
    Jarvis já usa para clima em services/live_data.py).
  - Tiles oficiais do OpenStreetMap (tile.openstreetmap.org) -> baixamos
    um mosaico de ladrilhos (tiles) ao redor do ponto e "costuramos" com
    Pillow numa única imagem, virando a textura real do terreno no
    holograma — é o próprio mapa do OpenStreetMap renderizado, não uma
    imagem de satélite paga.
  - Overpass API (overpass-api.de) -> consulta ao banco de dados aberto
    do OpenStreetMap para trazer o contorno (pegada no chão) e a altura
    real de cada prédio ao redor do ponto, usada para extrudar prédios
    3D de verdade no holograma — o mesmo tipo de efeito visual do
    Google Maps 3D/Cesium, só que com dado aberto e sem custo nenhum
    (ver get_buildings() mais abaixo).

Nada aqui precisa de chave de API, cartão de crédito ou cadastro. Como
é um serviço comunitário mantido por doações, seguimos a política de
uso da OSM Foundation: identificamos o app com um User-Agent descritivo
e fazemos no máximo 1 requisição por vez (sem paralelismo agressivo).
"""

import base64
import io
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

try:
    from PIL import Image
    _HAS_PILLOW = True
except ImportError:  # Pillow pode não estar instalado em ambientes antigos
    _HAS_PILLOW = False

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
# Dois espelhos públicos e gratuitos da Overpass API (mesmo serviço,
# operadores diferentes) — se o primeiro estiver fora do ar ou
# sobrecarregado, tentamos o segundo antes de desistir dos prédios.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Identificação obrigatória pela política de uso do OpenStreetMap
# (https://operations.osmfoundation.org/policies/nominatim/ e
# .../tiles/) — sem isso o serviço pode bloquear as requisições.
USER_AGENT = "Tristan-Thorne-Jarvis-Holograma/1.0 (uso pessoal, sem fins comerciais)"

REQUEST_TIMEOUT = 12

# Tamanho da malha de elevação: GRID x GRID pontos. Antes era 20 (400
# pontos, 4 lotes de 100) — em picos de uso da Open-Meteo isso batia
# fácil no limite de requisições por minuto do plano grátis e devolvia
# "429 Too Many Requests", derrubando o holograma inteiro. 12x12 (144
# pontos, 2 lotes) já dá um relevo bem detalhado pra visualização em
# 3D e reduz pela metade o número de chamadas feitas por pedido.
GRID = 12
# Metade da largura da área capturada ao redor do ponto, em metros.
HALF_SIZE_METERS = 900  # área de ~1.8km x 1.8km

# Zoom do mosaico de tiles do OSM (0-19). 15 dá um bom nível de detalhe
# de bairro/ruas para a textura do holograma.
TILE_ZOOM = 15
# Mosaico NxN de tiles de 256px ao redor do ponto central.
TILE_GRID = 5

# Raio (em metros) ao redor do ponto onde buscamos prédios reais para
# extrudar em 3D. Menor que a área do relevo (HALF_SIZE_METERS) de
# propósito: extrudar cada prédio é bem mais caro (geometricamente e
# para o navegador renderizar) do que só deformar uma malha de
# terreno, então focamos num "núcleo" central denso em vez da área
# inteira do relevo — visualmente já dá o efeito de "cidade real"
# sem pesar o holograma.
BUILDING_RADIUS_METERS = 260
# Trava de segurança: em bairros muito densos (centro de grande
# cidade) pode haver milhares de prédios num raio de 260m — cortamos
# em 220 (a própria Overpass já devolve só os primeiros N) para o
# holograma continuar leve em qualquer navegador, inclusive celular.
MAX_BUILDINGS = 220
# Altura média de um andar, usada só quando o prédio tem a tag
# "building:levels" (número de andares) mas não a altura em metros
# diretamente.
DEFAULT_LEVEL_HEIGHT_METERS = 3.2
# Prédio sem "height" nem "building:levels" no OpenStreetMap (comum
# fora de grandes centros): assumimos uma altura modesta de "casa/
# prédio baixo padrão" em vez de deixar o prédio com altura zero.
DEFAULT_BUILDING_HEIGHT_METERS = 9.0

# Quantas vezes tentamos de novo uma chamada que falhou por rate limit
# (429) ou erro temporário do servidor (5xx) antes de desistir daquela
# chamada específica, com espera crescente entre tentativas (backoff).
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1.5

# Cache simples em memória do último relevo buscado por coordenada
# (arredondada), só para o caso comum de a pessoa pedir o mesmo lugar
# de novo em seguida (ex: clicou duas vezes, ou tentou de novo depois
# de um erro) — evita gastar outra rodada inteira de requisições na
# Open-Meteo por nada. Expira sozinho depois de alguns minutos.
_ELEVATION_CACHE = {}
_ELEVATION_CACHE_TTL_SECONDS = 15 * 60

# Cache simples da imagem já costurada do mapa por coordenada — evita
# baixar os mesmos 25 tiles de novo se a pessoa pedir o mesmo lugar
# (ou um lugar próximo) outra vez logo em seguida.
_TILE_IMAGE_CACHE = {}
_TILE_IMAGE_CACHE_TTL_SECONDS = 30 * 60

# Cache simples dos prédios já buscados por coordenada — a Overpass é
# o serviço mais lento e mais sensível a sobrecarga dos três que
# usamos aqui, então reaproveitar o mesmo lugar pedido de novo em
# seguida evita bater nela sem necessidade.
_BUILDINGS_CACHE = {}
_BUILDINGS_CACHE_TTL_SECONDS = 30 * 60

# Respeito à política de uso do Nominatim: no máximo ~1 requisição por
# segundo. Sem isso, pedir dois lugares em sequência rápida (ex:
# "funcionou na primeira, bugou na segunda") facilmente devolve 403/429
# e o holograma cai no modo de emergência (relevo plano).
_NOMINATIM_LOCK = threading.Lock()
_NOMINATIM_MIN_INTERVAL = 1.1
_last_nominatim_call = [0.0]


def _respect_nominatim_rate_limit():
    with _NOMINATIM_LOCK:
        wait = _NOMINATIM_MIN_INTERVAL - (time.time() - _last_nominatim_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_nominatim_call[0] = time.time()


def _elevation_cache_key(lat, lng):
    return (round(lat, 4), round(lng, 4))


def _get_with_retry(url, params, headers, what):
    """GET com retentativa e espera crescente para erros passageiros
    (429 'Too Many Requests' e 5xx) — os provedores gratuitos que
    usamos aqui não têm SLA nenhum, então uma única tentativa falhando
    não deveria derrubar o holograma inteiro. Erros "definitivos" (404,
    400 etc.) não são retentados, só relançados na hora."""
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = httpx.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 429 or resp.status_code >= 500:
                last_exc = RuntimeError(f"{what}: HTTP {resp.status_code}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                resp.raise_for_status()
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            last_exc = e
            if e.response is not None and (e.response.status_code == 429 or e.response.status_code >= 500) and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise
        except httpx.RequestError as e:
            # Falha de rede/timeout também vale uma nova tentativa.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise
    if last_exc:
        raise last_exc


def _no_pillow_message():
    return (
        "A biblioteca Pillow não está instalada no servidor (necessária "
        "para montar o mosaico de tiles do OpenStreetMap). Rode "
        "'pip install Pillow' e tente de novo."
    )


def _meters_to_deg_lat(meters):
    return meters / 111_320.0


def _meters_to_deg_lng(meters, at_lat):
    return meters / (111_320.0 * max(math.cos(math.radians(at_lat)), 0.01))


def geocode_place(query):
    """Converte um texto livre (endereço, cidade, ponto turístico) em
    coordenadas reais + nome formatado, usando o Nominatim — o serviço
    de geocodificação oficial do próprio OpenStreetMap, de graça."""
    query = (query or "").strip()
    if not query:
        raise RuntimeError("Diga qual lugar você quer ver no holograma.")

    _respect_nominatim_rate_limit()
    resp = _get_with_retry(
        NOMINATIM_URL,
        params={"q": query, "format": "jsonv2", "limit": 1, "accept-language": "pt-BR"},
        headers={"User-Agent": USER_AGENT},
        what="Nominatim (busca do lugar)",
    )
    results = resp.json()

    if not results:
        raise RuntimeError(f"Não encontrei nenhum lugar chamado \"{query}\" no OpenStreetMap.")

    place = results[0]
    return {
        "lat": float(place["lat"]),
        "lng": float(place["lon"]),
        "formatted_address": place.get("display_name", query),
    }


def _single_point_elevation(lat, lng):
    """Busca a altitude de um único ponto — usado como último recurso
    quando a malha completa falha, para pelo menos ter uma base real
    (em vez de simplesmente inventar 0m) e montar um terreno plano
    nessa altura."""
    resp = _get_with_retry(
        ELEVATION_URL,
        params={"latitude": f"{lat:.6f}", "longitude": f"{lng:.6f}"},
        headers={"User-Agent": USER_AGENT},
        what="Open-Meteo (elevação de 1 ponto)",
    )
    elevations = resp.json().get("elevation") or []
    return float(elevations[0]) if elevations else 0.0


def get_elevation_grid(lat, lng):
    """Busca uma malha real de altitudes (metros acima do nível do mar)
    ao redor do ponto, usando a Elevation API grátis da Open-Meteo — é
    isso que vira o relevo de verdade do terreno no holograma, em vez
    de ruído procedural.

    A Open-Meteo é um serviço comunitário com um limite de requisições
    por minuto relativamente baixo no plano grátis; em picos de uso
    isso pode devolver "429 Too Many Requests". Para não derrubar o
    holograma inteiro por isso: (1) reaproveitamos um resultado recente
    em cache pra mesma coordenada, (2) tentamos de novo com espera
    crescente (ver _get_with_retry) e (3), se mesmo assim tudo falhar,
    caímos para um terreno plano na altitude real de um único ponto —
    o holograma ainda materializa o lugar certo (coordenadas e mapa
    reais), só sem o relevo detalhado dessa vez."""
    cache_key = _elevation_cache_key(lat, lng)
    cached = _ELEVATION_CACHE.get(cache_key)
    if cached and (time.time() - cached["fetched_at"]) < _ELEVATION_CACHE_TTL_SECONDS:
        return cached["grid"]

    dlat = _meters_to_deg_lat(HALF_SIZE_METERS)
    dlng = _meters_to_deg_lng(HALF_SIZE_METERS, lat)

    lats, lngs = [], []
    for iy in range(GRID):
        fy = iy / (GRID - 1)
        plat = lat + dlat - fy * (2 * dlat)
        for ix in range(GRID):
            fx = ix / (GRID - 1)
            plng = lng - dlng + fx * (2 * dlng)
            lats.append(f"{plat:.6f}")
            lngs.append(f"{plng:.6f}")

    # A Elevation API da Open-Meteo aceita listas de "latitude"/
    # "longitude" separadas por vírgula, até 100 pontos por chamada —
    # com GRID=12 (144 pontos) isso já cabe em só 2 lotes.
    all_elevations = []
    batch = 100
    try:
        for i in range(0, len(lats), batch):
            resp = _get_with_retry(
                ELEVATION_URL,
                params={
                    "latitude": ",".join(lats[i:i + batch]),
                    "longitude": ",".join(lngs[i:i + batch]),
                },
                headers={"User-Agent": USER_AGENT},
                what="Open-Meteo (malha de elevação)",
            )
            payload = resp.json()
            elevations = payload.get("elevation")
            if not elevations:
                raise RuntimeError("resposta sem elevação")
            all_elevations.extend(elevations)
            # Um respiro entre lotes ajuda a não estourar o limite de
            # requisições por segundo/minuto do serviço gratuito.
            if i + batch < len(lats):
                time.sleep(0.4)

        grid_2d = [all_elevations[i * GRID:(i + 1) * GRID] for i in range(GRID)]
    except Exception:
        # Malha completa indisponível agora (ex: 429 persistente) — em
        # vez de derrubar o holograma inteiro, caímos para um terreno
        # plano na altitude real do ponto central, se conseguirmos
        # buscar pelo menos essa (uma única requisição é bem mais leve
        # e tem muito mais chance de passar do que 144 de uma vez).
        try:
            base_height = _single_point_elevation(lat, lng)
        except Exception:
            base_height = 0.0
        grid_2d = [[base_height] * GRID for _ in range(GRID)]

    _ELEVATION_CACHE[cache_key] = {"grid": grid_2d, "fetched_at": time.time()}
    return grid_2d


def _deg_to_tile(lat, lng, zoom):
    """Converte lat/lng para coordenadas de tile (x, y) no esquema
    padrão de slippy map usado pelo OpenStreetMap e por praticamente
    todo servidor de tiles compatível."""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = (lng + 180.0) / 360.0 * n
    y = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def get_satellite_image_data_uri(lat, lng):
    """Baixa um mosaico real de tiles do OpenStreetMap ao redor do
    ponto e costura tudo numa única imagem com Pillow — é o mapa de
    verdade do OSM (ruas, construções, relevo urbano) virando textura
    do terreno no Three.js, sem precisar de chave nem de imagem de
    satélite paga."""
    if not _HAS_PILLOW:
        raise RuntimeError(_no_pillow_message())

    cx, cy = _deg_to_tile(lat, lng, TILE_ZOOM)
    cx_i, cy_i = int(math.floor(cx)), int(math.floor(cy))
    half = TILE_GRID // 2

    cache_key = (cx_i, cy_i, TILE_ZOOM)
    cached = _TILE_IMAGE_CACHE.get(cache_key)
    if cached and (time.time() - cached["fetched_at"]) < _TILE_IMAGE_CACHE_TTL_SECONDS:
        return cached["data_uri"]

    mosaic = Image.new("RGB", (TILE_GRID * 256, TILE_GRID * 256), (30, 30, 30))

    def fetch_tile(client, row, col):
        tx = cx_i - half + col
        ty = cy_i - half + row
        try:
            resp = client.get(TILE_URL.format(z=TILE_ZOOM, x=tx, y=ty))
            resp.raise_for_status()
            tile_img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            return row, col, tile_img
        except Exception:
            # Um tile faltando (ex: borda do mapa, oceano sem dado)
            # não deve derrubar o mosaico inteiro — só deixamos aquele
            # quadrado com a cor de fundo.
            return row, col, None

    # Baixa os 25 tiles em paralelo (antes eram 25 requisições em
    # série, uma de cada vez — o gargalo que fazia o holograma de
    # "lugar real" demorar dezenas de segundos e travar a página
    # enquanto isso). Um limite de 6 conexões simultâneas é gentil o
    # bastante com o servidor gratuito de tiles da OSM sem virar um
    # ataque de força bruta.
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT) as client:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [
                pool.submit(fetch_tile, client, row, col)
                for row in range(TILE_GRID)
                for col in range(TILE_GRID)
            ]
            for future in futures:
                row, col, tile_img = future.result()
                if tile_img is not None:
                    mosaic.paste(tile_img, (col * 256, row * 256))

    buffer = io.BytesIO()
    mosaic.save(buffer, format="JPEG", quality=88)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    data_uri = f"data:image/jpeg;base64,{encoded}"
    _TILE_IMAGE_CACHE[cache_key] = {"data_uri": data_uri, "fetched_at": time.time()}
    return data_uri


def _parse_height_meters(tags):
    """Extrai a altura de um prédio a partir das tags do OpenStreetMap,
    na ordem de confiança: "height" (metros, direto) > "building:levels"
    (número de andares, convertido) > None (sem informação nenhuma)."""
    height_raw = tags.get("height")
    if height_raw:
        match = re.search(r"[\d.]+", height_raw)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass

    levels_raw = tags.get("building:levels") or tags.get("levels")
    if levels_raw:
        match = re.search(r"[\d.]+", levels_raw)
        if match:
            try:
                return float(match.group()) * DEFAULT_LEVEL_HEIGHT_METERS
            except ValueError:
                pass

    return None


def get_buildings(lat, lng):
    """Busca, de graça e sem chave nenhuma, o contorno real (pegada no
    chão) e a altura real de cada prédio ao redor do ponto, usando a
    Overpass API — o serviço público de consultas ao banco de dados
    aberto do próprio OpenStreetMap (a mesma base usada em
    geocode_place() e get_elevation_grid()).

    É isso que dá o efeito de "prédios de verdade" no holograma — cada
    quarteirão com sua forma e altura reais extrudadas em 3D — em vez
    de só um terreno com relevo. Não depende de nenhum serviço pago de
    tiles 3D (tipo Google Maps Platform 3D Tiles ou Cesium ion, que
    cobram por requisição/uso).

    Assim como get_elevation_grid(), isto é "best effort": a Overpass é
    um serviço comunitário sem SLA, então se os dois espelhos
    estiverem fora do ar ou sobrecarregados, devolvemos uma lista
    vazia em vez de derrubar o holograma inteiro — o lugar ainda
    materializa normalmente, só sem prédios extrudados desta vez."""
    cache_key = _elevation_cache_key(lat, lng)
    cached = _BUILDINGS_CACHE.get(cache_key)
    if cached and (time.time() - cached["fetched_at"]) < _BUILDINGS_CACHE_TTL_SECONDS:
        return cached["buildings"]

    query = (
        "[out:json][timeout:20];"
        f"(way[\"building\"](around:{BUILDING_RADIUS_METERS},{lat:.6f},{lng:.6f}););"
        f"out geom {MAX_BUILDINGS};"
    )

    payload = None
    for url in OVERPASS_URLS:
        try:
            resp = httpx.post(
                url,
                data={"data": query},
                headers={"User-Agent": USER_AGENT},
                timeout=25,
            )
            resp.raise_for_status()
            payload = resp.json()
            break
        except Exception:
            continue

    if payload is None:
        return []

    cos_lat = max(math.cos(math.radians(lat)), 0.01)
    buildings = []
    for el in payload.get("elements", []):
        geometry = el.get("geometry")
        if not geometry or len(geometry) < 3:
            continue
        tags = el.get("tags") or {}

        # Converte cada nó do contorno de lat/lng absolutos para metros
        # relativos ao centro (leste/norte positivos) — mesmo sistema
        # de coordenadas locais que o front-end usa pra posicionar o
        # terreno, então os prédios caem no lugar certo em cima dele.
        footprint = []
        for node in geometry:
            dx = (node["lon"] - lng) * 111_320.0 * cos_lat
            dy = (node["lat"] - lat) * 111_320.0
            footprint.append([round(dx, 1), round(dy, 1)])

        levels = None
        levels_raw = tags.get("building:levels")
        if levels_raw:
            match = re.search(r"[\d.]+", levels_raw)
            if match:
                try:
                    levels = float(match.group())
                except ValueError:
                    levels = None

        height_m = _parse_height_meters(tags)
        if height_m is None:
            # Sem "height" nem "building:levels" nas tags (comum fora
            # de grandes cidades): altura padrão modesta, com uma
            # pequena variação determinística por prédio (baseada no
            # próprio id da via no OSM) só pra não deixar todo prédio
            # sem essa tag do exato mesmo tamanho — o que ficaria
            # artificial demais.
            height_m = DEFAULT_BUILDING_HEIGHT_METERS + (el.get("id", 0) % 5) * 2.4

        buildings.append({
            "footprint": footprint,
            "height_m": round(height_m, 1),
            "levels": levels,
        })

    _BUILDINGS_CACHE[cache_key] = {"buildings": buildings, "fetched_at": time.time()}
    return buildings


def get_place_hologram_data(query):
    """Orquestra as 3 chamadas acima e devolve tudo pronto pro
    holograma: coordenadas, endereço, malha de elevação real e a
    textura de mapa real do OpenStreetMap — em uma única resposta pro
    frontend. 100% grátis, sem chave de API nenhuma.

    Elevação, mosaico de tiles e prédios são buscados EM PARALELO (3
    threads) depois da geocodificação — antes eram 3 chamadas em
    série (cada uma podendo levar vários segundos, e a Overpass
    sozinha até ~25s), então o pedido inteiro podia passar de 40-50s
    e estourar o timeout do servidor/proxy antes de responder — é
    isso que fazia o navegador receber uma página de erro em HTML no
    lugar do JSON esperado ("Unexpected token '<'"). Em paralelo, o
    tempo total cai para o da chamada mais lenta das três, não a soma
    delas."""
    query = (query or "").strip()
    if not query:
        raise RuntimeError("Diga qual lugar você quer ver no holograma.")

    place = geocode_place(query)

    with ThreadPoolExecutor(max_workers=3) as pool:
        elevation_future = pool.submit(get_elevation_grid, place["lat"], place["lng"])
        satellite_future = pool.submit(get_satellite_image_data_uri, place["lat"], place["lng"])
        buildings_future = pool.submit(get_buildings, place["lat"], place["lng"])

        elevation_grid = elevation_future.result()
        satellite_data_uri = satellite_future.result()
        try:
            buildings = buildings_future.result()
        except Exception:
            # Prédios são um "bônus" visual — qualquer falha aqui não deve
            # impedir o holograma de materializar o lugar com relevo e
            # mapa reais, que são o essencial.
            buildings = []

    flat = [v for row in elevation_grid for v in row]
    # Se a malha caiu no modo de reserva (terreno plano, ver
    # get_elevation_grid), todos os valores são idênticos — usamos isso
    # pra avisar o front-end, sem transformar isso num erro: o
    # holograma ainda materializa o lugar certo, só sem relevo real
    # desta vez.
    elevation_degraded = (max(flat) - min(flat)) < 0.01
    return {
        "query": query,
        "lat": place["lat"],
        "lng": place["lng"],
        "formatted_address": place["formatted_address"],
        "grid_size": GRID,
        "area_meters": HALF_SIZE_METERS * 2,
        "elevation_grid": elevation_grid,
        "elevation_min": min(flat),
        "elevation_max": max(flat),
        "elevation_degraded": elevation_degraded,
        "satellite_image": satellite_data_uri,
        "buildings": buildings,
        "buildings_radius_meters": BUILDING_RADIUS_METERS,
        "source": "OpenStreetMap",
    }
