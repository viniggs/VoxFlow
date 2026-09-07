# VoxFlow 0.5.4 — Checklist manual de aceite da Fase 4

Data: 2026-09-07

## Instalação e conexão

- [ ] Instalar `VoxFlow-0.5.4-fase-4-setup.exe` por cima da versão atual.
- [ ] Abrir Configurações → Hermes e clicar em “Testar conexão”.
- [ ] Se estiver parado, clicar em “Iniciar Hermes” e testar novamente.
- [ ] Confirmar que aparece “Hermes conectado”.

## Conversa hands-free

- [ ] Pressionar `F9` e confirmar que o painel “Hermes ao vivo” aparece como “Ouvindo”.
- [ ] Falar uma pergunta e ficar em silêncio por cerca de 700 ms.
- [ ] Confirmar que “Você disse” mostra a transcrição e a resposta surge aos poucos na UI.
- [ ] Confirmar que a resposta é lida em voz alta por frases.
- [ ] Fazer cinco turnos seguidos sem tocar no teclado.
- [ ] Enquanto o Hermes fala, começar a falar e confirmar que a voz para e o novo turno é ouvido.
- [ ] Ativar half-duplex nas configurações e confirmar que ele não tenta ouvir durante a própria voz.
- [ ] Pressionar `F9` novamente e confirmar retorno ao modo Ditado.

## Diagnóstico rápido

- [ ] Conferir `%LOCALAPPDATA%\VoxFlow\logs\voxflow.log` e localizar
  `ttfb_hermes_ms` e `tts_first_audio_ms`.

Recomenda-se usar fones para o teste de interrupção. Com caixas de som, a própria voz do
Hermes pode entrar no microfone; nesse caso, use half-duplex.
