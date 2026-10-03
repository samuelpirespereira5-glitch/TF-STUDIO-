# Autenticação obrigatória (login primeiro)

## Fluxo garantido

1. Usuário acessa qualquer URL (`/`, `/cyber`, `/jarvis`, `/api/...`, etc.).
2. `@app.before_request` (`_require_login`) verifica sessão válida (`tf_authed` + `tf_ver`).
3. **Sem sessão** → redireciona para `/login` (backend). APIs retornam 401 JSON.
4. Login: e-mail + senha mestre, token de uso único ou Passkey.
5. Se 2FA/TOTP estiver ativo → segundo passo em `/login/2fa`.
6. Só após sucesso a sessão é criada e o dashboard/Jarvis/Cyber Lab é liberado.
7. Logout limpa a sessão e envia headers `no-store` (impede “voltar” do navegador).

## O que NÃO acontece

- Dashboard, ferramentas, Cyber Lab ou dados privados **não** são renderizados antes do login.
- Proteção **não** depende só de JavaScript/frontend.
- Rotas privadas acessadas direto (`/cyber`, `/settings`, `/api/...`) redirecionam ou 401.

## Produção (Render)

Defina obrigatoriamente:

```
SECRET_KEY=<chave longa e estável>
MASTER_PASSWORD_HASH=<hash gerado>
FLASK_ENV=production
PRODUCTION=1
```

Gere o hash:

```bash
python scripts/generate_master_hash.py
```

Remova `FIRST_ACCESS_SETUP=0` se existir (modo aberto legado).

### Ainda entra direto (cookie antigo)?

1. Abra `https://SEU-SITE/logout` uma vez.
2. Ou limpe os dados do site no navegador (cookies de `tf-studio.onrender.com`).
3. Ou, no painel do Render, adicione temporariamente:

```
FORCE_REAUTH=1
```

salve, aguarde o redeploy e **remova** a variável depois (ela só precisa rodar uma vez no boot para invalidar todas as sessões).

Sessão em produção expira em **4 horas** por padrão (`SESSION_HOURS` ajusta).

**Recomendação de segurança:** use só `MASTER_PASSWORD_HASH` (remova `MASTER_PASSWORD` em texto puro do ambiente). Em produção o hash tem prioridade se ambos existirem.

## Reutilização

Sistema de autenticação existente reutilizado (`services/auth.py`, 2FA, Passkey, permissões, session_version). Nenhuma duplicação de login.
