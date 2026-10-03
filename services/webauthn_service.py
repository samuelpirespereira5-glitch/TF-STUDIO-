"""WebAuthn/Passkey integration for JARVIS.

This module deliberately delegates WebAuthn parsing and cryptographic verification
entirely to py_webauthn (duo-labs). It never implements signature/CBOR/COSE
verification itself and fails closed when the dependency/configuration is absent.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from urllib.parse import urlparse


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def dependency_available() -> bool:
    try:
        import webauthn  # noqa: F401
        return True
    except Exception:
        return False


def enabled() -> bool:
    return _env_bool("WEBAUTHN_ENABLED", False) and dependency_available() and config_ready()


def rp_id() -> str:
    configured = os.getenv("WEBAUTHN_RP_ID", "").strip().lower()
    return configured


def origin() -> str:
    return os.getenv("WEBAUTHN_ORIGIN", "").strip().rstrip("/")


def config_ready() -> bool:
    rp = rp_id()
    org = origin()
    if not rp or not org:
        return False
    try:
        parsed = urlparse(org)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            return False
        host = parsed.hostname or ""
        # The RP ID must be the origin host or a registrable/domain suffix of it.
        # The library performs the protocol-level RP ID hash verification; this
        # local check prevents an obviously inconsistent deployment config.
        if host != rp and not host.endswith("." + rp):
            return False
    except Exception:
        return False
    # Production must use HTTPS. localhost/http is intentionally allowed only
    # outside production so local development can exercise the ceremony.
    production = os.getenv("FLASK_ENV", "").strip().lower() == "production" or _env_bool("PRODUCTION")
    if production and parsed.scheme != "https":
        return False
    return True


def status() -> dict:
    return {
        "enabled": enabled(),
        "configured": config_ready(),
        "dependency": dependency_available(),
        "rp_id_configured": bool(rp_id()),
        "origin_configured": bool(origin()),
        "production_requires_https": True,
    }


def new_challenge() -> bytes:
    return secrets.token_bytes(32)


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64u(value: str) -> bytes:
    raw = (value or "").encode("ascii")
    return base64.urlsafe_b64decode(raw + b"=" * ((4 - len(raw) % 4) % 4))


def registration_options(*, user_name: str, user_id: bytes, exclude_ids: list[bytes], challenge: bytes) -> dict:
    if not enabled():
        raise RuntimeError("WebAuthn desativado ou configuração incompleta")
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        PublicKeyCredentialDescriptor,
        ResidentKeyRequirement,
        UserVerificationRequirement,
    )
    options = generate_registration_options(
        rp_id=rp_id(),
        rp_name=os.getenv("WEBAUTHN_RP_NAME", "JARVIS Cyber Platform")[:64],
        user_name=(user_name or "owner")[:254],
        user_id=user_id,
        user_display_name="JARVIS Owner",
        challenge=challenge,
        timeout=60000,
        exclude_credentials=[PublicKeyCredentialDescriptor(id=x) for x in exclude_ids],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    return json.loads(options_to_json(options))


def verify_registration(credential: dict, *, challenge: bytes) -> object:
    if not enabled():
        raise RuntimeError("WebAuthn desativado ou configuração incompleta")
    from webauthn import verify_registration_response
    return verify_registration_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=rp_id(),
        expected_origin=origin(),
        require_user_verification=True,
        require_user_presence=True,
    )


def authentication_options(*, credential_ids: list[bytes], challenge: bytes) -> dict:
    if not enabled():
        raise RuntimeError("WebAuthn desativado ou configuração incompleta")
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers.structs import UserVerificationRequirement
    # Empty allowCredentials enables discoverable passkeys and avoids exposing
    # which credential IDs exist to anonymous clients. The server still binds
    # the returned credential ID to the registered owner credential below.
    options = generate_authentication_options(
        rp_id=rp_id(),
        challenge=challenge,
        timeout=60000,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return json.loads(options_to_json(options))


def verify_authentication(credential: dict, *, challenge: bytes, public_key: bytes, sign_count: int) -> object:
    if not enabled():
        raise RuntimeError("WebAuthn desativado ou configuração incompleta")
    from webauthn import verify_authentication_response
    return verify_authentication_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=rp_id(),
        expected_origin=origin(),
        credential_public_key=public_key,
        credential_current_sign_count=int(sign_count or 0),
        require_user_verification=True,
    )
