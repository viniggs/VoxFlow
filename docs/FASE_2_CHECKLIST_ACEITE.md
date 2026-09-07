# VoxFlow 0.3.0 — Checklist manual de aceite da Fase 2

Data: 2026-09-06

## Instalação e ditado automático

- [ ] Instalar `VoxFlow-0.3.0-fase-2-setup.exe` por cima da versão atual.
- [ ] Confirmar que a janela “VoxFlow — Acompanhamento” abre e mostra “Pronto”.
- [ ] Segurar o atalho e acompanhar “Ouvindo” e o preview de transcrição na UI.
- [ ] Soltar o atalho e acompanhar “Transcrevendo”, “Limpando” e “Inserindo”.
- [ ] Confirmar que a transcrição bruta, o texto final ou um erro visível aparecem na janela.
- [ ] Abrir o Bloco de Notas, ditar e confirmar que o texto aparece sem pressionar `Ctrl+V`.
- [ ] Confirmar que o clipboard textual anterior é restaurado.

## Comandos, limpeza e fallback

- [ ] Ditar “primeira linha, nova linha, segunda linha” e confirmar a quebra.
- [ ] Ditar “texto errado, apaga isso, texto certo” e confirmar somente “texto certo”.
- [ ] Confirmar que hesitações e pontuação são limpas quando o OpenCode GO responde.
- [ ] Desconectar a rede, ditar e confirmar que o texto bruto ainda é inserido.

## Regras e Unicode

- [ ] Ditar dentro do Windows Terminal e confirmar inserção automática via Unicode.
- [ ] Conferir `%LOCALAPPDATA%\VoxFlow\logs\voxflow.log` e encontrar `stt_ms`,
  `cleanup_ms`, `inject_ms` e `total_after_release_ms`.

Observação: Muse Spark usa os dados para treinamento conforme o consentimento dado; em timeout,
o VoxFlow tenta DeepSeek V4 Flash e, se a rede falhar, preserva o texto bruto.
