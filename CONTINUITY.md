# VoxFlow — Continuidade do projeto

Atualizado em: 2026-09-07
Versão: 0.5.3
Fase concluída no código: Fase 4, aguardando aceite manual

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
- Cliente `httpx` para `/v1/responses`, estado por `conversation`, chave Bearer no keyring e
  parsing incremental de `response.output_text.delta`/`response.completed`.
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
- Entrega: `releases\fase-4\VoxFlow-0.5.3-fase-4-setup.exe`, ZIP de código no mesmo
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

## Próxima fase — somente após OK do usuário

Fase 5: comandos de voz do modo estudo, screenshot para Hermes, log Markdown por sessão e
resumo/revisão ao encerrar. Não iniciar antes do aceite manual da versão 0.5.0/Fase 4.

## Restrições

- Nunca bloquear a thread principal do Qt.
- Não armazenar credenciais em YAML, logs, ZIP ou repositório.
- O fallback CPU da Fase 1 garante funcionamento, mas o empacotamento independente das DLLs CUDA continua previsto para a Fase 6.
- Não implementar fases futuras antes do OK explícito.
- Validar uma vez por entrega, proporcionalmente ao risco.
