"""Global hotkeys with a native Windows hook.

Bindings come from the configuration, not from constants here, and the hook only
swallows a key when taking it would otherwise cost the user a character. A chord
passes through to whatever has focus: binding ``ctrl+a`` must not cost anybody the
use of Ctrl or of select-all.
"""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass, field

from loguru import logger

from voxflow.keys import MODIFIERS, Hotkey, contains, matches, parse

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
HC_ACTION = 0


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.WPARAM),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


@dataclass
class _Hold:
    """A binding that means something for as long as it is held."""

    name: str
    spec: Hotkey | None
    on_press: Callable[[], None] | None
    on_release: Callable[[], None] | None
    #: Cleared to hand the key back temporarily without forgetting the binding.
    armed: threading.Event = field(default_factory=threading.Event)
    down: bool = False
    #: Set when a hold was cancelled and its key-up still has to be eaten, which only
    #: happens for bindings we were swallowing in the first place.
    swallow_up: bool = False

    @property
    def swallows(self) -> bool:
        return self.spec is not None and self.spec.steals_typing


@dataclass
class _Tap:
    """A binding that fires once, on the way down."""

    name: str
    spec: Hotkey | None
    on_press: Callable[[], None] | None
    down: bool = False


class NativeHoldHotkey:
    def __init__(
        self,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
        on_cancel: Callable[[], None] | None = None,
        on_hermes_toggle: Callable[[], None] | None = None,
        on_talk_press: Callable[[], None] | None = None,
        on_talk_release: Callable[[], None] | None = None,
        on_talk_cancel: Callable[[], None] | None = None,
    ) -> None:
        self._on_cancel = on_cancel
        self._on_talk_cancel = on_talk_cancel
        self._dictation = _Hold("dictation", parse("ctrl+num_add"), on_press, on_release)
        self._talk = _Hold("talk", parse("num_add"), on_talk_press, on_talk_release)
        self._toggle = _Tap("hermes_toggle", parse("f9"), on_hermes_toggle)
        self._cancel_spec: Hotkey | None = parse("esc")
        self._dictation.armed.set()
        self._held: set[str] = set()
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._hook: int | None = None
        self._callback_ref: HOOKPROC | None = None
        self._ready = threading.Event()
        self._startup_error: Exception | None = None

    # -- bindings ------------------------------------------------------------------

    def set_bindings(
        self,
        *,
        dictation_hold: str | None = None,
        push_to_talk: str | None = None,
        hermes_toggle: str | None = None,
        cancel: str | None = None,
    ) -> None:
        """Rebind from configuration text. An unreadable or empty chord unbinds."""

        if dictation_hold is not None:
            self._dictation.spec = parse(dictation_hold)
        if push_to_talk is not None:
            self._talk.spec = parse(push_to_talk)
        if hermes_toggle is not None:
            self._toggle.spec = parse(hermes_toggle)
        if cancel is not None:
            self._cancel_spec = parse(cancel)
        logger.info(
            "hotkeys_bound dictation={} talk={} toggle={} swallowing={}",
            self._dictation.spec.text() if self._dictation.spec else "none",
            self._talk.spec.text() if self._talk.spec else "none",
            self._toggle.spec.text() if self._toggle.spec else "none",
            ",".join(
                hold.name for hold in (self._dictation, self._talk) if hold.swallows
            )
            or "none",
        )

    def set_talk_armed(self, armed: bool) -> None:
        """Hand push-to-talk its key, or give it back to Windows."""

        if armed:
            self._talk.armed.set()
        else:
            self._talk.armed.clear()

    # -- decisions -----------------------------------------------------------------

    def _fire(self, callback: Callable[[], None] | None, failure: str) -> None:
        if callback is None:
            return
        try:
            callback()
        except Exception:
            logger.exception(failure)

    def _release(self, hold: _Hold, key: int) -> bool | None:
        """Close out a hold on its key-up. ``None`` when this event is not its own."""

        if hold.spec is None or key != hold.spec.key:
            return None
        if hold.down:
            # A hold owns its key-up even if the modifiers were let go first, or the
            # binding was disarmed mid-hold; otherwise the press is never closed.
            hold.down = False
            self._fire(hold.on_release, f"{hold.name}_release_callback_failed")
            return hold.swallows
        if hold.swallow_up:
            hold.swallow_up = False
            return True
        return None

    def _cancel(self, hold: _Hold, callback: Callable[[], None] | None) -> bool:
        hold.down = False
        hold.swallow_up = hold.swallows
        self._fire(callback, f"{hold.name}_cancel_callback_failed")
        return False

    def _handle_key(self, key: int, is_down: bool, is_up: bool) -> bool:
        """Decide what a key event means. True swallows it from the rest of Windows.

        Kept apart from the hook callback so the rules — which decide whether a key
        still reaches the focused application — can be exercised without a real hook."""

        modifier = MODIFIERS.get(key)
        if modifier is not None:
            if is_down:
                self._held.add(modifier)
            elif is_up:
                self._held.discard(modifier)
            return False

        if is_up:
            for hold in (self._dictation, self._talk):
                verdict = self._release(hold, key)
                if verdict is not None:
                    return verdict
            if self._toggle.spec is not None and key == self._toggle.spec.key:
                self._toggle.down = False
            return False

        if not is_down:
            return False

        if self._cancel_spec is not None and contains(self._cancel_spec, key, self._held):
            # Cancelling is not worth taking the key for: Esc keeps working elsewhere.
            if self._talk.down:
                return self._cancel(self._talk, self._on_talk_cancel)
            if self._dictation.down:
                return self._cancel(self._dictation, self._on_cancel)

        for hold in (self._dictation, self._talk):
            if hold.spec is None or not hold.armed.is_set():
                continue
            if not matches(hold.spec, key, self._held):
                continue
            if not hold.down:
                hold.down = True
                self._fire(hold.on_press, f"{hold.name}_press_callback_failed")
            # Holding a key repeats the key-down; the guard above fires once.
            return hold.swallows

        if self._toggle.spec is not None and matches(self._toggle.spec, key, self._held):
            if not self._toggle.down:
                self._toggle.down = True
                self._fire(self._toggle.on_press, "hermes_hotkey_callback_failed")
            return self._toggle.spec.steals_typing

        return False

    # -- lifecycle -----------------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="voxflow-hotkey", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=3):
            raise RuntimeError("Timeout ao iniciar o hook global.")
        if self._startup_error is not None:
            raise RuntimeError("Falha ao instalar o hook global.") from self._startup_error
        logger.info("global_hotkey_ready backend=WH_KEYBOARD_LL")

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
        self._thread_id = 0

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,
            HOOKPROC,
            wintypes.HINSTANCE,
            wintypes.DWORD,
        ]
        user32.SetWindowsHookExW.restype = wintypes.HANDLE
        user32.CallNextHookEx.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.CallNextHookEx.restype = wintypes.LPARAM
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        self._thread_id = kernel32.GetCurrentThreadId()

        @HOOKPROC
        def callback(code: int, message: int, data_pointer: int) -> int:
            if code != HC_ACTION:
                return user32.CallNextHookEx(self._hook, code, message, data_pointer)
            data = ctypes.cast(data_pointer, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            is_down = message in {WM_KEYDOWN, WM_SYSKEYDOWN}
            is_up = message in {WM_KEYUP, WM_SYSKEYUP}
            if self._handle_key(data.vkCode, is_down, is_up):
                return 1
            return user32.CallNextHookEx(self._hook, code, message, data_pointer)

        self._callback_ref = callback
        module = kernel32.GetModuleHandleW(None)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, callback, module, 0)
        if not self._hook:
            self._startup_error = ctypes.WinError()
            self._ready.set()
            return
        self._ready.set()
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None
