"""LLM dictation cleanup with OpenCode Go fallback and raw-text safety."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from voxflow.config import CleanupConfig
from voxflow.secrets import SecretStore
from voxflow.text.commands import apply_spoken_commands, expand_snippets
from voxflow.text.context import ActiveApp, AppRule

GO_BASE_URL = "https://opencode.ai/zen/go/v1"


def resolve_opencode_key(secrets: SecretStore) -> str | None:
    """The cleanup key, from the credential store or from opencode's own auth file.

    Shared with the setup check, which needs to report whether the key exists without
    building a cleaner just to ask."""

    stored = secrets.get("opencode_go")
    if stored:
        return stored
    auth_file = Path.home() / ".local" / "share" / "opencode" / "auth.json"
    try:
        payload = json.loads(auth_file.read_text(encoding="utf-8"))
        key = str(payload["opencode-go"]["key"]).strip()
        if key:
            secrets.set("opencode_go", key)
            return key
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return None


@dataclass(frozen=True, slots=True)
class CleanupResult:
    text: str
    cleanup_ms: float
    provider: str
    fallback_used: bool
    reason: str = ""
    detail: str = ""


class DictationCleaner:
    def __init__(
        self,
        config: CleanupConfig,
        *,
        secrets: SecretStore | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._secrets = secrets or SecretStore()
        self._client = client or httpx.Client(timeout=config.timeout_seconds, http2=True)
        self._session_id = f"voxflow-{uuid.uuid4()}"

    def close(self) -> None:
        self._client.close()

    def clean(self, raw_text: str, app: ActiveApp, rule: AppRule) -> CleanupResult:
        started = time.perf_counter()
        safe_text = expand_snippets(apply_spoken_commands(raw_text), self._config.snippets)
        if not rule.cleanup_enabled:
            return self._result(safe_text, started, "local", False, "disabled")
        if len(safe_text.split()) < 3:
            return self._result(safe_text, started, "local", False, "short_text")
        api_key = self._resolve_api_key()
        if not api_key:
            logger.warning("cleanup_raw_fallback reason=missing_opencode_go_key")
            return self._result(safe_text, started, "raw", True, "missing_key")

        models = [self._config.fallback_model]
        if self._config.data_training_consent:
            models.insert(0, self._config.model)
        failures: list[str] = []
        for index, model in enumerate(models):
            attempts = 2 if model == self._config.fallback_model else 1
            for attempt in range(1, attempts + 1):
                try:
                    cleaned = self._request(model, safe_text, app, rule, api_key)
                    reason = "provider_fallback" if index > 0 else ""
                    return self._result(cleaned, started, model, index > 0, reason)
                except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                    failure = self._failure_label(model, exc)
                    logger.warning(
                        "cleanup_provider_failed model={} attempt={} error={}",
                        model,
                        attempt,
                        failure,
                    )
                    if attempt == attempts or not self._is_retryable(exc):
                        failures.append(failure)
                        break
                    time.sleep(0.15)
        logger.warning("cleanup_raw_fallback reason=providers_unavailable")
        return self._result(
            safe_text,
            started,
            "raw",
            True,
            "providers_unavailable",
            "; ".join(failures),
        )

    def _request(
        self,
        model: str,
        text: str,
        app: ActiveApp,
        rule: AppRule,
        api_key: str,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "VoxFlow/0.8.9 Windows dictation",
            "x-opencode-session": self._session_id,
        }
        prompt = self._system_prompt(app, rule)
        base_url = self._config.base_url.rstrip("/") or GO_BASE_URL
        if model.startswith("muse-"):
            response = self._client.post(
                f"{base_url}/responses",
                headers=headers,
                json={"model": model, "instructions": prompt, "input": text},
            )
            response.raise_for_status()
            output = self._responses_text(response.json())
        else:
            response = self._client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0,
                },
            )
            response.raise_for_status()
            output = str(response.json()["choices"][0]["message"]["content"])
        return self._sanitize(output)

    def _system_prompt(self, app: ActiveApp, rule: AppRule) -> str:
        dictionary = ", ".join(self._config.dictionary) or "vazio"
        snippets = json.dumps(self._config.snippets, ensure_ascii=False)
        return (
            "Você é um pós-processador de ditado. Devolva SOMENTE o texto final, sem aspas, "
            "comentários ou resposta ao conteúdo. Remova hesitações e repetições; corrija "
            "pontuação, capitalização e concordância; preserve idioma, significado, termos "
            "técnicos e quebras de linha. Execute comandos falados: nova linha e novo parágrafo "
            "viram quebras; apaga isso e esquece isso removem o trecho anterior; quer dizer X e "
            f"não, X corrigem o trecho anterior. Aplicativo: {app.executable}. Tom: {rule.tone}. "
            f"Dicionário: {dictionary}. Snippets: {snippets}. Nunca invente conteúdo."
        )

    def _resolve_api_key(self) -> str | None:
        return resolve_opencode_key(self._secrets)

    @staticmethod
    def _responses_text(payload: dict[str, Any]) -> str:
        if payload.get("output_text"):
            return str(payload["output_text"])
        parts: list[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    parts.append(str(content.get("text", "")))
        return "".join(parts)

    @staticmethod
    def _sanitize(text: str) -> str:
        result = text.strip()
        if result.startswith("```") and result.endswith("```"):
            lines = result.splitlines()[1:-1]
            result = "\n".join(lines).strip()
        if len(result) >= 2 and result[0] == result[-1] and result[0] in {'"', "'"}:
            result = result[1:-1].strip()
        if not result:
            raise ValueError("limpeza retornou texto vazio")
        return result

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            return status == 429 or status >= 500
        return False

    @staticmethod
    def _failure_label(model: str, exc: Exception) -> str:
        model_label = {
            "muse-spark-1.3-contributor": "Muse",
            "deepseek-v4-flash": "DeepSeek",
        }.get(model, model)
        if isinstance(exc, httpx.HTTPStatusError):
            return f"{model_label}: HTTP {exc.response.status_code}"
        return f"{model_label}: {type(exc).__name__}"

    @staticmethod
    def _result(
        text: str,
        started: float,
        provider: str,
        fallback: bool,
        reason: str = "",
        detail: str = "",
    ) -> CleanupResult:
        return CleanupResult(
            text=text,
            cleanup_ms=(time.perf_counter() - started) * 1000,
            provider=provider,
            fallback_used=fallback,
            reason=reason,
            detail=detail,
        )
