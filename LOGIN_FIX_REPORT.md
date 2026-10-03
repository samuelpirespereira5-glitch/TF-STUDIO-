# Correção completa do Login — JARVIS v34

## Escopo desta versão
Somente autenticação/autorização e testes foram corrigidos. A expansão de novas ferramentas e desafios foi propositalmente adiada até o fluxo de login passar pelos testes.

## Correções principais
- MASTER_PASSWORD_HASH é a única credencial de ambiente aceita para autenticação. MASTER_PASSWORD não autentica.
- Criação e validação usam Werkzeug com `scrypt` explícito.
- Hash nunca é descriptografado nem comparado manualmente.
- Sessão autenticada recebe um SID aleatório e sua identidade/role ficam registradas no backend (`auth.json` como hash do SID).
- Role/OWNER no frontend não é fonte de autorização.
- Rotação de SID após autenticação e após reautenticação/troca de senha.
- Logout revoga o SID no backend.
- `session_version` continua permitindo derrubar todas as sessões.
- Modo aberto/local legado removido: sem credencial, áreas privadas redirecionam para primeiro acesso.
- Passkey/WebAuthn falsa foi retirada do caminho de login; o código anterior só verificava challenge/ID e poderia virar bypass.
- APIs e páginas privadas continuam protegidas pelo middleware + capacidades backend.
- Testes incluem hash, configuração, login/logout, sessão adulterada, SID falso e usuário comum tentando API administrativa.

## Observação sobre execução dos testes
A análise foi feita sobre o ZIP enviado. O ambiente de execução desta sessão não possui as dependências Python do projeto e não tem acesso à internet para instalá-las; portanto o teste Flask completo não pôde ser executado aqui. A sintaxe Python dos arquivos alterados foi validada com `py_compile` e o ZIP foi validado com `unzip -t`. O script `scripts/test_auth_flow.py` foi atualizado para executar no ambiente do projeto/produção e a limitação foi registrada em vez de afirmar que os testes passaram.
