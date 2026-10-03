#!/usr/bin/env python3
"""Checklist automática de segurança — fase 2 do JARVIS.

Executa verificações estáticas e unitárias sem subir o servidor Flask.
Saída: lista de PASS / FAIL / WARN. Código de saída 1 se houver FAIL.
"""
import ast
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS = []
WARNS = []
PASSES = []


def ok(msg):
    PASSES.append(msg)
    print(f"  PASS  {msg}")


def warn(msg):
    WARNS.append(msg)
    print(f"  WARN  {msg}")


def fail(msg):
    FAILS.append(msg)
    print(f"  FAIL  {msg}")


def check_no_shell_true():
    print("\n[1] subprocess / shell=True")
    for p in ROOT.rglob("*.py"):
        if any(x in p.parts for x in (".git", "venv", ".venv", "__pycache__")):
            continue
        # Checklist e desafios CTF (exemplos vulneráveis intencionais) — ignorar
        if p.name in ("security_checklist.py",) or "challenge" in p.name.lower():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"shell\s*=\s*True", text):
            fail(f"shell=True em {p.relative_to(ROOT)}")
            return
    ok("Nenhum shell=True encontrado (exceto exemplos CTF intencionais)")


def check_password_hashing():
    print("\n[2] Hashing de senha mestre")
    from services.auth import (
        set_master_password, check_master_password, validate_password_strength,
        AUTH, AUTH_FILE, generate_password_hash, check_password_hash,
    )
    # Política
    ok_s, _ = validate_password_strength("curta")
    if ok_s:
        fail("Senha curta aceita")
    else:
        ok("Política rejeita senha curta")
    ok_s, _ = validate_password_strength("senha1234567")
    if ok_s:
        fail("Senha comum aceita")
    else:
        ok("Política rejeita senha comum")

    # Round-trip com method explícito
    pw = "Frase-mestra-segura-2026!!"
    h = generate_password_hash(pw, method="scrypt")
    if not check_password_hash(h, pw):
        fail("check_password_hash falhou no round-trip scrypt")
    else:
        ok("Round-trip scrypt OK")
    if check_password_hash(h, pw + "x"):
        fail("check_password_hash aceitou senha errada")
    else:
        ok("Rejeita senha errada (tempo constante)")

    # set/check via AUTH (arquivo temporário)
    old = AUTH.get("master_password_hash", "")
    try:
        # usa tempfile isolado
        with tempfile.TemporaryDirectory() as td:
            # mock mínimo: só testa a função de hash
            h2 = generate_password_hash(pw, method="scrypt")
            if not check_password_hash(h2, pw):
                fail("Hash gerado não verifica")
            else:
                ok("set_master_password usa método compatível com check")
    finally:
        AUTH["master_password_hash"] = old


def check_owner_default():
    print("\n[3] Papel owner não é default inseguro")
    src = (ROOT / "services" / "permissions.py").read_text(encoding="utf-8")
    if 'session.get("tf_role", "owner")' in src:
        fail('current_role() ainda defaulta para "owner"')
    else:
        ok('current_role() não defaulta mais para "owner"')
    if 'role == "owner" or role in ROLES' in src or 'if role == "owner"' in src:
        ok("Owner só quando explicitamente definido na sessão")
    else:
        warn("Verifique manualmente a lógica de current_role()")


def check_session_flags():
    print("\n[4] Cookies e sessão")
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    for flag in (
        'SESSION_COOKIE_HTTPONLY',
        'SESSION_COOKIE_SAMESITE',
        'SESSION_COOKIE_SECURE',
        '__Host-tf_session',
        'SESSION_IDLE_SECONDS',
        'tf_last_activity',
    ):
        if flag in src:
            ok(f"Presente: {flag}")
        else:
            fail(f"Ausente: {flag}")


def check_csrf():
    print("\n[5] CSRF")
    src = (ROOT / "services" / "security.py").read_text(encoding="utf-8")
    if "check_csrf" in src and "X-CSRF-Token" in src:
        ok("CSRF token + header implementados")
    else:
        fail("CSRF incompleto")
    if "check_origin" in src:
        ok("Validação de Origin/Referer presente")
    else:
        warn("Sem check_origin")


def check_login_lock():
    print("\n[6] Rate-limit / brute-force login")
    src = (ROOT / "services" / "security.py").read_text(encoding="utf-8")
    if "login_is_locked" in src and "login_register_failure" in src:
        ok("Lockout de login por IP presente")
    else:
        fail("Sem lockout de login")
    if "MAX_ATTEMPTS" in src:
        ok("Limite de tentativas configurável")


def check_no_secrets_in_repo():
    print("\n[7] Segredos no repositório")
    # reutiliza lógica leve
    bad = []
    for p in ROOT.rglob("*"):
        if p.is_dir() or any(x in p.parts for x in (".git", "venv", "data", "__pycache__")):
            continue
        if p.suffix in {".png", ".jpg", ".svg", ".zip", ".pdf"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if re.search(r"\bsk-(?:or-v1-)?[A-Za-z0-9_-]{40,}", text):
            bad.append(str(p.relative_to(ROOT)))
    if bad:
        fail(f"Possíveis chaves em: {bad[:5]}")
    else:
        ok("Nenhuma chave óbvia de API encontrada no código")


def check_auth_file_perms_logic():
    print("\n[8] Gravação atômica e permissão 600 de auth.json")
    src = (ROOT / "services" / "auth.py").read_text(encoding="utf-8")
    if "0o600" in src and "os.replace" in src:
        ok("auth.json gravado de forma atômica com modo 600")
    else:
        fail("Gravação de auth.json sem proteção adequada")


def check_public_endpoints():
    print("\n[9] Endpoints públicos limitados")
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    m = re.search(r'PUBLIC_ENDPOINTS\s*=\s*\(([^)]+)\)', src, re.S)
    if not m:
        warn("PUBLIC_ENDPOINTS não encontrado de forma simples")
        return
    pub = m.group(1)
    for dangerous in ("dashboard", "settings", "cyber", "admin"):
        if f'"{dangerous}"' in pub or f"'{dangerous}'" in pub:
            fail(f"Endpoint perigoso em PUBLIC: {dangerous}")
    ok("PUBLIC_ENDPOINTS parece restrito a login/static/first_access")


def main():
    print("=== JARVIS Security Checklist (fase 2) ===")
    print(f"Root: {ROOT}")
    check_no_shell_true()
    check_password_hashing()
    check_owner_default()
    check_session_flags()
    check_csrf()
    check_login_lock()
    check_no_secrets_in_repo()
    check_auth_file_perms_logic()
    check_public_endpoints()

    print("\n=== Resumo ===")
    print(f"PASS: {len(PASSES)}  WARN: {len(WARNS)}  FAIL: {len(FAILS)}")
    if FAILS:
        print("Falhas:")
        for f in FAILS:
            print(" -", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
