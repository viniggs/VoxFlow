"""Kokoro's local voice, and the three defects it arrived with.

Each of these guards one of them: a path with a user name compiled into the source, an
availability probe that loaded an 82M model, and dependencies installed by hand that the
next ``uv sync`` would have removed.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from voxflow.config import TTSConfig
from voxflow.hermes.synthesizers import KOKORO_REPO, KokoroSynthesizer, build
from voxflow.hermes.voices import KOKORO, voices_for

REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeSecrets:
    def get(self, name: str) -> str | None:
        return None

    def set(self, name: str, value: str) -> None:
        pass


@pytest.fixture
def only_here(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Search nowhere but this folder.

    `default_roots` always includes the real cache in the user's home, which would let
    the machine's own Kokoro download answer for the test.
    """

    import voxflow.models

    monkeypatch.setattr(voxflow.models, "default_roots", lambda: [tmp_path])
    return tmp_path


def plant_model(root: Path, *, snapshot: str = "abc123") -> Path:
    """A Kokoro download as the HuggingFace cache lays it out."""

    folder = root / KOKORO_REPO / "snapshots" / snapshot
    (folder / "onnx").mkdir(parents=True)
    (folder / "onnx" / "model.onnx").write_text("x", encoding="utf-8")
    (folder / "voices.bin").write_text("x", encoding="utf-8")
    return folder


# --- no user name may be compiled into the source --------------------------------


def test_no_absolute_home_path_survives_in_the_source() -> None:
    # The version that arrived had C:\Users\<name>\... written into it, which cannot
    # work on any other machine. This is the guard that it does not come back.
    source = (REPO_ROOT / "src" / "voxflow" / "hermes" / "synthesizers.py").read_text(
        encoding="utf-8"
    )
    lowered = source.lower()
    assert "c:\\users\\" not in lowered
    assert "c:/users/" not in lowered


def test_the_model_is_found_wherever_models_land(only_here: Path) -> None:
    plant_model(only_here)
    found = KokoroSynthesizer.find_model()
    assert found is not None
    model, voices = found
    assert model.name == "model.onnx"
    assert voices.name == "voices.bin"


def test_a_configured_folder_wins(only_here: Path) -> None:
    chosen = only_here / "elsewhere"
    (chosen / "onnx").mkdir(parents=True)
    (chosen / "onnx" / "model.onnx").write_text("x", encoding="utf-8")
    (chosen / "voices.bin").write_text("x", encoding="utf-8")
    found = KokoroSynthesizer.find_model(str(chosen))
    assert found is not None
    assert found[0].parent.parent == chosen


def test_the_newest_snapshot_is_preferred(only_here: Path) -> None:
    import os
    import time

    old = plant_model(only_here, snapshot="old")
    plant_model(only_here, snapshot="new")
    os.utime(old, (time.time() - 600, time.time() - 600))
    found = KokoroSynthesizer.find_model()
    assert found is not None
    assert found[0].parent.parent.name == "new"


def test_half_a_download_is_not_a_model(only_here: Path) -> None:
    folder = only_here / KOKORO_REPO / "snapshots" / "abc"
    (folder / "onnx").mkdir(parents=True)
    (folder / "onnx" / "model.onnx").write_text("x", encoding="utf-8")
    # voices.bin never arrived
    assert KokoroSynthesizer.find_model() is None


def test_nothing_downloaded_means_unavailable(only_here: Path) -> None:
    assert not KokoroSynthesizer.available()


# --- the probe must stay cheap ----------------------------------------------------


def test_asking_whether_kokoro_is_available_never_loads_the_engine(
    only_here: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The settings window asks this while it is being built, so paying for an 82M ONNX
    # graph here stalls the application's startup.
    plant_model(only_here)

    def explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("a sonda carregou o modelo")

    monkeypatch.setattr(KokoroSynthesizer, "engine", explode)
    assert KokoroSynthesizer.available()


# --- the packaging has to carry it ------------------------------------------------


def test_the_dependencies_are_declared_rather_than_installed_by_hand() -> None:
    # They were installed by hand and missing from the project, and `uv sync` — the
    # first step of the release script — removes anything not declared.
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = project["project"]["optional-dependencies"]
    assert "kokoro" in extras
    declared = " ".join(extras["kokoro"])
    for package in ("kokoro-onnx", "espeakng-loader", "soundfile"):
        assert package in declared


def test_the_release_script_installs_them() -> None:
    script = (REPO_ROOT / "scripts" / "build-release.ps1").read_text(encoding="utf-8")
    assert "--extra kokoro" in script


def test_the_package_data_is_collected() -> None:
    # kokoro_onnx reads its own config.json at runtime. Without this the provider
    # works from source and fails only once packaged, which is how it reached the user.
    spec = (REPO_ROOT / "packaging" / "voxflow.spec").read_text(encoding="utf-8")
    assert 'collect_data_files("kokoro_onnx")' in spec
    assert 'collect_data_files("espeakng_loader")' in spec


# --- wiring -----------------------------------------------------------------------


def test_choosing_kokoro_builds_the_kokoro_synthesizer() -> None:
    built = build(TTSConfig(provider="kokoro", voice="pf_dora"), secrets=FakeSecrets())
    assert isinstance(built, KokoroSynthesizer)


def test_the_configured_model_path_reaches_the_synthesizer() -> None:
    config = TTSConfig(provider="kokoro", voice="pf_dora", kokoro_path="D:/somewhere")
    built = build(config, secrets=FakeSecrets())
    assert isinstance(built, KokoroSynthesizer)
    assert built._model_path == "D:/somewhere"


def test_kokoro_offers_only_its_own_voices() -> None:
    kokoro = {item.identifier for item in voices_for(KOKORO)}
    edge = {item.identifier for item in voices_for("edge")}
    assert kokoro
    assert not kokoro & edge


def test_kokoro_writes_wav_because_that_is_what_it_produces() -> None:
    assert KokoroSynthesizer("pf_dora", "+0%").suffix == ".wav"


@pytest.mark.parametrize(
    ("rate", "expected"),
    [("+0%", 1.0), ("+50%", 1.5), ("-50%", 0.5), ("+900%", 2.0), ("lixo", 1.0)],
)
def test_speed_stays_inside_the_range_kokoro_accepts(rate: str, expected: float) -> None:
    assert KokoroSynthesizer("pf_dora", rate)._speed == pytest.approx(expected)
