# VoxFlow

VoxFlow será um aplicativo Windows de ditado universal e estudo por voz integrado ao Hermes.

## Estado atual

Fase 4.5: ditado universal, interface em torno do orbe da Friday renderizado na GPU,
e modo Hermes hands-free com raciocínio visível.

Segure `Ctrl + Numpad +`, fale e solte. O preview aparece somente no VoxFlow;
o texto final é inserido no aplicativo ativo depois que o atalho é solto.

Pressione `F9` para entrar no modo Hermes. O painel mostra o que ela está pensando
enquanto pensa, e a resposta conforme ela chega.

Ela ouve de duas maneiras, escolhidas em Ajustes → Hermes → **Como ela ouve**:

- **Fala contínua** — ela escuta sozinha e o silêncio encerra cada turno. Falar por
  cima interrompe.
- **Push-to-talk** — ela só escuta enquanto o atalho estiver pressionado. Nada de
  ruído ambiente abrindo turno, e nenhuma pausa para pensar cortando a frase.

O atalho de fala (por padrão o `+` do teclado numérico) **funciona nos dois modos**: no
push-to-talk ele é a única forma de falar; na fala contínua ele é um reforço para quando
o ambiente está barulhento ou você quer pensar no meio da frase. Ele funciona de
qualquer lugar do Windows e a qualquer momento: com ela fechada, segurar a tecla abre a
janela dela e já começa a captar; com ela falando, interrompe. Toques com menos de um
segundo e gravações sem voz são descartados sem gastar um turno, e `Esc` durante a
pressionada descarta o que foi gravado.

## Atalhos

Todos são configuráveis em Ajustes → **Atalhos**: clique num deles e pressione as teclas
que quiser. Os padrões são `Ctrl + Numpad +` para ditar, `+` do numpad para falar com a
Friday, `F9` para abrir/fechar e `Esc` para cancelar.

Uma tecla sozinha que normalmente escreve — o `+` do numpad, uma letra — **deixa de
escrever** enquanto estiver como atalho, porque não há como usá-la para as duas coisas.
Combinações com Ctrl, Alt, Shift ou Win continuam chegando normalmente no aplicativo em
uso, então usar `Ctrl + A` como atalho não custa a você o Ctrl nem o "selecionar tudo".
O próprio campo avisa qual dos dois casos é o seu.

O pensamento depende de um plugin instalado no Hermes, em
`%LOCALAPPDATA%\hermes\plugins\voxflow-reasoning\`, que escreve os deltas de raciocínio
em `%LOCALAPPDATA%\VoxFlow\reasoning\stream.jsonl`. Sem ele o resto funciona igual. O
plugin acompanha o VoxFlow: se não estiver instalado, o assistente de configuração
oferece um botão para copiá-lo, e depois basta reiniciar o Hermes.

## Instalar em outro computador

O instalador é por usuário e não leva nada da máquina de origem: a configuração fica em
`%APPDATA%\VoxFlow` e os segredos no Gerenciador de Credenciais do Windows. Como não é
assinado, o SmartScreen pede "Mais informações" → "Executar assim mesmo".

Na primeira execução, se faltar alguma coisa, aparece um assistente mostrando o que é e
como resolver: apontar o `hermes.exe` quando ele estiver fora do lugar padrão, instalar
o plugin de raciocínio, escolher o microfone e guardar a chave de limpeza do ditado. Dá
para seguir sem resolver — o ditado funciona de qualquer jeito — e o assistente só volta
a aparecer se algo novo faltar.

Duas coisas ficam por conta de quem recebe: o **Hermes** instalado e autenticado com a
conta dele, e o **modelo Whisper** (cerca de 1,6 GB), baixado na primeira transcrição
porque não cabe no instalador.

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
