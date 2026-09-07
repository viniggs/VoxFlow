"""Streaming client for the local Hermes OpenAI-compatible API."""

from __future__ import annotations

import json
import threading
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


def build_run_body(text: str, instructions: str, session_id: str) -> dict[str, Any]:
    """Build a ``POST /v1/runs`` request.

    History is not carried in the body. The gateway rebuilds it from the session, which
    is the difference that matters: the ``conversation`` chain used by ``/v1/responses``
    accumulates every turn — reasoning included, stored twice — into a blob it replays in
    full on each request, and that blob is what drove the time to first token from six
    seconds to nearly thirty.
    """
    return {
        "model": "hermes-agent",
        "input": text,
        "instructions": instructions,
        "session_id": session_id,
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
        self._run_lock = threading.Lock()
        self._active_run: str | None = None

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

    def stream_run(
        self,
        text: str,
        instructions: str,
        on_delta: Callable[[str], None],
        cancel: Event,
    ) -> HermesReply:
        """Run a turn over ``/v1/runs`` and stream the reply from its event feed.

        Unlike the responses path, a run has a handle: :meth:`stop_active_run` can end it
        from another thread. Checking a flag between SSE lines cannot cancel anything
        while the gateway is quiet, which is most of the wait.
        """
        started = time.perf_counter()
        chunks: list[str] = []
        first_delta = True
        last_delta_at = 0.0
        worst_gap = 0.0
        body = build_run_body(text, instructions, self._conversation_id)
        with httpx.Client(timeout=httpx.Timeout(90.0, connect=5.0)) as client:
            created = client.post(f"{self._base_url}/runs", headers=self._headers(), json=body)
            created.raise_for_status()
            run_id = str((created.json() or {}).get("run_id") or "")
            if not run_id:
                raise RuntimeError("O Hermes aceitou a pergunta mas não devolveu um run_id.")
            logger.info(
                "hermes_run_started run_id={} accepted_ms={:.2f}",
                run_id,
                (time.perf_counter() - started) * 1000,
            )
            self._set_active_run(run_id)
            try:
                with client.stream(
                    "GET",
                    f"{self._base_url}/runs/{run_id}/events",
                    headers=self._headers(),
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if cancel.is_set():
                            break
                        event = parse_sse_data(line)
                        if event is None:
                            continue
                        name = str(event.get("event") or event.get("type") or "")
                        if name in {"message.delta", "assistant.delta"}:
                            delta = str(event.get("delta") or event.get("text") or "")
                            if not delta:
                                continue
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
                                    logger.warning(
                                        "hermes_delta_gap hermes_delta_gap_ms={:.2f} "
                                        "chars_so_far={}",
                                        gap * 1000,
                                        len("".join(chunks)),
                                    )
                            last_delta_at = now
                            chunks.append(delta)
                            on_delta(delta)
                        elif name in {"run.completed", "run.finished"}:
                            break
                        elif name in {"run.failed", "error"}:
                            raise RuntimeError(self._event_error(event))
            finally:
                self._set_active_run(None)
        logger.info(
            "hermes_response_completed elapsed_ms={:.2f} chars={} worst_delta_gap_ms={:.2f}",
            (time.perf_counter() - started) * 1000,
            len("".join(chunks)),
            worst_gap * 1000,
        )
        return HermesReply("".join(chunks).strip(), "")

    def _set_active_run(self, run_id: str | None) -> None:
        with self._run_lock:
            self._active_run = run_id

    def stop_active_run(self) -> bool:
        """End the run in flight. Safe to call from any thread.

        This is what makes a barge-in actually stop the gateway. The old path could only
        notice a cancel flag when the next SSE line arrived, so an interrupted turn kept
        a worker busy until the server spoke again — up to ninety seconds — and two of
        those exhausted the pool and left the app thinking forever.
        """
        with self._run_lock:
            run_id = self._active_run
        if not run_id:
            return False
        try:
            httpx.post(
                f"{self._base_url}/runs/{run_id}/stop",
                headers=self._headers(),
                timeout=5.0,
            ).raise_for_status()
            logger.info("hermes_run_stopped run_id={}", run_id)
            return True
        except Exception as exc:
            logger.warning(
                "hermes_run_stop_failed run_id={} error_type={}", run_id, type(exc).__name__
            )
            return False

    def _headers(self) -> dict[str, str]:
        # The gateway advertises X-Hermes-Session-Id as its continuity header; with it
        # the run's history is rebuilt server-side instead of chained through stored
        # responses.
        headers = {
            "X-Hermes-Session-Key": self._session_key,
            "X-Hermes-Session-Id": self._conversation_id,
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    @staticmethod
    def _event_error(event: dict[str, Any]) -> str:
        error = event.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or "Falha no Hermes")
        return str(error or "Falha no Hermes")
