# Roadmap — Tibia Tools

## Fase 1 — Confiabilidade (concluída na v6)
- [x] Revisar o uso de pickle no cache HTTP (substituído por JSON/base64)
- [x] Rever a substituição global de requests.get (interceptação limitada aos hosts do app)
- [x] Melhorar o registro e o tratamento de exceções
- [x] Adicionar testes de cache expirado, corrompido e offline

## Fase 2 — Estabilidade Android (pendente: depende de aparelho real)
- [ ] Testar serviço em segundo plano em aparelhos reais (Android 15/16)
- [ ] Verificar encerramento e retomada de workers
- [ ] Testar rede indisponível e permissões
- [ ] Medir bateria, memória e tempo de inicialização

## Fase 3 — Arquitetura (concluída na v7/v8)
- [x] Extrair bosses e boosted do main.py
- [x] Separar parsers das integrações (ExevoPan e GuildStats)
- [x] Centralizar resultados de sucesso e erro (core/result.py)
- [x] Adicionar testes de regressão para cada funcionalidade

## Fase 4 — Evolução (concluída na v8)
- [x] Adicionar indicação de idade dos dados
- [x] Validar cálculos contra referências atuais
- [x] Melhorar histórico de XP e mortes
- [x] Automatizar testes e verificações de qualidade no CI

## Melhorias recentes (v9–v12)
- [x] Corrigir lista de bosses vazia com filtro de favoritos (v9)
- [x] Corrigir textos de mortes cortados e barra superior (v9)
- [x] README chamativo com capa ilustrada (v10/v11)
- [x] Respeitar limite de 6h/24h do serviço em primeiro plano no Android 15+ (v12)
- [x] Cache com validação e descarte seguro de dados corrompidos (v12)
- [x] Tratamento de erros reforçado no serviço de monitoramento (v12)

## Próximos passos
- [ ] Gerar APK de teste automaticamente no GitHub (CI de release)
- [ ] Dividir o arquivo principal do app (main.py) em partes menores
- [ ] Testar monitoramento em aparelho real com Android 15/16 (5h30 → pausa → retomada ao abrir o app)
## v15 — Revisão de código (higiene, HTTP, privacidade)
- [x] Removido log do projeto; .gitignore; teste impede logs, .pyc versionados e workflows de backup.
- [x] Cliente HTTP explícito (core/http_client.py); requests global não é mais alterado.
- [x] Busca simultânea: quem espera recebe o mesmo sucesso/erro/dado antigo, sem buscar de novo.
- [x] Log sem nomes pesquisados/URLs com parâmetros; .old expira em 14 dias; botões Compartilhar/Apagar log.
- [x] Fuso horário do servidor via zoneinfo (com regra manual de reserva).
- [x] README sem versão fixa; teste em emulador (manual) e checklist docs/TESTES_ANDROID.md.
- [ ] Rodar o teste em emulador e o checklist no aparelho.
## v16 — main.py dividido
- [x] Bosses, Boosted, Treino e Imbuements em features/<tela>/controller.py (main.py: 2.900 → 1.800 linhas).
- [x] APK v16 testado com sucesso no Galaxy S25+.
## v17 — Personagem dividido
- [x] features/char: controller (busca, 665 linhas) + display + stalker + history + _common.
- [ ] Opcional: rodar o teste em emulador (Android 10/13/14) no GitHub.
