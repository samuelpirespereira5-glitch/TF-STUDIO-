"""Registry de ferramentas do Jarvis (extensível por plugins).

Uma ferramenta = id + metadados + `handler(params, ctx) -> dict`.
O handler devolve {"findings": [...], "raw": {...}, "summary": "..."} para
ferramentas de análise, ou {"ui_action": {...}} para ferramentas que
comandam a interface (ex.: mostrar um holograma).

Plugins: qualquer arquivo `plugins/*.py` com `def register(registry): ...`
é carregado no boot. Exemplo mínimo:

    def register(reg):
        reg.register(id="meu_plugin", name="Meu plugin", category="custom",
                     description="...", cap="tools_basic", keywords=["olá"],
                     params={"texto": {"required": True}},
                     handler=lambda p, ctx: {"summary": "oi " + p["texto"]})
"""
import importlib.util
import time
import traceback
from pathlib import Path

from services import permissions, evidence, telemetry

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugins"


class Tool:
    def __init__(self, id, name, category, description, handler, cap="tools_basic",
                 keywords=None, params=None, kind="analysis", persist=False,
                 needs_target=False, explain=""):
        self.id, self.name, self.category = id, name, category
        self.description, self.handler, self.cap = description, handler, cap
        self.keywords = [k.lower() for k in (keywords or [])]
        self.params = params or {}
        self.kind = kind              # analysis | ui | ai
        self.persist = persist        # salva no Evidence Center
        self.needs_target = needs_target
        self.explain = explain or description

    def public(self):
        return {
            "id": self.id, "name": self.name, "category": self.category,
            "description": self.description, "capability": self.cap,
            "params": self.params, "kind": self.kind,
            "needs_target": self.needs_target,
        }


class Registry:
    def __init__(self):
        self.tools = {}
        self.plugin_errors = []

    def register(self, **kw):
        t = Tool(**kw)
        self.tools[t.id] = t
        return t

    def get(self, tool_id):
        return self.tools.get(tool_id)

    def list_for(self, role):
        return [t.public() for t in self.tools.values() if permissions.has_cap(t.cap, role)]

    def load_plugins(self):
        if not PLUGIN_DIR.exists():
            return
        for f in sorted(PLUGIN_DIR.glob("*.py")):
            if f.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(f"tf_plugin_{f.stem}", f)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "register"):
                    mod.register(self)
            except Exception as e:
                # plugin quebrado nunca derruba o app — vira item de diagnóstico
                self.plugin_errors.append({"plugin": f.name, "error": str(e)[:200]})


REGISTRY = Registry()


def execute(tool_id, params, role, ctx=None):
    """Executa uma ferramenta COM checagem de permissão no backend."""
    tool = REGISTRY.get(tool_id)
    ctx = ctx or {}
    if not tool:
        telemetry.log(role, ctx.get("session_id", ""), tool_id, params.get("target"), False, error="NotFound")
        return {"ok": False, "tool": tool_id, "error": f"Ferramenta '{tool_id}' não existe.", "error_type": "NotFound"}
    if not permissions.has_cap(tool.cap, role):
        telemetry.log(role, ctx.get("session_id", ""), tool_id, params.get("target"), False, error="PermissionDenied")
        return {"ok": False, "tool": tool_id, "error_type": "PermissionDenied",
                "error": f"Seu papel ({role}) não pode usar '{tool.name}' (exige '{tool.cap}')."}
    missing = [k for k, spec in tool.params.items() if spec.get("required") and not params.get(k)]
    if missing:
        telemetry.log(role, ctx.get("session_id", ""), tool_id, params.get("target"), False, error="MissingParams")
        return {"ok": False, "tool": tool_id, "error_type": "MissingParams",
                "error": f"Faltam parâmetros: {', '.join(missing)}."}
    ctx = {**ctx, "role": role}
    t0 = time.perf_counter()
    try:
        res = tool.handler(params, ctx) or {}
    except Exception as e:
        ms = round((time.perf_counter() - t0) * 1000)
        telemetry.log(role, ctx.get("session_id", ""), tool_id, params.get("target"), False, ms, str(e))
        return {"ok": False, "tool": tool_id, "error": str(e) or e.__class__.__name__,
                "error_type": e.__class__.__name__,
                "duration_ms": ms,
                "trace": traceback.format_exc(limit=3)[-600:] if permissions.has_cap("diagnostics", role) else None}
    ms = round((time.perf_counter() - t0) * 1000)
    telemetry.log(role, ctx.get("session_id", ""), tool_id, params.get("target"), True, ms)
    try:
        from services import gamification
        gamification.record_tool_use(str(ctx.get("session_id") or role or "owner"), tool_id)
    except Exception:
        pass
    out = {"ok": True, "tool": tool_id, "name": tool.name, "duration_ms": ms, "summary": res.get("summary", "")}
    findings = res.get("findings")
    if findings is not None:
        out["findings"] = findings
        out["score"] = evidence.risk_score(findings)
        out["risk"] = evidence.risk_label(out["score"])
        if tool.persist:
            target = evidence.normalize_target(params.get("target") or params.get("domain") or ctx.get("target") or "local")
            out["scan_id"] = evidence.save_scan(target, tool.id, findings, res.get("raw"), ms,
                                                ctx.get("session_id", ""))
            # Phase 2 only observes persisted scans; it does not replace the
            # Evidence Center. Import locally to avoid an import cycle.
            try:
                from services import cyber_phase2
                uid = ctx.get("session_id", "owner")
                cyber_phase2.mark_tool_used(uid, tool.id)
                saved = evidence.get_scan(out["scan_id"])
                cyber_phase2.sync_scan_alerts(uid, saved)
            except Exception:
                pass
    for k in ("raw", "ui_action", "scene", "text"):
        if k in res:
            out[k] = res[k]
    return out
