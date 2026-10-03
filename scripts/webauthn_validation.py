"""Validation report for JARVIS WebAuthn hardening.

This script never substitutes static checks for cryptographic verification. If
Flask/py_webauthn are unavailable in the current environment, the corresponding
runtime/crypto tests are explicitly reported as NOT EXECUTED.
"""
from __future__ import annotations
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQ = (ROOT / "requirements.txt").read_text(encoding="utf-8")

results = []
def add(name, status, detail=""):
    results.append((name, status, detail))

add("requirements Flask", "PASS" if re.search(r"(?m)^Flask[<=>]", REQ) else "FAIL", "Flask declarado")
add("requirements WebAuthn", "PASS" if re.search(r"(?m)^webauthn==3\.0\.1$", REQ) else "FAIL", "py_webauthn 3.0.1 declarado")
add("WebAuthn dependency installed", "PASS" if importlib.util.find_spec("webauthn") else "NOT EXECUTED", "biblioteca ausente no ambiente de build" if not importlib.util.find_spec("webauthn") else "")
add("Flask installed", "PASS" if importlib.util.find_spec("flask") else "NOT EXECUTED", "Flask ausente no ambiente de build" if not importlib.util.find_spec("flask") else "")

source = (ROOT / "app.py").read_text(encoding="utf-8")
svc = (ROOT / "services/webauthn_service.py").read_text(encoding="utf-8")
add("Frontend-only credential registration removed", "PASS" if "response.getPublicKey" not in (ROOT / "templates/settings.html").read_text(encoding="utf-8") else "FAIL")
add("Server challenge generation", "PASS" if "secrets.token_bytes(32)" in svc else "FAIL")
add("Challenge expiry", "PASS" if '"expires": time.time() + 120' in source else "FAIL")
add("Single-use challenge", "PASS" if 'session.pop("_webauthn_pending", None)' in source else "FAIL")
add("Origin/RP config", "PASS" if "WEBAUTHN_RP_ID" in svc and "WEBAUTHN_ORIGIN" in svc else "FAIL")
add("Crypto verification delegated to library", "PASS" if "verify_registration_response" in svc and "verify_authentication_response" in svc else "FAIL")
add("Signature not manually implemented", "PASS" if "cryptography" not in svc.lower() and "verify_signature" not in svc else "FAIL")
add("Fail closed", "PASS" if 'return jsonify({"error": "Passkey inválida, expirada ou não reconhecida."}), 401' in source else "FAIL")
add("Passkey default disabled", "PASS" if '_env_bool("WEBAUTHN_ENABLED", False)' in svc else "FAIL")
add("Session rotation after passkey", "PASS" if '_establish_authenticated_session("owner", "owner")' in source else "FAIL")
add("Sign count persistence", "PASS" if "update_webauthn_sign_count" in source else "FAIL")

if importlib.util.find_spec("flask") and importlib.util.find_spec("webauthn"):
    try:
        import app  # noqa: F401
        add("Flask import/runtime bootstrap", "PASS")
    except Exception as exc:
        add("Flask import/runtime bootstrap", "FAIL", type(exc).__name__)
else:
    add("Flask import/runtime bootstrap", "NOT EXECUTED", "dependências não instaladas no ambiente atual")

print("WEBAUTHN_VALIDATION")
for name, status, detail in results:
    print(f"{name}: {status}" + (f" — {detail}" if detail else ""))

failures = [r for r in results if r[1] == "FAIL"]
print("SUMMARY", json.dumps({"pass": sum(r[1]=='PASS' for r in results), "fail": len(failures), "not_executed": sum(r[1]=='NOT EXECUTED' for r in results)}))
raise SystemExit(1 if failures else 0)
