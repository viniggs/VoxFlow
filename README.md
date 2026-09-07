# VoxFlow

VoxFlow será um aplicativo Windows de ditado universal e estudo por voz integrado ao Hermes.

## Estado atual

Fase 4.5: ditado universal, interface em torno do orbe da Friday renderizado na GPU,
e modo Hermes hands-free com raciocínio visível.

Segure `Ctrl + Numpad +`, fale e solte. O preview aparece somente no VoxFlow;
o texto final é inserido no aplicativo ativo depois que o atalho é solto.

Pressione `F9` para entrar no modo Hermes. Fale normalmente e aguarde o silêncio
encerrar cada turno. O painel mostra o que ela está pensando enquanto pensa, e a
resposta conforme ela chega. Falar por cima interrompe.

O pensamento depende de um plugin instalado no Hermes
(`~/.hermes/plugins/voxflow-reasoning/`), que escreve os deltas de raciocínio em
`%LOCALAPPDATA%\VoxFlow\reasoning\stream.jsonl`. Sem ele o resto funciona igual.

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
