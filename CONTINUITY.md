# VoxFlow — Continuidade do projeto

Atualizado em: 2026-09-06  
Versão: 0.2.0  
Fase concluída no código: Fase 1, aguardando aceite manual

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

## Próxima fase — somente após OK do usuário

Fase 2: limpeza LLM, dicionário, snippets, regras por app, injeção Unicode e fallback
para texto bruto. Não iniciar antes do aceite manual da Fase 1.

## Restrições

- Nunca bloquear a thread principal do Qt.
- Não armazenar credenciais em YAML, logs, ZIP ou repositório.
- Não modificar a configuração do Hermes antes da Fase 4.
- O fallback CPU da Fase 1 garante funcionamento, mas o empacotamento independente das DLLs CUDA continua previsto para a Fase 6.
- Não implementar fases futuras antes do OK explícito.
- Validar uma vez por entrega, proporcionalmente ao risco.
