"""Global hold-to-dictate hotkey with a native Windows hook."""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes

from loguru import logger

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
VK_CONTROL = 0x11
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_ADD = 0x6B
VK_ESCAPE = 0x1B
VK_F9 = 0x78
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
        self._on_press = on_press
        self._on_release = on_release
        self._on_cancel = on_cancel
        self._on_hermes_toggle = on_hermes_toggle
        self._on_talk_press = on_talk_press
        self._on_talk_release = on_talk_release
        self._on_talk_cancel = on_talk_cancel
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._hook: int | None = None
        self._callback_ref: HOOKPROC | None = None
        self._ready = threading.Event()
        self._startup_error: Exception | None = None
        self._ctrl_keys_down: set[int] = set()
        self._combo_down = False
        self._f9_down = False
        # Bare numpad + only belongs to Friday while she is on screen. Outside a
        # conversation the key has to type "+" like any other key, so the hook is
        # gated instead of claiming the key for the whole session.
        self._talk_armed = threading.Event()
        self._talk_down = False
        self._swallow_talk_up = False

    def set_talk_armed(self, armed: bool) -> None:
        """Claim (or release) bare numpad + for push-to-talk.

        Called from the Qt thread while the hook thread reads the flag, which is why
        it is an Event and not a plain attribute."""

        if armed:
            self._talk_armed.set()
        else:
            self._talk_armed.clear()

    def _fire(self, callback: Callable[[], None] | None, failure: str) -> None:
        if callback is None:
            return
        try:
            callback()
        except Exception:
            logger.exception(failure)

    def _handle_key(self, key: int, is_down: bool, is_up: bool) -> bool:
        """Decide what a key event means. Returns True when the key is swallowed.

        Kept apart from the hook callback so the rules — which decide whether a key
        still reaches the rest of Windows — can be exercised without a real hook."""

        if key in {VK_CONTROL, VK_LCONTROL, VK_RCONTROL}:
            if is_down:
                self._ctrl_keys_down.add(key)
            elif is_up:
                self._ctrl_keys_down.discard(key)
            return False
        if key == VK_ADD:
            if is_down and self._ctrl_keys_down:
                if not self._combo_down:
                    self._combo_down = True
                    self._fire(self._on_press, "hotkey_press_callback_failed")
                return True
            if is_up and self._combo_down:
                self._combo_down = False
                self._fire(self._on_release, "hotkey_release_callback_failed")
                return True
            if is_up and self._swallow_talk_up:
                # The hold was already cancelled; eat the key-up so no stray "+" lands.
                self._swallow_talk_up = False
                return True
            if is_up and self._talk_down:
                # Released after the mode was disarmed mid-hold — still ours to finish,
                # otherwise the press would never be closed out.
                self._talk_down = False
                self._fire(self._on_talk_release, "talk_release_callback_failed")
                return True
            if is_down and self._talk_armed.is_set() and not self._ctrl_keys_down:
                if not self._talk_down:
                    self._talk_down = True
                    self._fire(self._on_talk_press, "talk_press_callback_failed")
                # Holding a key repeats the key-down; the guard above fires once.
                return True
            return False
        if key == VK_ESCAPE and is_down:
            if self._talk_down:
                self._talk_down = False
                self._swallow_talk_up = True
                self._fire(self._on_talk_cancel, "talk_cancel_callback_failed")
                return True
            if self._combo_down:
                self._fire(self._on_cancel, "hotkey_cancel_callback_failed")
                return True
            return False
        if key == VK_F9:
            if is_down and not self._f9_down:
                self._f9_down = True
                self._fire(self._on_hermes_toggle, "hermes_hotkey_callback_failed")
                return True
            if is_up:
                self._f9_down = False
                return True
        return False

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="voxflow-hotkey", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=3):
            raise RuntimeError("Timeout ao iniciar o hook global.")
        if self._startup_error is not None:
            raise RuntimeError("Falha ao instalar o hook global.") from self._startup_error
        logger.info("global_hotkey_ready shortcut=ctrl+num_add backend=WH_KEYBOARD_LL")

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
