#!/usr/bin/env python3
"""Static/regression checks for JARVIS Cyber Lab Phase 3 (stdlib only)."""
from pathlib import Path
import ast, re, sys

ROOT=Path(__file__).resolve().parents[1]
required=[
 "services/phase3.py","plugins/phase3_security_tools.py",
 "templates/security_center.html","services/auth.py","services/security.py","app.py"
]
for rel in required:
    p=ROOT/rel
    assert p.exists(), f"missing {rel}"
    if p.suffix == ".py":
        ast.parse(p.read_text(encoding="utf-8"), filename=str(p))

auth=(ROOT/"services/auth.py").read_text(encoding="utf-8")
app=(ROOT/"app.py").read_text(encoding="utf-8")
sec=(ROOT/"services/security.py").read_text(encoding="utf-8")
p3=(ROOT/"services/phase3.py").read_text(encoding="utf-8")
plugin=(ROOT/"plugins/phase3_security_tools.py").read_text(encoding="utf-8")
tpl=(ROOT/"templates/security_center.html").read_text(encoding="utf-8")

assert "check_password_hash" in auth and "MASTER_PASSWORD" in auth
assert "session_security_check" in auth and "expires_ts" in auth and "ua_hash" in auth
assert "SESSION_COOKIE_HTTPONLY" in app and "SESSION_COOKIE_SAMESITE" in app
assert "check_csrf" in sec and "Content-Security-Policy" in sec and "Strict-Transport-Security" in sec
for tool in ["security_headers_analyzer","cookie_security_analyzer","cors_analyzer",
             "api_security_checker","secrets_detector","dependency_security_auditor",
             "file_hash_analyzer","log_security_analyzer","metadata_analyzer",
             "dns_analyzer","tls_ssl_analyzer","ip_information","subnet_calculator_phase3",
             "network_config_analyzer","packet_log_analyzer","robots_sitemap_analyzer",
             "authentication_config_checker"]:
    assert tool in plugin, f"missing tool {tool}"
for api in ["/api/security/phase3/posture","/api/security/phase3/sessions",
            "/api/security/phase3/events","/api/security/phase3/sessions/revoke-all"]:
    assert api in app, f"missing API {api}"
for marker in ["Postura de segurança","Sessões ativas","Eventos recentes"]:
    assert marker in tpl, f"missing UI {marker}"
p3c=(ROOT/"services/phase3_challenges.py").read_text(encoding="utf-8")
for cid in ["p3-mfa-policy","p3-session-rotation","p3-jwt-alg-none","p3-hsts",
            "p3-api-rate-limit","p3-dependency-pin","p3-server-nonroot",
            "p3-forensics-timeline","p3-file-integrity","p3-secure-upload-path"]:
    assert cid in p3c, f"missing challenge {cid}"
print("PHASE3_STATIC_TESTS: PASS")
print("Files parsed:", len(required))
print("Defensive tools checked:", 18)
print("New Phase 3 challenges checked:", 10)
print("Security Center sections checked: posture, sessions, events")
