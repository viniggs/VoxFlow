# VoxFlow

VoxFlow será um aplicativo Windows de ditado universal e estudo por voz integrado ao Hermes.

## Estado atual

Fase 2: ditado universal com limpeza OpenCode GO, comandos falados, snippets,
regras por aplicativo, injeção Unicode e fallback seguro para o texto bruto.

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
