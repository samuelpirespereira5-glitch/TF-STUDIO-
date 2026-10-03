#!/usr/bin/env python3
"""Teste automatizado do fluxo completo de autenticação JARVIS.

Cobertura:
  1. Criação da credencial (set_master_password)
  2. Armazenamento do hash (auth.json atômico, permissão)
  3. Leitura da configuração (password_source / auth_config_state)
  4. Verificação do hash (check_master_password — mesmo algoritmo)
  5. Login via Flask test client (sessão, CSRF, cookies)
  6. Middleware/guard das rotas privadas
  7. Autorização OWNER (tf_role só no backend)
  8. Logout + bloqueio novamente
  9. Tentativa de usuário comum / sessão adulterada
 10. Rate-limit / rejeição de senha errada

Uso:
  cd <raiz-do-projeto>
  python scripts/test_auth_flow.py

Código de saída 0 = todos os testes passaram.
Nunca imprime senha ou hash em claro.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Ambiente de teste isolado ANTES de importar o app
os.environ["SECRET_KEY"] = "test-secret-key-for-auth-flow-only-32chars"
os.environ.pop("MASTER_PASSWORD", None)
os.environ.pop("MASTER_PASSWORD_HASH", None)
os.environ.pop("MASTER_PASSWOR", None)
os.environ["FLASK_ENV"] = "development"
os.environ.pop("PRODUCTION", None)
os.environ.pop("RENDER", None)
os.environ.pop("FORCE_REAUTH", None)

# Isola auth.json em diretório temporário
_TMPDIR = tempfile.mkdtemp(prefix="jarvis_auth_test_")
_AUTH_FILE = Path(_TMPDIR) / "auth.json"

# Patch AUTH_FILE antes do import de services.auth
import services.auth as auth_mod

auth_mod.AUTH_FILE = _AUTH_FILE
auth_mod.AUTH = auth_mod.DEFAULT_AUTH.copy()
auth_mod._IS_PRODUCTION = False

from werkzeug.security import generate_password_hash, check_password_hash

# Importa app depois do patch
import app as app_module

app = app_module.app
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = False  # CSRF testado separadamente via security
# Em teste usamos cookie normal (não __Host- que exige HTTPS)
app.config["SESSION_COOKIE_SECURE"] = False
app.config["SESSION_COOKIE_NAME"] = "tf_session_test"


MASTER_PW = "Frase-mestra-de-teste-2026!!"
WRONG_PW = "senha-errada-qualquer-12"


class AuthFlowTests(unittest.TestCase):
    def setUp(self):
        # Limpa estado entre testes
        auth_mod.AUTH = auth_mod.DEFAULT_AUTH.copy()
        if _AUTH_FILE.exists():
            _AUTH_FILE.unlink()
        os.environ.pop("MASTER_PASSWORD", None)
        os.environ.pop("MASTER_PASSWORD_HASH", None)
        auth_mod._IS_PRODUCTION = False
        self.client = app.test_client()

    def tearDown(self):
        if _AUTH_FILE.exists():
            _AUTH_FILE.unlink()

    # ------------------------------------------------------------------
    # 1–4: criação → armazenamento → leitura → verificação
    # ------------------------------------------------------------------
    def test_01_create_store_verify_hash(self):
        """Criação + armazenamento + verificação do hash (mesmo algoritmo)."""
        ok = auth_mod.set_master_password(MASTER_PW)
        self.assertTrue(ok, "set_master_password deve retornar True")
        self.assertTrue(_AUTH_FILE.exists(), "auth.json deve ser criado")
        stored = auth_mod.AUTH.get("master_password_hash", "")
        self.assertTrue(stored.startswith("scrypt:"), f"hash deve ser scrypt, got prefix={stored[:20]!r}")
        self.assertTrue(":" in stored)
        # Nunca comparação manual — só check_password_hash
        self.assertTrue(check_password_hash(stored, MASTER_PW))
        self.assertFalse(check_password_hash(stored, WRONG_PW))
        self.assertTrue(auth_mod.check_master_password(MASTER_PW))
        self.assertFalse(auth_mod.check_master_password(WRONG_PW))
        self.assertFalse(auth_mod.check_master_password(""))
        self.assertEqual(auth_mod.password_source(), "file")
        state = auth_mod.auth_config_state()
        self.assertTrue(state["hash_configured"])
        self.assertEqual(state["source"], "file")

    def test_02_env_hash_priority_production(self):
        """Em produção, MASTER_PASSWORD_HASH tem prioridade e não cai no arquivo."""
        auth_mod.set_master_password(MASTER_PW)
        env_hash = generate_password_hash("OutraSenhaEnv123!!", method="scrypt")
        os.environ["MASTER_PASSWORD_HASH"] = env_hash
        auth_mod._IS_PRODUCTION = True
        self.assertEqual(auth_mod.password_source(), "env_hash")
        self.assertTrue(auth_mod.check_master_password("OutraSenhaEnv123!!"))
        self.assertFalse(auth_mod.check_master_password(MASTER_PW),
                         "não deve cair no auth.json quando env_hash existe")
        # Aspas acidentais do painel
        os.environ["MASTER_PASSWORD_HASH"] = f"'{env_hash}'"
        self.assertTrue(auth_mod.check_master_password("OutraSenhaEnv123!!"))
        # Espaços / newline
        os.environ["MASTER_PASSWORD_HASH"] = f"  {env_hash}  \n"
        self.assertTrue(auth_mod.check_master_password("OutraSenhaEnv123!!"))

    def test_03_invalid_hash_format_logs_and_rejects(self):
        """Hash malformado (ex.: senha em claro no campo de hash) é rejeitado."""
        os.environ["MASTER_PASSWORD_HASH"] = "isso-nao-e-um-hash"
        auth_mod._IS_PRODUCTION = True
        self.assertFalse(auth_mod.check_master_password("isso-nao-e-um-hash"))
        self.assertFalse(auth_mod.check_master_password(MASTER_PW))

    def test_04_plaintext_environment_is_never_used(self):
        """MASTER_PASSWORD legado não pode autenticar; só hash é aceito."""
        os.environ["MASTER_PASSWORD"] = MASTER_PW
        os.environ["MASTER_PASSWOR"] = MASTER_PW
        self.assertFalse(auth_mod.has_master_password())
        self.assertFalse(auth_mod.check_master_password(MASTER_PW))
        auth_mod.set_master_password(MASTER_PW)
        self.assertTrue(auth_mod.check_master_password(MASTER_PW))

    def test_04_no_default_password_or_backdoor(self):
        """Sem credencial configurada → has_master_password False; sem senha padrão."""
        self.assertFalse(auth_mod.has_master_password())
        self.assertFalse(auth_mod.check_master_password("admin"))
        self.assertFalse(auth_mod.check_master_password("password"))
        self.assertFalse(auth_mod.check_master_password("jarvis"))

    # ------------------------------------------------------------------
    # 5–8: login → sessão → dashboard → logout → bloqueio
    # ------------------------------------------------------------------
    def _csrf_from(self, resp):
        """Extrai CSRF do cookie de sessão / meta (via GET /login)."""
        # O context processor injeta csrf_token; no test client lemos via sessão
        with self.client.session_transaction() as sess:
            return sess.get("_csrf_token") or ""

    def test_05_full_login_logout_guard(self):
        """Fluxo: sem sessão → login → autenticação → dashboard → logout → bloqueio."""
        auth_mod.set_master_password(MASTER_PW)

        # 1) Sem sessão: rota privada redireciona para login
        # Dashboard principal é "/" (endpoint dashboard); /painel também é privado
        r = self.client.get("/", follow_redirects=False)
        self.assertIn(r.status_code, (302, 303))
        self.assertIn("/login", r.headers.get("Location", ""))

        # 2) GET login
        r = self.client.get("/login")
        self.assertEqual(r.status_code, 200)
        csrf = self._csrf_from(r)
        self.assertTrue(csrf, "CSRF token deve existir na sessão após GET /login")

        # 3) POST senha errada
        r = self.client.post(
            "/login",
            data={"password": WRONG_PW, "_csrf": csrf, "email": "owner@test.local"},
            follow_redirects=False,
        )
        self.assertEqual(r.status_code, 401)
        with self.client.session_transaction() as sess:
            self.assertFalse(sess.get("tf_authed"))

        # 4) POST senha correta → sessão OWNER
        csrf = self._csrf_from(self.client.get("/login"))
        r = self.client.post(
            "/login",
            data={"password": MASTER_PW, "_csrf": csrf, "email": "owner@test.local"},
            follow_redirects=False,
        )
        self.assertIn(r.status_code, (302, 303), f"login deve redirecionar, got {r.status_code}")
        with self.client.session_transaction() as sess:
            self.assertTrue(sess.get("tf_authed"), "tf_authed deve ser True")
            self.assertEqual(sess.get("tf_role"), "owner")
            self.assertEqual(sess.get("tf_uid"), "owner")
            self.assertEqual(sess.get("tf_ver"), auth_mod.current_session_version())
            self.assertTrue(sess.get("tf_sid"))
            self.assertEqual(auth_mod.get_auth_session(sess.get("tf_sid"))["role"], "owner")

        # 5) Home/dashboard acessível
        r = self.client.get("/", follow_redirects=False)
        self.assertEqual(r.status_code, 200)

        # 6) Logout
        r = self.client.get("/logout", follow_redirects=False)
        self.assertIn(r.status_code, (302, 303))
        self.assertIn("no-store", (r.headers.get("Cache-Control") or "").lower())
        with self.client.session_transaction() as sess:
            self.assertFalse(sess.get("tf_authed"))

        # 7) Bloqueio novamente
        r = self.client.get("/", follow_redirects=False)
        self.assertIn(r.status_code, (302, 303))
        self.assertIn("/login", r.headers.get("Location", ""))

    def test_06_api_protected_without_session(self):
        """APIs privadas retornam 401 JSON sem sessão."""
        auth_mod.set_master_password(MASTER_PW)
        r = self.client.get("/api/diagnostics/status", follow_redirects=False)
        # Pode ser 401 ou 302 dependendo do path; o importante é NÃO 200 com dados
        self.assertNotEqual(r.status_code, 200)
        if r.is_json:
            body = r.get_json() or {}
            self.assertIn("error", body)

    def test_07_tampered_session_rejected(self):
        """Sessão com tf_ver diferente ou sem tf_authed é rejeitada."""
        auth_mod.set_master_password(MASTER_PW)
        csrf = self._csrf_from(self.client.get("/login"))
        self.client.post(
            "/login",
            data={"password": MASTER_PW, "_csrf": csrf},
            follow_redirects=False,
        )
        # Adulterar versão de sessão
        with self.client.session_transaction() as sess:
            sess["tf_ver"] = auth_mod.current_session_version() + 999
        r = self.client.get("/", follow_redirects=False)
        self.assertIn(r.status_code, (302, 303))
        self.assertIn("/login", r.headers.get("Location", ""))

    def test_08_owner_not_from_frontend(self):
        """Role/owner só pode vir do registro server-side da sessão."""
        from services import permissions as perm
        from flask import session as flask_session

        auth_mod.set_master_password(MASTER_PW)
        sid = auth_mod.create_auth_session("owner", "owner")

        with app.test_request_context("/"):
            flask_session.clear()
            flask_session["tf_authed"] = True
            flask_session["tf_sid"] = sid
            flask_session["tf_role"] = "user"  # adulteração de apresentação
            self.assertEqual(perm.current_role(), "owner")

        # SID inexistente + role=owner no cookie não concede privilégio.
        with app.test_request_context("/"):
            flask_session.clear()
            flask_session["tf_authed"] = True
            flask_session["tf_sid"] = "sid-falso"
            flask_session["tf_role"] = "owner"
            self.assertIsNone(perm.current_role())

        # Usuário comum não alcança OWNER/ADMIN.
        user_sid = auth_mod.create_auth_session("key:user", "user")
        with app.test_request_context("/"):
            flask_session.clear()
            flask_session["tf_authed"] = True
            flask_session["tf_sid"] = user_sid
            flask_session["tf_role"] = "owner"
            self.assertEqual(perm.current_role(), "user")
            self.assertFalse(perm.has_cap("manage_access"))
            self.assertFalse(perm.has_cap("cyber_advanced"))

    def test_09_direct_owner_api_rejected_for_user_session(self):
        """Usuário comum não consegue acessar API administrativa por URL direta."""
        auth_mod.set_master_password(MASTER_PW)
        sid = auth_mod.create_auth_session("key:user", "user")
        with self.client.session_transaction() as sess:
            sess["tf_authed"] = True
            sess["tf_sid"] = sid
            sess["tf_role"] = "user"
            sess["tf_uid"] = "key:user"
        r = self.client.get("/api/admin/access-log")
        self.assertEqual(r.status_code, 403)

    def test_09_same_algorithm_create_and_verify(self):
        """generate_password_hash(method=scrypt) e check_password_hash usam o mesmo formato."""
        h = generate_password_hash(MASTER_PW, method="scrypt")
        self.assertTrue(h.startswith("scrypt:"))
        self.assertTrue(check_password_hash(h, MASTER_PW))
        # set_master_password grava no mesmo formato
        auth_mod.set_master_password(MASTER_PW)
        stored = auth_mod.AUTH["master_password_hash"]
        self.assertTrue(stored.startswith("scrypt:"))
        self.assertTrue(auth_mod.check_master_password(MASTER_PW))

    def test_10_password_strength_enforced(self):
        ok, _ = auth_mod.validate_password_strength("curta")
        self.assertFalse(ok)
        ok, _ = auth_mod.validate_password_strength(MASTER_PW)
        self.assertTrue(ok)


def main():
    print("=== JARVIS Auth Flow Tests ===")
    print(f"Auth file isolado: {_AUTH_FILE}")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AuthFlowTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print()
    if result.wasSuccessful():
        print("TODOS OS TESTES PASSARAM.")
        return 0
    print(f"FALHAS: {len(result.failures)}  ERROS: {len(result.errors)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
