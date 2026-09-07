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
