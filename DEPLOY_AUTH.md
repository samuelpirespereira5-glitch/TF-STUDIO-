# Acesso seguro no Render / produção

## Por que a tela de login às vezes não aparece?

1. **Nenhuma senha mestre configurada** → o site leva para `/primeiro-acesso` (só funciona no próprio computador, 127.0.0.1). Crie a senha lá. Depois disso o `/login` passa a aparecer.
2. **Produção sem credencial** → o app recusa iniciar se não houver `MASTER_PASSWORD_HASH`.
3. **FIRST_ACCESS_SETUP=0** → modo aberto antigo (não pede senha). Remova essa variável para forçar autenticação.
4. **Cookie de sessão antigo ainda válido** → o navegador reenvia a sessão. Solução: `/logout`, limpar cookies do site, ou `FORCE_REAUTH=1` no painel (uma vez) e redeploy.

## Configuração recomendada (produção)

1. Escolha uma senha mestre com pelo menos 12 caracteres (frase longa é ótima).
2. Gere o hash localmente (método **scrypt** explícito, mesmo usado em `set_master_password`):

```bash
python scripts/generate_master_hash.py
```

3. No Render (ou similar), defina:

```text
SECRET_KEY=<chave estável longa e aleatória>
MASTER_PASSWORD_HASH=<hash gerado>
FLASK_ENV=production
PRODUCTION=1
```

**Atenção crítica ao `$` no hash:** o valor começa com `scrypt:32768:8:1$...`.  
O caractere `$` é o separador do Werkzeug e **não pode ser cortado**.

No painel do Render / Railway / similar:
1. Cole o hash **completo** (copie a linha inteira gerada pelo script).
2. Preferência: cole **sem aspas**. Se o painel ou o shell interpretar `$`, use aspas simples: `'scrypt:32768:8:1$abc...xyz'`.
3. Confirme no painel que o valor salvo ainda contém o `$` e tem comprimento típico (> 80 caracteres).
4. O backend remove aspas, espaços e escapes `\$` automaticamente, mas **não consegue recuperar um valor truncado**.

Se o login continuar falhando com “Senha ou token inválidos”:
- Verifique os logs do servidor (mensagem `MASTER_PASSWORD_HASH com formato inválido` ou `senha não confere`).
- Regenere o hash e substitua a variável de ambiente.
- Não use `MASTER_PASSWORD` em texto puro. Configure somente `MASTER_PASSWORD_HASH`.
- Reinicie o serviço após alterar as variáveis.

4. Não configure `MASTER_PASSWORD`/`MASTER_PASSWOR`; essas variáveis não são usadas para autenticação.
5. Reinicie o serviço.
6. Se o navegador ainda abrir o painel sem pedir senha: defina `FORCE_REAUTH=1`,
   redeploy, depois **remova** a variável. Isso invalida todas as sessões antigas.

### Diagnóstico rápido se o login falhar

- Confirme que `MASTER_PASSWORD_HASH` está definido e começa com `scrypt:` ou `pbkdf2:`.
- Logs do servidor mostram aviso se o hash tiver formato inválido (sem vazar o valor).
- Rode o teste automatizado localmente: `python scripts/test_auth_flow.py`
- Checklist estática: `python scripts/security_checklist.py`

## O que já está implementado

- Senha mestre com hash (werkzeug / pbkdf2)
- Em produção: somente `MASTER_PASSWORD_HASH` é aceito
- E-mail do proprietário (campo no login, armazenado para identificação)
- 2FA TOTP + códigos de recuperação de uso único
- Passkey / WebAuthn (login pela tela de entrada; cadastro após login em Configurações)
- Sessões: cookies HttpOnly + Secure + SameSite=Lax (e __Host- em HTTPS)
- Sessão em produção: 4h por padrão (`SESSION_HOURS`)
- Proteção contra brute-force (bloqueio progressivo por IP)
- Logout de todos os dispositivos (session_version / FORCE_REAUTH)
- Master Password validada só no backend
- Permissões por papel (owner / admin / user / guest) no backend
- Reautenticação com senha atual ao trocar a senha mestre
- Nenhuma senha em texto puro no frontend; funções admin não dependem só de JS

## Recuperação de conta

- Códigos de recuperação do 2FA (mostrados uma vez ao ativar o TOTP)
- Em emergência local: apague `auth.json` e reinicie → volta a tela de criar senha
- Em produção: não use uma senha em texto puro como mecanismo de recuperação; configure um novo `MASTER_PASSWORD_HASH` e reinicie

Nunca coloque a senha mestre, API keys ou `SECRET_KEY` no Git.
