"""Typed configuration persisted as YAML without secrets."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from voxflow.orb_settings import OrbStudioConfig
from voxflow.paths import AppPaths, get_app_paths


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GeneralConfig(StrictModel):
    language: Literal["auto", "pt", "en"] = "auto"
    autostart: bool = True
    sounds: bool = True
    #: Requirements the user has already seen and chosen to live without. The setup
    #: assistant stays quiet unless something new is missing.
    setup_acknowledged: list[str] = Field(default_factory=list)


class HotkeysConfig(StrictModel):
    dictation_hold: str = "ctrl+num_add"
    dictation_lock: str = "double_tap"
    hermes_toggle: str = "f9"
    cancel: str = "esc"
    #: Hold to talk to Friday, from anywhere. The key is claimed for the whole
    #: session; emptying this gives it back to Windows.
    hermes_push_to_talk: str = "num_add"
    #: A tap shorter than this is a slip, not a turn, and is thrown away unheard.
    hermes_push_to_talk_ms: int = Field(default=1000, ge=200, le=5000)


class AudioConfig(StrictModel):
    input_device: str = "SteelSeries Sonar"
    sample_rate: int = 16_000
    vad_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    speech_start_ms: int = Field(default=300, ge=100, le=1500)
    endpoint_silence_ms: int = Field(default=700, ge=100)
    preroll_ms: int = Field(default=300, ge=0)
    minimum_recording_ms: int = Field(default=400, ge=100)
    minimum_rms: float = Field(default=0.005, ge=0.0, le=1.0)


def _default_whisper_cache() -> str:
    return str(
        Path.home()
        / ".cache"
        / "huggingface"
        / "hub"
        / "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo"
    )


def _default_cuda_dll_dirs() -> list[str]:
    return [
        r"C:\AI\Chatterbox-Friday\.venv\Lib\site-packages\torch\lib",
        r"C:\AI\Qwen3-TTS-Friday\.venv\Lib\site-packages\torch\lib",
    ]


class STTConfig(StrictModel):
    primary: Literal["groq", "openai", "local", "deepgram"] = "local"
    fallback: Literal["groq", "openai", "local", "deepgram"] | None = None
    local_model: str = "large-v3-turbo"
    local_model_cache: str = Field(default_factory=_default_whisper_cache)
    local_device: Literal["cuda", "cpu"] = "cuda"
    local_compute_type: str = "float16"
    cuda_dll_dirs: list[str] = Field(default_factory=_default_cuda_dll_dirs)


class CleanupConfig(StrictModel):
    enabled: bool = True
    provider: Literal["opencode_go", "openai", "ollama"] = "opencode_go"
    model: str = "muse-spark-1.3-contributor"
    fallback_model: str = "deepseek-v4-flash"
    base_url: str = ""
    data_training_consent: bool = False
    timeout_seconds: float = Field(default=4.0, gt=0)
    dictionary: list[str] = Field(default_factory=lambda: ["Hermes", "VoxFlow"])
    snippets: dict[str, str] = Field(default_factory=dict)
    per_app: dict[str, dict[str, str | bool]] = Field(default_factory=dict)


class InjectConfig(StrictModel):
    strategy: Literal["clipboard", "unicode"] = "clipboard"
    restore_clipboard: bool = True
    trailing_space: bool = True


class TTSConfig(StrictModel):
    provider: Literal["edge", "openai", "sapi", "chatterbox", "kokoro"] = "edge"
    voice: str = "pt-BR-ThalitaMultilingualNeural"
    rate: str = "+5%"
    chatterbox_path: str = r"C:\AI\Chatterbox-Friday"
    #: Vazio significa procurar o modelo no cache do HuggingFace e na pasta de
    #: modelos do VoxFlow. Preencha só para apontar uma cópia fora do caminho.
    kokoro_path: str = ""


class HermesConfig(StrictModel):
    base_url: str = "http://127.0.0.1:8642/v1"
    #: Empty means the default install location. Set when Hermes lives elsewhere.
    executable_path: str = ""
    session_key: str = "voxflow:estudo"
    conversation_id: str = "voxflow:estudo"
    half_duplex: bool = False
    #: ``continuous`` lets the voice detector open turns by itself; ``push_to_talk``
    #: means she only hears while the key is held. The key works in both — in
    #: continuous mode it is an override for a noisy room or a pause for thought.
    listen_mode: Literal["continuous", "push_to_talk"] = "continuous"
    #: Use ``/v1/runs`` (server-side session history, real cancellation) instead of
    #: ``/v1/responses``. Kept switchable so the old path is one setting away.
    use_runs_api: bool = True
    attach_screenshot_on_command: bool = True
    #: Who takes the picture when you say "olha minha tela".
    #:
    #: ``hermes_tool`` asks her to look with her own ``computer_use`` tool. That keeps
    #: everything in one place: the turn, the tool call and the answer are written to
    #: Hermes' own session store, so the exchange shows up in the Hermes desktop app and
    #: she can refer back to what she saw.
    #:
    #: ``voxflow`` grabs the screen here and sends it inline. It has to go through
    #: ``/v1/responses``, because ``/v1/runs`` reads its input with ``str(content)`` —
    #: and that endpoint keeps its history in a different store, so the picture never
    #: reaches the session. Measured, not assumed: an image sent that way left no trace
    #: in ``state.db``. Kept for a Hermes without the tool.
    screenshot_source: Literal["hermes_tool", "voxflow"] = "hermes_tool"
    #: Written for a tutor who is heard, not read. The length is left to the question:
    #: a fixed word cap made her cut explanations short exactly when depth was asked for.
    instructions: str = (
        "Você é Hermes, um tutor por voz socrático. Responda em português brasileiro, "
        "com clareza e naturalidade. Faça no máximo uma pergunta por vez. Ajuste o tamanho "
        "da resposta ao que foi pedido: seja breve numa troca rápida e desenvolva à vontade "
        "quando eu pedir explicação, exemplo, comparação ou aprofundamento — sem limite de "
        "palavras. Escreva em frases que soem bem faladas em voz alta. Não use Markdown "
        "complexo, tabelas ou blocos de código salvo quando indispensável."
    )
    tts: TTSConfig = Field(default_factory=TTSConfig)


class AppConfig(StrictModel):
    orb: OrbStudioConfig = Field(default_factory=OrbStudioConfig)
    schema_version: int = 1
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    hotkeys: HotkeysConfig = Field(default_factory=HotkeysConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    stt: STTConfig = Field(default_factory=STTConfig)
    cleanup: CleanupConfig = Field(default_factory=CleanupConfig)
    inject: InjectConfig = Field(default_factory=InjectConfig)
    hermes: HermesConfig = Field(default_factory=HermesConfig)

    @field_validator("schema_version")
    @classmethod
    def supported_schema(cls, value: int) -> int:
        if value != 1:
            raise ValueError(f"unsupported config schema: {value}")
        return value


def load_config(paths: AppPaths | None = None) -> AppConfig:
    resolved = paths or get_app_paths()
    if not resolved.config_file.exists():
        config = AppConfig()
        save_config(config, resolved)
        return config
    payload = yaml.safe_load(resolved.config_file.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(payload)


def save_config(config: AppConfig, paths: AppPaths | None = None) -> Path:
    resolved = paths or get_app_paths()
    resolved.ensure_directories()
    payload = yaml.safe_dump(
        config.model_dump(mode="json"),
        allow_unicode=True,
        sort_keys=False,
    )
    handle, temporary_name = tempfile.mkstemp(
        dir=resolved.config_dir,
        prefix="config-",
        suffix=".yaml.tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, resolved.config_file)
    finally:
        temporary.unlink(missing_ok=True)
    return resolved.config_file
