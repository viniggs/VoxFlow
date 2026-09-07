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
