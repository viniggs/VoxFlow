# VoxFlow 0.6.0 — Checklist manual de aceite da Fase 4.5 (Interface)

Data: 2026-09-07

Esta fase é uma solicitação direta do usuário e troca apenas a camada visual. Nenhum
comportamento de ditado, VAD, barge-in, half-duplex ou contrato do Hermes foi alterado.

## Instalação

- [ ] Instalar `VoxFlow-0.6.0-fase-4.5-setup.exe` por cima da versão atual.
- [ ] Confirmar que o ícone na bandeja agora é o orbe azul, e não mais o alto-falante genérico.
- [ ] Confirmar que a janela principal abre como um portal escuro com estrelas e o orbe no centro.

## O orbe

- [ ] Em repouso, o orbe respira devagar em cinza-grafite.
- [ ] Ao segurar `Ctrl + Numpad +`, ele fica ciano e a onda acompanha sua voz.
- [ ] Ao soltar, ele passa por violeta (transcrevendo/limpando) e dá um pulso verde ao inserir.
- [ ] Em erro, ele fica vermelho.

## Cápsula de ditado

- [ ] A cápsula aparece no rodapé do monitor da janela ativa, com o orbe pequeno à esquerda.
- [ ] O preview parcial aparece nela enquanto você fala.
- [ ] **Confirmar que nada é digitado no Notepad/Chrome antes de soltar o atalho.**
- [ ] `Esc` cancela; clicar no orbe da cápsula também cancela.

## Painel da Friday (`F9`)

- [ ] O painel aparece na borda direita, sem barra de título, como uma janela para o espaço.
- [ ] Sua fala vira um balão à direita; a resposta da Friday vira um balão à esquerda.
- [ ] A resposta aparece em streaming, palavra por palavra.
- [ ] **Enquanto a Friday fala, a palavra que está saindo do alto-falante acende no balão.**
- [ ] O orbe fica rosa/laranja e pulsa no ritmo real da fala dela.
- [ ] Clicar no orbe do painel encerra o modo Hermes (mesmo efeito de `F9`).
- [ ] Passar o mouse sobre o painel revela voz, Ajustes e Ocultar.
- [ ] Trocar a voz no painel continua funcionando.
- [ ] Confirmar que dá para continuar digitando em outro aplicativo com o painel aberto
  (ele nunca rouba o foco do teclado).

## Descoberta das configurações

- [ ] Abrir a janela principal e clicar em **Ajustes** no topo — sem precisar achar a bandeja.
- [ ] Clicar em **Histórico** no topo abre o histórico.
- [ ] Arrastar a janela principal pelo fundo funciona (ela não tem barra de título).

## Regressão rápida da Fase 4

- [ ] Cinco turnos hands-free seguidos.
- [ ] Barge-in: falar por cima corta a voz dela.
- [ ] Half-duplex ligado em Ajustes → Hermes impede o barge-in, como esperado.
- [ ] `%LOCALAPPDATA%\VoxFlow\logs\voxflow.log` ainda registra `ttfb_hermes_ms` e
  `tts_first_audio_ms`.

## Desempenho

- [ ] Com a janela principal aberta e o painel visível, o uso de CPU permanece aceitável.
- [ ] Fechar/ocultar a janela principal reduz o uso (as animações param quando escondidas).

---

# VoxFlow 0.7.0 — Pensamento visível e conversa que não trava

Data: 2026-09-07

Esta parte substitui o transporte usado para falar com o Hermes. O modo Ditado
não foi tocado.

## O pensamento da Friday

- [ ] Pressionar `F9`, fazer uma pergunta que exija raciocínio
  ("pense com calma e explique por que o gelo derretendo aumenta a entropia").
- [ ] Confirmar que aparece um **balão discreto, menor e mais apagado**, com o
  pensamento dela sendo escrito, **antes** da resposta.
- [ ] Confirmar que o texto do pensamento é diferente da resposta — é o raciocínio
  interno, não um adiantamento do que ela vai dizer.
- [ ] Fazer uma pergunta que a leve a usar uma ferramenta. Confirmar que aparecem
  **dois balões de pensamento separados** (ela pensa, usa a ferramenta, pensa de novo)
  em vez de um bloco só.

## A conversa não trava mais

- [ ] Fazer uma pergunta longa e, enquanto ela fala, **interromper falando por cima**.
- [ ] Confirmar que ela para e o novo turno começa **imediatamente** — sem aquela
  espera de vários segundos.
- [ ] Repetir a interrupção quatro ou cinco vezes seguidas, rápido.
  **Antes isso travava o app em "pensando" para sempre.** Confirmar que não trava mais.
- [ ] Fazer cinco turnos seguidos e confirmar que nenhum fica preso em "falando"
  sem falar nada.

## Memória

- [ ] Perguntar algo, e no turno seguinte perguntar "o que eu acabei de te perguntar?".
- [ ] Confirmar que ela lembra. **Se não lembrar**, abrir Ajustes → Hermes e desligar
  `use_runs_api`; o caminho antigo volta e a conversa segue funcionando.

## Diagnóstico

- [ ] Conferir `%LOCALAPPDATA%\VoxFlow\logs\voxflow.log` e localizar:
  - `hermes_run_started ... accepted_ms=` — deve ficar em torno de 200 ms
  - `hermes_first_delta ttfb_hermes_ms=` — compare com os 28 s de antes
  - `hermes_run_stopped` — aparece a cada interrupção
  - `hermes_delta_gap` — só aparece quando o Hermes engasga de verdade
- [ ] Conferir que `%LOCALAPPDATA%\VoxFlow\reasoning\stream.jsonl` está crescendo.

Se o pensamento não aparecer, o plugin do Hermes é a primeira coisa a conferir:
`~/.hermes/plugins/voxflow-reasoning/` e `plugins.stream_reasoning_deltas: true`.

---

# VoxFlow 0.7.1 — o pensamento deixa de atrasar

Data: 2026-09-07

- [ ] Instalar `VoxFlow-0.7.1-fase-4.5-setup.exe` por cima.
- [ ] Fazer uma **sessão longa** com a Friday, de uns quinze minutos, com perguntas que a
  façam pensar bastante.
- [ ] Confirmar que o pensamento aparece **acompanhando o raciocínio dela**, e não
  atrasado.
- [ ] Ao final, num momento de silêncio, confirmar que **não chega uma rajada de
  pensamento antigo** do começo da sessão. Era esse o defeito.
- [ ] Confirmar que o balão de pensamento não cresce sem limite: em turnos muito longos
  ele mantém a parte final, que é a que ainda está sendo escrita.
- [ ] Confirmar que a interface continua fluida enquanto ela pensa — sem travadinhas no
  orbe ou nas estrelas.

---

# VoxFlow 0.7.2 — Estúdio do Orbe

Data: 2026-09-07

- [ ] Instalar `VoxFlow-0.7.2-fase-4.5-setup.exe` por cima.
- [ ] Abrir Ajustes → **Estúdio do Orbe** e confirmar que a prévia aparece sem mover o
  restante da janela.
- [ ] Trocar **Editar** entre um estado e **Todos juntos**; confirmar que a seleção
  individual preserva as diferenças e que Todos juntos aplica apenas o controle movido.
- [ ] Arrastar cada color picker e confirmar que núcleo, sombras e malha mudam na hora.
- [ ] Ajustar foco, correntes internas, amplitude/frequência da malha e tamanho das
  bolinhas; confirmar atualização ao vivo na prévia GPU.
- [ ] Ajustar intensidade, alcance, velocidade e frequência das **Erupções de plasma**;
  confirmar que a frequência muda a cadência e alcance muda o tamanho das expulsões.
- [ ] Escolher **Simular fala** e mover o nível; confirmar ondas subindo e descendo sem
  alterar o repouso. Escolher **Sem voz** e confirmar que elas param.
- [ ] Salvar o orbe, fechar/reabrir Ajustes e confirmar que os valores permanecem.
- [ ] Usar **Voltar ao salvo** e **Restaurar padrão**; confirmar que cada ação atualiza
  a prévia e os controles.
- [ ] Confirmar que a aba Áudio mantém os controles de sensibilidade, início da fala,
  silêncio de encerramento e pré-roll.

---

# VoxFlow 0.7.3 — Push-to-talk da Friday

Data: 2026-09-07

## A tecla fora da conversa

- [ ] Com a Friday **desligada**, abrir o Bloco de Notas e apertar o `+` do teclado
  numérico. Confirmar que ele digita `+` normalmente.
- [ ] Confirmar que `Ctrl + Numpad +` continua ditando como sempre.

## A tecla durante a conversa

- [ ] Apertar `F9`. Ir ao Bloco de Notas e apertar o `+` do numpad: confirmar que
  **nada é digitado** (a tecla agora é da Friday).
- [ ] Segurar o `+`, falar uma frase e soltar. Confirmar que o balão do usuário aparece
  com o que foi falado e que a Friday responde.
- [ ] Segurar o `+` e falar com **pausas longas para pensar** no meio. Confirmar que o
  turno só é enviado quando a tecla é solta, e não na primeira pausa.

## As duas regras

- [ ] Dar um toque rápido no `+` (menos de 1 s) falando. Confirmar que nada é enviado e
  que o estado volta a ouvir com "toque curto ignorado".
- [ ] Segurar o `+` por uns 4 s **em silêncio** e soltar. Confirmar que nada é enviado e
  que aparece "não ouvi fala; nada foi enviado".

## Interrupção e cancelamento

- [ ] Enquanto a Friday **fala**, segurar o `+` e falar por cima. Confirmar que ela para
  na hora, que a gravação corre enquanto a tecla está pressionada e que soltar envia o
  turno novo.
- [ ] Segurar o `+`, falar, e apertar `Esc` sem soltar. Confirmar que a gravação é
  descartada e que nenhum `+` aparece na janela ativa ao soltar a tecla.
- [ ] Segurar o `+` e apertar `F9` (encerrar Hermes) antes de soltar. Confirmar que o
  app volta ao ditado sem microfone preso e sem travar.

## Resposta sem teto

- [ ] Pedir uma explicação com profundidade ("me explica isso com calma, com exemplo").
  Confirmar que a resposta **não é mais cortada em ~120 palavras**.
- [ ] Fazer uma pergunta curta de sim/não e confirmar que ela continua respondendo
  curto — o tamanho deve seguir a pergunta, não um teto fixo.

---

# VoxFlow 0.7.4 — A tecla da Friday é global

Data: 2026-09-07

Substitui os itens de 0.7.3 sobre a posse da tecla, que testavam o contrário.

## A tecla em qualquer lugar

- [ ] Com a Friday **fechada**, estando no editor de notas, segurar o `+` do numpad e
  falar. Confirmar que a janela dela **abre sozinha** e que o que foi falado desde o
  começo chega — nada perdido no tempo de subida.
- [ ] Repetir soltando a tecla **bem rápido depois de falar** (antes de ela terminar de
  subir). Confirmar que o turno ainda chega, e não é descartado.
- [ ] Confirmar que o `+` da tecla que divide com `=` continua digitando normalmente.
- [ ] Confirmar que `Ctrl + Numpad +` continua ditando como sempre.

## Com ela já aberta

- [ ] Segurar o `+` de dentro de outro aplicativo e falar. Confirmar que chega.
- [ ] Segurar o `+` e falar com **pausas longas para pensar**. Confirmar que o turno só
  sai ao soltar, e não na primeira pausa.
- [ ] Enquanto ela **fala**, segurar o `+`. Confirmar que ela para na hora e que o turno
  novo entra ao soltar.

## As duas regras

- [ ] Toque rápido no `+` (menos de 1 s): nada enviado, "toque curto ignorado".
- [ ] Segurar uns 4 s **em silêncio**: nada enviado, "não ouvi fala; nada foi enviado".
- [ ] Segurar, falar e apertar `Esc` sem soltar: gravação descartada e nenhum `+` solto
  na janela ativa ao soltar a tecla.
- [ ] Ditar com `Ctrl + Numpad +` e, **enquanto a transcrição roda**, segurar o `+`.
  Confirmar que ele é recusado com aviso, sem embaralhar os dois caminhos.

---

# VoxFlow 0.7.5 — Assistente de primeira execução

Data: 2026-09-07

## No teu computador (nada deve mudar)

- [ ] Instalar por cima e abrir. Como já tens Hermes, plugin, microfone e chave, o
  assistente **não deve aparecer**.
- [ ] Confirmar que a Friday e o ditado continuam funcionando como antes.

## Simulando o computador do amigo

- [ ] Renomear temporariamente `%LOCALAPPDATA%\hermes\plugins\voxflow-reasoning` e
  abrir o app. O assistente deve aparecer apontando o plugin como não instalado.
- [ ] Clicar em **Instalar plugin** e confirmar a mensagem de sucesso. Verificar que os
  dois arquivos voltaram para a pasta.
- [ ] Clicar em **Verificar de novo** e confirmar que a linha virou ✓.
- [ ] Clicar em **Continuar assim mesmo** e reabrir o app: o assistente **não deve
  voltar**, porque nada novo está faltando.

## O seletor do Hermes

- [ ] Editar `%APPDATA%\VoxFlow\config.yaml` e pôr um `executable_path` inexistente.
  Abrir o app: o assistente deve aparecer dizendo que não encontrou o Hermes.
- [ ] Usar **Procurar hermes.exe…**, apontar o real, e confirmar que a linha vira ✓ e
  que a Friday sobe normalmente depois.

## Microfone e chave

- [ ] Trocar o microfone no seletor do assistente e confirmar que a escolha aparece
  depois em Ajustes → Áudio.
- [ ] Confirmar que a chave, quando já existe, aparece como "Configurada" e sem campo
  de digitação.

## Entrega ao amigo

- [ ] Mandar só o `.exe` e confirmar com ele: SmartScreen pede "Executar assim mesmo";
  o assistente aparece; o botão de instalar plugin funciona; o Whisper baixa sozinho na
  primeira transcrição.

---

# VoxFlow 0.7.6 — Modo de escuta e atalhos configuráveis

Data: 2026-09-07

## O modo de escuta

- [ ] Ajustes → Hermes → **Como ela ouve** = *Push-to-talk*. Abrir a Friday, **falar sem
  segurar nada** e confirmar que ela **não responde**.
- [ ] Ainda em push-to-talk: segurar o atalho, falar, soltar. Confirmar que responde.
- [ ] Ainda em push-to-talk: enquanto ela fala, **falar por cima sem segurar** e
  confirmar que ela **não** é interrompida.
- [ ] Voltar para *Fala contínua* e confirmar que ela volta a ouvir sozinha.
- [ ] Em fala contínua, segurar o atalho e falar: confirmar que **ainda funciona** e que
  o silêncio no meio não corta a frase.

## Atalhos configuráveis

- [ ] Ajustes → **Atalhos**: clicar em "Segurar para falar com a Friday", pressionar
  `Ctrl + A`, salvar. Confirmar que o campo diz *continua funcionando normalmente*.
- [ ] No Bloco de Notas, confirmar que `Ctrl + A` **ainda seleciona tudo** e que
  segurá-lo também fala com a Friday.
- [ ] Confirmar que o `+` do numpad **voltou a escrever** depois da troca.
- [ ] Voltar o atalho para `Num +` e confirmar que o campo avisa *esta tecla deixará de
  digitar*, e que ela realmente para de escrever.
- [ ] Usar **Remover** num atalho e confirmar que a tecla volta ao Windows e a função
  fica sem atalho.
- [ ] Trocar "Mínimo para valer a pressionada" para 1500 ms e confirmar que toques mais
  curtos passam a ser ignorados.

## O ponto a decidir

- [ ] Com o ditado ainda em `Ctrl + Numpad +`, ditar dentro do Chrome. **Verificar se a
  página dá zoom junto.** Se der, me avisar: a regra "só engolir tecla que escreve
  sozinha" foi implementada como pedida, e é isso que deixa o `Ctrl +` chegar no
  navegador. Inverter é rápido.

---

# VoxFlow 0.7.7 — Seleção de modelos

Data: 2026-09-07

- [ ] Ajustes → **STT**: confirmar que "Modelo instalado" lista os modelos de
  transcrição do seu cache com o tamanho, e que o atual já vem selecionado.
- [ ] Confirmar que a nota abaixo lista os outros modelos do cache separados por
  categoria (Demucs, Chatterbox, Qwen3-TTS) e que **nenhum deles** aparece no seletor.
- [ ] Confirmar que "Nome do modelo" e "Pasta do modelo" estão desabilitados enquanto um
  modelo da lista estiver escolhido.
- [ ] Escolher **Outro (informar manualmente)** e confirmar que os dois campos voltam a
  ser editáveis.
- [ ] Trocar para o outro modelo de transcrição da lista, salvar, reabrir Ajustes e
  confirmar que a escolha permaneceu.
- [ ] **Ditar depois de trocar** e confirmar que a transcrição continua funcionando —
  é o teste que importa, porque o caminho de resolução do modelo mudou de campo.
- [ ] Baixar um modelo novo com o app aberto, clicar em **Procurar de novo** e confirmar
  que ele aparece.
- [ ] Aba Geral: confirmar que "Atalhos" agora aponta para a aba Atalhos em vez de
  anunciar `Ctrl + Numpad +`.

---

# VoxFlow 0.7.8 — Provider de voz de verdade

Data: 2026-09-07

## O seletor funciona

- [ ] Ajustes → Hermes → **Provider TTS**: confirmar que aparecem os quatro, com
  *(indisponível)* em OpenAI (sem chave) e Chatterbox, e a explicação embaixo.
- [ ] Escolher **Windows (offline)** e confirmar que a lista de vozes vira Maria e Zira.
- [ ] Salvar, falar com a Friday e confirmar que **a voz mudou de verdade** — é o teste
  que prova a correção.
- [ ] Confirmar que o realce palavra por palavra e o movimento do orbe continuam
  acompanhando a fala com a voz do Windows.
- [ ] Voltar para **Edge** e confirmar que as vozes voltam a ser Thalita/Francisca/etc.

## As listas não se misturam

- [ ] Com o provider em Windows, abrir a Friday (F9) e confirmar que a barra de
  controles mostra **Maria/Zira**, não as vozes do Edge.
- [ ] Trocar o provider em Ajustes e salvar com a Friday aberta; confirmar que a lista
  na barra dela se atualiza junto.
- [ ] Confirmar que nenhuma voz do Edge aparece quando o provider é Windows, e
  vice-versa.

## Se você tiver chave da OpenAI

- [ ] Guardar a chave, reabrir Ajustes e confirmar que OpenAI deixa de estar
  *(indisponível)* e oferece Alloy/Echo/Fable/Onyx/Nova/Shimmer.

---

# VoxFlow 0.7.9 — Preparo para modelos de transcrição novos

Data: 2026-09-07

- [ ] Ajustes → STT: confirmar que a nota continua listando os modelos do cache por
  categoria, e que nada mudou no que já funcionava.
- [ ] Baixar um Whisper em formato Transformers (por exemplo `openai/whisper-small`) e
  confirmar que ele aparece na nota como **"precisa converter"**, e **não** no seletor.
- [ ] Rodar `./scripts/add-stt-model.ps1 -Model 'openai/whisper-small'` e confirmar que
  a conversão termina gerando `model.bin`. **Este é o teste que nunca foi executado.**
- [ ] Clicar em **Procurar de novo** e confirmar que o modelo convertido aparece no
  seletor como pronto.
- [ ] Selecioná-lo, salvar e **ditar**, confirmando que a transcrição funciona com ele.
- [ ] Apontar o script para um modelo que não é Whisper (por exemplo um Parakeet) e
  confirmar que ele falha explicando o motivo e **não deixa pasta pela metade**.

---

# VoxFlow 0.7.10 — Correção do travamento na abertura

Data: 2026-09-07

- [ ] Instalar por cima da 0.7.9 e **abrir o app**. Ele tem que subir sem erro — este é
  o item que importa; a 0.7.9 morria aqui.
- [ ] Abrir Ajustes → STT e confirmar que a lista de modelos aparece.
- [ ] Confirmar que os tamanhos estão certos (o turbo deve aparecer com ~1,6 GB, e não
  com o dobro).
- [ ] Confirmar que os modelos de voz e o Demucs continuam sendo listados na nota por
  categoria. Se algum aparecer como *"config.json ilegível"*, está correto: significa
  que o app instalado não conseguiu seguir os links daquele modelo, e ele foi reportado
  em vez de escondido.
- [ ] Ditar e falar com a Friday, confirmando que nada mais regrediu.

---

# VoxFlow 0.7.12 — A API local do Hermes

Data: 2026-09-08

## Na sua máquina (tudo já configurado)

- [ ] Abrir o app e confirmar que o assistente **não aparece** — as seis verificações
  passam, incluindo as duas novas.
- [ ] Se aparecer, ler o que ele diz sobre `API local do Hermes` e `Chave da API`.

## Simulando o computador do amigo

- [ ] Editar `%APPDATA%\VoxFlow\config.yaml` e trocar a porta do `hermes.base_url` para
  uma que não existe (por exemplo `8643`). Abrir o app: o assistente deve aparecer
  dizendo que o Hermes serve em `127.0.0.1:8642` e o VoxFlow aponta para outro lugar.
- [ ] Clicar em **Usar 127.0.0.1:8642** e confirmar que a linha vira ✓ e que a Friday
  volta a funcionar.
- [ ] Renomear temporariamente o `config.yaml` do Hermes e derrubar o gateway
  (`hermes gateway stop`). Abrir o app: o assistente deve dizer que não conseguiu ler a
  configuração dele.

## A chave

- [ ] Em Ajustes → Hermes, apagar a chave guardada (ou trocá-la por algo errado).
  Reabrir o app e confirmar que o assistente diz que ela **difere** da que o Hermes
  espera — e não apenas que está ausente.
- [ ] Clicar em **Importar do Hermes** e confirmar que a linha vira ✓ e a Friday volta
  a responder.

## O que continua manual

- [ ] Confirmar que o assistente **não edita** o `config.yaml` do Hermes em nenhum caso,
  só instrui. Ligar `API_SERVER_ENABLED: true` é uma ação sua, por decisão de projeto.

---

# VoxFlow 0.7.13 — Kokoro, janela e rótulos honestos

Data: 2026-09-08

## O Kokoro funcionando

- [ ] Ajustes → Hermes → Provider TTS: confirmar que **Kokoro (local, PT-BR)** aparece
  **sem** sufixo de indisponível.
- [ ] Escolher Kokoro, voz **Dora**, salvar e falar com a Friday. Confirmar que ela
  responde com a voz do Kokoro, offline.
- [ ] Confirmar que a primeira frase demora um pouco mais (carga do modelo) e as
  seguintes saem rápido.
- [ ] Confirmar que o realce palavra por palavra continua acompanhando a fala.
- [ ] Trocar as vozes (Dora, Alex, Santa) e confirmar que todas falam.

## O app abrindo

- [ ] Com o VoxFlow já rodando, clicar no ícone dele. **A janela tem que aparecer** —
  antes não acontecia nada. Este é o item principal desta versão.
- [ ] Repetir algumas vezes seguidas e confirmar que a janela sobe uma vez por clique,
  sem abrir cópias.

## Os rótulos

- [ ] Confirmar que o Chatterbox agora diz **"(ainda não implementado)"** e não
  "(indisponível)" — ele não existe no código, não é problema da tua máquina.
- [ ] Confirmar que o OpenAI diz **"(falta configurar)"**, que é o caso dele: sem chave.

## Se for reconstruir

- [ ] Rodar `scripts/build-release.ps1` e confirmar que o Kokoro continua funcionando no
  app instalado depois do build. O `uv sync` do começo do script removeria os pacotes se
  eles não estivessem declarados — foi o que quase aconteceu.

---

# VoxFlow 0.7.14 — O catálogo de vozes do Edge

Data: 2026-09-08

- [ ] Ajustes → Hermes: confirmar que a nota do provider Edge mostra a contagem de
  vozes, e que existe a linha **Idioma da voz**.
- [ ] Confirmar que ela abre em **"Português e multilíngues (14)"** e que as três
  brasileiras (Antonio, Francisca, Thalita ML) aparecem **no topo** da lista de vozes.
- [ ] Confirmar que **nenhuma voz de Portugal** aparece nesse grupo.
- [ ] Trocar para **Todas** e confirmar que passam de 300 vozes.
- [ ] Escolher um idioma qualquer (japonês, alemão) e confirmar que a lista de vozes
  muda só para aquele idioma.
- [ ] Escolher uma voz multilíngue de outro idioma (Ava ML, Seraphina ML) e **falar com
  a Friday em português** — elas devem falar português mesmo sendo en-US/de-DE.
- [ ] Clicar em **Atualizar vozes** e confirmar que a janela **não trava** durante a
  busca e que aparece a contagem ao terminar.
- [ ] Abrir a Friday (F9) e confirmar que a barra de controles dela mostra as 14 do
  grupo português, e não as 322.
- [ ] Escolher uma voz de outro idioma em Ajustes, salvar, fechar e reabrir Ajustes:
  confirmar que a linha de idioma **abre no idioma daquela voz**, e não no padrão.

---

# VoxFlow 0.7.15 — Guarda da documentação

Data: 2026-09-08

Entrega sem mudança de comportamento no aplicativo: é um teste que impede o build de
sair com documentação desatualizada, mais as correções que ele apontou.

- [ ] Confirmar que o aplicativo continua funcionando igual à 0.7.14 — não há nada novo
  na interface.
- [ ] Ler a seção **A voz da Friday** no README e confirmar que o Kokoro está lá.
- [ ] Confirmar no README que clicar no ícone com o app aberto traz a janela de volta.

---

# VoxFlow 0.7.16 — Realce sincronizado e modo de escuta no painel

Data: 2026-09-08

## O realce das palavras

- [ ] Falar com a Friday e acompanhar o rosa: ele deve andar **junto** com a voz, uma
  palavra de cada vez, sem correr na frente.
- [ ] Repetir com uma resposta longa, cheia de "a", "de", "que" — era exatamente aí que
  ele disparava para a frente.
- [ ] Trocar a voz para o **Edge** e conferir que continua certo (o defeito valia para
  os dois; o Edge só o disfarçava menos).

## O modo de escuta no painel da Friday

- [ ] Abrir a Friday (`F8`, na tua configuração) e clicar no orbe para revelar os
  controles: agora há **duas linhas** — voz e modo em cima, Ajustes e Ocultar embaixo.
- [ ] Confirmar que nenhum controle aparece cortado.
- [ ] Escolher **Push-to-talk** e confirmar que ela **para de abrir turno sozinha**:
  falar perto do microfone sem segurar a tecla não deve iniciar nada.
- [ ] Segurar `Ctrl + Numpad *` (a tua tecla de fala), falar, soltar — o turno deve ir.
- [ ] Voltar para **Fala contínua** e confirmar que ela volta a ouvir sozinha.
- [ ] Abrir Ajustes → Hermes e confirmar que **Como ela ouve** mostra a mesma escolha
  feita no painel; mudar lá e confirmar que o painel acompanha.
- [ ] Confirmar que a troca vale **sem reiniciar** o VoxFlow.
