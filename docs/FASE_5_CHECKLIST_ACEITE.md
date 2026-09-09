# VoxFlow 0.8.0 — Fase 5: modo estudo

Data: 2026-09-08

Esta instalação carrega a Fase 5 **e** tudo que ficou sem aceite desde a 0.7.13. Se
alguma coisa falhar, o painel diz o quê e o log fica em
`%LOCALAPPDATA%\VoxFlow\logs\voxflow.log`.

## Instalação

- [ ] Rodar `VoxFlow-0.8.0-fase-5-setup.exe`. O SmartScreen pede "Mais informações" →
  "Executar assim mesmo".
- [ ] Confirmar que a versão instalada é **0.8.0** (Configurações do Windows →
  Aplicativos, ou o título da janela).

## Os comandos de voz

Abre a Friday e fala cada um. Nenhum deles pode virar uma resposta dela sobre o assunto —
o app é que responde.

- [ ] **"olha minha tela"** — ela olha e descreve. Leva um tempo (veja a seção abaixo).
- [ ] **"olha minha tela e explica esse slide"** — a pergunta depois do comando tem que
  chegar junto: a resposta deve ser sobre o slide, não uma descrição genérica.
- [ ] **"repete"** — ela repete a última resposta **sem** consultar o Hermes de novo
  (é instantâneo; se demorar, algo está errado).
- [ ] **"mais devagar"** e depois **"mais rápido"** — a velocidade da fala muda na hora.
- [ ] **"pausa"** — ela para de falar imediatamente e volta a ouvir.
- [ ] **"nova sessão"** — começa um histórico novo. O antigo **não é apagado**.
- [ ] **"modo ditado"** — a janela dela fecha e o ditado volta a funcionar.
- [ ] Fazer uma pergunta longa que contenha uma dessas palavras, por exemplo
  *"você pode repetir o que eu disse sobre a prova de amanhã?"* — isso é **pergunta**,
  não comando, e ela deve responder normalmente.

## Quem olha a tela

Em Ajustes → Hermes → **Quem olha a tela**:

- [ ] Com **"VoxFlow captura"** (padrão): a resposta deve chegar em torno de **10 s**.
- [ ] Trocar para **"Ela olha com a ferramenta dela"** e pedir de novo: vai demorar
  minutos. Confirmar que a conversa aparece no **app desktop do Hermes**, no grupo
  **API** da barra lateral (ele vem fechado — precisa clicar para abrir).
- [ ] Desmarcar **Permitir screenshot por comando** e pedir: ela deve recusar dizendo que
  a captura está desligada, em vez de tentar.

## O arquivo da sessão

- [ ] Depois de conversar, abrir `Documentos\VoxFlow\sessions\` e confirmar que existe um
  arquivo com a data de hoje (`2026-09-08.md`).
- [ ] Confirmar que é o seu Documentos **real** — se você usa OneDrive, o arquivo tem que
  estar em `OneDrive\Documentos`, não numa pasta `Documents` esquecida.
- [ ] Abrir o arquivo e conferir: cabeçalho do dia, horário de início da sessão, e os
  turnos marcados **Você** e **Friday** com o horário de cada um.
- [ ] Conversar mais um pouco e confirmar que os turnos novos foram **acrescentados** ao
  mesmo arquivo.

## Encerrar a sessão

- [ ] Falar **"encerra sessão"**. Ela deve fazer um resumo do que foi estudado e propor
  perguntas de revisão.
- [ ] Confirmar que o modo Hermes só desliga **depois** que ela termina de falar — a fala
  não pode ser cortada no meio.
- [ ] Confirmar que o resumo também foi para o arquivo `.md`.

## O que veio junto, ainda sem aceite

- [ ] **Realce (0.7.16):** o rosa acompanha a voz palavra por palavra, sem correr na
  frente, inclusive numa resposta longa cheia de "a", "de", "que".
- [ ] **Modo de escuta (0.7.16):** o seletor está na barra sob o orbe, ao lado da voz,
  em duas linhas, e escolher **Push-to-talk** faz ela parar de abrir turno sozinha.
- [ ] **Kokoro (0.7.13):** em Ajustes → Hermes, o Kokoro aparece disponível e fala.
- [ ] **Vozes do Edge (0.7.14):** a lista abre nas 14 que falam português e **Idioma da
  voz** alcança as demais.
- [ ] **Bandeja (0.7.13):** clicar no ícone com o app aberto traz a janela de volta em
  vez de abrir uma segunda cópia.


---

# VoxFlow 0.8.1 — Captura rápida como padrão

Data: 2026-09-09

- [ ] Dizer **"olha minha tela"** e cronometrar: a resposta deve chegar em torno de
  **10 segundos**, não em minutos.
- [ ] Abrir o app desktop do Hermes, clicar no grupo **API** da barra lateral e confirmar
  que esse turno aparece lá.
- [ ] Saber o que **não** funciona ainda: perguntar depois, por voz, *"o que você viu na
  minha tela?"* — ela não vai lembrar, porque o turno com imagem cai numa sessão
  diferente da conversa por voz. A união depende de uma autorização de escrita no banco
  do Hermes.
