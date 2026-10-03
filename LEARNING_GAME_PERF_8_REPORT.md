# JARVIS Learning + Game Studio + Performance 8.0

## Escopo
Expansão incremental sobre Programming Universe 7.0. O projeto não foi reescrito e as rotas/APIs existentes foram preservadas.

## 1. Learning Engine 8.0
- Nova `services/learning8.py` com 8 trilhas progressivas.
- Aulas estruturadas com introdução, conceito, exemplo, linha explicada, experimento, exercício, desafio, erros comuns, extra e mini projeto.
- Níveis de explicação: CRIANÇA, INICIANTE, INTERMEDIÁRIO e AVANÇADO.
- Progresso persistido no mesmo banco da aplicação.
- XP, conteúdos concluídos e erros frequentes.
- Recomendação baseada em pré-requisitos e no que já foi concluído.
- Busca educacional.
- Desafio diário.
- Modos: jogar, aulas, programar, experimentar e criar projetos.
- O módulo evita recomendar novamente uma aula já concluída quando existem próximos conteúdos desbloqueados.

## 2. Chat/JARVIS 8.0
- Mantida a rota `/api/jarvis` existente.
- Frontend mantém bloqueio contra envio duplicado.
- Enter continua enviando; composição/teclados móveis são respeitados.
- Timeout de 90 segundos para evitar loading infinito.
- AbortController continua permitindo cancelamento.
- O request agora recebe contexto de interface: Game Lab, Programming/Aula/IDE, Editor, Segurança defensiva ou Geral.
- Backend injeta instruções contextuais no mesmo sistema de IA, sem criar outro chat.
- Resposta inclui `request_id`, `elapsed_ms` e `context` para diagnóstico.
- HUD mostra conclusão e tempo da requisição.
- Erro de resposta vazia agora é tratado explicitamente.

## 3. Game Lab 8.0
- Mantida a engine existente e seu ciclo MENU/PLAYING/PAUSED/GAME OVER/VICTORY.
- Medição de FPS no HUD.
- Indicador de alerta quando FPS médio recente cai abaixo de 45.
- Fundo com gradientes e grid leve para maior profundidade visual.
- Glow limitado por qualidade para não penalizar celulares.
- Performance mode LOW continua removendo efeitos mais pesados.
- Limpeza de RAF, timers, listeners e áudio existente foi preservada.
- Não foram adicionados dezenas de jogos duplicados; a prioridade permanece corrigir e melhorar os jogos existentes.

## 4. Performance
- Aproveita o Performance Center 6.0 já existente.
- Novos recursos não executam código arbitrário no servidor.
- SQL educativo permanece em SQLite `:memory:`.
- Preview de código permanece local/sandboxed.

## 5. Validação estática
- `python -m compileall -q .` — PASS
- `node --check` em todos os JS — PASS
- parsing Jinja de todos os templates — PASS
- `scripts/final_expansion_check.py` — PASS
- Python files: 93
- Routes: 313
- Duplicate routes: 0
- Errors: 0

## 6. Limitação de teste runtime
O ambiente de validação não possui Flask/Werkzeug instalados. Portanto, não foi possível executar testes HTTP reais, navegador/Chrome, mobile ou chamadas reais do provedor de IA. Esses itens não são marcados como testados.
