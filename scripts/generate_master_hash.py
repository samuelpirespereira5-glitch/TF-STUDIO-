#!/usr/bin/env python3
"""Gera MASTER_PASSWORD_HASH de forma segura e consistente.

Uso:
  python scripts/generate_master_hash.py

Copie a linha impressa para a variável de ambiente MASTER_PASSWORD_HASH
(no Render/Railway/etc use aspas simples se o valor contiver $).

Nunca coloque a senha em texto puro em produção.
"""
import getpass
import sys
from pathlib import Path

# Permite rodar de qualquer diretório
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from werkzeug.security import generate_password_hash
from services.auth import validate_password_strength

pw = getpass.getpass("Senha mestre (mínimo 12 caracteres): ")
ok, msg = validate_password_strength(pw)
if not ok:
    raise SystemExit(msg)

# method="scrypt" explícito = mesmo formato usado por set_master_password
hash_value = generate_password_hash(pw, method="scrypt")
print()
print("# Cole o valor abaixo em MASTER_PASSWORD_HASH (sem aspas extras no painel):")
print(hash_value)
print()
print("# Dica Render/Heroku: se o painel interpretar $, use aspas simples no valor.")
print("# Depois de definir, reinicie o serviço. A senha antiga deixa de valer.")
