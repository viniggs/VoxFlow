"""Streaming client for the local Hermes OpenAI-compatible API."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event
from typing import Any

import httpx
from loguru import logger

#: A stream that goes quiet for longer than this is stalling, not thinking: the
#: gateway has already started emitting text by then.
_DELTA_GAP_ALERT_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class HermesReply:
    text: str
    response_id: str = ""


def parse_sse_data(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line.startswith("data:"):
        return None
    payload = line[5:].strip()
    if not payload or payload == "[DONE]":
        return None
    value = json.loads(payload)
    return value if isinstance(value, dict) else None


def build_response_body(
    text: str,
    instructions: str,
    conversation_id: str,
) -> dict[str, Any]:
    """Build a Responses API request with explicit chat-turn semantics."""
    return {
        "model": "hermes-agent",
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            }
        ],
        "instructions": instructions,
        "conversation": conversation_id,
        "store": True,
        "stream": True,
    }


class HermesClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        session_key: str,
        conversation_id: str,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._session_key = session_key
        self._conversation_id = conversation_id

    def health(self, timeout: float = 2.0) -> tuple[bool, str]:
        root = self._base_url.removesuffix("/v1")
        try:
            response = httpx.get(
                f"{root}/health",
                headers=self._headers(),
                timeout=timeout,
            )
            response.raise_for_status()
            return True, "Hermes conectado"
        except Exception as exc:
            return False, f"Hermes indisponível: {type(exc).__name__}"

    def stream_response(
        self,
        text: str,
        instructions: str,
        on_delta: Callable[[str], None],
        cancel: Event,
    ) -> HermesReply:
        started = time.perf_counter()
        first_delta = True
        chunks: list[str] = []
        response_id = ""
        last_delta_at = 0.0
        worst_gap = 0.0
        body = build_response_body(text, instructions, self._conversation_id)
        with (
            httpx.Client(timeout=httpx.Timeout(90.0, connect=5.0)) as client,
            client.stream(
                "POST",
                f"{self._base_url}/responses",
                headers=self._headers(),
                json=body,
            ) as response,
        ):
            response.raise_for_status()
            for line in response.iter_lines():
                if cancel.is_set():
                    break
                event = parse_sse_data(line)
                if event is None:
                    continue
                event_type = str(event.get("type", ""))
                if event_type == "response.output_text.delta":
                    delta = str(event.get("delta", ""))
                    if delta:
                        now = time.perf_counter()
                        if first_delta:
                            logger.info(
                                "hermes_first_delta ttfb_hermes_ms={:.2f}",
                                (now - started) * 1000,
                            )
                            first_delta = False
                        else:
                            gap = now - last_delta_at
                            worst_gap = max(worst_gap, gap)
                            if gap >= _DELTA_GAP_ALERT_SECONDS:
                                # The gateway stopped mid-reply. Logged where it happens,
                                # so a stall can never again be mistaken for slow speech.
                                logger.warning(
                                    "hermes_delta_gap hermes_delta_gap_ms={:.2f} "
                                    "chars_so_far={}",
                                    gap * 1000,
                                    len("".join(chunks)),
                                )
                        last_delta_at = now
                        chunks.append(delta)
                        on_delta(delta)
                elif event_type == "response.completed":
                    completed = event.get("response", {})
                    if isinstance(completed, dict):
                        response_id = str(completed.get("id", ""))
                    break
                elif event_type in {"error", "response.failed"}:
                    raise RuntimeError(self._event_error(event))
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "hermes_response_completed elapsed_ms={:.2f} chars={} worst_delta_gap_ms={:.2f}",
            elapsed_ms,
            len("".join(chunks)),
            worst_gap * 1000,
        )
        return HermesReply("".join(chunks).strip(), response_id)

    def _headers(self) -> dict[str, str]:
        headers = {"X-Hermes-Session-Key": self._session_key}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    @staticmethod
    def _event_error(event: dict[str, Any]) -> str:
        error = event.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or "Falha no Hermes")
        return str(error or "Falha no Hermes")
