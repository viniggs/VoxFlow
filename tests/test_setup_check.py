"""What a second computer is told it needs.

These run against the plugin that actually ships in the repository, so a delivery that
forgot to vendor it fails here rather than on somebody else's machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voxflow import setup_check
from voxflow.config import AppConfig
from voxflow.setup_check import (
    PLUGIN_FILES,
    bundled_plugin,
    check_requirements,
    install_plugin,
    plugin_state,
    resolve_hermes_executable,
)


class FakeSecrets:
    def __init__(self, key: str | None = None) -> None:
        self._key = key

    def get(self, name: str) -> str | None:
        return self._key if name == "opencode_go" else None

    def set(self, name: str, value: str) -> None:
        self._key = value


def devices(*names: str):
    return lambda: [{"name": name, "max_input_channels": 2} for name in names]


@pytest.fixture
def machine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A blank computer: no Hermes, no plugin, nothing installed."""

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


# --- the plugin ships with the app ----------------------------------------------


def test_the_plugin_is_vendored_in_the_repository() -> None:
    source = bundled_plugin()
    assert source.is_dir(), f"plugin não versionado em {source}"
    for name in PLUGIN_FILES:
        assert (source / name).is_file(), f"faltando {name}"


def test_a_blank_machine_reports_the_plugin_missing(machine: Path) -> None:
    assert plugin_state() == "missing"


def test_installing_the_plugin_makes_it_current(machine: Path) -> None:
    target = install_plugin()
    assert target == machine / "hermes" / "plugins" / "voxflow-reasoning"
    for name in PLUGIN_FILES:
        assert (target / name).is_file()
    assert plugin_state() == "ok"


def test_a_different_copy_is_reported_as_outdated(machine: Path) -> None:
    target = install_plugin()
    (target / "__init__.py").write_text("# edited by hand\n", encoding="utf-8")
    assert plugin_state() == "outdated"


def test_half_a_plugin_counts_as_missing(machine: Path) -> None:
    target = install_plugin()
    (target / "plugin.yaml").unlink()
    assert plugin_state() == "missing"


def test_nothing_to_install_is_not_the_same_as_not_installed(tmp_path: Path) -> None:
    empty = tmp_path / "no-plugin-here"
    empty.mkdir()
    assert plugin_state(source=empty, target=tmp_path / "target") == "unavailable"


# --- where Hermes lives ----------------------------------------------------------


def test_hermes_defaults_to_its_install_location(machine: Path) -> None:
    assert resolve_hermes_executable("") == machine / "hermes" / "bin" / "hermes.exe"


def test_a_configured_path_wins(machine: Path) -> None:
    chosen = machine / "elsewhere" / "hermes.exe"
    assert resolve_hermes_executable(str(chosen)) == chosen
    # Whitespace is a typo, not a path.
    assert resolve_hermes_executable("   ") == machine / "hermes" / "bin" / "hermes.exe"


def test_a_machine_without_hermes_says_so(machine: Path) -> None:
    found = _requirement(machine, "hermes")
    assert not found.ok
    assert not found.optional


def test_pointing_at_a_real_file_satisfies_it(machine: Path) -> None:
    executable = machine / "custom" / "hermes.exe"
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    config = AppConfig()
    config.hermes.executable_path = str(executable)
    found = _find(
        check_requirements(config, secrets=FakeSecrets(), query_devices=devices("Mic")),
        "hermes",
    )
    assert found.ok


# --- the microphone --------------------------------------------------------------


def test_the_configured_microphone_being_present_is_fine(machine: Path) -> None:
    config = AppConfig()
    config.audio.input_device = "SteelSeries Sonar"
    found = _find(
        check_requirements(
            config,
            secrets=FakeSecrets(),
            query_devices=devices("Microfone (SteelSeries Sonar)"),
        ),
        "microphone",
    )
    assert found.ok


def test_a_microphone_that_does_not_exist_here_is_flagged_but_not_fatal(machine: Path) -> None:
    config = AppConfig()
    config.audio.input_device = "SteelSeries Sonar"
    found = _find(
        check_requirements(config, secrets=FakeSecrets(), query_devices=devices("Realtek Audio")),
        "microphone",
    )
    assert not found.ok
    # It still records, on the fallback device — worth saying, not worth blocking.
    assert found.optional
    assert "Realtek Audio" in found.detail


def test_no_microphone_at_all_is_fatal(machine: Path) -> None:
    found = _find(
        check_requirements(AppConfig(), secrets=FakeSecrets(), query_devices=devices()),
        "microphone",
    )
    assert not found.ok
    assert not found.optional


# --- the cleanup key -------------------------------------------------------------


def test_a_stored_key_satisfies_the_cleanup_requirement(machine: Path) -> None:
    found = _find(
        check_requirements(
            AppConfig(), secrets=FakeSecrets("abc123"), query_devices=devices("Mic")
        ),
        "opencode_key",
    )
    assert found.ok


def test_a_missing_key_is_optional(machine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup_check, "resolve_opencode_key", lambda secrets: None)
    found = _find(
        check_requirements(AppConfig(), secrets=FakeSecrets(), query_devices=devices("Mic")),
        "opencode_key",
    )
    assert not found.ok
    assert found.optional


def _find(requirements, key: str):
    return next(item for item in requirements if item.key == key)


def _requirement(machine: Path, key: str):
    return _find(
        check_requirements(AppConfig(), secrets=FakeSecrets(), query_devices=devices("Mic")),
        key,
    )
