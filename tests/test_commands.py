from voxflow.text.commands import apply_spoken_commands, expand_snippets


def test_spoken_commands_work_without_network() -> None:
    text = "primeira tentativa apaga isso versão certa nova linha próximo item ponto"

    assert apply_spoken_commands(text) == "versão certa \n próximo item."


def test_snippets_are_case_insensitive() -> None:
    assert expand_snippets("MINHA ASSINATURA", {"minha assinatura": "Atenciosamente, Vini"}) == (
        "Atenciosamente, Vini"
    )
