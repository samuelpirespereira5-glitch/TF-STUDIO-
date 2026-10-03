"""TOTP (RFC 6238) — segundo fator de autenticação para o login do dono.

Implementação mínima e auditável, só com a biblioteca padrão do Python
(hmac/hashlib/struct/base64) — sem depender de pyotp/qrcode. Compatível
com qualquer app autenticador comum (Google Authenticator, Authy, Aegis,
Bitwarden, 1Password, etc.), que aceitam cadastro manual por "segredo"
além de QR code.

Fluxo:
  1. totp_start_setup() gera um segredo novo (ainda não ativo).
  2. O dono cadastra o segredo manualmente no app autenticador dele.
  3. totp_confirm_setup(code) confirma que o app gerou o código certo
     antes de ativar de verdade — evita travar o dono fora por engano.
  4. A partir daí, verify_totp(code) valida o código de 6 dígitos a
     cada login, com tolerância de ±1 passo (30s) para relógios
     ligeiramente dessincronizados.
"""
import base64
import hashlib
import hmac
import os
import secrets as _secrets
import struct
import time
import urllib.parse

STEP_SECONDS = 30
DIGITS = 6


def generate_secret() -> str:
    """20 bytes aleatórios (160 bits), codificados em Base32 — o formato
    que todo app autenticador espera para cadastro manual."""
    return base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")


def _hotp(secret_b32: str, counter: int) -> str:
    secret_b32 = (secret_b32 or "").strip().upper().replace(" ", "")
    pad = "=" * ((8 - len(secret_b32) % 8) % 8)
    try:
        key = base64.b32decode(secret_b32 + pad)
    except Exception:
        return ""
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = (struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** DIGITS)
    return str(code).zfill(DIGITS)


def totp_now(secret_b32: str, for_time: float = None) -> str:
    t = time.time() if for_time is None else for_time
    return _hotp(secret_b32, int(t // STEP_SECONDS))


def verify_totp(secret_b32: str, code: str, window: int = 1) -> bool:
    """Valida o código do passo atual e até `window` passos para trás/frente
    (tolerância de relógio dessincronizado — padrão de mercado é 1)."""
    code = (code or "").strip().replace(" ", "")
    if not secret_b32 or not code.isdigit() or len(code) != DIGITS:
        return False
    counter = int(time.time() // STEP_SECONDS)
    for delta in range(-window, window + 1):
        expected = _hotp(secret_b32, counter + delta)
        if expected and hmac.compare_digest(expected, code):
            return True
    return False


def provisioning_uri(secret_b32: str, account: str = "dono", issuer: str = "Tristan Thorne") -> str:
    """URI otpauth:// — alguns apps aceitam colar isso direto; a maioria
    também aceita digitar o segredo Base32 manualmente, que é o jeito
    oferecido por padrão aqui (sem depender de biblioteca de QR code)."""
    label = urllib.parse.quote(f"{issuer}:{account}")
    params = urllib.parse.urlencode({
        "secret": secret_b32, "issuer": issuer, "algorithm": "SHA1",
        "digits": DIGITS, "period": STEP_SECONDS,
    })
    return f"otpauth://totp/{label}?{params}"


def generate_recovery_codes(n: int = 8) -> list:
    """Códigos de recuperação de uso único (formato aaaaa-bbbbb), para o
    caso do dono perder acesso ao app autenticador. Só são mostrados uma
    vez na hora de ativar o 2FA — só o hash fica guardado."""
    out = []
    for _ in range(n):
        raw = _secrets.token_hex(5)
        out.append(f"{raw[:5]}-{raw[5:]}")
    return out
