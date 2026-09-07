import ctypes

from voxflow.text.inject import INPUT, ClipboardInjector


def test_win32_input_structure_has_native_size() -> None:
    assert ctypes.sizeof(INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)


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


def test_clipboard_failure_falls_back_to_unicode() -> None:
    clipboard = FakeClipboard()
    typed: list[str] = []
    injector = ClipboardInjector(
        restore_clipboard=True,
        clipboard=clipboard,
        send_paste=lambda: (_ for _ in ()).throw(OSError("blocked")),
        send_unicode=typed.append,
        sleeper=lambda _: None,
    )

    injector.inject("Olá", strategy="clipboard")

    assert typed == ["Olá"]
    assert clipboard.text == "anterior"
