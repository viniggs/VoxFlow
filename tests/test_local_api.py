"""Hermes does not open its local port until somebody turns it on.

VoxFlow talks to Hermes over 127.0.0.1:8642, and on the machine it grew up on that had
been enabled by hand long ago. Nothing checked it, so on a second computer the
conversation never started and the interface said only that Hermes had not answered.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voxflow import setup_check
from voxflow.config import AppConfig
from voxflow.hermes import local_api
from voxflow.setup_check import check_requirements


class FakeSecrets:
    def __init__(self, **stored: str) -> None:
        self._stored = stored

    def get(self, name: str) -> str | None:
        return self._stored.get(name)

    def set(self, name: str, value: str) -> None:
        self._stored[name] = value


def devices(*names: str):
    return lambda: [{"name": name, "max_input_channels": 2} for name in names]


@pytest.fixture
def hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    # The port is closed unless a test says otherwise: a reachable gateway short-circuits
    # the whole check, and a real one running on the developer's machine would hide it.
    monkeypatch.setattr(setup_check, "gateway_reachable", lambda *args, **kwargs: False)
    home = tmp_path / "hermes"
    home.mkdir()
    return home


@pytest.fixture
def running_gateway(hermes_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(setup_check, "gateway_reachable", lambda *args, **kwargs: True)
    return hermes_home


def write_config(home: Path, body: str) -> None:
    (home / "config.yaml").write_text(body, encoding="utf-8")


def requirement(config: AppConfig, key: str, *, secrets: FakeSecrets | None = None):
    found = check_requirements(
        config, secrets=secrets or FakeSecrets(), query_devices=devices("Mic")
    )
    return next(item for item in found if item.key == key)


# --- reading what Hermes says -----------------------------------------------------


def test_a_machine_with_no_hermes_config_says_so(hermes_home: Path) -> None:
    settings = local_api.read()
    assert not settings.config_found
    assert settings.enabled is None


def test_the_api_being_switched_off_is_detected(hermes_home: Path) -> None:
    write_config(hermes_home, "API_SERVER_ENABLED: false\nAPI_SERVER_PORT: 8642\n")
    settings = local_api.read()
    assert settings.enabled is False
    assert settings.port == 8642


def test_an_absent_setting_is_not_read_as_enabled(hermes_home: Path) -> None:
    # A fresh Hermes simply has no such line, and assuming "on" would be the bug.
    write_config(hermes_home, "some_other_key: true\n")
    assert local_api.read().enabled is None


def test_a_nested_key_of_the_same_name_is_not_mistaken_for_it(hermes_home: Path) -> None:
    write_config(hermes_home, "something:\n  API_SERVER_ENABLED: true\n")
    assert local_api.read().enabled is None


def test_the_port_is_read_from_the_configuration(hermes_home: Path) -> None:
    write_config(hermes_home, "API_SERVER_ENABLED: true\nAPI_SERVER_PORT: 9999\n")
    settings = local_api.read()
    assert settings.port == 9999
    assert not local_api.matches(settings, "http://127.0.0.1:8642/v1")
    assert local_api.matches(settings, "http://127.0.0.1:9999/v1")


def test_the_url_can_be_moved_onto_the_real_port(hermes_home: Path) -> None:
    write_config(hermes_home, "API_SERVER_ENABLED: true\nAPI_SERVER_PORT: 9999\n")
    moved = local_api.base_url_for(local_api.read(), "http://127.0.0.1:8642/v1")
    assert moved == "http://127.0.0.1:9999/v1"


def test_the_key_is_read_from_the_environment_file(hermes_home: Path) -> None:
    (hermes_home / ".env").write_text('API_SERVER_KEY="sk-local-123"\n', encoding="utf-8")
    assert local_api.api_key() == "sk-local-123"


def test_no_environment_file_means_no_key(hermes_home: Path) -> None:
    assert local_api.api_key() == ""


# --- what the assistant reports ---------------------------------------------------


def test_the_switched_off_api_is_reported_with_the_line_to_change(hermes_home: Path) -> None:
    write_config(hermes_home, "API_SERVER_ENABLED: false\n")
    found = requirement(AppConfig(), "hermes_api")
    assert not found.ok
    assert not found.optional
    assert "API_SERVER_ENABLED" in found.detail


def test_a_port_mismatch_names_both_sides(hermes_home: Path) -> None:
    write_config(hermes_home, "API_SERVER_ENABLED: true\nAPI_SERVER_PORT: 9999\n")
    found = requirement(AppConfig(), "hermes_api")
    assert not found.ok
    assert "9999" in found.detail
    assert "8642" in found.detail


def test_enabled_but_not_running_is_not_a_problem(hermes_home: Path) -> None:
    # VoxFlow starts the gateway itself; being down right now is expected.
    write_config(hermes_home, "API_SERVER_ENABLED: true\nAPI_SERVER_PORT: 8642\n")
    found = requirement(AppConfig(), "hermes_api")
    assert found.ok


def test_a_key_hermes_demands_and_voxflow_lacks_is_flagged(hermes_home: Path) -> None:
    (hermes_home / ".env").write_text("API_SERVER_KEY=sk-local-123\n", encoding="utf-8")
    found = requirement(AppConfig(), "hermes_key")
    assert not found.ok
    assert not found.optional


def test_a_matching_key_passes(hermes_home: Path) -> None:
    (hermes_home / ".env").write_text("API_SERVER_KEY=sk-local-123\n", encoding="utf-8")
    found = requirement(AppConfig(), "hermes_key", secrets=FakeSecrets(hermes="sk-local-123"))
    assert found.ok


def test_a_stale_key_is_worse_than_none_and_says_so(hermes_home: Path) -> None:
    (hermes_home / ".env").write_text("API_SERVER_KEY=sk-new\n", encoding="utf-8")
    found = requirement(AppConfig(), "hermes_key", secrets=FakeSecrets(hermes="sk-old"))
    assert not found.ok
    assert "Diferente" in found.detail


def test_no_key_required_is_not_a_missing_requirement(hermes_home: Path) -> None:
    found = requirement(AppConfig(), "hermes_key")
    assert found.ok
    assert found.optional


def test_a_gateway_already_answering_settles_the_question(running_gateway: Path) -> None:
    # Whatever the configuration says, a port that answers is the ground truth.
    write_config(running_gateway, "API_SERVER_ENABLED: false\n")
    found = requirement(AppConfig(), "hermes_api")
    assert found.ok
    assert "Respondendo" in found.detail
