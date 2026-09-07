# VoxFlow 0.4.1 — Checklist manual de aceite da Fase 3

Data: 2026-09-07

## Ditado, preview e inserção

- [ ] Instalar `VoxFlow-0.4.1-fase-3-setup.exe` por cima da versão atual.
- [ ] Abrir o Bloco de Notas, segurar `Ctrl + Numpad +` e falar por pelo menos 4 segundos.
- [ ] Confirmar que a janela e o overlay atualizam o preview em blocos enquanto você fala.
- [ ] Confirmar que o preview aparece somente no VoxFlow e não escreve parcialmente no Bloco de Notas.
- [ ] Soltar o atalho e confirmar que o texto final entra sozinho, sem pressionar `Ctrl+V`.
- [ ] Repetir no Chrome ou outro campo de texto comum.
- [ ] Pressionar `Esc` durante outro ditado e confirmar o cancelamento.

## Limpeza e comandos visíveis

- [ ] Verificar “Tratamento de texto” e confirmar que ele identifica Muse, DeepSeek ou texto bruto.
- [ ] Ditar uma frase com hesitação/repetição e conferir se a UI informa se o texto foi alterado.
- [ ] Ditar “primeira linha, nova linha, segunda linha” e confirmar a quebra no texto final.
- [ ] Ditar “texto errado, apaga isso, texto certo” e confirmar somente “texto certo”.
- [ ] Desconectar a rede, ditar e confirmar que a UI informa fallback bruto sem perder o texto.
- [ ] No Windows Terminal, confirmar inserção automática via Unicode.

## Fase 3

- [ ] Abrir o menu do tray e conferir status, modo, microfone, autostart, histórico e configurações.
- [ ] Abrir Configurações e salvar uma alteração sem editar `config.yaml`.
- [ ] Confirmar que o overlay aparece no monitor do aplicativo ativo.
- [ ] Confirmar os sons de início e conclusão ou desativá-los em Configurações.
- [ ] Abrir Histórico, buscar o último ditado e copiar o texto.
- [ ] Conferir `%LOCALAPPDATA%\VoxFlow\logs\voxflow.log` e localizar `stt_ms`, `cleanup_ms`,
  `inject_ms`, `total_after_release_ms`, provider e fallback.

Observação: o preview é uma retranscrição local periódica do áudio acumulado, portanto atualiza
em blocos curtos, não caractere por caractere. A injeção continua acontecendo somente após soltar.
