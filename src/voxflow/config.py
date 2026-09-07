"""Typed configuration persisted as YAML without secrets."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from voxflow.paths import AppPaths, get_app_paths


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GeneralConfig(StrictModel):
    language: Literal["auto", "pt", "en"] = "auto"
    autostart: bool = True
    sounds: bool = True


class HotkeysConfig(StrictModel):
    dictation_hold: str = "ctrl+num_add"
    dictation_lock: str = "double_tap"
    hermes_toggle: str = "f9"
    cancel: str = "esc"


class AudioConfig(StrictModel):
    input_device: str = "SteelSeries Sonar"
    sample_rate: int = 16_000
    vad_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
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
    provider: Literal["edge", "openai", "sapi", "chatterbox"] = "edge"
    voice: str = "pt-BR-ThalitaMultilingualNeural"
    rate: str = "+5%"
    chatterbox_path: str = r"C:\AI\Chatterbox-Friday"


class HermesConfig(StrictModel):
    base_url: str = "http://127.0.0.1:8642/v1"
    session_key: str = "voxflow:estudo"
    half_duplex: bool = False
    attach_screenshot_on_command: bool = True
    instructions: str = (
        "Você é Hermes, um tutor por voz socrático. Responda em português brasileiro, "
        "com clareza e naturalidade. Faça no máximo uma pergunta por vez, prefira respostas "
        "curtas que soem bem faladas e limite-se a cerca de 120 palavras. Não use Markdown "
        "complexo, tabelas ou blocos de código salvo quando indispensável."
    )
    tts: TTSConfig = Field(default_factory=TTSConfig)


class AppConfig(StrictModel):
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
