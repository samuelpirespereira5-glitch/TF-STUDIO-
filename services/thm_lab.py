"""TryHackMe Lab — área privada do desenvolvedor (dono/owner).

Espaço pessoal e expansível para ferramentas, labs, comandos, cheatsheets,
desafios e anotações de estudo em cybersecurity. "TryHackMe" aqui é só o
nome da área (referência de treinamento/laboratório) — nenhum conteúdo
proprietário da plataforma TryHackMe é incluído ou copiado.

Sem limites artificiais: qualquer categoria (mesmo uma nova, digitada pelo
usuário) e qualquer quantidade de itens são aceitos. Persistido em JSON
simples (mesma filosofia de services/scope.py), protegido pela capability
'thm_lab' (só o papel 'owner' tem, ver services/permissions.py).
"""
import json
import threading
import time
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FILE = DATA_DIR / "thm_lab.json"
_lock = threading.Lock()

# Categorias sugeridas na UI (chips de filtro) — não é uma lista fechada:
# o usuário pode digitar qualquer outra categoria ao criar um item.
DEFAULT_CATEGORIES = [
    "Web Security", "Network", "Linux", "Windows", "Privilege Escalation",
    "OSINT", "Cryptography", "Forensics", "Reverse Engineering",
    "Malware Analysis", "SOC", "Pentest", "CTF",
]


def _empty():
    return {"items": {}, "history": []}


def _load():
    if not FILE.exists():
        data = _empty()
        _save(data)
        _seed_once(data)
        return _load()
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return _empty()


def _seed_once(data):
    """Popula a base na primeira execução com ferramentas/comandos reais e
    genéricos de cybersecurity (não é conteúdo proprietário do TryHackMe —
    ver services/thm_seed.py)."""
    from services import thm_seed

    def _add(**kw):
        item_id = uuid.uuid4().hex[:12]
        now = time.time()
        data["items"][item_id] = {
            "id": item_id, "title": kw["title"], "category": kw["category"],
            "kind": kw.get("kind", "tool"), "description": kw.get("description", ""),
            "content": kw.get("content", ""), "tags": kw.get("tags", []),
            "url": kw.get("url", ""), "notes": "", "favorite": False,
            "views": 0, "created_at": now, "updated_at": now,
        }

    thm_seed.seed_items(_add)
    _save(data)


def _save(data):
    DATA_DIR.mkdir(exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(FILE)


def categories():
    data = _load()
    used = {it["category"] for it in data["items"].values() if it.get("category")}
    return sorted(set(DEFAULT_CATEGORIES) | used, key=lambda c: (c not in DEFAULT_CATEGORIES, c))


def list_items(category=None, q=None, only_favorites=False, tag=None):
    data = _load()
    items = list(data["items"].values())
    if category:
        items = [i for i in items if i.get("category", "").lower() == category.lower()]
    if only_favorites:
        items = [i for i in items if i.get("favorite")]
    if tag:
        items = [i for i in items if tag.lower() in [t.lower() for t in i.get("tags", [])]]
    if q:
        q = q.lower()
        items = [
            i for i in items
            if q in i.get("title", "").lower()
            or q in i.get("description", "").lower()
            or q in i.get("content", "").lower()
            or q in i.get("notes", "").lower()
            or any(q in t.lower() for t in i.get("tags", []))
        ]
    return sorted(items, key=lambda i: i.get("updated_at", 0), reverse=True)


def get_item(item_id):
    return _load()["items"].get(item_id)


def add_item(title, category, kind="tool", description="", content="", tags=None, url=""):
    title = (title or "").strip()
    if not title:
        raise ValueError("Título é obrigatório.")
    category = (category or "Geral").strip() or "Geral"
    item_id = uuid.uuid4().hex[:12]
    now = time.time()
    item = {
        "id": item_id, "title": title, "category": category, "kind": kind,
        "description": (description or "").strip(), "content": content or "",
        "tags": [t.strip() for t in (tags or []) if t.strip()],
        "url": (url or "").strip(), "notes": "", "favorite": False,
        "views": 0, "created_at": now, "updated_at": now,
    }
    with _lock:
        data = _load()
        data["items"][item_id] = item
        _save(data)
    return item


def update_item(item_id, **fields):
    with _lock:
        data = _load()
        item = data["items"].get(item_id)
        if not item:
            raise ValueError("Item não encontrado.")
        for k in ("title", "category", "kind", "description", "content", "url", "notes"):
            if k in fields and fields[k] is not None:
                item[k] = fields[k]
        if "tags" in fields and fields["tags"] is not None:
            item["tags"] = [t.strip() for t in fields["tags"] if t.strip()]
        item["updated_at"] = time.time()
        _save(data)
        return item


def delete_item(item_id):
    with _lock:
        data = _load()
        existed = data["items"].pop(item_id, None) is not None
        _save(data)
        return existed


def toggle_favorite(item_id):
    with _lock:
        data = _load()
        item = data["items"].get(item_id)
        if not item:
            raise ValueError("Item não encontrado.")
        item["favorite"] = not item.get("favorite", False)
        _save(data)
        return item


def register_view(item_id, by="owner"):
    """Conta a visualização e grava no histórico (usado quando o item é aberto)."""
    with _lock:
        data = _load()
        item = data["items"].get(item_id)
        if not item:
            return None
        item["views"] = item.get("views", 0) + 1
        data["history"].insert(0, {"item_id": item_id, "title": item["title"], "by": by, "ts": time.time()})
        data["history"] = data["history"][:300]
        _save(data)
        return item


def history(limit=50):
    data = _load()
    return data["history"][:limit]


def clear_history():
    with _lock:
        data = _load()
        data["history"] = []
        _save(data)


def stats():
    data = _load()
    items = list(data["items"].values())
    by_cat = {}
    for i in items:
        by_cat[i.get("category", "Geral")] = by_cat.get(i.get("category", "Geral"), 0) + 1
    return {
        "total": len(items),
        "favorites": sum(1 for i in items if i.get("favorite")),
        "by_category": by_cat,
        "history_count": len(data["history"]),
    }
