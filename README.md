# VoxFlow

VoxFlow será um aplicativo Windows de ditado universal e estudo por voz integrado ao Hermes.

## Estado atual

Fase 0: fundação do projeto, configuração segura, diagnóstico de microfone, logging,
testes e empacotamento.

## Desenvolvimento

```powershell
uv sync --extra dev
uv run voxflow --check
uv run ruff check .
uv run pytest
```

Configurações ficam em `%APPDATA%\VoxFlow\config.yaml`, dados e logs em
`%LOCALAPPDATA%\VoxFlow`, e segredos no Gerenciador de Credenciais do Windows.

