"""Read-only metadata about the currently foreground Windows window."""

import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
import sys


if sys.platform == "win32":
    USER32 = ctypes.WinDLL("user32", use_last_error=True)
    KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)

    USER32.GetForegroundWindow.restype = wintypes.HWND
    USER32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    USER32.GetWindowTextLengthW.restype = ctypes.c_int
    USER32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    USER32.GetWindowTextW.restype = ctypes.c_int
    USER32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        wintypes.LPDWORD,
    ]
    USER32.GetWindowThreadProcessId.restype = wintypes.DWORD

    KERNEL32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    KERNEL32.OpenProcess.restype = wintypes.HANDLE
    KERNEL32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        wintypes.LPDWORD,
    ]
    KERNEL32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
    KERNEL32.CloseHandle.restype = wintypes.BOOL
else:
    USER32 = None
    KERNEL32 = None


_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _empty_result(timestamp: str) -> dict[str, object]:
    return {
        "application": None,
        "window_title": None,
        "process_id": None,
        "timestamp": timestamp,
    }


def _get_foreground_window() -> int | None:
    if USER32 is None:
        return None

    handle = USER32.GetForegroundWindow()
    return int(handle) if handle else None


def _get_window_title(window_handle: int) -> str | None:
    if USER32 is None:
        return None

    title_length = USER32.GetWindowTextLengthW(window_handle)

    if title_length <= 0:
        return None

    title_buffer = ctypes.create_unicode_buffer(title_length + 1)
    copied_length = USER32.GetWindowTextW(
        window_handle,
        title_buffer,
        len(title_buffer),
    )

    if copied_length <= 0:
        return None

    return title_buffer.value


def _get_process_id(window_handle: int) -> int | None:
    if USER32 is None:
        return None

    process_id = wintypes.DWORD()
    result = USER32.GetWindowThreadProcessId(
        window_handle,
        ctypes.byref(process_id),
    )

    if not result or not process_id.value:
        return None

    return int(process_id.value)


def _get_process_name(process_id: int | None) -> str | None:
    if KERNEL32 is None or not process_id:
        return None

    process_handle = KERNEL32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        process_id,
    )

    if not process_handle:
        return None

    try:
        path_buffer = ctypes.create_unicode_buffer(1024)
        path_length = wintypes.DWORD(len(path_buffer))
        result = KERNEL32.QueryFullProcessImageNameW(
            process_handle,
            0,
            path_buffer,
            ctypes.byref(path_length),
        )

        if not result or not path_buffer.value:
            return None

        return Path(path_buffer.value).name or None

    finally:
        KERNEL32.CloseHandle(process_handle)


def get_active_window() -> dict[str, object]:
    """Return structured metadata for the current foreground window."""

    timestamp = datetime.now(timezone.utc).isoformat()
    result = _empty_result(timestamp)

    try:
        window_handle = _get_foreground_window()
    except Exception:
        return result

    if not window_handle:
        return result

    try:
        result["window_title"] = _get_window_title(window_handle)
    except Exception:
        result["window_title"] = None

    try:
        process_id = _get_process_id(window_handle)
    except Exception:
        process_id = None

    result["process_id"] = process_id

    try:
        result["application"] = _get_process_name(process_id)
    except Exception:
        result["application"] = None

    return result
