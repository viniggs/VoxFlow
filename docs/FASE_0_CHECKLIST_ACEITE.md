# VoxFlow 0.1.0 — Checklist manual de aceite da Fase 0

Data: 2026-09-06

## Preparação

- [x] Instalar `VoxFlow-0.1.0-fase-0-setup.exe`.
- [x] Confirmar que a instalação termina sem solicitar privilégios administrativos.
- [x] Confirmar a existência do VoxFlow em `%LOCALAPPDATA%\Programs\VoxFlow`.

## Configuração e microfone

- [x] Executar no código-fonte: `uv run voxflow --check`.
- [x] Confirmar que o resultado contém `"ok": true`.
- [x] Confirmar que o microfone selecionado contém `SteelSeries Sonar`.
- [x] Confirmar a criação de `%APPDATA%\VoxFlow\config.yaml`.
- [x] Confirmar a criação de `%LOCALAPPDATA%\VoxFlow\logs\voxflow.log`.
- [x] Confirmar que nenhuma chave de API aparece no YAML ou no log.

## Instalação

- [~] Reiniciar a sessão do Windows e confirmar que a entrada de inicialização do VoxFlow não apresenta erro. Dispensado pelo usuário em 2026-09-06, sem execução.
- [x] Desinstalar pelo painel Aplicativos Instalados e confirmar a remoção da entrada de autostart.

Observação: a Fase 0 ainda não grava, transcreve ou injeta texto; essas capacidades começam na Fase 1.
