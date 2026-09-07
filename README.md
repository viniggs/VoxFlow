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

Para decidir você mesmo quando ela ouve, segure o `+` do teclado numérico enquanto
fala e solte para enviar — inclusive por cima da fala dela, que é interrompida. A tecla
só pertence à Friday enquanto ela está na tela; fora disso o `+` digita normalmente.
Toques com menos de um segundo e gravações sem voz são descartados sem gastar um turno,
e `Esc` durante a pressionada descarta o que foi gravado.

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
