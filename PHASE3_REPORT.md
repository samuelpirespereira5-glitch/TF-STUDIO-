# JARVIS Cyber Lab — Terceira Fase

## Preservação
- O fluxo existente de login, Master Password, OWNER, TOTP, tokens, permissões e sessões não foi substituído.
- A autenticação continua server-side: o cookie não é a fonte da role.
- Login bem-sucedido continua rotacionando o identificador server-side.
- `FORCE_REAUTH`, `session_version`, CSRF e rate limit existentes foram preservados.

## Segurança avançada implementada
- Metadados de sessão server-side com expiração absoluta, última atividade e hash do User-Agent.
- Detecção de mudança de navegador/User-Agent e rejeição da sessão.
- Vínculo opcional por prefixo de rede via `SESSION_BIND_IP=1`, evitando quebrar redes móveis por padrão.
- Gerenciamento de sessões ativas no Security Center.
- Revogação individual de sessões e revogação global preservando a sessão atual.
- Auditoria das anomalias/revogações.
- Proxy metadata somente com número de proxies confiáveis.
- CSP aplicada + CSP estrita em Report-Only para preparar migração dos scripts inline sem quebrar a UI atual.
- Headers existentes de HSTS, nosniff, frame/origin isolation, Permissions-Policy e Referrer-Policy preservados.
- Redaction de segredos em respostas/logs preservada.
- Uploads continuam sujeitos à validação de conteúdo e tamanho.

## Central de Ferramentas — Fase 3
Novas ferramentas registradas no Tool Registry:
- Security Headers Analyzer
- Cookie Security Analyzer
- CORS Analyzer
- HTTP Response Analyzer
- TLS/SSL Analyzer
- DNS Analyzer
- IP Information
- Network Configuration Analyzer
- Subnet Calculator
- Packet/Log Analyzer
- robots.txt / sitemap Analyzer
- API Security Checker
- Authentication Configuration Checker
- Log/Security Event Analyzer
- File Hash Analyzer
- Metadata Analyzer
- Dependency Security Checker
- Secrets Detection

As análises textuais trabalham apenas sobre conteúdo fornecido ao laboratório. DNS/TLS reutilizam os guards públicos já existentes. Não há exploração automática contra terceiros.

## CTF / desafios
A Fase 3 adicionou 10 novos laboratórios verificáveis:
- MFA para conta privilegiada
- Rotação após autenticação
- JWT sem algoritmo confiável
- HTTPS com HSTS
- Rate limit de API sensível
- Dependência fixada
- Servidor sem root
- Linha do tempo de incidente
- Integridade por SHA-256
- Upload sem traversal

O catálogo existente da Fase 1/2 já continha laboratórios de XSS, SQLi, IDOR/BOLA, autenticação, sessão, CSRF, CORS, APIs, upload, path traversal, secrets, headers, configuração, logs, incidente, PCAP e reverse engineering, além dos desafios extras.
A Fase 3 reutiliza esse catálogo e a validação automática existente, sem duplicar o sistema de desafios.

## JARVIS / Dashboard
O Security Center agora mostra:
- Security Posture score baseado em verificações reais;
- estado do MFA;
- sessões ativas;
- eventos recentes;
- recomendações;
- estado de controles de segurança.
Nenhum resultado é inventado: o estado é calculado a partir da configuração e dos registros disponíveis.

## Passkeys
O projeto já possui armazenamento de metadados WebAuthn e detecção de credenciais. O login por Passkey continua bloqueado até haver verificação criptográfica WebAuthn completa; isso evita transformar uma credencial enviada pelo navegador em um bypass de senha. Não foi criado um falso fluxo de Passkey.

## Testes executados
1. `compileall` em todo o projeto — PASS.
2. Teste estático da Fase 3 (`scripts/security_phase3_check.py`) — PASS.
3. Validação AST dos arquivos alterados — PASS.
4. Conferência dos IDs das novas ferramentas — PASS.
5. Conferência das novas APIs do Security Center — PASS.
6. Conferência da presença das seções de postura, sessões e eventos — PASS.
7. O teste dinâmico legado `scripts/test_auth_flow.py` foi tentado, mas o ambiente de execução desta sessão não possui `werkzeug` instalado; portanto não foi declarado como PASS.

## Observação importante
A CSP atual ainda precisa de uma futura migração dos handlers/scripts inline para nonce/hash para sair do modo Report-Only e usar uma política estrita sem `unsafe-inline`. Isso foi mantido assim deliberadamente para não quebrar telas existentes nesta fase.
