"""Desafios adicionais da Terceira Fase — somente laboratório textual."""
from services.cyber_challenges import _challenge

CHALLENGES = [
_challenge("p3-mfa-policy","MFA para conta privilegiada","auth-fraca","intermediário",200,
 "Exija um segundo fator antes de concluir o login do proprietário.",
 "O fluxo libera a sessão logo depois da senha.",
 """<pre>
if verify_password(password):
    session["authenticated"] = True
    return redirect("/dashboard")
# tarefa: inserir etapa MFA antes de criar a sessão autenticada
</pre>""",
 required=(("MFA verificado antes da sessão",r"(verify_totp|verify_mfa|webauthn|second.factor|2fa)"),),
 forbidden=(("não liberar sessão só com senha",r'session\[[^]]*authenticated[^]]*\]\s*=\s*true\s*[\s\S]{0,80}return\s+redirect'),),
 hints=("Senha e segundo fator são etapas diferentes.","A sessão autenticada só deve nascer depois das duas verificações."),
 explanation="MFA reduz o impacto de uma senha comprometida.",
 solution="Valide o segundo fator e somente então crie/eleve a sessão autenticada."),

_challenge("p3-session-rotation","Rotação após autenticação","sessao","intermediário",200,
 "Evite session fixation trocando o identificador após o login.",
 "O laboratório reaproveita o mesmo identificador de sessão antes e depois da autenticação.",
 """<pre>
def login(user):
    if check_password(user.password):
        session["uid"] = user.id
        session["authenticated"] = True
# tarefa: renovar/rotacionar a sessão aqui
</pre>""",
 required=(("rotacionar sessão",r"(regenerate|rotate|renew|session\.clear|new_session|cycle)"),),
 hints=("O estado pré-login não deve sobreviver ao login privilegiado.","Crie um novo identificador server-side."),
 explanation="Session fixation ocorre quando um atacante consegue influenciar o identificador usado depois da autenticação.",
 solution="Invalide a sessão anterior e gere um novo identificador server-side ao autenticar."),

_challenge("p3-jwt-alg-none","JWT sem algoritmo confiável","jwt","avançado",300,
 "Valide o algoritmo permitido no servidor e rejeite tokens com algoritmo inesperado.",
 "O laboratório confia no campo alg do próprio token.",
 """<pre>
header = decode_header(token)
if header["alg"] == token_algorithm:
    return accept(token)
# tarefa: definir allowlist de algoritmos e verificar assinatura
</pre>""",
 required=(("allowlist de algoritmo",r"(allowed_algorithms|algorithms\s*=|algorithm_allowlist|RS256|ES256)"),
            ("verificação de assinatura",r"(verify|signature|decode\()")),
 forbidden=(("não confiar no alg do token",r"header\[[\"']alg[\"']\]\s*==\s*token_algorithm"),),
 hints=("O token é controlado pelo cliente.","A política criptográfica deve vir do servidor."),
 explanation="Confiar no algoritmo declarado pelo token pode permitir aceitar tokens sem a garantia criptográfica esperada.",
 solution="Defina explicitamente os algoritmos aceitos e valide a assinatura com a chave correta."),

_challenge("p3-hsts","HTTPS com HSTS","headers","iniciante",100,
 "Adicione HSTS somente ao serviço HTTPS.",
 "A resposta não informa ao navegador para preferir HTTPS.",
 """<pre>
HTTP/1.1 200 OK
Content-Type: text/html
# tarefa: adicionar Strict-Transport-Security em HTTPS
</pre>""",
 required=(("HSTS presente",r"strict-transport-security"),),
 hints=("HSTS é um header de resposta.","Não use HSTS para sites que ainda dependem de HTTP."),
 explanation="HSTS reduz downgrade e acesso acidental por HTTP após a política ser aprendida pelo navegador.",
 solution="Em HTTPS, envie Strict-Transport-Security com max-age apropriado."),

_challenge("p3-api-rate-limit","Rate limit de API sensível","api-insegura","intermediário",200,
 "Limite tentativas de uma operação sensível.",
 "O endpoint aceita requisições ilimitadas.",
 """<pre>
@app.post("/api/login")
def login():
    verify(request.json)
    return {"ok": True}
# tarefa: aplicar rate limit e resposta segura
</pre>""",
 required=(("rate limit",r"(rate_limit|ratelimit|throttle|limiter|retry_after)"),),
 hints=("Limite deve ser aplicado no servidor.","Considere IP, identidade e janela de tempo."),
 explanation="Rate limiting reduz abuso automatizado e protege endpoints de autenticação e operações caras.",
 solution="Aplique um limitador server-side com janela, chave adequada e Retry-After quando apropriado."),

_challenge("p3-dependency-pin","Dependência fixada","config","iniciante",100,
 "Fixe a versão da dependência e mantenha auditoria de vulnerabilidades.",
 "A aplicação instala sempre a versão mais recente.",
 """<pre>
Flask
requests
# tarefa: fixar versões compatíveis e auditar dependências
</pre>""",
 required=(("versão fixada",r"[A-Za-z0-9_.-]+\s*(==|>=\s*\d+\.\d+)"),),
 forbidden=(("linhas sem versão",r"(?m)^(Flask|requests)\s*$"),),
 hints=("Reprodutibilidade importa.","Depois de fixar, use um auditor de dependências."),
 explanation="Versões não fixadas dificultam reproduzir builds e controlar mudanças.",
 solution="Fixe versões testadas e execute pip-audit regularmente."),

_challenge("p3-server-nonroot","Servidor sem root","config","iniciante",100,
 "Execute o serviço com usuário sem privilégios.",
 "O processo do laboratório inicia como root.",
 """<pre>
USER root
CMD ["python","app.py"]
# tarefa: usar usuário dedicado sem privilégios
</pre>""",
 required=(("usuário não-root",r"(?m)^user\s+(?!root)\w+"),),
 forbidden=(("remover USER root",r"(?m)^user\s+root"),),
 hints=("Crie um usuário dedicado.","O processo não precisa de privilégios de root para servir HTTP."),
 explanation="Menos privilégios reduzem o impacto de uma exploração.",
 solution="Crie um usuário dedicado e use USER antes do CMD."),

_challenge("p3-forensics-timeline","Linha do tempo de incidente","logs","intermediário",200,
 "Identifique a sequência temporal de eventos e o primeiro acesso suspeito.",
 "O log contém eventos em ordem misturada.",
 """<pre>
10:04:10 login OK user=ana
10:04:02 FAIL user=admin ip=203.0.113.9
10:04:08 file_changed path=/srv/app.py
10:04:05 FAIL user=admin ip=203.0.113.9
# tarefa: ordenar por horário e identificar a sequência
</pre>""",
 required=(("linha do tempo",r"(10:04:02.*10:04:05|10:04:05.*10:04:08|timeline|ordem cronológica)"),),
 hints=("Compare os horários.","Relacione falhas de login com alterações de arquivo."),
 explanation="Timeline é uma técnica básica de forense para reconstruir o que aconteceu.",
 solution="Ordene os eventos por timestamp e destaque a cadeia de falhas e mudança de arquivo."),

_challenge("p3-file-integrity","Integridade por SHA-256","reverse","iniciante",100,
 "Verifique se o hash do arquivo corresponde ao valor esperado.",
 "O laboratório compara um hash fornecido sem especificar o algoritmo.",
 """<pre>
expected = "..."
actual = hash_file(path)
# tarefa: usar SHA-256 e comparar em hexadecimal
</pre>""",
 required=(("SHA-256",r"(sha256|SHA-256|hashlib\.sha256)"),("comparação",r"(compare|==|compare_digest)")),
 hints=("Hash identifica o conteúdo, não prova quem criou o arquivo.","Use SHA-256 e compare valores completos."),
 explanation="Verificação de integridade detecta alterações acidentais ou não autorizadas.",
 solution="Calcule SHA-256 do arquivo e compare com uma referência confiável."),

_challenge("p3-secure-upload-path","Upload sem traversal","upload","intermediário",200,
 "Impeça que o nome do arquivo controle um caminho fora do diretório de uploads.",
 "O código concatena o nome enviado pelo cliente ao diretório.",
 """<pre>
filename = request.files["file"].filename
path = "/srv/uploads/" + filename
save(path)
# tarefa: normalizar e garantir que o destino permaneça dentro do diretório
</pre>""",
 required=(("nome seguro ou resolução dentro do root",r"(secure_filename|resolve\(|commonpath|safe_join)"),),
 forbidden=(("remover concatenação insegura",r"[\"']/srv/uploads/[\"']\s*\+\s*filename"),),
 hints=("O nome é controlado pelo cliente.","Valide o caminho final contra o diretório permitido."),
 explanation="Path traversal pode escapar do diretório destinado a uploads.",
 solution="Use secure_filename/safe_join e valide o caminho resolvido dentro do root."),

]
