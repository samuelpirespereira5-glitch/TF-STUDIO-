# JARVIS — Security Validation + Real WebAuthn

## Objetivo

Esta fase foi tratada como estabilização, não como nova expansão funcional.
O sistema de autenticação existente foi preservado. A antiga implementação de
Passkey que aceitava `publicKey` enviado pelo navegador sem validar a cerimônia
foi substituída por uma cerimônia WebAuthn servidor→browser→servidor com
challenge emitido pelo servidor e verificação delegada à biblioteca
`py_webauthn`.

A biblioteca fornece as rotinas oficiais de geração/verificação de registration
e authentication responses; a aplicação não implementa CBOR/COSE/assinaturas
manualmente.

## Estado atual do Passkey

**WEBAUTHN_ENABLED=false por padrão.**

A ativação foi mantida desligada porque o ambiente de build desta execução não
possui Flask nem `webauthn` instalados. Portanto, a validação criptográfica real
com uma credencial WebAuthn não poderia ser honestamente marcada como PASS.

Para produção, a aplicação exige:

- `WEBAUTHN_ENABLED=true`
- `WEBAUTHN_RP_ID=<host do RP>`
- `WEBAUTHN_ORIGIN=https://<origin exata>`
- dependência `webauthn==3.0.1`

Em produção, a configuração WebAuthn rejeita origin HTTP.

## Implementação realizada

### Registro

1. servidor gera challenge aleatório de 32 bytes;
2. challenge é associado à sessão Flask e expira em 120 segundos;
3. challenge é de uso único (`session.pop` antes da verificação);
4. servidor gera Registration Options;
5. navegador executa `navigator.credentials.create()`;
6. navegador devolve `attestationObject` + `clientDataJSON`;
7. backend valida challenge, origin, RP ID, user presence, user verification,
   formato da resposta e chave pública usando `verify_registration_response()`;
8. somente após a validação a credential é persistida.

### Login

1. servidor gera novo challenge;
2. navegador executa `navigator.credentials.get()`;
3. backend localiza a credential cadastrada pelo `credential ID`;
4. backend valida challenge, origin, RP ID, user presence, user verification,
   assinatura e contador usando `verify_authentication_response()`;
5. credential desconhecida ou resposta inválida é rejeitada;
6. contador é persistido;
7. somente depois da validação a sessão é regenerada pelo sistema existente.

### Proteções

- fail closed;
- mensagens genéricas para autenticação inválida;
- sem private key no servidor;
- sem biometria no servidor;
- sem secrets em logs;
- sessão existente e RBAC existente continuam responsáveis pela autorização;
- rate limiting/CSRF/origin existentes continuam no `before_request`;
- auditoria de início, sucesso e falha de Passkey;
- RP ID e Origin não são escolhidos pelo cliente;
- Passkeys legadas da implementação anterior não são tratadas como credenciais
  criptograficamente validadas.

## Arquivos alterados

- `app.py`
- `services/auth.py`
- `services/webauthn_service.py` (novo)
- `templates/login.html`
- `templates/settings.html`
- `requirements.txt`
- `.env.example`
- `render.yaml`
- `scripts/webauthn_validation.py` (novo)

## Rotas WebAuthn

Existentes e atualizadas:

- `POST /login/webauthn/options`
- `POST /login/webauthn/verify`
- `POST /api/settings/webauthn/register`
- `GET /api/settings/webauthn/list`

Nova rota de ceremony options:

- `POST /api/settings/webauthn/register/options`

Nenhuma rota WebAuthn duplicada foi criada.

## Banco / persistência

Não foi criado um segundo sistema de autenticação.

As credenciais continuam no mecanismo existente `services.auth`.
Foram acrescentados metadados necessários para uma credential WebAuthn validada:

- `user_id`
- `sign_count`
- `verified`
- `created`
- `public_key`

O `webauthn_user_id` é aleatório e estável para a conta do proprietário; não é
calculado a partir do e-mail.

## Dependências

Adicionada:

`webauthn==3.0.1`

Flask continua declarado no `requirements.txt` existente.

A implementação utiliza uma biblioteca especializada para a verificação
criptográfica, em vez de implementar assinatura/CBOR/COSE manualmente.

## Validação executada

| Teste | Status |
|---|---|
| Python compile | PASS |
| Jinja validation | PASS |
| Rotas duplicadas | PASS — 0 |
| final_expansion_check | PASS — 0 errors |
| JavaScript login | PASS |
| JavaScript settings | PASS |
| Challenge criptograficamente aleatório | PASS — revisão estática |
| Expiração do challenge | PASS — revisão estática |
| Challenge single-use | PASS — revisão estática |
| Origin/RP configuráveis | PASS — revisão estática |
| Verificação por biblioteca WebAuthn | PASS — código integrado |
| Assinatura manual | PASS — não implementada |
| Fail closed | PASS — revisão estática |
| Passkey default disabled | PASS |
| Session rotation | PASS — código integrado |
| Sign count persistence | PASS — código integrado |
| Flask runtime | NOT EXECUTED |
| WebAuthn runtime | NOT EXECUTED |
| Teste criptográfico com autenticador real | NOT EXECUTED |
| Teste de replay real | NOT EXECUTED |
| Teste de assinatura inválida real | NOT EXECUTED |

## Motivo dos testes não executados

O ambiente desta execução não possui `Flask`, `Werkzeug` e `webauthn`
instalados. A tentativa de baixar a dependência foi impedida pela ausência de
acesso à rede do ambiente de build.

Isso é reportado como `NOT EXECUTED`, não como PASS.

No Render, `pip install -r requirements.txt` deverá instalar a dependência
antes do boot do serviço.

## Observações de segurança

Os scripts antigos `security_checklist.py` e `check_secrets.py` possuem alguns
falsos positivos porque analisam também textos de desafios educacionais que
contêm exemplos de `shell=True` e credenciais fictícias. Isso não foi tratado
como uma vulnerabilidade de produção sem evidência de execução real.

## Critério para ativação

Não ativar Passkey ainda neste build.

Depois de instalar as dependências no ambiente de execução, executar pelo
menos:

1. runtime Flask;
2. registration real com autenticador;
3. authentication real;
4. assinatura inválida;
5. challenge expirado;
6. replay do challenge;
7. origin incorreta;
8. RP ID incorreto;
9. credential desconhecida;
10. sign-count inconsistente;
11. sessão regenerada após sucesso.

Somente com esses testes passando a variável `WEBAUTHN_ENABLED` deve ser
alterada para `true` e RP ID/Origin configurados para o domínio real.
