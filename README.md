# VoxFlow

VoxFlow será um aplicativo Windows de ditado universal e estudo por voz integrado ao Hermes.

## Estado atual

Fase 4.5: ditado universal, interface em torno do orbe da Friday renderizado na GPU, e
modo Hermes com raciocínio visível — ouvindo sozinha ou só quando você segura o atalho.

Segure `Ctrl + Numpad +`, fale e solte. O preview aparece somente no VoxFlow;
o texto final é inserido no aplicativo ativo depois que o atalho é solto.

Pressione `F9` para entrar no modo Hermes. O painel mostra o que ela está pensando
enquanto pensa, e a resposta conforme ela chega.

O VoxFlow fica na bandeja do sistema, que o Windows 11 esconde por padrão. Clicar no
ícone dele com o aplicativo já aberto **traz a janela para a frente** em vez de abrir
uma segunda cópia.

O pensamento depende de um plugin instalado no Hermes, em
`%LOCALAPPDATA%\hermes\plugins\voxflow-reasoning\`, que escreve os deltas de raciocínio
em `%LOCALAPPDATA%\VoxFlow\reasoning\stream.jsonl`. Sem ele o resto funciona igual. O
plugin acompanha o VoxFlow: se não estiver instalado, o assistente de configuração
oferece um botão para copiá-lo, e depois basta reiniciar o Hermes.

Ela ouve de duas maneiras, escolhidas **no painel dela**, na barra sob o orbe, ao lado
do seletor de voz — e também em Ajustes → Hermes → **Como ela ouve**. Os dois lugares
mostram sempre a mesma escolha:

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

## A voz da Friday

Em Ajustes → Hermes → **Provider TTS**:

- **Edge** — online e gratuito, sem conta. É o padrão, e o único que informa onde cada
  palavra cai, então o realce palavra por palavra é exato. São **322 vozes em 75
  idiomas**, buscadas na Microsoft e guardadas em cache. A lista abre nas 14 que falam
  português (as brasileiras e todas as multilíngues); **Idioma da voz** alcança o resto,
  e **Atualizar vozes** rebusca o catálogo.
- **Kokoro** — voz local, offline, em português do Brasil (Dora, Alex, Santa). Roda na
  sua máquina: a primeira frase leva cerca de um segundo e meio, carregando o modelo, e
  as seguintes saem em torno de 400 ms. Precisa do modelo baixado; a tela diz se falta.
- **Windows (offline)** — usa as vozes que já existem no seu Windows. Não depende de
  rede e responde mais rápido que o Edge.
- **OpenAI** — exige uma chave guardada nos segredos.
- **Chatterbox** — ainda não implementado.

O dropdown distingue os dois motivos de um provider não estar disponível: *"falta
configurar"* é coisa da sua máquina, *"ainda não implementado"* é código que não existe.

A lista de vozes é sempre a do provider escolhido: um nome do Edge não significa nada
para o Windows. Trocar de provider reconstrói a lista tanto em Ajustes quanto na barra
de controles sob a Friday.

Nos providers que não informam limites de palavra, o realce é distribuído sobre a
duração real do áudio, então ele continua acompanhando a fala em vez de ficar parado.

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

## Modelos de transcrição

O VoxFlow transcreve com faster-whisper, que carrega **um formato só**: CTranslate2.
Isso é o que decide se um modelo entra ou não, e não o quão bom ele é.

A aba Ajustes → STT classifica o que está no seu cache em três situações:

- **Pronto** — já está em CTranslate2 e aparece no seletor.
- **Precisa converter** — é Whisper, mas em formato Transformers. Quase todo fine-tune
  brasileiro é publicado assim. Uma conversão resolve, e ela é feita uma vez por modelo:

  ```powershell
  ./scripts/add-stt-model.ps1 -Model 'organizacao/nome-do-modelo'
  ```

  O resultado vai para `%LOCALAPPDATA%\VoxFlow\models`, que o app já varre — depois é
  só usar **Procurar de novo** na aba STT.

- **Outro runtime** — reconhecido como transcrição, mas construído sobre algo que o
  VoxFlow não carrega.

### Sobre as listas de "melhores modelos PT-BR"

A regra é arquitetural, não de qualidade:

| Família | Situação | Por quê |
|---|---|---|
| Whisper e seus fine-tunes (large-v3, WhisperX, variantes PT-BR) | conversível | mesma arquitetura, só muda o formato |
| Parakeet, Nemotron e outros da NVIDIA | não carrega | são NeMo, uma stack inteira à parte |
| Versões ONNX desses | não carrega | exigem um pipeline de decodificação próprio |
| Qwen3-ASR, Voxtral e afins | não carrega | são LLMs de áudio, não modelos Whisper |

Ou seja: das listas que circulam, **a coluna Whisper é a que dá para usar hoje**. Os
demais não são piores — precisam de um segundo backend de transcrição no VoxFlow, que
seria uma entrega própria.

O script de conversão só entende Whisper. Se você apontá-lo para um Parakeet, ele falha
dizendo exatamente isso, em vez de deixar meia pasta para trás.

> A conversão empresta `transformers` e `torch` via `uv tool run` só enquanto roda. Eles
> passam de 2 GB e **não** entram no ambiente do VoxFlow de propósito — o instalador tem
> 100 MB e manteria isso.
