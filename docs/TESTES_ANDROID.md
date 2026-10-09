# Checklist de testes no Android

Os testes automáticos (Python) não testam o celular de verdade. Use esta lista
a cada versão nova. Marque ✅ ou ❌ e anote o modelo/Android.

## Automático (GitHub)
- [ ] Actions → **Teste no emulador Android** → Run workflow: abre o app em Android 10, 13 e 14.

## No aparelho
| # | Teste | Como fazer | Esperado |
|---|-------|-----------|----------|
| 1 | Instalação limpa | Desinstale e instale o APK | Abre sem fechar |
| 2 | Atualização | Instale por cima da versão anterior | Favoritos e config. mantidos |
| 3 | Notificação permitida | Aceite o pedido de notificação | Monitor avisa online/morte/level |
| 4 | Notificação negada | Negue; abra Configurações | App não fecha; mostra aviso |
| 5 | Reiniciar celular | Monitor ligado → reinicie | Monitor volta sozinho |
| 6 | Android fecha o app | Abra vários apps pesados / "Forçar parada" | Ao reabrir, volta normal |
| 7 | Sem internet | Modo avião → abra Bosses/Char | Mostra dado antigo ou aviso claro |
| 8 | Volta da internet | Desligue modo avião → atualizar | Dados novos, sem notificação repetida |
| 9 | Botão/gesto voltar | Em cada tela | Volta para a tela anterior |
| 10 | Log de erros | Configurações → Compartilhar log | Abre opções de compartilhar |
