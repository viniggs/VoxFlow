# VoxFlow 0.1.0 — Checklist manual de aceite da Fase 0

Data: 2026-09-06

## Preparação

- [ ] Instalar `VoxFlow-0.1.0-fase-0-setup.exe`.
- [ ] Confirmar que a instalação termina sem solicitar privilégios administrativos.
- [ ] Confirmar a existência do VoxFlow em `%LOCALAPPDATA%\Programs\VoxFlow`.

## Configuração e microfone

- [ ] Executar no código-fonte: `uv run voxflow --check`.
- [ ] Confirmar que o resultado contém `"ok": true`.
- [ ] Confirmar que o microfone selecionado contém `SteelSeries Sonar`.
- [ ] Confirmar a criação de `%APPDATA%\VoxFlow\config.yaml`.
- [ ] Confirmar a criação de `%LOCALAPPDATA%\VoxFlow\logs\voxflow.log`.
- [ ] Confirmar que nenhuma chave de API aparece no YAML ou no log.

## Instalação

- [ ] Reiniciar a sessão do Windows e confirmar que a entrada de inicialização do VoxFlow não apresenta erro.
- [ ] Desinstalar pelo painel Aplicativos Instalados e confirmar a remoção da entrada de autostart.

Observação: a Fase 0 ainda não grava, transcreve ou injeta texto; essas capacidades começam na Fase 1.

