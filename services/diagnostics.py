"""Auto-diagnóstico do sistema: detecta → causa → correção SEGURA → reteste."""
import os
import sqlite3
import tempfile
from pathlib import Path

from services import scope, evidence, config as cfg
from services.tool_registry import REGISTRY

BASE = Path(__file__).resolve().parent.parent


def _check_data_dir():
    d = BASE / "data"
    try:
        d.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=d, delete=True):
            pass
        return True, "data/ gravável"
    except Exception as e:
        return False, f"data/ não gravável: {e}"


def _fix_data_dir():
    (BASE / "data").mkdir(exist_ok=True)


def _check_db():
    try:
        with evidence._conn() as c:
            c.execute("SELECT COUNT(*) FROM scans").fetchone()
        return True, "SQLite do Evidence Center OK"
    except sqlite3.Error as e:
        return False, f"SQLite com erro: {e}"


def _check_ai():
    return (True, "Provedor de IA configurado") if cfg.has_any_ai_key() else \
           (False, "Nenhuma chave de IA configurada (Configurações)")


def _check_targets():
    try:
        n = len(scope.list_targets())
        return True, f"{n} alvo(s) autorizado(s)"
    except Exception as e:
        return False, f"lista de alvos ilegível: {e}"


def _check_tools():
    n = len(REGISTRY.tools)
    if REGISTRY.plugin_errors:
        return False, f"{n} ferramentas; plugins com erro: " + ", ".join(p["plugin"] for p in REGISTRY.plugin_errors)
    return True, f"{n} ferramentas registradas"


def _check_secret_key():
    if os.getenv("SECRET_KEY", "tf-studio-web-troque-esta-chave") == "tf-studio-web-troque-esta-chave":
        return False, "SECRET_KEY padrão em uso — defina SECRET_KEY no ambiente"
    return True, "SECRET_KEY personalizada"


CHECKS = [
    ("data_dir", "Pasta de dados", _check_data_dir, _fix_data_dir),
    ("database", "Banco de evidências", _check_db, lambda: evidence._conn().close()),
    ("ai_provider", "Provedor de IA", _check_ai, None),
    ("targets", "Alvos autorizados", _check_targets, None),
    ("tools", "Registry de ferramentas", _check_tools, None),
    ("secret_key", "Chave de sessão", _check_secret_key, None),
]


def run_selfcheck(fix=True):
    out = []
    for cid, name, check, fixer in CHECKS:
        ok, msg = check()
        item = {"id": cid, "name": name, "ok": ok, "message": msg, "fixed": False}
        if not ok and fix and fixer:
            try:
                fixer()
                ok2, msg2 = check()
                item.update({"ok": ok2, "message": msg2, "fixed": ok2, "before": msg})
            except Exception as e:
                item["fix_error"] = str(e)[:120]
        out.append(item)
    return {"ok": all(i["ok"] for i in out), "checks": out}
