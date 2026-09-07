"""Secret storage backed by Windows Credential Manager through keyring."""

from __future__ import annotations

from typing import Final

import keyring

SERVICE_NAME: Final = "VoxFlow"
ALLOWED_SECRET_NAMES: Final = frozenset(
    {"groq", "openai", "deepgram", "opencode_go", "hermes"}
)


class SecretStore:
    def _validate_name(self, name: str) -> None:
        if name not in ALLOWED_SECRET_NAMES:
            raise ValueError(f"unsupported secret name: {name}")

    def get(self, name: str) -> str | None:
        self._validate_name(name)
        return keyring.get_password(SERVICE_NAME, name)

    def set(self, name: str, value: str) -> None:
        self._validate_name(name)
        if not value.strip():
            raise ValueError("secret cannot be empty")
        keyring.set_password(SERVICE_NAME, name, value)

    def delete(self, name: str) -> None:
        self._validate_name(name)
        try:
            keyring.delete_password(SERVICE_NAME, name)
        except keyring.errors.PasswordDeleteError:
            return

