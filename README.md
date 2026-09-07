# VoxFlow

VoxFlow será um aplicativo Windows de ditado universal e estudo por voz integrado ao Hermes.

## Estado atual

Fase 4: ditado universal completo e modo Hermes hands-free com VAD, resposta SSE
em tempo real, leitura por frases, interrupção por voz, half-duplex e painel dedicado.

Segure `Ctrl + Numpad +`, fale e solte. O preview aparece somente no VoxFlow;
o texto final é inserido no aplicativo ativo depois que o atalho é solto.

Pressione `F9` para entrar no modo Hermes. Fale normalmente e aguarde o silêncio
encerrar cada turno; a conversa segue sem teclado. Pressione `F9` novamente para sair.

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
