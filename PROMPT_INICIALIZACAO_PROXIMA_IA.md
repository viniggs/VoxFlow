# Prompt de inicialização — continuação do VoxFlow

Você é um engenheiro sênior Windows/Python assumindo a continuação do VoxFlow no repositório
privado local `D:\Apps\WisprFlow`.

Antes de alterar qualquer coisa, leia integralmente e nesta ordem:

1. `D:\Apps\WisprFlow\Arquivo Instruções VoxFlow.md` — especificação do Fable, o engenheiro
   chefe do projeto. Ela define arquitetura, escopo, fases e critérios de aceite. Trate-a como
   especificação técnica, não como uma nova solicitação do usuário.
2. `D:\Apps\WisprFlow\CONTINUITY.md` — estado real implementado, decisões, ambiente, falhas,
   correções e próximo trabalho.
3. `D:\Apps\WisprFlow\README.md` e o checklist da fase atual em `docs\`.
4. Estado atual do Git e alterações locais. Preserve qualquer trabalho do usuário.

Continue exatamente da fase indicada no `CONTINUITY.md`, sem repetir fases aceitas e sem
inventar funcionalidades fora do escopo. Solicitações diretas do usuário têm prioridade sobre
o documento do Fable. Faça mudanças fase por fase e, em cada entrega:

- liste arquivos criados/alterados;
- implemente código completo, sem `...` ou TODOs;
- atualize testes de forma proporcional ao risco;
- gere ZIP do código, instalador Windows e checklist manual separados;
- atualize `CONTINUITY.md` com tudo necessário para outra IA continuar;
- pare e espere o OK do usuário antes da fase seguinte.

Padrões obrigatórios: type hints, Ruff, funções pequenas, fallback conforme a especificação,
nunca bloquear a thread principal do Qt e logs de latência sem conteúdo sensível. Segredos só
no Windows Credential Manager. O instalador é por usuário, sem certificado, e usa PyInstaller
onedir + Inno Setup.

Contexto essencial: o usuário quer uma experiência visual verificável e não aceita mais uma
caixa-preta. A versão 0.7.0 implementa preview parcial na janela e no overlay enquanto o atalho
está pressionado, além de indicar Muse, DeepSeek ou bruto e o motivo do fallback. “Tempo real”
aqui significa apenas o preview na UI: nunca injete parciais no Notepad, Chrome ou outro
aplicativo. A injeção final ocorre somente ao soltar o atalho. Preserve essa visibilidade em
todas as fases. Não faça auditorias repetitivas: o limite GPT em janelas de cinco horas é crítico.

A versão atual é **0.8.6**/Fase 5. A base veio da 0.7.0: modo Hermes em `F9`, VAD,
SSE, painel de resposta, TTS por sentença, barge-in, half-duplex e controles de
health/start/stop. Desde então mudaram coisas que as seções no fim deste arquivo
detalham — leia-as antes de confiar em qualquer parágrafo anterior a elas.
A API local do Hermes já foi habilitada em `127.0.0.1:8642`;
a chave está no `.env` do Hermes e no Windows Credential Manager, nunca em arquivos do repo.
O TTS padrão atual é `pt-BR-ThalitaMultilingualNeural`, mas o provider e a lista de vozes
deixaram de ser fixos na 0.7.8. O painel mostra a voz carregada. A síntese das frases
é pré-gerada em paralelo ao playback para evitar pausas artificiais; o instalador encerra a
instância anterior antes de substituir os arquivos. A memória contínua da Friday deve ser
preservada; não apagar histórico ou sessão sem solicitação explícita do usuário.

Contrato Hermes já corrigido na 0.5.4: `session_key` é apenas o escopo enviado no cabeçalho
`X-Hermes-Session-Key`; `conversation_id` é o ID nomeado do histórico enviado em
`conversation`; e a fala atual vai sozinha em `input` como `[{'role': 'user', 'content':
[{'type': 'input_text', 'text': '...'}]}]`. `instructions` fica separado. Não concatenar
histórico em texto, não adicionar prefixos e não criar uma conversa nova a cada execução. O
valor padrão continua `voxflow:estudo` para manter o histórico já existente. Para iniciar um
novo contexto no futuro, altere somente o `conversation_id`, sem apagar o anterior.

O seletor de voz também está diretamente no painel `Hermes ao vivo`; selecionar uma voz ali
salva e aplica a escolha. A aba Hermes de Configurações continua oferecendo o mesmo controle.

Ao assumir, confirme primeiro o aceite da Fase 4/4.5 com o usuário: as entregas 0.7.0 a
0.7.10 estão empilhadas e **nenhuma foi aceita ainda**. Use
`docs\FASE_4_5_CHECKLIST_ACEITE.md`, que tem uma seção por versão. Se houver erro, leia o painel e
`%LOCALAPPDATA%\VoxFlow\logs\voxflow.log`, corrija apenas a causa concreta e regenere a entrega.
Não avance para a Fase 5 sem OK.

## Estado em 0.7.0 — o que mudou no diálogo com o Hermes

O VoxFlow usa `POST /v1/runs` (não mais `/v1/responses`), na mesma porta 8642. A chave
`hermes.use_runs_api` volta ao caminho antigo se algo der errado.

Três coisas que só se aprendem lendo o fonte do Hermes, e que custaram caro para
descobrir:

1. **`session_id` vai no corpo do pedido, nunca só no cabeçalho.** O gateway resolve
   `body.get("session_id") or stored_session_id or run_id`; mandar apenas
   `X-Hermes-Session-Id` cai no fallback e o histórico passa a ser o `run_id`. O
   cabeçalho `X-Hermes-Session-Key` é outra coisa: escopo de memória de longo prazo.
2. **Cancelar exige `POST /v1/runs/{id}/stop`.** Uma flag lida entre linhas do SSE não
   cancela nada enquanto o gateway está calado, que é a maior parte de um turno lento.
3. **O raciocínio não vem por HTTP.** `/v1/responses` e `/v1/runs` não transmitem
   `reasoning.delta`; o `reasoning.available` que existe ali é a *resposta* com as tags
   removidas. O pensamento real chega por um plugin do Hermes que escreve
   `%LOCALAPPDATA%\VoxFlow\reasoning\stream.jsonl`, lido por `hermes/reasoning.py`.
   Se o pensamento parar de aparecer, conferir primeiro
   `%LOCALAPPDATA%\hermes\plugins\voxflow-reasoning\` e
   `plugins.stream_reasoning_deltas: true`. **Não é `~/.hermes/plugins/`** — essa era a
   grafia errada que este arquivo trazia até a 0.7.10, e seguir por ela instala o plugin
   num lugar onde o Hermes não olha.

Antes de culpar o TTS ou a interface por um travamento, olhe `hermes_delta_gap` no log:
ele registra silêncios dentro de uma resposta. Uma investigação inteira já foi gasta
acusando o `edge-tts` de um engasgo que era do gateway — a medição (A/B do edge-tts, e a
interface animando no mesmo processo) inocentou os dois.

Não repita a suposição de que o histórico inchado vinha do corpo enviado: ele mede
585 bytes. O acúmulo era server-side, na cadeia `conversation` do `/v1/responses`.

## Onde as entregas ficam

`releases/fase-<fase>/<versao>/` — cada versão na própria pasta, com o instalador, o ZIP
do código e qualquer log ou nota daquela entrega. Não largue arquivos soltos na pasta da
fase: uma fase acumula correções e a pasta vira um monte onde não se distingue qual ZIP
acompanha qual instalador. O `scripts/build-release.ps1` já grava no lugar certo; ele
aceita fase fracionada (`-Phase 4.5`).

## Continuação visual já implementada

O `Estúdio do Orbe` está commitado (`b87af6b`) e vai em todos os instaladores desde a
0.7.3. Ele fica na aba homônima das configurações e
também pode ser aberto isoladamente com `scripts/preview_friday.py --studio`. A prévia
é ao vivo e usa os mesmos uniforms GPU do orbe principal; não remova essa ligação ao
alterar o editor. O modelo está em `src/voxflow/orb_settings.py` e o editor em
`src/voxflow/ui/orb_studio.py`. O próximo agente deve preservar seleção por estado,
`Todos juntos`, color pickers ao vivo, salvar/resetar e os controles de erupção e voz.

## Entrada de voz — um modo escolhido, não dois convivendo

Atenção se você leu uma versão anterior deste arquivo: até a 0.7.5 os dois modos
coexistiam, e o usuário rejeitou isso. Desde a 0.7.6 `hermes.listen_mode` **escolhe**:

1. `continuous` — a detecção de voz abre a gravação sozinha e o silêncio encerra o
   turno. É o comportamento original.
2. `push_to_talk` — `_hermes_tick` retorna antes de consultar o detector, **inclusive o
   de barge-in**: nesse modo, interromper também é trabalho da tecla.

O atalho de fala funciona nos **dois** modos, e isso foi pedido explicitamente: no
contínuo ele é reforço para ambiente barulhento ou pausa para pensar. Enquanto a tecla
está pressionada o endpointing não encerra nada — quem decide o fim do turno é a tecla.

Se for mexer nisso, as armadilhas já pagas:

- **A tecla é da Friday durante a sessão inteira, e isso é intencional.** Foi um
  pedido explícito do usuário: ele quer alcançá-la de dentro do editor de notas, sem
  passar pelo F9. Uma primeira versão limitou a posse ao tempo em que ela estava na
  tela e foi rejeitada. `set_talk_armed` é chamado uma vez em `start()`, a partir de
  `hotkeys.hermes_push_to_talk`; esvaziar essa chave devolve a tecla ao Windows.
- **Os atalhos são do usuário desde a 0.7.6.** Nada de constantes: `src/voxflow/keys.py`
  modela o acorde e `hotkeys.py` é dirigido por configuração. Não volte a fixar teclas.
- **Segurar a tecla com ela fechada tem que acordá-la e já gravar.** `toggle_hermes`
  sobe o serviço de forma assíncrona, então o clipe fica em `_pending_talk_clip` e é
  despachado quando `_on_gateway_result` confirma a subida. Sem isso, quem falasse
  rápido perderia o turno para o tempo de startup.
- **O key-up sempre precisa ser tratado**, mesmo se o modo foi desligado no meio da
  pressionada — senão a gravação fica aberta sem quem a feche.
- **Os callbacks da TTS podem chegar atrasados.** `_on_tts_started` e `_on_tts_idle`
  ignoram o período da tecla pressionada, porque uma frase já entregue ao player ainda
  reporta o fim depois de a Friday ter sido interrompida e sobrescreveria o estado.

As regras de posse da tecla vivem em `NativeHoldHotkey._handle_key`, separada do
callback do hook para poder ser testada sem um hook real (`tests/test_push_to_talk.py`).

## Tamanho da resposta

`hermes.instructions` teve um teto de "cerca de 120 palavras" da Fase 4 até 0.7.2. Foi
removido em 0.7.3: cortava explicações justamente quando o usuário pedia profundidade.
Se alguém reclamar de resposta curta demais ou longa demais, é esse texto que manda —
e ele também fica persistido no `config.yaml` do usuário, então mudar só o padrão do
código não alcança quem já tem o arquivo salvo.

## Distribuição para outras máquinas (0.7.5)

O app cresceu numa máquina onde tudo já estava no lugar. `src/voxflow/setup_check.py`
existe para descobrir isso em qualquer outra, e é sem Qt de propósito — a lógica é
testável e a janela (`ui/setup_wizard.py`) só a desenha.

Fatos que custaram para ser descobertos:

- **O plugin de raciocínio fica em `%LOCALAPPDATA%\hermes\plugins\`**, não em
  `~/.hermes/plugins/` como o README dizia até 0.7.5. Ele agora é versionado em
  `packaging/hermes-plugin/` e embarcado pelo PyInstaller.
- **Nada da máquina de origem viaja no instalador.** Config em `%APPDATA%\VoxFlow`,
  segredos no Credential Manager, e os defaults com `Path.home()` são resolvidos com
  `default_factory`, ou seja, na máquina de destino.
- **O modelo Whisper não é embarcado** (1,6 GB contra 100 MB de instalador). Ele é
  baixado na primeira transcrição porque `local_files_only` é falso quando o cache não
  existe. Se alguém reclamar de "primeira execução travada", é isso.
- **`cuda_dll_dirs` e `chatterbox_path` apontam para pastas do usuário original.**
  Diretório inexistente é ignorado sem erro, então não quebram nada — mas continuam
  errados em qualquer outra máquina.

Se for acrescentar um requisito ao assistente, mexa em `check_requirements` e marque
`optional` corretamente: opcional degrada um recurso, obrigatório remove um inteiro.
`general.setup_acknowledged` é o que impede a janela de reaparecer para algo que o
usuário já recusou — grave só o que ainda falta no momento do "Continuar assim mesmo",
nunca a lista inteira.

## Sondar o disco nunca pode derrubar o app (0.7.10)

**Leia isto antes de escrever qualquer código que olhe o cache do HuggingFace.**

Um snapshot do cache é feito de symlinks para `blobs`. O aplicativo **instalado** nem
sempre tem permissão para atravessá-los: o Windows responde `WinError 448`, "ponto de
montagem não confiável". E `Path.is_file()` do pathlib **não engole esse erro** — ele
ignora só um conjunto fixo, e o 448 não está nele.

Isso derrubou a 0.7.9 na abertura, e o projeto **já sabia disso**:
`faster_whisper_local._materialize_symlinks` existe exatamente por essa razão, e é por
isso que há uma cópia do modelo em `%LOCALAPPDATA%\VoxFlow\models`. A lição é essa: se
você encontrar uma função que parece redundante, descubra por que ela existe antes de
escrever algo que a ignore.

Regras que ficaram:

- Toda sondagem passa por `src/voxflow/fsprobe.py` (`is_file`, `is_dir`, `modified_at`),
  que respondem "não" em vez de levantar. Não chame os métodos crus em código que varre
  pastas do usuário.
- `discover()` pula a pasta que falhar e registra qual, em vez de abortar a lista.
- As chamadas em `settings.py` e `main.py` ficam dentro de `try`: a lista de modelos é
  conveniência e não pode ser o motivo de o app não abrir.
- Classificar continua funcionando mesmo sem seguir links, porque decide por **nomes de
  arquivo**. Só o `config.json` fica ilegível, e isso é reportado como tal — dizer
  "formato não reconhecido" seria mentira sobre o disco.

O ambiente de desenvolvimento **consegue** seguir os links, então esse bug não aparece
rodando pelo código-fonte. Os testes o simulam (`tests/test_models.py`).

## Modelos: o que entra e o que não entra (0.7.7 e 0.7.9)

`src/voxflow/models.py` classifica por evidência em disco, nunca por nome de
repositório — `openai/whisper-large-v3` parece servir para transcrição e o
faster-whisper não carrega, porque é Transformers e não CTranslate2.

O que decide é formato, não qualidade. Das listas de "melhores modelos PT-BR", só a
família Whisper é alcançável: Parakeet e Nemotron são NeMo, Qwen3-ASR e Voxtral são LLMs
de áudio. Habilitá-los exige um segundo backend de transcrição, que é entrega própria.

Whisper em formato Transformers é marcado como conversível, e
`scripts/add-stt-model.ps1` faz a conversão emprestando `transformers` e `torch` via
`uv tool run`. **Eles não são dependências do app de propósito**: juntos passam de 2 GB
e o instalador tem 100 MB. Não os adicione ao `pyproject.toml`.

Reconhecer não é oferecer: conversíveis e de outro runtime aparecem nomeados, com o
motivo, mas ficam fora do seletor porque nenhum carrega hoje.

## Voz: o seletor precisa mesmo trocar quem fala (0.7.8)

Por meses o seletor listava quatro providers e o código usava só o Edge. O usuário
percebeu sozinho. A costura agora é `hermes/synthesizers.py`: um provider tem um
trabalho só — escrever a frase num arquivo e reportar os tempos das palavras se souber.

- Só o Edge reporta limites de palavra. Para os demais, `estimate_word_timings`
  distribui as palavras **ancorado na duração real do clipe**, consultada no MCI depois
  de abrir o arquivo. Não troque isso por uma estimativa de palavras por minuto: o
  realce descolaria do áudio.
- Listas de voz não se misturam entre providers, nos **dois** lugares onde aparecem
  (Ajustes e a barra sob a Friday). Um nome do Edge não significa nada para o Windows.
- Provider indisponível aparece marcado com o motivo, em vez de sumir.

Chatterbox continua não integrado, e é viável: importa da pasta do usuário, torch com
CUDA disponível, `generate(text, audio_prompt_path=..., language_id=...)`. Falta um
processo persistente — carregar o modelo por frase inviabiliza conversa — e a "voz" dele
é um áudio de referência, não um nome. Meça a latência antes de prometer que serve para
conversa ao vivo.

## Estado das entregas

Fase 4 e 4.5 seguem **pendentes de aceite do usuário**, acumulando de 0.7.0 a 0.7.10.
A Fase 5 (comandos de voz de estudo, screenshot para o Hermes, log Markdown por sessão,
resumo ao fechar) está explicitamente travada esperando liberação — não comece sem ela.

## A porta 8642 não abre sozinha (0.7.12)

Ter o Hermes instalado não é ter a API local dele no ar. Três coisas, todas configuradas
à mão na máquina de origem e ausentes em qualquer outra:

1. `API_SERVER_ENABLED: true` — chave **de topo** no `config.yaml` do Hermes. Ausente
   numa instalação nova, e sem ela `hermes gateway run` não abre porta.
2. `API_SERVER_HOST` / `API_SERVER_PORT` — precisam bater com `hermes.base_url`.
3. `API_SERVER_KEY` no `.env` do Hermes — o VoxFlow manda `Authorization: Bearer` a
   partir do segredo `hermes`.

Sem eles o sintoma é "Hermes não respondeu após 60 segundos", que não diz a causa.
`src/voxflow/hermes/local_api.py` lê isso e o assistente reporta.

**Somente leitura, e isso é regra.** A configuração é de outro aplicativo. Já houve o
episódio de escrever `model.reasoning_echo` no `config.yaml` do Hermes e ter que
reverter. Reporte a linha exata a mudar; não edite.

Ao ler aquele arquivo, case as chaves em coluna zero — o `config.yaml` do usuário tem
centenas de linhas e uma chave aninhada de mesmo nome não pode ser confundida. E chave
ausente é `None`, nunca "ligado".

## Vozes locais e o que empacotar (0.7.13)

O Kokoro fala português offline: ~1,7 s na primeira frase (carga do modelo) e ~400 ms
nas seguintes. Ele chegou com três defeitos que valem como aviso permanente:

- **Nunca escreva um caminho absoluto com nome de usuário no fonte.** Havia
  `C:\Users\<nome>\.cache\...` gravado no código. Use `models.default_roots()`.
  `tests/test_kokoro.py` falha se um caminho de home voltar ao módulo.
- **Nunca instale dependência só no venv.** `build-release.ps1` começa com `uv sync`,
  que **remove** o que não está no `pyproject.toml`. O extra é `kokoro`, e o script
  precisa do `--extra kokoro`.
- **`available()` não pode ser caro.** A janela de Ajustes pergunta enquanto é montada,
  ou seja, na abertura. A sonda do Kokoro procura arquivos: 0,9 ms. Havia uma versão que
  carregava o ONNX inteiro ali.

E o que realmente quebrava não era nenhum dos três: `kokoro_onnx` lê o próprio
`config.json` em tempo de execução, e o spec não coletava esse dado. **Funcionava pelo
código-fonte e falhava só empacotado.** Ao adicionar qualquer biblioteca com arquivos de
dados, acrescente `collect_data_files` e teste o aplicativo instalado, não só o fonte.

### A janela que não voltava

Clicar no ícone com o aplicativo rodando não fazia nada: a segunda execução via o mutex
e retornava calada, enquanto a primeira estava numa bandeja que o Windows 11 esconde por
padrão. Existe agora um evento nomeado `SHOW`, irmão do `QUIT`, consumido uma vez por
pedido para a janela subir uma vez e não a cada tique.

### "Indisponível" dizia duas coisas

`Provider.status` separa `ready`, `needs_setup` (falta configurar nesta máquina) e
`not_implemented` (não existe código). O usuário leu "indisponível" no Chatterbox e
concluiu que faltava algo na máquina dele, quando faltava o código.

## O catálogo de vozes do Edge (0.7.14)

São 322 vozes em 75 idiomas, buscadas na Microsoft e guardadas em
`%LOCALAPPDATA%\VoxFlow\edge-voices.json`. **Nunca busque na thread do Qt** — é um segundo
de janela congelada; a busca vai para um executor e volta por sinal.

A lista abre nas 14 que falam português: as `pt-BR` **mais todas as multilíngues**, que
falam português independentemente do locale delas. As de Portugal ficam fora por pedido
explícito do usuário. Não mude esse agrupamento sem perguntar.

**Lição que custou caro:** as oito vozes anteriores foram escritas à mão, e uma delas
(`pt-BR-ThalitaNeural`) **não existia** — escolhê-la falhava na síntese sem explicação.
Não escreva identificadores de catálogo de memória; busque-os.

## Os documentos não podem ficar para trás

`tests/test_documentation.py` falha quando `CONTINUITY.md`, o checklist ou este arquivo
não mencionam a versão atual, e quando um provider de voz que funciona não está no
README. O `build-release.ps1` roda os testes antes de empacotar, então **não é possível
gerar instalador com documentação velha**.

Isso existe porque esquecer virou hábito, e o usuário cobrou mais de uma vez. CONTINUITY
e checklist eram atualizados por serem registro de entrega, enquanto este arquivo e o
README descrevem o presente — e toda mudança de comportamento os tornava falsos sem nada
falhar. Se você criar outro documento que descreva o estado atual, acrescente-o a esse
teste.


## O realce das palavras, e por que ele não é do provider de voz (0.7.16)

O realce cor-de-rosa corria na frente da voz. Quatro medições descartaram os suspeitos
naturais: o clipe do Kokoro tem 2% de silêncio nas pontas; este export ONNX não publica
durações (`has_timings=False`), então estimar é obrigatório; o estimador erra no máximo
140 ms; e o MCI reporta a posição em milissegundos, fiel ao relógio, em WAV e MP3.

O defeito era o acoplamento: o laço amostra a cada 40 ms e mandava o **texto** da palavra
toda vez, enquanto `Bubble.highlight_word` procura a **próxima** ocorrência. Uma palavra
de 200 ms era anunciada cinco vezes e o realce caminhava para os cinco "a" seguintes.
`SpeechCursor` anuncia por **índice**, uma vez por palavra. Valia igual no Edge — não era
do Kokoro.

Se for mexer no realce: a amplitude precisa continuar saindo a cada amostra, senão o orbe
perde o envelope. Só o nome da palavra é que sai uma vez.

## O modo de escuta mora em dois lugares (0.7.16)

`hermes.listen_mode` já existia desde a 0.7.6, mas só em Ajustes → Hermes. O usuário
procurou o controle na barra sob o orbe, ao lado da voz, não achou, e concluiu que a
funcionalidade não existia. Agora está nos dois lugares, com a mesma volta da voz: o
painel emite, Ajustes salva, e `saved` devolve ao painel.

Os controles da barra estão em **duas linhas** por medição, não por gosto: dois seletores
e dois botões pedem 542 px num painel de 470, com larguras fixas — numa linha só, o
último era cortado. `tests/test_listen_mode_panel.py` reprova quem voltar para uma linha.


## Fase 5 e a captura de tela (0.8.0)

`hermes/study.py` reconhece os comandos falados antes de enviar o turno, e escreve o log
Markdown da sessão. Duas armadilhas medidas, não supostas:

- **`/v1/runs` não aceita imagem.** O gateway resolve o input com
  `raw_input[-1].get("content", "")` e o histórico com `str(entry["content"])`. Só
  `/v1/responses` chama `_normalize_multimodal_content`. Não tente mandar imagem pelo
  runs.
- **A imagem enviada pelo `/v1/responses` não entra na sessão.** Conferido no `state.db`:
  nenhum traço. Ela vive no `response_store.db`. Por isso o padrão é pedir que a **Friday
  olhe com a ferramenta `computer_use` dela** — aí o turno, a chamada e a resposta ficam
  na sessão, aparecem no app desktop do Hermes e ela pode voltar ao assunto. Custa 170 s
  contra 10,5 s da captura local; a escolha é `hermes.screenshot_source`.

A conversa do VoxFlow **já** vive no mesmo `state.db` do app desktop, com
`source='api_server'`. A listagem de sessões só filtra por origem quando alguém pede.

`AppPaths.session_dir` agora pergunta ao Windows onde fica Documentos
(`SHGetKnownFolderPath`). `~/Documents` estava errado nesta máquina: o Documentos real é
`OneDrive\Documentos`, e a pasta antiga também existe — os logs iriam para onde ninguém
olha.


## A demora da Friday não é do VoxFlow (0.8.1)

Medido pelos carimbos de tempo da tabela `messages` do `state.db`: num turno de 170 s, as
ferramentas custaram 0,0 s e **uma única resposta do modelo levou 130 s**. Num teste
controlado, "Responda apenas: OK", sem ferramenta nenhuma, respondeu em 2,7 s e depois em
23,6 s — mesma frase, sessão nova, segundos depois. É o provedor do Hermes.

Por isso o padrão de `hermes.screenshot_source` é `voxflow`: a captura local é um único
turno de modelo (cerca de 10 s), enquanto pedir que ela olhe custa três ou mais.

Correção de um erro meu na 0.8.0: eu disse que a imagem enviada pelo VoxFlow não aparecia
no `state.db`. Aparece. O `/v1/responses` escolhe a sessão pelo cabeçalho
`X-Hermes-Session-Key`, não pelo campo `conversation` — então ela é gravada, só que numa
sessão diferente da usada pelo `/v1/runs`. É por isso que ela não lembra da imagem nos
turnos de voz seguintes.


## O link do cache do HuggingFace já mordeu três vezes (0.8.2)

`onnx/model.onnx` e afins são **links simbólicos** para `blobs`. O aplicativo instalado
nem sempre pode atravessá-los (WinError 448), e `fsprobe.is_file` responde "não" — o
modelo presente vira modelo ausente, sem erro visível. Aconteceu com o Whisper na Fase 2,
com `models.py` na 0.7.10 e com o Kokoro na 0.8.1.

Regra: **nunca carregue um modelo direto do cache do HuggingFace.** Materialize por
hardlink em `%LOCALAPPDATA%\VoxFlow\models\<nome>` e carregue de lá. E sonde o arquivo
físico (`_physical`), não o link.

Sintoma para reconhecer: o `--check` acha o modelo e o aplicativo em execução não.


## Prove a voz fazendo ela falar (0.8.3)

`voxflow --check-voices` sintetiza uma frase com cada provider disponível. Use-o **no
executável instalado**, não só pelo código: o Kokoro construía sem erro enquanto não
achava o modelo, e o Edge respondia sem tempos de palavra. Construir não é falar.


## Chatterbox roda fora do processo (0.8.4)

Ele tem ambiente Python próprio e 2 GB de torch: não é importável nem empacotável.
`packaging/chatterbox_worker.py` roda no Python dele e mantém o modelo carregado;
`hermes/chatterbox.py` conversa por stdin/stdout. Carga 10,5 s uma vez, 2,2 s por frase.

Armadilha: rodar um arquivo de script põe a pasta **do script** no `sys.path`, não o
`cwd`. A raiz do Chatterbox é passada como argumento e inserida no path — sem isso,
`import chatterbox` falha.


## Um processo filho herda o Python do pai (0.8.5)

O worker do Chatterbox (3.11) subia encontrando o `python312.dll` do VoxFlow empacotado e
morria com "Module use of python312.dll conflicts with this version of Python". Qualquer
processo externo iniciado pelo app precisa de `child_environment()`: sem `PYTHONHOME`,
`PYTHONPATH`, e sem a pasta do interpretador no `PATH`.
