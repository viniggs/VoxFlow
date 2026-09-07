# VoxFlow — Continuidade do projeto

Atualizado em: 2026-09-06  
Versão: 0.3.0  
Fase concluída no código: Fase 2 com UI emergencial de diagnóstico, aguardando aceite manual

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
- Hermes 0.20.6 em `C:\Users\vinig\AppData\Local\hermes`.
- Hermes estava parado e a API Server não estava configurada em 2026-09-06.
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
injeção automática, corrigida na Fase 2 com fallback Unicode.

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
- transcrição bruta após soltar o atalho (o Whisper atual é batch, não streaming por palavra);
- texto final, métricas, eventos e erros com abertura automática em falha;
- botão para copiar o texto final e botão para abrir a pasta de logs;
- ícone de bandeja com ações para reabrir a janela e encerrar o VoxFlow.

`main.py` agora usa `QApplication` e mantém a interface disponível inclusive quando a
inicialização do pipeline falha. A entrega precisa ser instalada e testada manualmente antes
de considerar a Fase 2 aceita.

Feedback de 2026-09-07: a UI funcionou, mas o STT falhou com `WinError 448` porque os arquivos
do snapshot Hugging Face são links simbólicos e o Windows bloqueou a travessia do ponto de
montagem no executável instalado. O provider agora materializa o snapshot uma única vez em
`%LOCALAPPDATA%\VoxFlow\models\large-v3-turbo` usando hardlinks para os blobs físicos (cópia
somente como fallback), eliminando reparse points sem duplicar normalmente o modelo de 1,5 GB.

Importante: a escrita palavra por palavra enquanto o usuário fala AINDA NÃO EXISTE. O STT atual
é batch e só produz texto após soltar o atalho. A próxima IA deve implementar streaming/parciais
visíveis se esse requisito do usuário permanecer prioritário; não afirmar que já está pronto.

O prompt pronto para a próxima IA está em `PROMPT_INICIALIZACAO_PROXIMA_IA.md`.

## Próxima fase — somente após OK do usuário

Fase 3: tray, overlay, settings, histórico SQLite, autostart e sons. Não iniciar antes
do aceite manual da Fase 2.

## Restrições

- Nunca bloquear a thread principal do Qt.
- Não armazenar credenciais em YAML, logs, ZIP ou repositório.
- Não modificar a configuração do Hermes antes da Fase 4.
- O fallback CPU da Fase 1 garante funcionamento, mas o empacotamento independente das DLLs CUDA continua previsto para a Fase 6.
- Não implementar fases futuras antes do OK explícito.
- Validar uma vez por entrega, proporcionalmente ao risco.
