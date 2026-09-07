from voxflow.text.inject import ClipboardInjector


class FakeClipboard:
    CF_UNICODETEXT = 13

    def __init__(self) -> None:
        self.text = "anterior"

    def OpenClipboard(self) -> None: ...

    def CloseClipboard(self) -> None: ...

    def IsClipboardFormatAvailable(self, format_id: int) -> bool:
        return bool(self.text) and format_id == self.CF_UNICODETEXT

    def GetClipboardData(self, format_id: int) -> str:
        assert format_id == self.CF_UNICODETEXT
        return self.text

    def EmptyClipboard(self) -> None:
        self.text = ""

    def SetClipboardText(self, text: str, format_id: int) -> None:
        assert format_id == self.CF_UNICODETEXT
        self.text = text


def test_clipboard_injection_restores_previous_text() -> None:
    clipboard = FakeClipboard()
    pasted: list[str] = []
    injector = ClipboardInjector(
        restore_clipboard=True,
        clipboard=clipboard,
        send_paste=lambda: pasted.append(clipboard.text),
        sleeper=lambda _: None,
    )

    injector.inject("texto novo")

    assert pasted == ["texto novo"]
    assert clipboard.text == "anterior"

