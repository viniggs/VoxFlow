"""The documents must not fall behind the code, and forgetting must not be silent.

This exists because forgetting kept happening. CONTINUITY and the acceptance checklist
were updated because they are the record of a delivery, while the handoff prompt and the
README describe the present — so every behaviour change made them wrong without anything
failing. Now something fails.

`build-release.ps1` runs the suite before it builds, so a release with stale documents
cannot be produced.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from voxflow import __version__

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTINUITY = REPO_ROOT / "CONTINUITY.md"
CHECKLIST = REPO_ROOT / "docs" / "FASE_4_5_CHECKLIST_ACEITE.md"
PROMPT = REPO_ROOT / "PROMPT_INICIALIZACAO_PROXIMA_IA.md"
README = REPO_ROOT / "README.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_continuity_has_a_section_for_this_version() -> None:
    assert f"## {__version__}" in read(CONTINUITY), (
        f"CONTINUITY.md não tem seção para {__version__}. "
        "Cada versão precisa da sua, com o que mudou e por quê."
    )


def test_the_checklist_has_a_section_for_this_version() -> None:
    # A release with nothing to test by hand still needs to say so, rather than being
    # quietly absent and indistinguishable from a forgotten one.
    assert f"VoxFlow {__version__}" in read(CHECKLIST), (
        f"O checklist não tem seção para {__version__}. "
        "Se não há nada a testar à mão, escreva isso explicitamente."
    )


def test_the_handoff_prompt_announces_this_version() -> None:
    # The strongest of the three: the prompt describes the present, so a stale version
    # line means somebody will read outdated behaviour as current.
    text = read(PROMPT)
    match = re.search(r"A versão atual é \*\*([0-9.]+)\*\*", text)
    assert match is not None, (
        "Não achei a linha 'A versão atual é **X**' no prompt da próxima IA."
    )
    assert match.group(1) == __version__, (
        f"O prompt anuncia {match.group(1)} e o código está em {__version__}."
    )


@pytest.mark.parametrize(
    ("claim", "where"),
    [
        # Each of these was true once and became a lie without anything failing.
        ("~/.hermes/plugins/voxflow-reasoning/", PROMPT),
        ("ainda sem commit", PROMPT),
        ("coexistem de propósito", PROMPT),
        ("hands-free", README),
    ],
)
def test_claims_that_went_stale_before_do_not_come_back(claim: str, where: Path) -> None:
    assert claim not in read(where), f"'{claim}' voltou a {where.name} e já é falso."


def test_every_working_voice_provider_is_documented() -> None:
    """A provider nobody wrote about is a provider nobody finds."""

    from voxflow.hermes.voices import providers

    readme = read(README).lower()
    for entry in providers():
        if not entry.available:
            continue
        # Matched on the label rather than the internal name: "sapi" is not what the
        # README should be calling it, and a reader would never search for that.
        shown = entry.label.split(" (")[0].strip().lower()
        assert shown in readme, (
            f"O provider '{entry.label}' funciona mas não aparece no README."
        )
