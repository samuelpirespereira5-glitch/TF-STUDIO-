# JARVIS — Security Phase 2 Report (Auditoria + Hardening)

**Data:** 2026-10-01  
**Escopo:** Master Password, Owner/Identity, Login hardening, Route protection, Auditoria geral.  
**Princípio:** Não quebrar o que já funciona. Correções cirúrgicas. Sem backdoors.

---

## 1. MASTER PASSWORD

### Problema
Hash da senha mestre às vezes não era reconhecido (mensagem: "Senha ou token inválidos...").

| Campo | Detalhe |
|-------|---------|
| **Arquivo/rota** | `services/auth.py` (`check_master_password`, `set_master_password`), `scripts/generate_master_hash.py` |
| **Severidade** | Alta (impede acesso legítimo do owner) |
| **Causa** | (1) Método de hash implícito podia variar entre versões do Werkzeug; (2) hashes colados no painel de env com aspas extras ou espaços; (3) comparação sem normalização do valor de `MASTER_PASSWORD_HASH`. |
| **Correção aplicada** | - `set_master_password` e o script de geração usam **explicitamente** `method="scrypt"`. <br>- `check_master_password` normaliza o hash (strip + remove aspas acidentais) e trata formatos inválidos sem vazar informação. <br>- Mantida compatibilidade com hashes antigos (pbkdf2/scrypt). <br>- Nunca se tenta "descriptografar" o hash; só `check_password_hash`. |
| **Teste** | Round-trip: gerar hash com `generate_password_hash(..., method="scrypt")` → `check_password_hash` aceita a senha correta e rejeita a errada. Script `scripts/security_checklist.py` cobre o caso. |

**Mensagens de erro:** Continuam genéricas ("Senha ou token inválidos...") — não revelam se o e-mail existe ou qual fator falhou.

**Fluxo de alteração:** Já existia (exige senha atual + valida força + bump de `session_version`). Mantido.

---

## 2. DONO / OWNER

### Problema
`current_role()` fazia fallback para `"owner"` quando `tf_role` estava ausente na sessão.

| Campo | Detalhe |
|-------|---------|
| **Arquivo** | `services/permissions.py` |
| **Severidade** | Alta (elevação de privilégio se sessão parcial) |
| **Causa** | `session.get("tf_role", "owner")` — default permissivo. |
| **Correção** | Default removido. Só retorna `"owner"` se a sessão tiver explicitamente `tf_role == "owner"` (definido **somente** no backend após `check_master_password` bem-sucedido). Qualquer valor desconhecido → `"user"`. |
| **Teste** | Checklist estática verifica ausência do default perigoso. Login com senha mestre continua setando `tf_role="owner"` + `tf_uid="owner"`. |

**Garantias mantidas/reforçadas:**
- Usuário tem `tf_uid` único (`"owner"` ou `"key:<id>"`).
- Role armazenada só no servidor (sessão assinada).
- Frontend **nunca** envia role; APIs usam `require_cap` / `enforce_path` em **toda** requisição.
- Alteração de role/owner pelo usuário: impossível (não existe endpoint que aceite role do cliente).
- Ações críticas (troca de senha mestre) exigem reautenticação (senha atual).
- Ações administrativas registradas em `access_log` + `audit_event`.

---

## 3. LOGIN MAIS SEGURO

Já existia boa base (rate-limit, CSRF, cookies, headers). Complementos:

| Item | Status |
|------|--------|
| Rate limiting / brute-force | Já: 8 tentativas / 5 min → lockout escalonado até 24h |
| Sessões seguras | HttpOnly + Secure + SameSite=Lax + `__Host-` em HTTPS |
| Rotação de sessão após login | `session.clear()` + novos flags em todo caminho de login |
| **Expiração por inatividade** | **NOVO:** `SESSION_IDLE_MINUTES` (padrão 30 em produção). Verifica `tf_last_activity` no `before_request` |
| Logout global | Já: `bump_session_version()` encerra todas as sessões |
| CSRF | Token por sessão + Origin/Referer |
| Cookies | Já configurados corretamente |
| Headers de segurança | Já em `security.apply_security_headers` |
| Validação rigorosa | Limites de tamanho de senha/token; `safe_next_url` |
| Mensagens genéricas | Mantidas |
| 2FA/TOTP + Passkey | Já implementados |
| Recuperação | Tokens de uso único + códigos TOTP de recuperação + instruções de emergência via env |

---

## 4. PROTEÇÃO DAS ROTAS

- `@app.before_request` `_require_login` bloqueia **tudo** que não está em `PUBLIC_ENDPOINTS` se não houver sessão válida.
- `permissions.enforce_path()` aplica `PATH_CAPS` (prefixo → capability) em **toda** requisição autenticada.
- `require_cap` decorator nas rotas admin.
- Testes manuais recomendados (checklist abaixo).

**Checklist de teste (executar após deploy):**

1. Acesso sem login → `/`, `/cyber`, `/api/cyber/...` → redirect 302 para `/login` ou 401 JSON.
2. Usuário com role_key `user` tentando `/api/admin` ou `/cyber` → 403.
3. Tentar enviar `tf_role=owner` no form/cookie → ignorado (servidor não lê role do cliente).
4. Chamar API diretamente com cookie de sessão expirada / versão antiga → 401/redirect.
5. Logout + botão Voltar → páginas privadas não reaparecem (Cache-Control no-store + sessão limpa).
6. Múltiplas abas: `bump_session_version` (troca de senha / "encerrar todas") invalida as outras.
7. Alteração de credenciais → exige senha atual; demais sessões caem.

---

## 5. AUDITORIA GERAL (resumo)

| Categoria | Resultado |
|-----------|-----------|
| XSS | Templates Jinja escapam por padrão; JS usa função `esc()` em innerHTML dinâmico. CSP ainda permite `unsafe-inline` (limitação conhecida da UI atual). |
| CSRF | Token + Origin. |
| SQL Injection | Sem SQL clássico (JSON files). |
| Command injection | `tool_adapter` força `shell=False` + argv lista. |
| SSRF | Escopo de alvos autorizados + validação em ferramentas de rede. |
| Path traversal | Paths controlados; uploads validados. |
| Upload inseguro | `validate_image_upload` (tipo real, tamanho). |
| Exposição de secrets | Chaves de API não vão mais para o HTML (hardening anterior). `check_secrets.py` existe. |
| Permissões | Backend-only; default owner removido. |
| Sessão | Melhorada com idle timeout. |
| APIs sem autorização | Cobertas pelo before_request + PATH_CAPS. |
| Dependências | `requirements.txt` mínimo; `pip-audit` listado. |
| Vazamento de info | Mensagens de login genéricas; `auth_config_state` não vaza hash/senha. |

**Nenhum backdoor ou bypass de autenticação foi introduzido.**

---

## 6. TESTE FINAL

Script criado: `scripts/security_checklist.py`

```bash
python scripts/security_checklist.py
```

Cobre: shell=True, hashing round-trip, default de role, flags de cookie/sessão, CSRF, lockout, segredos no repo, permissões de auth.json, endpoints públicos.

---

## Arquivos alterados nesta fase

- `services/auth.py` — hashing explícito + normalização do hash de env
- `services/permissions.py` — remoção do default `"owner"`
- `app.py` — idle timeout + `tf_last_activity` em todos os logins
- `scripts/generate_master_hash.py` — method scrypt + instruções de deploy
- `scripts/security_checklist.py` — **novo**
- `.env.example` — `SESSION_IDLE_MINUTES`

---

## Como recuperar acesso se o hash continuar falhando

1. No painel do host, **remova** temporariamente `MASTER_PASSWORD_HASH`.
2. Defina `MASTER_PASSWORD=<sua-senha-forte>` (texto puro) **ou** regenere o hash com:
   ```bash
   python scripts/generate_master_hash.py
   ```
   e cole o valor **sem aspas extras**.
3. Reinicie o serviço.
4. Entre e, em Configurações, troque a senha (grava no `auth.json` e permite remover a env var depois).
5. Em emergência local: apague `data/auth.json` e acesse `/primeiro-acesso` **somente de 127.0.0.1**.
