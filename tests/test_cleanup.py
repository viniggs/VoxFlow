import httpx

from voxflow.config import CleanupConfig
from voxflow.text.cleanup import DictationCleaner
from voxflow.text.context import ActiveApp, AppRule


class FakeSecrets:
    def get(self, name: str) -> str | None:
        return "key"

    def set(self, name: str, value: str) -> None: ...


class FakeResponse:
    def raise_for_status(self) -> None: ...

    def json(self) -> dict:
        return {"choices": [{"message": {"content": "Texto limpo."}}]}


class FakeClient:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.urls.append(url)
        if url.endswith("/responses"):
            raise httpx.ReadTimeout("timeout")
        return FakeResponse()

    def close(self) -> None: ...


def test_muse_timeout_falls_back_to_deepseek() -> None:
    client = FakeClient()
    cleaner = DictationCleaner(
        CleanupConfig(data_training_consent=True),
        secrets=FakeSecrets(),  # type: ignore[arg-type]
        client=client,  # type: ignore[arg-type]
    )
    rule = AppRule(True, "casual", "clipboard", True)

    result = cleaner.clean("um texto bruto", ActiveApp(executable="notepad.exe"), rule)

    assert result.text == "Texto limpo."
    assert result.provider == "deepseek-v4-flash"
    assert result.fallback_used is True
    assert client.urls[0].endswith("/responses")
    assert client.urls[1].endswith("/chat/completions")


def test_short_text_skips_remote_cleanup() -> None:
    client = FakeClient()
    cleaner = DictationCleaner(
        CleanupConfig(data_training_consent=True),
        secrets=FakeSecrets(),  # type: ignore[arg-type]
        client=client,  # type: ignore[arg-type]
    )
    rule = AppRule(True, "casual", "clipboard", True)

    result = cleaner.clean("bom dia", ActiveApp(executable="notepad.exe"), rule)

    assert result.provider == "local"
    assert result.reason == "short_text"
    assert client.urls == []
