"""Finding a newer VoxFlow, and never being surprised by one.

Manual on purpose: the app looks only where it is told, only when asked, and installs
only when the user says so. These cover the two ways a source can be read and the
comparison that decides whether anything is offered at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from voxflow import __version__
from voxflow.updates import MANIFEST, Update, look, parse_version, write_manifest


def plant(folder: Path, version: str, phase: str = "5") -> Path:
    """An installer named the way the release script names them."""

    target = folder / f"fase-{phase}" / version
    target.mkdir(parents=True, exist_ok=True)
    installer = target / f"VoxFlow-{version}-fase-{phase}-setup.exe"
    installer.write_bytes(b"MZ")
    return installer


# --- comparing versions -------------------------------------------------------------


def test_ten_comes_after_nine() -> None:
    """Compared as text, 0.8.9 sorts above 0.8.10 — and this project is well past nine
    patches inside a phase."""

    assert parse_version("0.8.10") > parse_version("0.8.9")
    assert parse_version("0.9.0") > parse_version("0.8.99")


def test_a_version_that_is_not_a_number_does_not_explode() -> None:
    assert parse_version("") == (0,)
    assert parse_version("1.2.beta3") == (1, 2, 3)


def test_only_a_higher_version_counts_as_newer() -> None:
    assert Update(__version__, "x").newer is False
    assert Update("0.0.1", "x").newer is False
    assert Update("999.0.0", "x").newer is True


# --- reading a folder ---------------------------------------------------------------


def test_the_newest_installer_in_a_folder_is_offered(tmp_path: Path) -> None:
    plant(tmp_path, "0.8.9")
    newest = plant(tmp_path, "999.1.0")
    plant(tmp_path, "0.8.10")

    found, message = look(str(tmp_path))

    assert found is not None
    assert found.version == "999.1.0"
    assert Path(found.location) == newest
    assert "999.1.0" in message


def test_nothing_is_offered_when_the_source_only_has_older_builds(tmp_path: Path) -> None:
    plant(tmp_path, "0.0.9")

    found, message = look(str(tmp_path))

    assert found is None
    assert __version__ in message


def test_an_empty_source_never_looks_anywhere() -> None:
    """Nothing here phones home. No source means no check, not a default address."""

    found, message = look("")

    assert found is None
    assert "Nenhuma origem" in message


def test_a_source_that_is_not_there_says_so(tmp_path: Path) -> None:
    found, message = look(str(tmp_path / "nao-existe"))

    assert found is None
    assert "não encontrada" in message


def test_a_folder_without_installers_says_so(tmp_path: Path) -> None:
    (tmp_path / "vazia").mkdir()

    found, message = look(str(tmp_path / "vazia"))

    assert found is None
    assert "Nenhum instalador" in message


# --- reading an address -------------------------------------------------------------


def test_a_manifest_describes_a_folder_that_cannot_be_listed(tmp_path: Path) -> None:
    """A folder lists itself; an HTTP address does not. The release script writes this."""

    plant(tmp_path, "0.8.9")
    plant(tmp_path, "0.8.10")

    written = write_manifest(tmp_path)

    assert written.name == MANIFEST
    payload = json.loads(written.read_text(encoding="utf-8"))
    versions = [entry["version"] for entry in payload["versions"]]
    assert versions == ["0.8.9", "0.8.10"]
    assert payload["versions"][-1]["file"].endswith("setup.exe")


def test_an_address_is_read_through_its_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    class FakeResponse:
        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict[str, object]:
            return {"versions": [{"version": "999.2.0", "file": "VoxFlow-999.2.0-setup.exe"}]}

    asked: dict[str, str] = {}

    def fake_get(url: str, **_options: object) -> FakeResponse:
        asked["url"] = url
        return FakeResponse()

    monkeypatch.setattr(httpx, "get", fake_get)

    found, message = look("https://exemplo.invalido/voxflow")

    assert asked["url"].endswith(MANIFEST)
    assert found is not None
    assert found.version == "999.2.0"
    # Relative names resolve against the manifest, so a folder can be served as it sits.
    assert found.location == "https://exemplo.invalido/voxflow/VoxFlow-999.2.0-setup.exe"
    assert "999.2.0" in message


def test_a_source_that_refuses_is_reported_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    # The settings window must never see an exception from a check it started.
    import httpx

    def explode(*_args: object, **_options: object) -> None:
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(httpx, "get", explode)

    found, message = look("https://exemplo.invalido/voxflow")

    assert found is None
    assert "Não consegui consultar" in message
