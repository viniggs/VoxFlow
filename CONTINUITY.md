# VoxFlow — Continuidade do projeto

Atualizado em: 2026-09-07
Versão: 0.7.2
Fase concluída no código: Fase 4.5, aguardando aceite manual

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
