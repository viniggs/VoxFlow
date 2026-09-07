# VoxFlow — Continuidade do projeto

Atualizado em: 2026-09-06  
Versão: 0.1.0  
Fase concluída no código: Fase 0

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

## Próxima fase — somente após OK do usuário

Fase 1: hotkey hold, captura de áudio, um provedor STT e injeção clipboard no app em foco,
com aceite no Bloco de Notas e Chrome e latência medida. Como não há chave Groq/OpenAI
configurada, a implementação deve usar o faster-whisper local já presente, salvo nova decisão do usuário.

## Restrições

- Nunca bloquear a thread principal do Qt.
- Não armazenar credenciais em YAML, logs, ZIP ou repositório.
- Não modificar a configuração do Hermes antes da Fase 4.
- Não implementar fases futuras antes do OK explícito.
- Validar uma vez por entrega, proporcionalmente ao risco.

