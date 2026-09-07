"""Named Windows kernel objects for one instance and graceful shutdown."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

MUTEX_NAME = "Local\\VoxFlow-5B592C8E-01CF-4AFE-97E5-5E91A7C7759D"
QUIT_EVENT_NAME = "Local\\VoxFlow-Quit-5B592C8E-01CF-4AFE-97E5-5E91A7C7759D"
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
WAIT_OBJECT_0 = 0


def _kernel32() -> ctypes.WinDLL:
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateEventW.argtypes = [
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    kernel32.CreateEventW.restype = wintypes.HANDLE
    kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.OpenEventW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.SetEvent.argtypes = [wintypes.HANDLE]
    kernel32.SetEvent.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    return kernel32


class InstanceGuard:
    def __init__(self) -> None:
        kernel32 = _kernel32()
        self._mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not self._mutex:
            raise ctypes.WinError()
        self.already_running = kernel32.GetLastError() == ERROR_ALREADY_EXISTS
        self._quit_event = kernel32.CreateEventW(None, True, False, QUIT_EVENT_NAME)
        if not self._quit_event:
            kernel32.CloseHandle(self._mutex)
            raise ctypes.WinError()

    def quit_requested(self) -> bool:
        return _kernel32().WaitForSingleObject(self._quit_event, 0) == WAIT_OBJECT_0

    def close(self) -> None:
        kernel32 = _kernel32()
        if self._quit_event:
            kernel32.CloseHandle(self._quit_event)
            self._quit_event = None
        if self._mutex:
            kernel32.CloseHandle(self._mutex)
            self._mutex = None


def request_running_instance_quit() -> bool:
    kernel32 = _kernel32()
    handle = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, QUIT_EVENT_NAME)
    if not handle:
        return False
    try:
        return bool(kernel32.SetEvent(handle))
    finally:
        kernel32.CloseHandle(handle)
