from voxflow.config import AppConfig
from voxflow.text.context import ActiveApp, resolve_app_rule


def test_terminal_defaults_to_unicode_and_technical_tone() -> None:
    rule = resolve_app_rule(AppConfig(), ActiveApp(executable="WindowsTerminal.exe"))

    assert rule.inject_strategy == "unicode"
    assert rule.tone == "technical"


def test_per_app_rule_overrides_defaults() -> None:
    config = AppConfig.model_validate(
        {"cleanup": {"per_app": {"notepad.exe": {"tone": "formal", "trailing_space": False}}}}
    )

    rule = resolve_app_rule(config, ActiveApp(executable="NOTEPAD.EXE"))

    assert rule.tone == "formal"
    assert rule.trailing_space is False
