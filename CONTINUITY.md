# VoxFlow — Continuidade do projeto

Atualizado em: 2026-09-08
Versão: 0.7.15
Fase concluída no código: Fase 4.5, aguardando aceite manual
Instalador mais recente gerado: 0.7.14 (`releases/fase-4.5/0.7.14/`)
Versão instalada nesta máquina: 0.7.13 — a 0.7.14 nunca foi instalada e a 0.7.15
ainda não tem instalador. O aceite da Fase 4.5 está pendente.

## Objetivo

Aplicativo Windows em tray com dois modos: ditado universal e estudo por voz integrado ao Hermes.
A implementação deve seguir, sem saltos, as fases da especificação em
`Arquivo Instruções VoxFlow.md`.

## Decisões confirmadas pelo usuário

- Projeto e produto: VoxFlow.
- Repositório Git local privado: `D:\Apps\WisprFlow`.
- Hotkey de ditado: `Ctrl+Numpad +` (`ctrl+num_add` internamente).
- Microfone preferido: SteelSeries Sonar, com seletor de dispositivo nas configurações.
- UI pt-BR; detecção automática de fala pt/en.
- Instalação por usuário, autostart habilitado e instalador inicialmente sem assinatura.
- LLM de limpeza pretendida: Muse Spark 1.3 Contributor via OpenCode GO; fallback por timeout para DeepSeek V4 Flash.
- Muse exige consentimento de uso dos dados para treinamento. O padrão seguro permanece `false` até aceite explícito na interface.
- Hermes poderá ser configurado na Fase 4 em `127.0.0.1:8642`, com segredo forte no `.env` do Hermes e no Windows Credential Manager para o VoxFlow.
- Modelos locais podem ser baixados quando necessário.
- A escolha final da melhor voz será a última atividade do desenvolvimento.

## Ambiente verificado

- Windows nativo; Hermes não roda no WSL2.
- Python 3.12.10, uv 0.12.9, Git e FFmpeg disponíveis.
- NVIDIA GeForce RTX 5070, 12 GB de VRAM.
- Hermes 0.21.0 em `C:\Users\vinig\AppData\Local\hermes`.
- Hermes é nativo, não WSL2. A API local foi habilitada em `127.0.0.1:8642` e uma chave
  forte foi gravada no `.env` do Hermes e no Windows Credential Manager, sem entrar no repo.
- Chatterbox pt-BR em `C:\AI\Chatterbox-Friday`, repositório
  `ResembleAI/Chatterbox-Multilingual-pt-br`, incluindo `s3gen_v3.pt`.
- Faster Whisper large-v3-turbo já está no cache Hugging Face em
  `C:\Users\vinig\.cache\huggingface\hub\models--mobiuslabsgmbh--faster-whisper-large-v3-turbo`.

## Fase 0 implementada

- Estrutura `src/voxflow` e namespaces previstos pela arquitetura.
- Configuração Pydantic/YAML com gravação atômica e campos desconhecidos proibidos.
- Segredos exclusivamente via keyring, serviço `VoxFlow`.
- Logs rotativos sem diagnóstico sensível.
- Diagnóstico `voxflow --check` para configuração e dispositivo de entrada.
- Testes unitários, Ruff e workflow de CI Windows.
- PyInstaller onedir/noconsole e Inno Setup.
- Script de release que produz ZIP do código e instalador separados.

Aceite manual recebido em 2026-09-06: instalação sem elevação, diretório correto,
diagnóstico e SteelSeries aprovados, e desinstalação removeu autostart. O reinício foi
explicitamente dispensado pelo usuário e permanece não testado.

## Fase 1 implementada

- Hotkey global nativa `WH_KEYBOARD_LL` para `Ctrl+Numpad +`, com press/release e supressão do `+`.
- Captura contínua 16 kHz mono int16 com pre-roll de 300 ms.
- Cancelamento abaixo de 400 ms ou RMS mínimo.
- Faster Whisper large-v3-turbo local, GPU float16 e fallback CPU int8.
- Reuso seguro dos DLLs CUDA presentes nas instalações locais de TTS.
- Injeção por clipboard com `SendInput` Ctrl+V, cinco tentativas e restauração após 150 ms.
- State machine `IDLE → RECORDING → TRANSCRIBING → INJECTING → IDLE`.
- STT e injeção executados em worker; loop Qt permanece livre.
- Instância única e comando/atalho `--quit` para encerramento controlado.
- Logs de `stt_ms`, `inject_ms` e `total_after_release_ms` sem registrar o conteúdo ditado.
- Empacotamento exclui o ICU 78 do Poppler exposto pelo ambiente Codex; o Qt usa a
  biblioteca compatível do Windows. O script de release falha se essas DLLs voltarem ao pacote.
- O instalador também remove `icuuc.dll` e `icudt78.dll` deixadas pela primeira build
  da Fase 1, garantindo correção ao atualizar por cima sem desinstalação manual.
- Logging de `--quit` ignora o sink de console quando o executável windowed não possui
  `stderr`, evitando falha no atalho “Encerrar VoxFlow”.

Aceite manual recebido em 2026-09-06. Ditado/STT e velocidade aprovados. O usuário
identificou que precisava pressionar `Ctrl+V`; ausência de `inject_ms` confirmou falha da
injeção automática, corrigida definitivamente na Fase 3 com a estrutura Win32 x64 completa.

## Fase 2 implementada

- Limpeza via OpenCode GO: Muse Spark 1.3 Contributor com consentimento e fallback por
  timeout/erro para DeepSeek V4 Flash; falha total preserva o texto bruto.
- Importação segura da chave já conectada no OpenCode para o Windows Credential Manager.
- Comandos locais “nova linha”, “novo parágrafo”, pontuação, “apaga isso” e “esquece isso”.
- Dicionário e snippets enviados ao limpador; snippets também expandem sem rede.
- Detecção do aplicativo ativo e regras por executável para tom, limpeza, espaço e injeção.
- Windows Terminal, PowerShell e CMD usam Unicode; clipboard cai para Unicode se falhar.
- Logs incluem `cleanup_ms`, provider/fallback, `inject_ms` e latência total sem conteúdo.

## UI emergencial adicionada após feedback de aceite

O usuário informou que a build 0.3.0 não inseria texto nem mantinha conteúdo no clipboard e
que era impossível testar sem UI. Os logs existentes não mostraram eventos da execução 0.3.0,
embora o processo instalado estivesse ativo e o executável tivesse o mesmo hash da build.

Para remover a caixa-preta, foi adicionada uma janela visível ao iniciar com:

- estado ao vivo: inicializando, pronto, ouvindo, transcrevendo, limpando e inserindo;
- a UI deve mostrar um preview de transcrição atualizado enquanto o atalho está pressionado;
  isso é separado da injeção, que só acontece depois que o atalho é solto;
- texto final, métricas, eventos e erros com abertura automática em falha;
- botão para copiar o texto final e botão para abrir a pasta de logs;
- ícone de bandeja com ações para reabrir a janela e encerrar o VoxFlow.

`main.py` agora usa `QApplication` e mantém a interface disponível inclusive quando a
inicialização do pipeline falha. Essa interface foi incorporada e ampliada na Fase 3.

Feedback de 2026-09-07: a UI funcionou, mas o STT falhou com `WinError 448` porque os arquivos
do snapshot Hugging Face são links simbólicos e o Windows bloqueou a travessia do ponto de
montagem no executável instalado. A primeira correção de materialização foi empacotada, mas não
foi acionada: ela também dependia de `.exists()`, que falha nesse mesmo link. A correção atual
seleciona o snapshot sem testar `model.bin` com `.exists()`, detecta o link com `os.path.islink`
e materializa o snapshot em `%LOCALAPPDATA%\VoxFlow\models\large-v3-turbo`, usando hardlinks
para os blobs físicos (cópia somente como fallback), eliminando reparse points sem duplicar
normalmente o modelo de 1,5 GB. A verificação local também encontrou um artefato incompleto de
5 bytes deixado pela tentativa anterior; o provider agora o rejeita e substitui quando o modelo
físico não tem tamanho plausível. O provider foi verificado contra o cache real e produziu
`model.bin` físico de 1.617.884.929 bytes. A build recompilada ainda precisa de aceite manual.

Importante: o usuário esclareceu que “escrita em tempo real” significa somente o preview dentro
da UI do VoxFlow, não texto sendo inserido no Notepad/Chrome enquanto fala. A injeção no aplicativo
ativo deve ocorrer apenas após soltar o atalho. A versão 0.4.1 implementa esse preview por
retranscrição periódica do áudio acumulado, em blocos de aproximadamente 900 ms, sem injetar
nenhum parcial no aplicativo ativo.

## Correções incorporadas na Fase 3

- `WinError 87` na inserção foi causado pela estrutura Win32 `INPUT` incompleta: sem
  `MOUSEINPUT`, `sizeof(INPUT)` era 32 em x64, mas `SendInput` exige 40. A união agora contém
  `MOUSEINPUT`, `KEYBDINPUT` e `HARDWAREINPUT`, com assinatura nativa e erro preservado.
- A janela ativa e o posicionamento do overlay agora declaram corretamente `HWND` de 64 bits.
- O preview parcial é gerado aproximadamente a cada 900 ms a partir de snapshots do áudio em
  gravação, no mesmo worker serial do STT. Ele aparece somente na UI/overlay; nunca é injetado.
- A interface mostra provider da limpeza, se houve fallback, motivo e se o texto mudou.
- Verificação real em 2026-09-07: Muse expirou após o timeout configurado; DeepSeek V4 Flash
  respondeu, removeu hesitação/repetição e pontuou corretamente a frase artificial de teste.
- Regras por aplicativo aceitam tanto os nomes internos `cleanup_enabled`/`inject_strategy`
  quanto os nomes documentados `cleanup`/`inject`.
- Logs passaram a gravar imediatamente, sem fila assíncrona que ocultava eventos da build.

## Fase 3 implementada

- Tray com status, modo, seleção de microfone, autostart, histórico, configurações e saída.
- Overlay inferior no monitor da janela ativa, com estado, nível do microfone, preview e cancelar.
- Configurações gráficas em abas Geral, Áudio, STT, Texto, Hermes e Histórico; segredos continuam
  fora do YAML. Mudanças de áudio/modelo exigem reiniciar; texto e preferências simples são
  aplicadas em execução quando o controlador está ocioso.
- Histórico SQLite local em `%LOCALAPPDATA%\VoxFlow\history.sqlite3`, com busca, cópia e limpeza.
- Autostart gerenciável pela UI via HKCU e sons não bloqueantes para início/fim/erro/cancelamento.
- `Esc` e o botão do overlay cancelam um ditado em gravação.
- Testes automatizados: Ruff aprovado e 22 testes aprovados em 2026-09-07.

### Correção 0.4.1 após primeiro aceite

O usuário viu “Texto bruto · Muse e DeepSeek indisponíveis”. A chave estava presente; o
executável instalado era idêntico à build e continha o certificado HTTPS. Uma chamada imediata
com a mesma configuração respondeu pelo Muse, confirmando indisponibilidade transitória, não
quebra de credencial ou endpoint. A fragilidade real era somente uma tentativa no DeepSeek e
nenhum detalhe na UI. A 0.4.1 tenta o DeepSeek uma segunda vez em erros transitórios e mostra
tipos seguros (`ReadTimeout`, conexão ou HTTP) no painel. Eventos visíveis também são enviados
ao log para garantir diagnóstico mesmo se um componente não registrar sua própria etapa.

O prompt pronto para a próxima IA está em `PROMPT_INICIALIZACAO_PROXIMA_IA.md`.

## Fase 4 implementada

- `F9` alterna entre Ditado e Hermes; o menu do tray oferece os mesmos modos.
- Máquina de estados `OFF → LISTENING → TRANSCRIBING → THINKING → SPEAKING → LISTENING`.
- Endpointing local por energia: fala sustentada por 300 ms e fim após 700 ms de silêncio.
- Cliente `httpx` para `/v1/responses`, histórico contínuo por `conversation`, chave Bearer no
  keyring e parsing incremental de `response.output_text.delta`/`response.completed`.
- Painel sempre no topo mostra a fala reconhecida e a resposta do Hermes conforme os deltas SSE.
- Edge TTS consome frases de aproximadamente 40 caracteres ou mais; playback Windows pode ser
  interrompido imediatamente, descartando a fila no barge-in.
- Half-duplex desativa a escuta durante a fala do Hermes para uso com caixas de som.
- Configurações incluem URL, chave protegida, sessão, prompt do tutor, voz, velocidade,
  half-duplex e botões de health/start/stop do gateway.
- Rede, STT, gateway e TTS ficam fora da thread principal do Qt. Logs incluem
  `ttfb_hermes_ms` e `tts_first_audio_ms`, sem conteúdo da conversa.
- A voz padrão provisória foi trocada para a feminina `pt-BR-ThalitaMultilingualNeural`; a escolha e o
  tuning da voz definitiva permanecem para o fim do projeto, conforme pedido do usuário.
- O endpointing usa um detector RMS leve nesta fase. `silero-vad` segue disponível como extra,
  mas não foi empacotado para evitar custo pesado sem evidência de necessidade na RTX 5070.
- Validação automatizada final em 2026-09-07: Ruff aprovado e 26 testes aprovados.
- O executável empacotado respondeu com código 0 ao diagnóstico `--check`.
- Entrega: `releases\fase-4\VoxFlow-0.5.4-fase-4-setup.exe`, ZIP de código no mesmo
  diretório e checklist em `docs\FASE_4_CHECKLIST_ACEITE.md`.

### Correção 0.5.1 após primeiro teste

O VoxFlow já verificava a porta 8642 e executava `hermes gateway run` quando ela estava
fechada. O primeiro teste mostrou que o Hermes 0.21.0 leva cerca de 15 segundos para carregar
as ferramentas, enquanto o app desistia após 8 segundos e escondia o painel. O limite passou
para 60 segundos; uma falha mantém o painel aberto com a causa e permite tentar novamente.
Também foi bloqueada a reativação tardia caso o usuário pressione F9 durante a inicialização.

### Correção 0.5.2 — pausas entre frases

O Edge TTS sintetizava e reproduzia cada frase sequencialmente, causando uma pausa longa em
cada ponto final. A síntese e o playback agora usam workers e filas separados: enquanto uma
frase toca, as próximas já são geradas. A ordem, o descarte no barge-in e a sinalização de fim
foram preservados. O log inclui `tts_gap_ms` para medir o intervalo real entre frases.

### Correção 0.5.3 — início da resposta

O histórico contínuo `voxflow:estudo` foi preservado por pedido explícito do usuário. Para
reduzir o tempo até a primeira voz, uma sentença completa agora é liberada ao TTS a partir de
12 caracteres, em vez de aguardar aproximadamente 40. Interjeições muito curtas continuam
agrupadas para evitar áudio fragmentado.

O instalador agora encerra graciosamente qualquer instância antiga antes de substituir os
arquivos. Antes disso, o pós-instalação podia abrir a nova versão, encontrar o mutex da versão
anterior e sair, deixando voz e código antigos residentes até um encerramento manual. O painel
mostra o nome da voz realmente carregada e o log registra `tts_speaker_ready` com a voz ativa.
As configurações oferecem um dropdown editável com Thalita e Francisca (femininas) e Antônio
(masculina); a troca é aplicada após reiniciar o VoxFlow.

### Correção 0.5.4 — contrato explícito de conversa

O histórico da Friday não é apagado nem recriado a cada execução. O valor existente
`voxflow:estudo` continua sendo usado como `conversation_id`, preservando a conversa nomeada
no Hermes. A configuração agora separa claramente:

- `session_key`: escopo de memória/autorização enviado no cabeçalho `X-Hermes-Session-Key`;
- `conversation_id`: identificador da conversa/histórico enviado no campo `conversation`;
- `input`: apenas a fala atual, estruturada como um turno `role=user` com conteúdo `input_text`;
- `instructions`: instruções do sistema/tutor, separadas do turno do usuário.

Isso segue a semântica normal da Responses API: o Hermes recupera os turnos anteriores pela
conversa nomeada e recebe a fala nova como uma mensagem distinta, sem prefixos ou bloco manual
de histórico. A UI de configurações expõe os dois identificadores com nomes diferentes. Para
começar uma conversa nova no futuro, basta escolher outro `conversation_id`; isso não apaga a
conversa antiga.

### Correção 0.5.5 — seletor de voz no painel ao vivo

O seletor de voz agora aparece diretamente no painel `VoxFlow — Hermes ao vivo`, e não apenas
em Configurações. A escolha emite um evento para a janela de configurações, salva a opção e
recria o speaker com a voz selecionada.

## Próxima fase — somente após OK do usuário

Fase 5: comandos de voz do modo estudo, screenshot para Hermes, log Markdown por sessão e
resumo/revisão ao encerrar. Não iniciar antes do aceite manual da versão 0.7.0.

## Restrições

- Nunca bloquear a thread principal do Qt.
- Não armazenar credenciais em YAML, logs, ZIP ou repositório.
- O fallback CPU da Fase 1 garante funcionamento, mas o empacotamento independente das DLLs CUDA continua previsto para a Fase 6.
- Não implementar fases futuras antes do OK explícito.
- Validar uma vez por entrega, proporcionalmente ao risco.
- Cada versão entregue mora na própria pasta, dentro da pasta da sua fase:
  `releases/fase-<fase>/<versao>/`. Uma fase acumula correções — só a Fase 4
  entregou nove versões — e uma pasta plana deixa de mostrar qual ZIP pertence a
  qual instalador. Logs de instalação e notas daquela versão vão junto, na mesma
  pasta. O `scripts/build-release.ps1` já grava assim.


## UI Friday — malha de pérolas e raios GPU (2026-09-07)

- Estado encontrado: `gpu.py` tinha mudanças locais do Opus na malha aleatória;
  README/continuidade ainda descreviam principalmente a Fase 4, sem este visual.
- Núcleo volumétrico preservado. Malha aleatória substituída por billboards de pérolas
  em anéis simétricos, com população proporcional à circunferência, halo e profundidade.
  Posições e ondas calculadas no vertex shader, sem atualização de partículas pela CPU.
- Repouso: respiração lenta; ouvindo: ondas suaves com entrada do microfone;
  pensando: bandas entrelaçadas; falando: expansão guiada pelo envelope já existente.
  Transições de 1,15 s, fase contínua e suavização de áudio independente do FPS.
- Raios triangulares substituídos por faixas suaves no fragment shader, em buffer
  separado de 384 px. Origem acompanha o centro real da esfera nas duas janelas.
- Esfera maior no painel principal e no painel Hermes. O restante do fundo e composição
  continua em Qt/QPainter: não afirmar que toda a interface é desenhada na GPU.
- Fala usa tempos das palavras do Edge TTS, não análise PCM/espectral; sem tempos,
  o mecanismo anterior usa cadência sintética. Integração de voz não foi alterada.
- Prévia interativa: `.venv/Scripts/python.exe scripts/preview_friday.py`.
  Botões alternam os estados; áudio SIMULADO, sem microfone, Hermes ou rede.
  `--capture` salva imagens da janela real em `build/friday-preview`.
- Verificação: shaders renderizados em OpenGL 3.3, imagens inspecionadas; 16 testes
  existentes de UI/sincronia/balões passaram, Ruff passou. Sem teste ao vivo de TTS.
- Alterações estão no código-fonte; instalador/executável de releases não foi refeito.

### Refinamento pela referência de superfície fluida

Malha ampliada para 72 anéis e até 144 pontos por anel (cerca de 6,6 mil pontos).
Três ondas contínuas sobre a esfera e uma corrente tangencial limitada deformam
a superfície sem dispersar os pontos. Tamanho individual reduzido para manter
a separação visual; hemisfério traseiro atenuado. Núcleo preservado.
Capturas dos quatro estados renderizadas em OpenGL e imagem inspecionada.
Prévia interativa atualizada; áudio continua simulado nessa prévia.

Refinamento seguinte: 112 anéis / até 224 pontos por anel (~16 mil pontos), frequência espacial das ondas aumentada e altura reduzida em cerca de 70%. Corrente tangencial e expansão por áudio também reduzidas para preservar a silhueta esférica. Captura GPU conferida; prévia atualizada.

Ajuste pontual: brilho das pérolas integrado sobre a área do pixel (Gaussianas com footprint por derivadas) para reduzir cintilação subpixel. Núcleo 15% mais rápido. Shaders renderizaram com sucesso; melhora perceptiva das piscadas ainda depende da observação em movimento pelo usuário.

## Visual aprovado e entrega 0.6.0

Usuário aprovou explicitamente a malha final e o núcleo. Velocidade final da
nebulosa: multiplicador 2,30 no tempo do volume (substitui o ajuste de 15%).
Malha preservada após o aceite. Autorizada a geração/publicação do instalador
local e salvamento das alterações. Não há remoto Git configurado.

## 0.6.1 — interação de voz e mouse

- Orbe F9: 240 → 360 px (50% maior).
- Ondas extras emitidas pelo envelope de voz; intensidade proporcional à entrada,
  propagação pela superfície, limite de deformação e dissipação no silêncio.
- Movimento e intensidade originais de repouso preservados por pedido explícito.
- Mouse: ondulação local e atração delicada na face frontal, posição e força suavizadas,
  retorno ao sair. Sem alterar o comportamento de clique do F9.
- Processamento das deformações permanece no vertex shader; CPU envia quatro pulsos
  e a posição do cursor. Voz TTS continua usando tempos de palavras, não volume PCM.
- Prévia: acrescentar `--conversation` para ver o painel real F9, com áudio simulado.
- 46 testes passaram; Ruff passou; shaders OpenGL renderizados e captura F9 inspecionada.

Controles F9 (voz, ajustes, ocultar) agora alternam por clique no orbe.
Hover não mostra controles. Layout reserva a altura da linha oculta para que
a conversa e o orbe permaneçam imóveis ao revelar/esconder os botões.

Prévia agora inicia com áudio simulado DESLIGADO; botão Simular voz permite
ativá-lo explicitamente. Ciclo sintético (~2,7 s) não pertence ao app instalado.

## 0.6.2 — moldura, movimento e tamanho das janelas

- Janelas com pintura própria não solicitam borda, backdrop ou arredondamento extra
  do DWM. Contorno arredondado do Qt permanece como único desenho da borda.
- WindowInteraction compartilhado: arrastar fundo vazio/topo; redimensionar pelas
  bordas/cantos com cursores apropriados, captura do mouse e tamanho mínimo.
- F9 sem largura/altura fixas; posicionamento automático apenas na primeira abertura,
  preserva posição/tamanho nas seguintes durante a sessão. Orbe acompanha o tamanho.
- Testes de redimensionamento ancorado, limites, movimento por eventos de mouse e
  reabertura passaram. Corrigida entrega de eventos durante descarte de objetos Qt:
  event filters globais precisam tolerar atributos do dono já liberados.
- Controles por clique e reação da malha preservados. Verificação visual da borda
  nativa no desktop ainda depende da observação do usuário.
## 0.7.0 — Pensamento visível e a conversa que parou de travar (2026-09-07)

Esta entrega troca o endpoint usado para falar com o Hermes e passa a mostrar o
raciocínio da Friday ao vivo. O modo Ditado não foi tocado.

### O sintoma que iniciou tudo

O usuário relatou dois travamentos que "antes nunca aconteciam": ela ficava presa
em "pensando", ou falava quase toda a resposta, omitia a última frase e ficava presa
em "falando" sem dizer nada. O usuário recusou, com razão, a primeira proposta de
mitigação (timeouts para pular o que travasse) e exigiu a causa raiz.

### O que a investigação encontrou, com evidência

O diagnóstico só ficou correto depois de descartar três suspeitos por medição:

- **Não era o `edge-tts`.** Um teste A/B alternado entre `communicate.save()` e o
  `_collect()` deste projeto deu bytes de áudio idênticos e zero travadas em 14
  chamadas. Uma troca feita na 0.6.0 (para capturar `WordBoundary`) parecia culpada
  pela coincidência de datas, e não era.
- **Não era a interface.** Com as duas janelas animando no mesmo processo, a síntese
  manteve mediana de 1154 ms e zero travadas em 12 chamadas.
- **Era o gateway.** O log mostrou dois silêncios de 110 s *dentro da mesma resposta*,
  sem nenhum turno novo entre eles. E o tempo até o primeiro token subiu sozinho ao
  longo do dia: 6,0 s → 16,5 s → 42,1 s → 28,2 s, com respostas chegando a 71 s.

A causa: `response_store.db` do Hermes tinha 21,5 MB, e a maior resposta guardada
tinha 4,83 MB — dos quais 4,827 MB eram `conversation_history`, com `reasoning` e
`reasoning_content` gravados **em dobro** (674 KB cada) contra 432 KB de conversa real.
A cadeia `conversation` do `/v1/responses` acumulava tudo e reenviava a cada turno.
O VoxFlow **não** enviava esse histórico: o corpo medido era de 585 bytes.

### O pensamento: por que não aparecia, e como aparece agora

`/v1/responses` e `/v1/runs` não transmitem raciocínio. O evento `reasoning.available`
que existe ali é derivado: `agent/turn_response_intake.py` pega o *texto da resposta*,
remove as tags `<think>`/`<reasoning>` e envia os primeiros 500 caracteres — por isso
o texto chegava idêntico à resposta.

O raciocínio real é emitido como `reasoning.delta`, e apenas por quem registra um
`reasoning_callback`. O servidor HTTP não registra nenhum. O app desktop do Hermes vê
porque fala outro protocolo: JSON-RPC sobre WebSocket, em `/api/ws`, servido por
processos `hermes serve` **efêmeros** que o próprio desktop cria — porta aleatória e
token rotativo, o que torna esse caminho inviável para o VoxFlow.

A solução veio de uma consulta ao próprio Hermes, que apontou um hook oficial que
esta investigação não tinha encontrado: com `plugins.stream_reasoning_deltas: true`,
todo delta de raciocínio é enfileirado para plugins com `kind="reasoning"`
(`agent/stream_delivery.py`). O gate `wants_reasoning` já era verdadeiro no caminho
HTTP, porque o api_server passa `stream_delta_callback` — o delta já era produzido e
simplesmente descartado.

### O que existe agora

**Do lado do Hermes** (fora deste repositório, instalado e validado):

- `~/.hermes/plugins/voxflow-reasoning/` — plugin que escreve cada delta como uma
  linha JSON.
- `plugins.enabled: ["voxflow-reasoning"]` e `plugins.stream_reasoning_deltas: true`.

**Contrato do arquivo**, em `%LOCALAPPDATA%\VoxFlow\reasoning\stream.jsonl`:

```json
{"ts":..., "session_id":"voxflow:estudo", "turn_id":"...", "iteration":1,
 "kind":"reasoning", "delta":"..."}
```

Um arquivo único, não um por sessão: ids de sessão contêm dois-pontos
(`voxflow:estudo`) e o Windows proíbe isso em nome de arquivo. O plugin escreve o
raciocínio de **todas** as sessões do gateway (Discord, cron, etc.), então filtrar por
`session_id` do lado do VoxFlow é obrigatório. Rotação automática em 1 MiB.

**Do lado do VoxFlow:**

- `hermes/reasoning.py` — segue o arquivo, filtra por sessão, descarta linhas com
  `kind` diferente de `reasoning` (o hook também carrega a resposta, que já chega por
  SSE) e agrupa por `turn_id`. Rotação é detectada por inode, não por tamanho: um
  arquivo novo que já cresceu além do offset antigo é indistinguível de conteúdo
  acrescentado — um teste pegou isso antes de chegar no app.
- `ui/conversation.py` — cada bloco de raciocínio vira um balão próprio, menor e mais
  apagado, acima da resposta. Um turno que pensa, chama uma ferramenta e pensa de novo
  aparece como dois balões, não um parágrafo só.

### A migração para `/v1/runs`

`hermes/client.py` ganhou `stream_run`, ao lado do `stream_response` existente. A
chave `hermes.use_runs_api` escolhe entre os dois; o padrão é o caminho novo.

- **`session_id` vai no corpo**, não no cabeçalho. `api_server_runs.py` resolve
  `body.get("session_id") or stored_session_id or run_id`; mandar só o cabeçalho cai
  no fallback e o histórico vira o `run_id`. O cabeçalho `X-Hermes-Session-Key` existe
  mas é outra coisa: escopo de memória de longo prazo.
- **Cancelamento de verdade.** `stop_active_run()` faz `POST /v1/runs/{id}/stop` a
  partir da thread que cancela. Antes, a flag de cancelamento só era lida entre linhas
  do SSE, então um turno interrompido continuava enquanto o gateway estivesse calado —
  no log, quinze segundos depois de um barge-in — segurando um dos dois workers do
  pool. Dois desses e o app ficava em "pensando" para sempre.
- **Pool separado para controle.** Parar, health e start/stop do gateway não disputam
  mais lugar com um turno em andamento.

Medições contra o gateway real: aceite do run em 212 ms; primeiro token em 11,5 s
contra 28,2 s na conversa encadeada; `stop_active_run` retornou em 184 ms e o worker
foi liberado 249 ms depois.

### Instrumentação nova

- `hermes_delta_gap hermes_delta_gap_ms=` — silêncio de 2 s ou mais **dentro** de uma
  resposta. Antes só existia o primeiro delta e o fim, então um engasgo no meio era
  invisível e se manifestava como pausa entre frases faladas, o que parecia (e não era)
  falha de síntese.
- `hermes_response_completed` agora carrega `worst_delta_gap_ms`.
- `hermes_run_started ... accepted_ms=` — o aceite quase imediato do run.
- `hermes_run_stopped` / `hermes_run_stop_failed`.

### Um engano corrigido

Durante a investigação foi adicionado `model.reasoning_echo: true` ao
`~/.hermes/config.yaml` na crença errada de que aquilo controlava a exibição do
raciocínio. Não controla: `agent/message_sanitization.py` mostra que é política de
reenvio para as famílias `kimi`/`deepseek`/`mimo`, que devolvem 400 se o
`reasoning_content` não voltar no wire. O provider em uso (`opencode-go`) não está
nessa tabela. **A chave foi removida.** Backup em
`config.yaml.bak.pre-reasoning-echo-20260907_111306`.

### 0.7.1 — o pensamento chegava atrasado

Sintoma relatado: durante uma sessão longa, raciocínio do início da conversa aparecia
no fim, em rajada, num momento de silêncio. A hipótese natural — o leitor reprocessando
o arquivo — estava errada e foi descartada por medição: zero linhas duplicadas, zero
timestamps fora de ordem, um bloco contíguo por turno.

A causa estava na renderização. O raciocínio chega em deltas do tamanho de um token:
uma sessão real gravou 11.651 deltas de 8,3 caracteres em média, e o pior turno sozinho
teve 3.178 deltas somando 32.944 caracteres num único balão. Cada delta redesenhava o
balão inteiro — escapando todo o texto acumulado, medindo cada linha, redimensionando —
o que custa 2 ms com ele vazio e 51 ms com ele cheio. Custo quadrático, na thread que
também pinta o cosmos e o orbe.

Reproduzindo o pior turno real: 13,78 s de trabalho de interface um delta por vez,
contra 0,44 s agrupado — 106 redesenhos em vez de 3.178.

Correções: o leitor junta os deltas e os libera a cada 120 ms, forçando a liberação na
troca de bloco para que um turno nunca se misture ao seguinte; e o balão de pensamento
mantém apenas a cauda do texto, já que ninguém lê dezenas de milhares de caracteres num
painel flutuante.

Observado de passagem: o plugin rotaciona o arquivo por rename a cada 1 MiB, e uma
sessão de 79 minutos gerou 2,18 MB em três arquivos. O leitor acompanha a rotação pelo
inode.

### Riscos conhecidos desta entrega

- O histórico passa a vir do `state.db` por sessão, em vez da cadeia de respostas
  armazenadas. Foi validado que a Friday cita o turno anterior sem histórico no corpo,
  mas **a primeira conversa real deve confirmar que ela ainda lembra**. Se não lembrar,
  desligar `use_runs_api` em Ajustes → Hermes devolve o comportamento anterior.
- O `response_store.db` de 21,5 MB continua no disco. O caminho novo não o alimenta
  mais, mas ele não foi limpo.
- As conversas `voxflow:probe-*` criadas durante a investigação ficaram no `state.db` e
  podem ser removidas quando conveniente.

## 0.7.2 — Estúdio do Orbe (2026-09-07)

O estúdio de personalização pedido pelo usuário foi concluído no código-fonte, sem
commit e sem atualizar o executável instalado. A aba `Estúdio do Orbe` aparece em
`SettingsWindow` e mantém um preview GPU vivo com:

- seleção de um estado (`Repouso`, `Ouvindo`, `Transcrevendo`, `Pensando`, `Falando`,
  `Entregando texto`, `Erro`) ou `Todos juntos`;
- prévia independente, simulação de fala, nível manual e fonte `Microfone do app`;
- núcleo (fluxo, turbulência, tamanho, foco, energia, branco, bloom e correntes),
  erupções (intensidade, alcance, velocidade e frequência), malha (amplitude,
  velocidade, frequência, tamanho/luz/branco das bolinhas e hover) e reação à voz
  (ganho, ondas, limiar, ataque, release e intervalo);
- três color pickers com atualização enquanto a cor é arrastada;
- `Salvar orbe`, `Voltar ao salvo` e `Restaurar padrão`, com persistência por estado.

`src/voxflow/orb_settings.py` é o modelo persistido, com limites seguros e migração de
estados ausentes. `src/voxflow/ui/orb_studio.py` implementa o editor. `gpu.py` recebe
os perfis como uniforms reais do raymarch e da malha; `orb.py` publica o perfil ao vivo;
`settings.py`, `main.py`, `config.py` e `app.py` completam a integração, inclusive os
parâmetros de endpointing do áudio. `scripts/preview_friday.py --studio` abre um
estúdio isolado que não grava a configuração do usuário.

Validação desta continuação: Ruff aprovado, 69 testes aprovados, `voxflow --check`
aprovado, shaders OpenGL 3.3 renderizados e imagem customizada diferente da imagem
base confirmada. A prévia interativa do estúdio foi deixada aberta para observação.
Ainda falta apenas o aceite visual do usuário e, se ele pedir, a geração de um novo
instalador; nenhuma entrega instalada foi alterada.

## 0.7.3 — Push-to-talk da Friday e resposta sem teto (2026-09-07)

### Push-to-talk

Segurar o `+` do teclado numérico grava e, ao soltar, envia para a Friday. Convive com
a detecção de voz existente: o modo mãos-livres continua funcionando, e a tecla é um
atalho por cima dele para quando o ambiente tem ruído ou a pausa para pensar seria
cortada pelo endpointing.

Três regras definem o comportamento, todas pedidas pelo usuário:

- **A tecla só é da Friday enquanto ela está na tela.** Fora de uma conversa o `+`
  digita normalmente. `NativeHoldHotkey.set_talk_armed()` liga e desliga essa posse, e
  `_set_hermes_state` a mantém sincronizada com o estado do Hermes.
- **Toque menor que 1 s é descartado.** Medido pela tecla, não pelo clipe: a detecção
  de voz pode ter aberto a gravação antes da tecla descer. Ajustável em
  `hotkeys.hermes_push_to_talk_ms` (padrão 1000, faixa 200–5000).
- **Sem voz, nada é enviado.** Mesmo teste de RMS do ditado
  (`audio.minimum_rms`), com a Friday voltando a ouvir sem gastar um turno.

Detalhes que exigiram cuidado:

- Enquanto a tecla está pressionada, `_hermes_tick` retorna cedo. Sem isso o
  endpointing encerraria o turno na primeira pausa para pensar.
- `_on_tts_started` e `_on_tts_idle` também ignoram o período da tecla pressionada.
  Apertar `+` durante a fala interrompe a Friday, mas uma frase já entregue ao player
  ainda reporta o fim e sobrescreveria o estado da gravação em andamento.
- Apertar `+` fora de `LISTENING` é uma interrupção: cancela o turno em voo pelo mesmo
  caminho do barge-in (`_abandon_hermes_turn` + `speaker.interrupt`).
- `Esc` durante a pressionada descarta a gravação e engole o key-up seguinte, para não
  deixar um `+` solto na janela ativa.
- Se o modo Hermes for desligado com a tecla ainda pressionada, o key-up continua sendo
  tratado; caso contrário a gravação ficaria aberta sem quem a fechasse.

As regras de posse da tecla ficam em `NativeHoldHotkey._handle_key`, separada do
callback do hook justamente para poder ser testada sem um hook real do Windows.

### Resposta sem teto de palavras

`hermes.instructions` dizia "prefira respostas curtas ... e limite-se a cerca de 120
palavras". Foi escrito na Fase 4, quando a Friday só respondia falando. Depois que ela
passou a escrever arquivos de estudo, o teto passou a cortar explicações justamente
quando profundidade era o que se pedia. O texto novo mantém a resposta adequada à voz
e deixa o tamanho por conta da pergunta.

O `config.yaml` ativo do usuário também foi atualizado (backup em
`config.yaml.bak.pre-ptt`), porque o valor antigo já estava persistido lá e o novo
padrão sozinho não o alcançaria.

### Arquivos alterados

`src/voxflow/hotkeys.py`, `src/voxflow/app.py`, `src/voxflow/config.py`,
`tests/test_push_to_talk.py` (novo), `tests/test_push_to_talk_rules.py` (novo).

Validação: Ruff aprovado, 83 testes aprovados.

## 0.7.4 — A tecla da Friday é global (2026-09-07)

Correção de uma decisão errada em 0.7.3. Naquela versão eu limitei a posse do `+` do
numpad ao tempo em que a Friday estava ativa, para não tirar a tecla do usuário no
Windows inteiro. O usuário rejeitou: ele **quer** a tecla tomada, porque o objetivo é
falar com ela de dentro do editor de notas, sem passar pelo F9 antes. O `+` que ele
usa para digitar é o da tecla que divide com `=`, no teclado principal, que nunca foi
tocado (`VK_OEM_PLUS`, diferente de `VK_ADD`).

O que mudou:

- `set_talk_armed` passou de `_set_hermes_state` (por estado) para `start()` (uma vez,
  pela configuração). Esvaziar `hotkeys.hermes_push_to_talk` devolve a tecla ao Windows;
  é a única saída, e é intencional que seja explícita.
- **Segurar a tecla com a Friday fechada agora a acorda e já grava.** `_on_talk_pressed`
  chama `toggle_hermes()`, que já estava ligado a `conversation.present()` em
  `main.py` — a janela abre sozinha e o microfone abre no mesmo gesto.
- Como a subida do serviço é assíncrona, quem fala rápido soltaria a tecla antes de ela
  estar de pé. O clipe fica em `_pending_talk_clip` e `_on_gateway_result` o despacha
  quando a subida confirma. Se a subida falhar, o clipe é descartado junto.
- Se a tecla ainda estiver pressionada quando a subida terminar, a gravação em curso
  continua direto para o turno, sem reiniciar.
- Um `+` segurado com um ditado ainda em voo é recusado, pela mesma razão que
  `toggle_hermes` já recusava: os dois caminhos disputariam o mesmo microfone.

### Uma armadilha que o teste pegou

O primeiro stub de `_enter_hermes_listening` nos testes só registrava a mensagem, sem
mudar o estado — e o teste "ainda segurando quando ela termina de subir" falhou. Era
artefato do stub, não do código, mas mostrou que o fluxo depende de entrar em
`LISTENING` para sair de `STARTING`. O stub agora espelha isso.

### Arquivos alterados

`src/voxflow/app.py`, `tests/test_push_to_talk.py`, `tests/test_push_to_talk_rules.py`,
`README.md`, `PROMPT_INICIALIZACAO_PROXIMA_IA.md`.

Validação: Ruff aprovado, 90 testes aprovados.

## 0.7.5 — Assistente de primeira execução e plugin versionado (2026-09-07)

Motivada por uma pergunta do usuário: dá para mandar o instalador para um amigo? A
auditoria encontrou coisas que eram verdade só na máquina de origem.

### O plugin de raciocínio não existia em lugar nenhum versionado

Ele estava apenas em `%LOCALAPPDATA%\hermes\plugins\voxflow-reasoning\`, na máquina do
usuário. Não estava no repositório, nem no instalador, nem em backup. Um disco perdido
levava junto. Agora vive em `packaging/hermes-plugin/voxflow-reasoning/` e é embarcado
pelo PyInstaller em `hermes-plugin/`.

`tests/test_setup_check.py::test_the_plugin_is_vendored_in_the_repository` roda contra
o arquivo real, então uma entrega que esquecer de versioná-lo falha aqui e não na
máquina de outra pessoa.

### O README apontava o caminho errado do plugin

Dizia `~/.hermes/plugins/`. O correto é `%LOCALAPPDATA%\hermes\plugins\`. Quem seguisse
a documentação instalaria no lugar errado e não teria como descobrir por quê.

### O caminho do Hermes era imutável

`gateway_executable()` tinha o caminho fixo. Se o Hermes estivesse em outro lugar, não
havia nada a fazer pela interface. Agora existe `hermes.executable_path` (vazio = local
padrão) e o assistente tem um seletor de arquivo.

### O assistente

`src/voxflow/setup_check.py` responde o que falta, sem Qt, e por isso é testável:
Hermes, plugin (`ok`/`outdated`/`missing`/`unavailable`), microfone e chave do
`opencode_go`. `src/voxflow/ui/setup_wizard.py` desenha isso sobre `CosmicPanel`, com
os reparos: procurar o `hermes.exe`, instalar o plugin, escolher o microfone e guardar
a chave no Credential Manager.

Aparece em `main.py` antes de `controller.start()` — antes do microfone abrir e dos
atalhos entrarem no ar — e só quando falta algo que o usuário ainda não dispensou.
`general.setup_acknowledged` guarda o que foi dispensado; o assistente volta se algo
**novo** faltar, e não repete o que já foi recusado.

Requisitos são marcados `optional` quando degradam um recurso (plugin, chave, microfone
diferente do configurado) e obrigatórios quando removem um inteiro (Hermes ausente,
nenhum microfone). O microfone continua caindo no primeiro dispositivo disponível — o
assistente só passou a dizer isso em voz alta em vez de trocar em silêncio.

### Efeito colateral útil

`_resolve_api_key` do `DictationCleaner` virou `resolve_opencode_key(secrets)` no nível
do módulo, porque o assistente precisa saber se a chave existe sem construir um cleaner.

### Arquivos alterados

`src/voxflow/setup_check.py` (novo), `src/voxflow/ui/setup_wizard.py` (novo),
`packaging/hermes-plugin/voxflow-reasoning/` (novo), `src/voxflow/main.py`,
`src/voxflow/config.py`, `src/voxflow/app.py`, `src/voxflow/hermes/gateway.py`,
`src/voxflow/text/cleanup.py`, `packaging/voxflow.spec`,
`tests/test_setup_check.py` (novo), `README.md`.

Validação: Ruff aprovado, 105 testes aprovados, assistente renderizado (665×560) com as
quatro linhas corretas numa máquina simulada sem Hermes e sem plugin.

## 0.7.6 — Modo de escuta e atalhos do usuário (2026-09-07)

Quatro correções pedidas pelo usuário sobre o push-to-talk de 0.7.3–0.7.5.

### 1. Push-to-talk virou modo, não só um botão

Era uma adição ao detector de voz: a tecla funcionava, mas a Friday continuava ouvindo
sozinha o tempo todo, o que anulava o propósito. Agora `hermes.listen_mode` escolhe
entre `continuous` e `push_to_talk`, em Ajustes → Hermes. No modo push-to-talk,
`_hermes_tick` retorna antes de consultar o detector — inclusive o de barge-in, porque
interromper também passa a ser trabalho da tecla.

### 2. A tecla continua útil no modo contínuo

Não é desativada: vira reforço para ambiente barulhento ou pausa para pensar. Foi
pedido explicitamente, e há teste para isso.

### 3. Atalhos configuráveis

`src/voxflow/keys.py` (novo) é o modelo: `Hotkey`, `parse`, `matches`, `contains`,
tabela de nomes de virtual-key e `types_text`. `hotkeys.py` foi reescrito em cima de
`_Hold`/`_Tap` dirigidos por configuração, em vez de constantes. `ui/hotkey_edit.py`
(novo) captura o acorde pressionando as teclas, e a aba **Atalhos** reúne os quatro
atalhos mais o mínimo da pressionada.

`matches` exige que os modificadores batam **exatamente**; sem isso `num_add` dispararia
junto com `ctrl+num_add` e os dois nunca poderiam coexistir na mesma tecla.

### 4. Só engole a tecla se ela escreveria sozinha

Regra do usuário: `Hotkey.steals_typing` é verdadeiro apenas para tecla sem modificador
que produz texto. Um acorde passa direto para o aplicativo em foco, então usar `ctrl+a`
não custa o Ctrl nem o "selecionar tudo".

**Consequência que o usuário precisa avaliar:** o padrão do ditado é `ctrl+num_add`, que
agora **não é mais suprimido**. Em navegadores e editores, `Ctrl` com `+` é zoom, então
ditar pode dar zoom na página junto. A regra foi implementada como pedida e isto está
sinalizado; inverter é trocar um predicado.

### Um bug que o teste pegou

`Esc` durante um acorde nunca cancelava: `matches` exige modificadores exatos, e
segurando `ctrl+a` o Ctrl está necessariamente pressionado. Daí `contains`, que tolera
modificadores presos por outro motivo, usado só para o cancelamento.

### Arquivos alterados

`src/voxflow/keys.py` (novo), `src/voxflow/ui/hotkey_edit.py` (novo),
`src/voxflow/hotkeys.py` (reescrito), `src/voxflow/app.py`, `src/voxflow/config.py`,
`src/voxflow/ui/settings.py`, `tests/test_push_to_talk.py` (reescrito),
`tests/test_push_to_talk_rules.py`, `README.md`.

Validação: Ruff aprovado, 121 testes aprovados, aba Atalhos renderizada e ciclo
salvar/ler conferido (`ctrl+a`, `f8`, 1500 ms, `push_to_talk`).

## 0.7.7 — Seleção de modelos por compatibilidade (2026-09-07)

O campo "Modelo" do STT era texto livre com `large-v3-turbo` escrito à mão. O usuário
tem nove modelos no cache do HuggingFace e queria escolher entre eles — mas só entre os
que aquele lugar consegue carregar.

### Classificação por evidência, não por nome

`src/voxflow/models.py` (novo) olha o que cada pasta realmente contém:

| Formato | O que denuncia |
|---|---|
| `stt_faster_whisper` | `model.bin` + `vocabulary.*` (formato CTranslate2) |
| `tts_qwen3` | `config.json` com `model_type` contendo `tts` |
| `tts_chatterbox` | checkpoints `t3_*` **e** `s3gen*` |
| `audio_separation` | receita `.yaml` do Demucs |
| `unknown` | qualquer outra coisa |

Nome de repositório não decide nada de propósito: `openai/whisper-large-v3` parece
servir para transcrição e o faster-whisper não carrega — é Transformers, não
CTranslate2. Há teste para exatamente esse engano.

Metade de um Chatterbox (só `t3_*`, sem `s3gen*`) é reportada como incompleta em vez de
oferecida, porque falharia no carregamento sem nada legível para ler.

### Na interface

Aba STT: "Modelo instalado" lista só os compatíveis, com tamanho, mais "Outro
(informar manualmente)" para baixar por nome numa máquina sem cache. Os campos de nome
e pasta ficam desabilitados quando um modelo da lista está escolhido, para não
divergirem dele. Uma nota diz quantos foram encontrados e por que os outros não servem
— era o "como saber o que é compatível" que o usuário perguntou.

`activated` e não `currentIndexChanged`: o segundo dispara ao reconstruir a lista e
reescreveria a configuração sem ninguém ter escolhido nada.

Varredura custa 14 ms, medidos, então roda na construção. O botão **Procurar de novo**
é explícito porque uma revarredura automática a cada abertura descartaria uma escolha
ainda não salva.

### Achado colateral

O seletor de provedor de TTS (`edge`/`openai`/`sapi`/`chatterbox`) **não faz nada**:
`chatterbox` só aparece em `config.py` e `settings.py`, e `_create_speaker` devolve
`EdgeSentenceSpeaker` em qualquer caso. Não foi mexido nesta entrega, mas está
registrado — oferecer escolha de modelo de voz antes de resolver isso seria construir
sobre nada.

Também removido um resquício: a aba Geral ainda anunciava `Ctrl + Numpad +` fixo,
desatualizado desde que os atalhos viraram configuráveis em 0.7.6.

### Arquivos alterados

`src/voxflow/models.py` (novo), `src/voxflow/ui/settings.py`,
`tests/test_models.py` (novo).

Validação: Ruff aprovado, 133 testes aprovados, aba STT renderizada com 2 de 9 modelos
oferecidos e os 7 restantes explicados por categoria.

## 0.7.8 — O seletor de voz passa a valer (2026-09-07)

O usuário já tinha percebido sozinho: trocar o provider de TTS não mudava nada.
`_create_speaker` devolvia `EdgeSentenceSpeaker` em qualquer caso, e `chatterbox` só
existia como string em `config.py` e `settings.py`.

### A costura

Só uma coisa difere entre providers: `frase → (arquivo de áudio, tempos das palavras)`.
Fila, interrupção, reprodução e realce são compartilhados. `hermes/synthesizers.py`
(novo) isola exatamente isso num `Protocol`, e `EdgeSentenceSpeaker` virou
`SentenceSpeaker`, que recebe um sintetizador em vez de voz e velocidade.

| Provider | Estado | Observação |
|---|---|---|
| `edge` | funciona | único que reporta limites de palavra |
| `sapi` | funciona | offline, via COM do Windows; **133 ms** até o primeiro áudio, medido |
| `openai` | funciona | exige chave em `openai` nos segredos |
| `chatterbox` | não integrado | marcado como indisponível, com o motivo |

### O realce sobrevive sem limites de palavra

Só o Edge diz onde cada palavra cai. Sem isso o karaokê e o orbe ficariam parados.
`estimate_word_timings` distribui as palavras proporcionalmente ao comprimento —
mas **ancorado na duração real do clipe**, consultada no MCI (`status length`) depois
de abrir o arquivo, e não numa estimativa de palavras por minuto. Assim o realce não
adianta nem atrasa em relação ao áudio. Verificado com SAPI: 10 palavras, todas
realçadas na ordem.

Por isso `AudioItem` passou a carregar a frase em vez de só a contagem de caracteres:
a estimativa acontece na reprodução, quando a duração é conhecida.

### As listas de voz não se misturam

`hermes/voices.py` (novo) responde quais providers a máquina consegue rodar e quais
vozes cada um tem. Um nome do Edge não significa nada para o Windows, então trocar de
provider **reconstrói** a lista, nos dois lugares: Ajustes → Hermes e a barra sob a
Friday. Cada voz tem um nome curto próprio, porque truncar a etiqueta longa colidia
duas Thalitas diferentes numa só.

Providers indisponíveis aparecem marcados com o motivo, em vez de sumirem — quem
escolheu `openai` precisa saber que falta a chave, não que a opção evaporou.

### O que ficou de fora, e por quê

Chatterbox **é viável**: importa da pasta do usuário, torch 2.8 com CUDA disponível,
`generate(text, audio_prompt_path=..., language_id=...)`. Mas a "voz" dele é um áudio
de referência, não um nome, e carregar o modelo por frase inviabilizaria a conversa.
Precisa de um processo persistente e de medição de latência antes de prometer que serve
para conversa ao vivo. É uma entrega própria.

### Arquivos alterados

`src/voxflow/hermes/synthesizers.py` (novo), `src/voxflow/hermes/voices.py` (novo),
`src/voxflow/hermes/tts.py`, `src/voxflow/app.py`, `src/voxflow/main.py`,
`src/voxflow/ui/settings.py`, `src/voxflow/ui/conversation.py`,
`tests/test_voice_providers.py` (novo).

Validação: Ruff aprovado, 158 testes aprovados, SAPI sintetizado e reproduzido de ponta
a ponta (241 ms de síntese, 133 ms até o primeiro áudio, realce correto).

## 0.7.9 — Preparado para receber modelos de transcrição novos (2026-09-07)

O usuário trouxe uma leaderboard de STT para PT-BR e pediu o ambiente preparado para
adicionar um deles. A lista era de **transcrição**, não de voz — vale registrar, porque
o pedido veio logo depois do trabalho de TTS.

### O que decide se um modelo entra

Não é qualidade: é formato. O faster-whisper carrega CTranslate2 e nada mais. Das
famílias que aparecem nessas listas, só a do Whisper é alcançável hoje; Parakeet e
Nemotron são NeMo, e Qwen3-ASR e Voxtral são LLMs de áudio. Nenhum deles roda sem um
segundo backend de transcrição, que seria uma entrega própria.

### Reconhecer em vez de dar de ombros

`classify` ganhou duas categorias, porque `unknown` escondia justamente os melhores
modelos disponíveis:

- `stt_whisper_transformers` — Whisper em formato Transformers (`model_type=whisper`).
  É como quase todo fine-tune brasileiro é publicado, e está a uma conversão de
  funcionar.
- `stt_other_runtime` — `.nemo`, `.onnx` ou config de ASR. Reconhecido, com o motivo
  visível, mas fora do seletor.

Reconhecer não é oferecer: ambos continuam fora da lista de escolha, porque nenhum
carrega hoje. Há teste para exatamente isso.

### A conversão

`scripts/add-stt-model.ps1` roda `ct2-transformers-converter` — que já existe no venv,
vindo do faster-whisper — mas `transformers` e `torch` **não** são dependências do app.
Eles passam de 2 GB e o instalador tem 97 MB. O script os empresta por meio de
`uv tool run` só durante a conversão.

O destino é `%LOCALAPPDATA%\VoxFlow\models\<nome>`, que `discover()` já varre, então o
resultado aparece como qualquer outro modelo. `--copy_files tokenizer.json
preprocessor_config.json` é obrigatório: sem eles o faster-whisper carrega os pesos e
não sabe transformar áudio em features nem números em texto.

O script falha limpo e apaga a pasta parcial quando o modelo não é Whisper, explicando o
motivo em vez de deixar meia conversão para trás.

### Não verificado

**Nenhuma conversão real foi executada** — exigiria baixar transformers, torch e um
modelo de vários GB. Foram verificados: a existência de `ct2-transformers-converter.exe`
no venv, a disponibilidade de `uv tool run`, e a sintaxe do script pelo parser do
PowerShell. O primeiro uso real é o teste de verdade.

### Arquivos alterados

`src/voxflow/models.py`, `src/voxflow/ui/settings.py`,
`scripts/add-stt-model.ps1` (novo), `tests/test_models.py`, `README.md`.

Validação: Ruff aprovado, 163 testes aprovados, script validado pelo parser do
PowerShell.

## 0.7.10 — Correção: o app não abria (2026-09-07)

A 0.7.9 instalada não iniciava. Erro na abertura:

```
OSError: [WinError 448] O caminho não pode ser atravessado porque contém um ponto
de montagem não confiável:
'...\.cache\huggingface\hub\models--...\snapshots\0a363e...\config.json'
```

### A causa

O cache do HuggingFace preenche cada snapshot com **symlinks** para `blobs`. O
aplicativo instalado nem sempre tem permissão para atravessá-los, e o `Path.is_file()`
do pathlib **não engole** o WinError 448 — ele só ignora um conjunto fixo de erros, e
esse não está nele. Eu chamei `is_file()` fora do `try` em `_read_config`, então a
exceção subiu até `main`, e como a `SettingsWindow` é construída na abertura, o app
inteiro morria antes de aparecer.

**Isto já era conhecido no projeto.** `faster_whisper_local._materialize_symlinks`
existe exatamente porque o app instalado não consegue seguir esses links — é por isso
que existe a cópia em `%LOCALAPPDATA%\VoxFlow\models\large-v3-turbo`. Entrei direto na
mesma armadilha ao escrever `models.py`, sem olhar por que aquela função existia.

### A correção

`src/voxflow/fsprobe.py` (novo): `is_file`, `is_dir` e `modified_at` que respondem
"não" em vez de levantar. Toda sondagem de disco em `models.py` e `setup_check.py`
passa por eles — nenhuma chamada crua sobrou.

Além disso, duas redes de segurança, porque a lista de modelos é uma conveniência e
nunca deve ser o motivo de o app não abrir:

- `discover()` pula a pasta que falhar, registrando qual, em vez de abortar a varredura.
- A chamada em `settings.py` e o `needs_setup` em `main.py` ficam dentro de `try`.

Classificar continua funcionando no app instalado: os formatos são reconhecidos por
**nomes de arquivo**, e listar uma pasta não exige seguir os links. Só `config.json`
fica ilegível, e agora isso é dito — `"config.json ilegível (links do cache do
HuggingFace)"` — em vez de virar "formato não reconhecido", que seria mentira.

### Tamanho: dois erros no caminho

Ao consertar, medi a pasta inteira do repositório e os tamanhos **dobraram**: `blobs`
tem os bytes reais e `snapshots` tem links para os mesmos bytes. Trocar para só `blobs`
também errava, porque ele acumula todas as revisões já baixadas (3,18 GB contra 1,62 GB
do modelo em uso).

Final: mede o snapshot, que é a revisão em uso; se vier zero — exatamente o caso em que
os links não podem ser seguidos — recorre a `blobs`. Ambos têm teste.

### Arquivos alterados

`src/voxflow/fsprobe.py` (novo), `src/voxflow/models.py`, `src/voxflow/setup_check.py`,
`src/voxflow/ui/settings.py`, `src/voxflow/main.py`, `tests/test_models.py`.

Validação: Ruff aprovado, 170 testes aprovados (5 novos reproduzem o WinError 448),
varredura real conferida com os tamanhos de volta aos valores corretos.

## 0.7.11 — Auditoria da documentação (2026-09-07)

O usuário pediu que eu **conferisse** os documentos em vez de responder de memória.
Fiz certo em manter `CONTINUITY.md` e o checklist a cada versão, mas errei no resto.

### O que estava errado

| Onde | Problema |
|---|---|
| `PROMPT_INICIALIZACAO_PROXIMA_IA.md` | Parou na 0.7.5. Faltavam 0.7.6 a 0.7.10 |
| idem | Dizia que os dois modos de escuta "coexistem de propósito" — falso desde a 0.7.6, quando viraram escolha |
| idem | Dizia que o Estúdio do Orbe estava "ainda sem commit, instalador" — falso desde a 0.7.3 |
| idem | Anunciava "A versão atual é 0.7.0" |
| idem | **Mandava procurar o plugin em `~/.hermes/plugins/`** — o mesmo caminho errado que eu corrigi no README na 0.7.5 e esqueci aqui |
| `README.md` | Nenhuma menção aos providers de voz, entregues na 0.7.8 |
| idem | Chamava o modo Hermes de "hands-free", que virou só um dos dois |
| idem | Parágrafo do plugin ficou órfão dentro da seção "Atalhos" |
| idem | "o instalador tem 97 MB" — são 100 MB desde a 0.7.9 |

O caminho errado do plugin é o mais grave: quem seguisse o prompt instalaria num lugar
onde o Hermes não olha, e o pensamento simplesmente não apareceria, sem erro nenhum.
A correção agora diz explicitamente que `~/.hermes/plugins/` **não** é o caminho, para
que uma leitura futura de um documento antigo não reintroduza o engano.

### Lição de processo

`CONTINUITY.md` e o checklist eu atualizava porque são o registro da entrega. O prompt
da próxima IA e o README descrevem o **estado atual**, então cada mudança de
comportamento os torna obsoletos em silêncio — nada falha, o texto só passa a mentir.
Antes de fechar uma entrega, vale reler as afirmações desses dois em vez de só
acrescentar uma seção nova.

### Verificação feita

- Cobertura de versões conferida arquivo a arquivo.
- Varredura por afirmações obsoletas conhecidas (`hands-free`, `97 MB`, `coexistem`,
  `0.7.0/Fase`, `ainda sem commit`) — nenhuma restante.
- Varredura por bytes de controle nos quatro documentos: limpos. Um `\v` de um caminho
  Windows tinha virado tabulação vertical numa edição por heredoc, deixando
  `plugins\voxflow-reasoning` escrito como `pluginsoxflow-reasoning`.

### Arquivos alterados

`PROMPT_INICIALIZACAO_PROXIMA_IA.md`, `README.md`.

## 0.7.12 — A API local do Hermes precisa estar ligada (2026-09-08)

O usuário perguntou se a porta 8642 abre sozinha no computador do amigo. Não abre, e o
assistente de 0.7.5 não checava nada disso — ele conferia só se o `hermes.exe` existia,
e mostrava um ✓ verde que dava **falsa confiança**.

### Três coisas que estavam invisíveis

Na máquina de origem tudo isso foi configurado à mão há muito tempo:

1. `API_SERVER_ENABLED: true` no `config.yaml` do Hermes (chave de topo). Numa
   instalação nova simplesmente não existe, e sem ela `hermes gateway run` não abre
   porta nenhuma.
2. `API_SERVER_HOST` / `API_SERVER_PORT` — configuráveis, e precisam bater com
   `hermes.base_url` do VoxFlow.
3. `API_SERVER_KEY` no `.env` do Hermes. O VoxFlow manda `Authorization: Bearer` a
   partir do segredo `hermes`; se não bater, o gateway recusa.

Sem os três, o sintoma é "Hermes não respondeu após 60 segundos" — que não diz nada
sobre a causa.

### O que foi feito

`src/voxflow/hermes/local_api.py` (novo) lê a configuração do Hermes, **somente leitura
e de propósito**: a configuração é de outro aplicativo. Já houve o episódio de eu
escrever `model.reasoning_echo` no `config.yaml` dele e ter que reverter; a lição
valeu. Aqui a API desligada é *reportada com a linha exata a mudar*, não corrigida por
baixo do pano.

Dois requisitos novos no assistente:

- `hermes_api` — porta respondendo agora, ou configuração habilitada e coerente. Um
  gateway que responde é a verdade final e encerra a questão, mesmo com a configuração
  dizendo o contrário.
- `hermes_key` — a chave guardada tem que ser a mesma que o Hermes espera. Chave
  divergente é reportada diferente de chave ausente: as causas são outras.

Reparos oferecidos: **Usar `<host:porta>`** move o `base_url` do VoxFlow para o endereço
que o Hermes serve, e **Importar do Hermes** copia a `API_SERVER_KEY` do `.env` dele
para o Gerenciador de Credenciais. Os dois arquivos são da mesma máquina e do mesmo
usuário, e o segredo só se move para onde o VoxFlow guarda segredos — mesma prática que
`resolve_opencode_key` já usava.

Detalhes de cuidado: as chaves são casadas em **coluna zero** (`^API_SERVER_ENABLED:`),
porque o `config.yaml` do usuário tem centenas de linhas e uma chave aninhada de mesmo
nome não pode ser confundida. Ausente é lido como `None`, nunca como ligado. E o valor
da chave nunca é registrado em log — só a sua presença.

### Arquivos alterados

`src/voxflow/hermes/local_api.py` (novo), `src/voxflow/setup_check.py`,
`src/voxflow/ui/setup_wizard.py`, `tests/test_local_api.py` (novo).

Validação: Ruff aprovado, 185 testes aprovados, e o caso do amigo simulado numa máquina
falsa — Hermes instalado com a API desligada produz exatamente o aviso com a linha a
corrigir.

## 0.7.13 — Kokoro corrigido, janela que volta, e "indisponível" com nome (2026-09-08)

O usuário pediu à Friday que adicionasse o Kokoro e pediu que eu auditasse, com receio
de estrago. **Nada commitado foi tocado**: quatro arquivos na árvore de trabalho, todos
sobre Kokoro, e nenhum commit. O trabalho anterior está inteiro.

### Os três defeitos do Kokoro

1. **Caminho absoluto com o nome do usuário** (`C:\Users\vinig\.cache\...`) escrito no
   código — a mesma classe de bug que a 0.7.5 inteira eliminou. Agora `find_model`
   procura via `models.default_roots()`, com `tts.kokoro_path` para apontar uma cópia
   fora do caminho. Há teste que falha se um caminho de home voltar ao fonte.
2. **Dependências instaladas à mão**, ausentes do `pyproject.toml`. O
   `build-release.ps1` começa com `uv sync`, que **remove** o que não está declarado —
   o build seguinte perderia o Kokoro em silêncio. Agora existe o extra `kokoro` e o
   script o instala.
3. **`available()` carregava o modelo ONNX inteiro**, e é chamado ao montar a janela de
   Ajustes, ou seja, na abertura, na thread do Qt. Agora só procura pacote e arquivos:
   **0,9 ms**, medido. Há teste que explode se a sonda carregar o motor.

### E o que realmente quebrava

O log deu a causa: `kokoro_onnx\config.json` faltando no pacote. O `voxflow.spec`
coletava os dados do `espeakng_loader` mas não os do próprio `kokoro_onnx`, que lê o
seu `config.json` em tempo de execução. Funcionava pelo código-fonte e falhava só
empacotado — foi assim que chegou ao usuário.

Medido depois do conserto: **1,7 s** na primeira frase (com carga do modelo) e
**402 ms** nas seguintes, offline.

### "Só abre na primeira vez"

Não era build, como se supôs. É [main.py](src/voxflow/main.py): a segunda execução via
o mutex e fazia `return 0` **calado**. O app estava rodando o tempo todo, numa bandeja
que o Windows 11 esconde por padrão. Agora existe um evento nomeado `SHOW`, irmão do
`QUIT` que já existia: a segunda execução o dispara e a primeira levanta a janela. O
evento é consumido uma vez, para a janela subir uma vez e não a cada tique.

### "Indisponível" dizia duas coisas diferentes

O usuário leu "indisponível" no Chatterbox e concluiu que faltava algo na máquina dele —
quando na verdade **não existe código**. Agora `Provider` tem `status`: `ready`,
`needs_setup` (falta configurar) e `not_implemented` (ainda não existe). O dropdown
mostra o sufixo certo.

### Uma hipótese minha que a medição derrubou

Vi entradas de log com carimbo ~3 h à frente e supus que o build congelado usava UTC.
Medi: o exe instalado marcou `03:11:44` contra `03:11:43` do Windows — **o fuso está
certo**. É um único salto para trás em 2.226 linhas, de origem desconhecida, e não
inventei correção para isso.

### Arquivos alterados

`packaging/voxflow.spec`, `pyproject.toml`, `scripts/build-release.ps1`,
`src/voxflow/config.py`, `src/voxflow/hermes/synthesizers.py`,
`src/voxflow/hermes/voices.py`, `src/voxflow/single_instance.py`,
`src/voxflow/main.py`, `src/voxflow/ui/settings.py`, `tests/test_kokoro.py` (novo),
`tests/test_voice_providers.py`, `tests/test_local_api.py`.

Validação: Ruff aprovado, 207 testes aprovados, Kokoro sintetizando de verdade e o
evento de mostrar janela exercitado ponta a ponta.

### O que continua na fila

**Chatterbox de verdade** e a **Fase 5**, ambos pedidos e ambos entregas próprias.

## 0.7.14 — As 322 vozes do Edge, e uma que eu tinha inventado (2026-09-08)

O usuário perguntou por que só apareciam oito vozes do Edge. Porque **eu escrevi oito à
mão** na 0.7.8, comentando que "o catálogo é enorme e online". Conferindo contra a lista
real, achei coisa pior: **`pt-BR-ThalitaNeural` não existe**. Se ele tivesse escolhido
essa voz, a síntese falharia com erro de rede e nenhuma explicação.

Microsoft publica **322 vozes em 75 idiomas**, e buscá-las custa 1,1 s.

### Como fica

`src/voxflow/hermes/edge_catalogue.py` (novo) busca, converte e guarda em
`%LOCALAPPDATA%\VoxFlow\edge-voices.json`. Nunca da thread do Qt: um segundo de rede ali
é um segundo de janela congelada, então a busca vai para um executor e volta por sinal.
Sem cache, um fallback de 14 vozes **verificadas contra a lista real** — não mais nomes
escritos de memória.

### O agrupamento, pedido pelo usuário

Ele foi específico: as de Portugal não, as brasileiras e as multilíngues sim. Uma voz
multilíngue fala português independentemente do locale dela, então
`speaks_portuguese` aceita `pt-BR` **ou** qualquer `*Multilingual*` — são 14 no total.
As brasileiras vêm primeiro, senão a lista abriria em alemão.

As outras 308 continuam alcançáveis pela linha **Idioma da voz**, com 142 idiomas mais
"Todas". A barra sob a Friday tem 150 px e recebe só o grupo do português: 322 num
combo daquele tamanho seria inútil.

### Uma colisão que o teste da 0.7.8 pegou

`test_short_names_are_unique_within_a_provider` existia desde que duas Thalitas
colidiram ao truncar a etiqueta. Com o catálogo inteiro ele falhou de novo: o inuktitut
publica Siqiniq e Taqqiq em dois alfabetos, `iu-Cans-CA` e `iu-Latn-CA`. Quem colide
agora recebe o locale no nome; os demais ficam limpos.

### Arquivos alterados

`src/voxflow/hermes/edge_catalogue.py` (novo), `src/voxflow/hermes/voices.py`,
`src/voxflow/ui/settings.py`, `src/voxflow/ui/conversation.py`,
`tests/test_edge_catalogue.py` (novo), `README.md`.

Validação: Ruff aprovado, 222 testes aprovados, catálogo real buscado (322 vozes, 14 que
falam português, 142 idiomas) e a aba Hermes renderizada com a linha de idioma.

## 0.7.15 — Um guarda para a documentação não ficar para trás (2026-09-08)

O usuário cobrou pela segunda vez que os documentos estavam desatualizados, e estava
certo: eu tinha corrigido isso na 0.7.11 e **falhei de novo** nas 0.7.13 e 0.7.14.
Prometer atenção não resolveu, então agora falha em teste.

### O que estava errado desta vez

| Onde | Problema |
|---|---|
| `PROMPT_INICIALIZACAO_PROXIMA_IA.md` | Parou na 0.7.12; faltavam 0.7.13 e 0.7.14 |
| idem | Anunciava "A versão atual é 0.7.10" |
| idem | Nenhuma menção ao Kokoro, um provider que funciona |
| `README.md` | Nenhuma menção ao Kokoro |
| idem | Dizia que o OpenAI "aparece marcado como indisponível" — desde a 0.7.13 ele diz "falta configurar", que é outra coisa |
| idem | Nada sobre clicar no ícone trazer a janela de volta |

### O guarda

`tests/test_documentation.py` falha quando:

- `CONTINUITY.md` não tem seção para a versão atual;
- o checklist de aceite não tem seção para a versão atual — mesmo uma entrega sem nada
  a testar precisa dizer isso, em vez de ficar ausente e indistinguível de esquecimento;
- o prompt da próxima IA não anuncia a versão atual;
- um provider de voz que **funciona** não aparece no README (casado pelo rótulo que o
  usuário vê, não pelo nome interno — ninguém procuraria por "sapi" no README);
- uma afirmação que já ficou obsoleta uma vez reaparece (`~/.hermes/plugins/`,
  `ainda sem commit`, `coexistem de propósito`, `hands-free`).

`build-release.ps1` roda os testes antes de empacotar, então **não é possível gerar
instalador com documentação velha**. Verificado na prática: subi a versão para 0.7.99 de
mentira e os três documentos falharam com a mensagem certa.

### Por que só agora

CONTINUITY e checklist eu atualizava porque são **registro de entrega** — acrescentar
seção é natural. O prompt e o README descrevem o **estado atual**, então cada mudança de
comportamento os tornava falsos em silêncio: nada quebrava, o texto só passava a mentir.
Era um erro de processo, não de intenção, e por isso disciplina não bastou.

### Arquivos alterados

`tests/test_documentation.py` (novo), `PROMPT_INICIALIZACAO_PROXIMA_IA.md`, `README.md`.

Validação: Ruff aprovado, 227 testes aprovados, e o guarda exercitado contra uma versão
falsa para confirmar que ele realmente reprova.

## O repositório foi para o GitHub, e o CI rodou pela primeira vez (2026-09-08)

O usuário pediu para subir o projeto e dar acesso a um amigo. Antes do push, o histórico
inteiro foi varrido por segredos (`sk-`, `ghp_`, `xox`, `Bearer`, `API_SERVER_KEY`),
por `.env`/`config.yaml` versionados e por caminhos com o nome do usuário: nada. Os
`releases/`, `dist/` e `build/` já estavam ignorados, então o repositório publicado tem
111 arquivos e 626 KiB, sem instaladores nem modelos.

Remoto: `https://github.com/viniggs/VoxFlow`, **privado**, `main`, 54 commits.

### O CI nunca tinha sido executado

`.github/workflows/ci.yml` existe desde a Fase 0, mas não havia remoto — então o
primeiro push foi também a primeira execução, e ela **falhou**:

```
ERROR: pytest-qt requires either PySide6, PyQt5 or PyQt6 installed.
```

`uv sync --extra dev` instala pytest, pytest-qt e Ruff, e mais nada. O `.venv` de quem
desenvolve tem os extras, então a suíte passava aqui e a lacuna ficou invisível por sete
fases. É a mesma classe de erro da 0.7.5 — algo que era verdade só na máquina de origem.

Reproduzido num venv isolado (`UV_PROJECT_ENVIRONMENT` apontando para fora do projeto,
sem tocar no `.venv` do usuário), o que os testes realmente exigem:

| Extra | Por quê |
|---|---|
| `dev` | pytest, pytest-qt, Ruff |
| `desktop` | PySide6 e httpx — as janelas e o cliente do gateway |
| `kokoro` | sem o pacote, `KokoroSynthesizer.available()` é falso e o teste que garante que a sonda **não** carrega o ONNX de 82M falha |

Os demais extras ficam de fora de propósito: os testes alcançam transcrição e provedores
de nuvem por fábricas injetadas, nunca pelos pacotes reais. Medido: com `dev` +
`desktop`, 230 passam e 1 falha (o do Kokoro); com os três, **231 passam** e o Ruff passa.

`conftest.py` já fixa `QT_QPA_PLATFORM=offscreen`, então o runner não precisa de sessão
gráfica.

### Arquivos alterados

`.github/workflows/ci.yml`.

## O Kokoro dizia "falta configurar" numa build que já não era a instalada (2026-09-08)

O usuário perguntou por que o Kokoro ainda aparecia como `(falta configurar)`. A resposta
exigiu medir dentro do executável empacotado, porque é lá que ele difere do fonte.

### A hipótese natural estava errada

`onnx/model.onnx` no cache do HuggingFace **é** um symlink, e este projeto já tropeçou
nisso duas vezes (Fase 2 e 0.7.10, que é por que o Whisper é materializado em
`%LOCALAPPDATA%\VoxFlow\models\large-v3-turbo`). Era o suspeito óbvio. A medição o
descartou: o aplicativo empacotado atravessa o link sem problema.

Para medir, `voxflow --check` ganhou `kokoro_probe`, que informa pacote encontrado,
modelo encontrado, caminho configurado e raízes buscadas. Rodado no exe empacotado:

```
kokoro_probe package=True model='...\snapshots\1939ad2a...\onnx\model.onnx'
             configured='' roots=[...\huggingface\hub, ...\VoxFlow\models]
```

Como nenhum commit tocou `synthesizers.py`, `models.py`, `fsprobe.py` ou `voices.py`
desde a 0.7.14, essa medição vale para a build instalada.

### A causa real

O log guardava o motivo antigo:

```
kokoro_unavailable reason=[Errno 2] No such file or directory:
  '...\Programs\VoxFlow\_internal\kokoro_onnx\config.json'
```

É o defeito que a **0.7.13** corrigiu no `voxflow.spec`. O usuário estava vendo uma tela
anterior à instalação da 0.7.14, que aconteceu no meio da conversa — o registro dizia
0.7.13 no início da sessão e 0.7.14 depois, com o processo subindo às 10:37 a partir do
executável instalado. Confirmado por ele: com a 0.7.14 no ar, o Kokoro aparece pronto.

Lição registrada: antes de investigar um sintoma de interface, confirmar **qual build
está na tela**. O registro de desinstalação e o carimbo do `VoxFlow.exe` respondem isso
em dois comandos, e teriam encurtado esta investigação.

### Um defeito real encontrado no caminho

`providers()` nunca recebia `tts.kokoro_path`. O sintetizador honra a configuração —
`find_model` a usa como primeiro candidato —, mas a janela de Ajustes perguntava sem
ela. Quem guardasse o modelo fora dos caches padrão leria `(falta configurar)` na
própria tela que acabara de ser informada de onde o modelo está. O caminho agora é
passado por `providers()`, `available()`, `_kokoro_available()` e `_kokoro_detail()`.

### Arquivos alterados

`src/voxflow/diagnostics.py`, `src/voxflow/hermes/voices.py`,
`src/voxflow/ui/settings.py`, `tests/test_kokoro.py`.

Validação: Ruff aprovado, 233 testes aprovados, sonda medida no executável empacotado e
o teste novo exercitado contra o defeito para confirmar que ele reprova.

## O realce que corria na frente, e o modo de escuta no painel (2026-09-08)

Dois pedidos do usuário: o realce cor-de-rosa das palavras estava "completamente
dessincronizado", e o modo push-to-talk parecia não existir.

### O realce: quatro medições até achar o culpado

O usuário chutou que era bug do app e não do Kokoro, e estava certo. Três suspeitos
foram descartados por medição, nesta ordem:

| Suspeito | Medição | Veredito |
|---|---|---|
| Silêncio nas pontas do clipe do Kokoro | 30 ms na frente, 60 ms atrás — 2,0% | inocente |
| Timings reais do Kokoro (`create_timed`) | `has_timings=False`; este export ONNX não publica durações | indisponível |
| O estimador proporcional | erro máximo de 140 ms contra a duração real de cada palavra sintetizada isolada | não explica |
| Posição reportada pelo MCI | `time format=milliseconds` e posição fiel ao relógio, tanto em WAV quanto em MP3 | inocente |

O culpado estava no último elo. O laço de reprodução amostra a cada 40 ms e chamava
`_on_speech` com o **texto** da palavra em cada amostra. `Bubble.highlight_word` procura
a **próxima** ocorrência a partir do cursor — então uma palavra de 200 ms era anunciada
cinco vezes e o realce pulava para os cinco "a" seguintes do parágrafo. Em português,
com "a", "de", "que", "e", ele disparava na frente da voz. Reproduzido em três linhas:
`highlight_word("a")` três vezes seguidas caminhou de `[0:1]` para `[19:20]` e `[34:35]`.

Isso nunca dependeu do Kokoro: valia igual no Edge. O que mudou foi o usuário reparar.

`SpeechCursor` (novo, em `hermes/tts.py`) anuncia a palavra uma vez por **índice**, não
por texto — assim uma frase que repete a mesma palavra ainda avança na segunda. A
amplitude continua saindo a cada amostra, para o orbe não perder o envelope.

### O modo de escuta estava pronto, no lugar errado

A funcionalidade existe desde a 0.7.6: `hermes.listen_mode` em `push_to_talk` faz
`_hermes_tick` retornar antes de consultar o detector de voz, inclusive o de barge-in —
o microfone deixa de abrir turno sozinho e a tecla passa a ser a única forma de falar.
O que faltava era o controle **onde o usuário procurou**: a barra sob o orbe, ao lado do
seletor de voz. Ele olhou lá, não achou, e concluiu que nada tinha sido feito.

Agora o seletor está nos dois lugares, com a mesma volta que a voz já usava: o painel
emite, a janela de Ajustes salva, e o `saved` devolve a escolha ao painel. `apply_config`
já troca o `config` vivo, então vale sem reiniciar.

**Os controles não cabiam em uma linha.** Medido: dois seletores e dois botões pedem
542 px num painel de 470, e as larguras são fixas, então o último seria cortado em vez
de encolher. Passaram a duas linhas — seletores em cima, botões embaixo — 292×66.

### Arquivos alterados

`src/voxflow/hermes/tts.py`, `src/voxflow/ui/conversation.py`,
`src/voxflow/ui/settings.py`, `src/voxflow/main.py`, `README.md`,
`tests/test_speech_sync.py`, `tests/test_listen_mode_panel.py` (novo).

Validação: Ruff aprovado, 241 testes aprovados, painel renderizado com os controles
cabendo, e o teste do realce exercitado contra o defeito para confirmar que reprova.
