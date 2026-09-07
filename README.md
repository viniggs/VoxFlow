# VoxFlow

VoxFlow será um aplicativo Windows de ditado universal e estudo por voz integrado ao Hermes.

## Estado atual

Fase 3: ditado universal com preview parcial na UI e overlay, limpeza OpenCode GO
com rota visível, inserção automática, configurações gráficas, tray completo,
histórico SQLite, autostart e sons.

Segure `Ctrl + Numpad +`, fale e solte. O preview aparece somente no VoxFlow;
o texto final é inserido no aplicativo ativo depois que o atalho é solto.

## Desenvolvimento

```powershell
uv sync --extra dev
uv run voxflow --check
uv run voxflow
uv run voxflow --quit
uv run ruff check .
uv run pytest
```

Configurações ficam em `%APPDATA%\VoxFlow\config.yaml`, dados e logs em
`%LOCALAPPDATA%\VoxFlow`, e segredos no Gerenciador de Credenciais do Windows.
