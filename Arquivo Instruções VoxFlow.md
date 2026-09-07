# ESPEC TÉCNICA — "VoxFlow" (clone Wispr Flow p/ Windows + companheiro de estudo por voz com Hermes Agent)

---

## 1. Produto e requisitos

**Dois modos, um app em tray:**

1. **Modo Ditado (Wispr-like):** segura hotkey → fala → solta → texto limpo (sem "éé", com pontuação, formatado) aparece onde o cursor está, em **qualquer app** (navegador, VS Code, WhatsApp, Word, Anki, terminal).
2. **Modo Hermes (estudo):** conversa contínua por voz com o Hermes Agent — hands-free com detecção de fim de fala (VAD) ou push-to-talk; resposta em streaming lida em voz (TTS); interrupção (barge-in); opção de mandar screenshot da tela junto ("explica esse slide").

**Não-funcionais:**

- Latência ditado (soltar tecla → texto na tela): **< 1,5 s** cloud, **< 2,5 s** local.
- Latência Hermes (fim da fala → começa a falar): **< 2,5 s** (TTS por sentença, não espera resposta inteira).
- RAM < 400 MB sem modelo local; roda em tray; inicia com o Windows; pt-BR + en com auto-detect; modo 100% offline opcional (STT local + LLM local).
- Nunca travar a UI; falha de rede → fallback (texto bruto sem limpeza) em vez de perder o ditado.

---

## 2. Stack e ferramentas (Windows 10/11)

| Componente            | Escolha                                                                                                                                                                                                      | Motivo                                                                         |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| Linguagem             | **Python 3.12 + `uv`**                                                                                                                                                                                       | Mais rápido/seguro pra um LLM gerar e depurar; ecossistema de áudio/STT maduro |
| UI                    | **PySide6** (QSystemTrayIcon, overlay frameless always-on-top, janela de config)                                                                                                                             | Tray + overlay + settings numa lib só                                          |
| Áudio                 | **`sounddevice`** (PortAudio/WASAPI), 16 kHz mono int16, `numpy`                                                                                                                                             | Estável no Windows, callback de baixa latência                                 |
| VAD                   | **`silero-vad`** (ONNX) — fallback `webrtcvad`                                                                                                                                                               | Endpointing hands-free e corte de silêncio                                     |
| Hotkeys globais       | **`pynput`** (hook low-level, detecta press **e** release) — fallback `ctypes` RegisterHotKey                                                                                                                | Precisa de "segurar pra falar"                                                 |
| Injeção de texto      | **`pywin32`** (clipboard + `SendInput` Ctrl+V); modo alternativo `SendInput` KEYEVENTF_UNICODE char-a-char                                                                                                   | Cobre 99% dos apps; unicode direto p/ terminais/RDP                            |
| Contexto do app ativo | `pywin32` (`GetForegroundWindow`, título) + `psutil` (nome do processo)                                                                                                                                      | Regras por app (tom, estratégia de injeção)                                    |
| STT (plugável)        | **cloud:** Groq `whisper-large-v3-turbo` ou OpenAI `gpt-4o-transcribe`/`whisper-1`; **local:** `faster-whisper` (`large-v3-turbo` GPU / `small` int8 CPU); **opcional streaming:** Deepgram Nova-3 WebSocket | Whisper-family é forte em pt-BR; interface única `STTProvider`                 |
| LLM de limpeza        | SDK `openai` apontando p/ qualquer endpoint OpenAI-compatível (modelo pequeno/rápido: mini/flash; ou Ollama local)                                                                                           | < 1 s, barato                                                                  |
| Hermes                | `httpx` (SSE streaming) → `http://127.0.0.1:8642/v1`                                                                                                                                                         | API OpenAI-compatível do Hermes                                                |
| TTS                   | **`edge-tts`** (default, pt-BR bom e grátis) · OpenAI TTS (premium) · `pyttsx3`/SAPI (offline)                                                                                                               | Playback via `sounddevice`                                                     |
| Screenshot            | `mss` + `Pillow`                                                                                                                                                                                             | Janela ativa → PNG base64                                                      |
| Config/segredos       | `pydantic-settings` + YAML em `%APPDATA%\VoxFlow\config.yaml`; API keys no **`keyring`** (Windows Credential Manager)                                                                                        | Nada de chave em texto puro                                                    |
| Histórico             | SQLite (`sqlite3`)                                                                                                                                                                                           | Ditados, latências, sessões                                                    |
| Logs                  | `loguru` (rotativo em `%LOCALAPPDATA%\VoxFlow\logs`)                                                                                                                                                         |                                                                                |
| Testes                | `pytest`, `pytest-qt`, providers mockados                                                                                                                                                                    |                                                                                |
| Empacotamento         | **PyInstaller** `--onedir --noconsole` + **Inno Setup**; autostart via registro `HKCU\...\Run`                                                                                                               | Instalador .exe                                                                |

Justificativa de design: ditado = **gravar-até-soltar e transcrever em lote** com provider rápido, não streaming Whisper — Whisper Streaming variants build real-time versions of Whisper. Promising for research, but production faces 1-5s latency in many implementations, heavy optimization work, and hardware-dependent performance. Streaming (Deepgram) fica como opcional só no modo Hermes, pra mostrar transcrição parcial no overlay — Deepgram is our first choice for conversational voice systems where turn timing is central.

---

## 3. Arquitetura

```
voxflow/
├─ main.py                  # bootstrap Qt, DPI awareness, single-instance mutex
├─ app.py                   # orquestrador + state machines
├─ config.py                # pydantic models, load/save YAML, keyring
├─ hotkeys.py               # pynput hooks: hold/toggle/double-tap
├─ audio/
│  ├─ capture.py            # sounddevice InputStream, ring buffer c/ pre-roll 300 ms
│  ├─ vad.py                # silero: is_speech(), endpointing
│  └─ playback.py           # fila de áudio TTS, stop imediato (barge-in)
├─ stt/
│  ├─ base.py               # STTProvider.transcribe(pcm16, lang_hint) -> Transcript
│  ├─ groq.py | openai.py | faster_whisper_local.py | deepgram_stream.py
├─ text/
│  ├─ cleanup.py            # LLM de limpeza + dicionário + snippets + regras por app
│  └─ inject.py             # clipboard-paste / unicode-sendinput / per-app override
├─ context.py               # janela ativa (processo, título)
├─ hermes/
│  ├─ client.py             # /v1/responses SSE, /health, conversation ids
│  ├─ tts.py                # sentence splitter + edge-tts/openai/sapi
│  └─ study.py              # modo estudo: comandos de voz, screenshot, log .md
├─ ui/
│  ├─ tray.py | overlay.py | settings.py | history.py
├─ storage.py               # SQLite
└─ tests/
```

**State machine — Ditado:** `IDLE → RECORDING → TRANSCRIBING → CLEANING → INJECTING → IDLE` (qualquer erro → `IDLE` com toast; timeout de limpeza → injeta texto bruto).

**State machine — Hermes:** `OFF → LISTENING → (VAD fim de fala) → TRANSCRIBING → THINKING (SSE) → SPEAKING → LISTENING`; barge-in em `SPEAKING` → para TTS → `LISTENING`.

**Threads:** Qt na main thread; callback de áudio em thread própria (só copia pra ring buffer); 1 event loop `asyncio` em thread dedicada pra rede/SSE/TTS; comunicação via `Signal/Slot` do Qt. **Nunca bloquear a main thread.**

---

## 4. Pipeline do Modo Ditado (detalhado)

1. **Hotkey hold** (default `Ctrl+Win`; configurável). `on_press` → começa captura, overlay "ouvindo", beep opcional. Double-tap → trava "mãos livres" até apertar de novo.
2. **Captura:** 16 kHz mono int16; **pre-roll** de 300 ms sempre em buffer (pega a primeira sílaba); RMS enviado ao overlay (barras).
3. **Release:** para; se < 400 ms ou RMS abaixo do limiar → cancela silenciosamente. Corta silêncio das pontas com VAD. Gera WAV em memória.
4. **STT:** `provider.transcribe()` com `language_hint` (auto/pt/en). Timeout 10 s, 1 retry, depois fallback pro 2º provider configurado.
5. **Limpeza (LLM):** pula se `cleanup=false` ou < 3 palavras. Entrada: texto bruto + contexto (processo/título da janela) + dicionário pessoal + snippets. Saída: **só o texto**. Timeout 4 s → usa bruto. Comandos falados ("nova linha", "novo parágrafo", "apaga isso", "quer dizer X") são resolvidos pelo LLM, não por regex.
6. **Injeção:**
   - **A (default) clipboard:** salva clipboard (texto), seta texto, `SendInput` Ctrl+V, espera 150 ms, restaura clipboard (retry se clipboard estiver travado por outro processo).
   - **B unicode:** `SendInput` com `KEYEVENTF_UNICODE` char-a-char (terminais, RDP, apps que bloqueiam paste). Override por processo no config.
   - Espaço final inteligente (config), Enter opcional após injetar (útil em chats).
7. **Histórico:** salva bruto, limpo, app, duração, latências por etapa. Overlay "✓".

---

## 5. Integração com o Hermes Agent

**Lado do Hermes** — API Server — Expose Hermes as an OpenAI-compatible HTTP endpoint. Habilitar no `~/.hermes/.env` (se o Hermes roda no WSL2, o arquivo fica dentro do WSL e `http://localhost:8642` é acessível do Windows por localhost forwarding; se não, `API_SERVER_HOST=0.0.0.0` ou networking "mirrored"):

```bash
API_SERVER_ENABLED=true
API_SERVER_KEY=<chave-forte>
# API_SERVER_PORT=8642 (default)
```

Depois `hermes gateway`. Testar: `GET /health` → `{"status":"ok"}`.

**Endpoint que o app deve usar (preferido): `POST /v1/responses`** com estado no servidor:

```json
{
  "model": "hermes-agent",
  "input": "texto transcrito",
  "instructions": "<prompt de tutor da seção 13>",
  "conversation": "voxflow-estudo-2026-09-05",
  "store": true,
  "stream": true
}
```

- Header `Authorization: Bearer <API_SERVER_KEY>` e `X-Hermes-Session-Key: voxflow:estudo` (escopo estável de memória de longo prazo).
- SSE: consumir `response.output_text.delta` (texto → splitter de sentenças → fila TTS) e `response.completed`.
- `conversation` faz o servidor encadear a última resposta automaticamente ("nova sessão" por voz = novo id).
- **Screenshot:** `input` como array com `{"type":"input_text",...}` + `{"type":"input_image","image_url":"data:image/png;base64,..."}`.
- Limites a respeitar: stored responses (for previous_response_id) are persisted in SQLite and survive gateway restarts. Max 100 stored responses (LRU eviction). → o app também guarda o histórico local em Markdown. E No file upload — inline images are supported on both /v1/chat/completions and /v1/responses, but uploaded files (file, input_file, file_id) and non-image document inputs are not supported → pra "ler um PDF", mande screenshot da página.
- Alternativa: `/v1/chat/completions` — Standard OpenAI Chat Completions format. Stateless — the full conversation is included in each request via the messages array. (o app gerencia o histórico).
- O `instructions`/system prompt é **empilhado** sobre o prompt do Hermes — ele mantém tools, memória e skills.

Obs.: o Hermes já tem STT próprio pra plataformas de mensagem (Speech-to-text supports eight providers: local faster-whisper (free, runs on-device), a local command wrapper, Groq, OpenAI Whisper API, Mistral, xAI, ElevenLabs Scribe, and DeepInfra.), mas o app faz STT do lado dele e envia texto — controle de latência, overlay com transcrição e o mesmo pipeline do ditado.

**Fluxo hands-free (modo estudo):**

1. `F9` liga `LISTENING` (ou segurar hotkey = push-to-talk).
2. VAD: fala ≥ 300 ms + silêncio ≥ 700 ms = fim do turno → STT → mostra transcrição no overlay.
3. POST streaming → TTS por sentença (regex em `.?!` com mínimo de ~40 chars; strip de markdown; blocos de código → "bloco de código omitido, está na tela").
4. **Barge-in:** fala detectada ≥ 300 ms durante `SPEAKING` → para playback imediato, descarta fila TTS. Recomendar fone; oferecer **half-duplex** (não escuta enquanto fala) pra quem usa caixa de som.
5. **Comandos de voz interceptados pelo app** (antes de enviar): "nova sessão", "captura a tela"/"olha minha tela", "modo ditado", "repete", "mais devagar/rápido", "pausa".
6. **Log de sessão:** `Documents\VoxFlow\sessions\YYYY-MM-DD.md` com turnos user/Hermes + timestamps. Ao encerrar ("encerra sessão"), pede ao Hermes resumo + perguntas de revisão (ele mesmo pode salvar arquivos com suas tools).
7. Painel de resposta opcional (janela pequena, sempre no topo) mostrando o texto do Hermes em streaming — útil pra fórmulas/código que TTS não lê bem.

---

## 6. Config (exemplo `config.yaml`)

```yaml
general: { language: auto, autostart: true, sounds: true }
hotkeys:
  dictation_hold: "ctrl+win"        # evitar Win+H (voice typing do Windows) e Win+Space (layout)
  dictation_lock: "double_tap"
  hermes_toggle: "f9"
  cancel: "esc"
audio: { input_device: default, sample_rate: 16000, vad_threshold: 0.5, endpoint_silence_ms: 700, preroll_ms: 300 }
stt:
  primary: groq            # groq | openai | local | deepgram
  fallback: local
  local_model: large-v3-turbo   # small-int8 se sem GPU
cleanup:
  enabled: true
  model: "<modelo-mini>"
  base_url: "https://api.openai.com/v1"   # ou http://localhost:11434/v1 (Ollama)
  dictionary: ["Hermes", "Nous Research", "VoxFlow"]
  snippets: { "meu email": "fulano@exemplo.com" }
  per_app:
    "Code.exe": { tone: technical, inject: unicode }
    "WindowsTerminal.exe": { cleanup: false, inject: unicode }
    "OUTLOOK.EXE": { tone: formal }
inject: { strategy: clipboard, restore_clipboard: true, trailing_space: true }
hermes:
  base_url: "http://localhost:8642/v1"
  session_key: "voxflow:estudo"
  half_duplex: false
  tts: { provider: edge, voice: "pt-BR-AntonioNeural", rate: "+5%" }
  attach_screenshot_on_command: true
# API keys -> keyring (serviço "VoxFlow"): groq, openai, deepgram, hermes
```

---

## 7. UI

- **Tray:** Status · Modo (Ditado/Hermes) · Microfone (lista) · Iniciar com Windows · Histórico · Configurações · Sair.
- **Overlay:** pílula ~240×56 no centro-inferior, frameless, always-on-top, click-through exceto botão cancelar; estados: *ouvindo* (barras RMS), *transcrevendo* (spinner), *Hermes falando* (ticker do texto). `Esc` cancela.
- **Configurações:** abas Geral / Áudio / STT / Texto (dicionário, snippets, regras por app) / Hermes (URL, chave, voz, prompt tutor, half-duplex, teste de conexão) / Histórico (busca, copiar, apagar).

---

## 8. Armadilhas do Windows (o modelo DEVE tratar)

1. **UIPI:** app não-elevado não injeta texto em janela elevada (admin). Detectar e avisar; opção "rodar como admin" no instalador.
2. **Clipboard travado** por outro processo → retry com backoff (5× 30 ms) antes de cair pro modo unicode.
3. **Win key solto sozinho abre o Menu Iniciar** — o hook deve engolir/tratar o release quando fez parte do hotkey.
4. **Conflitos de atalho:** `Win+H`, `Win+Space`, `Ctrl+Win+Space` são do sistema. Deixar tudo configurável e validar conflitos.
5. **DPI/multi-monitor:** `SetProcessDpiAwarenessContext` antes do Qt; posicionar overlay no monitor da janela ativa.
6. **Troca de dispositivo de áudio** (fone conecta/desconecta) → reabrir stream sem crashar.
7. **Eco no hands-free** com caixa de som → half-duplex ou fone.
8. **Antivírus/SmartScreen** com PyInstaller → `--onedir`, assinar se possível, não usar UPX.
9. **faster-whisper GPU** precisa CUDA 12 + cuDNN 9 (wheels `nvidia-cublas-cu12`, `nvidia-cudnn-cu12`); sem NVIDIA → `small`/`medium` int8 CPU ou ficar no cloud. Modelos baixados no 1º uso pra `%LOCALAPPDATA%\VoxFlow\models`.
10. **Instância única** via mutex nomeado; **autostart** via `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

---

## 9. Plano de fases (com critérios de aceite)

| Fase | Entrega                                                                                                              | Aceite                                                                                                   |
| ---- | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| 0    | Repo, `uv`, `pyproject`, estrutura, config/keyring, logging, CI de lint/teste                                        | `uv run voxflow --check` valida config e mic                                                             |
| 1    | **MVP ditado:** hotkey hold → gravar → STT (1 provider) → paste                                                      | Ditar no Bloco de Notas e no Chrome; latência < 1,5 s medida e logada                                    |
| 2    | Limpeza LLM, dicionário, snippets, regras por app, modo unicode, fallback p/ bruto                                   | Comandos "nova linha"/"apaga isso" funcionam; terminal recebe via unicode; queda de rede não perde texto |
| 3    | Tray, overlay, settings, histórico SQLite, autostart, sons                                                           | Tudo configurável sem editar YAML; overlay segue monitor ativo                                           |
| 4    | **Hermes:** cliente SSE `/v1/responses`, TTS por sentença, hands-free VAD, barge-in, half-duplex, painel de resposta | Conversa de 5 turnos sem tocar no teclado; interromper o Hermes falando funciona; `/health` no settings  |
| 5    | **Estudo:** comandos de voz, screenshot p/ Hermes, log `.md` por sessão, resumo/revisão ao encerrar, prompt tutor    | "Olha minha tela e explica" funciona; arquivo `.md` gerado                                               |
| 6    | STT local (faster-whisper) + LLM local (Ollama) = modo offline; 2º provider fallback                                 | Ditar com Wi-Fi desligado                                                                                |
| 7    | PyInstaller + Inno Setup, ícone, versão, updater manual                                                              | Instalar em máquina limpa e ditar em < 2 min                                                             |

---

## 10. Testes

- Unit: sentence splitter, strip de markdown, VAD endpointing (WAVs sintéticos), injeção (mock `SendInput`), parsing SSE (fixtures gravadas do Hermes), regras por app.
- Integração (opt-in c/ chaves): STT com WAV de referência pt-BR (WER < 10%), roundtrip Hermes `/health` + 1 turno.
- Manual checklist por fase (seção 9). Medir e logar latência por etapa (`stt_ms`, `cleanup_ms`, `inject_ms`, `ttfb_hermes_ms`, `tts_first_audio_ms`).

## 11. Empacotamento

`pyinstaller --onedir --noconsole --name VoxFlow --icon assets/icon.ico main.py` → Inno Setup (`setup.iss`: instala em `%LOCALAPPDATA%\Programs\VoxFlow`, atalho, opção autostart, opção "executar como admin"). Modelos e config **fora** do diretório do programa.

## 12. Dependências (`pyproject.toml`, sem pins fixos — o modelo resolve)

```
PySide6 sounddevice numpy silero-vad onnxruntime pynput pywin32 psutil
httpx[http2] openai groq faster-whisper edge-tts pyttsx3 mss Pillow
pydantic pydantic-settings pyyaml keyring loguru
[dev] pytest pytest-qt pytest-asyncio ruff pyinstaller
[optional] deepgram-sdk webrtcvad nvidia-cublas-cu12 nvidia-cudnn-cu12
```

## 13. Prompts

**Limpeza (system):**

> Você é um pós-processador de ditado. Receberá uma transcrição bruta e o contexto do app ativo. Devolva SOMENTE o texto final, sem aspas, sem comentários, sem responder ao conteúdo. Regras: remova hesitações e repetições; corrija pontuação, capitalização e concordância; mantenha o idioma original (pt-BR ou en) e o significado; execute comandos falados: "nova linha"/"novo parágrafo" → quebra; "apaga isso"/"esquece isso" → remova o trecho anterior; "quer dizer X"/"não, X" → substitua; "ponto/vírgula/interrogação" quando claramente ditados. Use o dicionário {dictionary} para grafias. Expanda snippets {snippets}. Tom: {tone} (technical: preserve termos/código; formal: sem gírias; casual: natural). Nunca adicione conteúdo que não foi dito.

**Tutor Hermes (`instructions`):**

> Você é meu tutor de estudos por voz. Sua resposta será lida em voz alta: frases curtas, sem markdown pesado, sem listas longas, máximo ~120 palavras a menos que eu peça mais. Método socrático: explique, depois faça UMA pergunta de verificação e espere. Quando eu errar, corrija com gentileza e dê o porquê. Se eu mandar uma imagem da tela, baseie-se nela. Comandos: "quiz" → 5 perguntas uma por vez; "resume" → resumo da sessão; "cartões" → flashcards Q/A salvos em arquivo. Responda em pt-BR salvo pedido contrário.

## 14. Custos/latência esperados

- Cloud STT em lote: centavos por hora de fala (ref.: OpenAI Whisper API pricing is $0.006 per minute for whisper-1, which works out to $0.36 per audio hour. Groq turbo costuma sair bem abaixo disso). Limpeza com modelo mini: desprezível. TTS edge: grátis.
- Ditado end-to-end: ~0,7–1,5 s cloud; local GPU ~0,6–1,2 s; CPU `small` ~2–4 s p/ 10 s de fala.





Pronto — isso é tudo que o GPT 5.6 precisa. Recomendação prática: começa em Fase 0–1 com **um** provider cloud (Groq ou OpenAI) pra validar o pipeline em uma sessão curta, e só depois cola o resto.


