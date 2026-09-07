from unittest.mock import patch

import pytest

from voxflow.secrets import SERVICE_NAME, SecretStore


def test_secret_store_uses_keyring() -> None:
    store = SecretStore()
    with (
        patch("voxflow.secrets.keyring.set_password") as setter,
        patch("voxflow.secrets.keyring.get_password", return_value="secret") as getter,
    ):
        store.set("hermes", "secret")
        assert store.get("hermes") == "secret"

    setter.assert_called_once_with(SERVICE_NAME, "hermes", "secret")
    getter.assert_called_once_with(SERVICE_NAME, "hermes")


def test_secret_store_rejects_unknown_names() -> None:
    with pytest.raises(ValueError):
        SecretStore().set("random", "secret")

