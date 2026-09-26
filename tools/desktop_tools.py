import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import struct
import sys
import threading
from queue import Queue

from ollama import chat as ollama_chat

from core.events import EVENT_BUS, EventType
from core.file_permissions import (
    DESKTOP_CAPABILITIES,
    DesktopCapability,
)


USER32 = ctypes.windll.user32 if sys.platform == "win32" else None
GDI32 = ctypes.windll.gdi32 if sys.platform == "win32" else None
SCREENSHOT_PATH = Path(r"D:\ultron\ultron_screenshot.bmp")
VISION_IMAGE_ROOT = Path(r"D:\ultron").resolve()
VISION_MODEL = os.environ.get("ULTRON_VISION_MODEL", "llava:7b")
VISION_BACKEND = os.environ.get("ULTRON_VISION_BACKEND", "ollama")
VISION_TIMEOUT_SECONDS = float(os.environ.get("ULTRON_VISION_TIMEOUT_SECONDS", "20"))
MAX_TYPED_CHARACTERS = 1000
ALLOWED_KEYS = {
    "enter": 0x0D,
    "esc": 0x1B,
    "space": 0x20,
    "tab": 0x09,
    "backspace": 0x08,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
}


def _audit(operation: str, success: bool) -> None:
    EVENT_BUS.emit(
        EventType.DESKTOP_OPERATION,
        operation=operation,
        success=success,
    )


def _require(capability: DesktopCapability) -> None:
    DESKTOP_CAPABILITIES.require(capability)


def _vision_result(payload) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Vision output must be a JSON object.")

    elements = payload.get("elements")
    confidence = payload.get("confidence")
    summary = payload.get("screen_summary")

    if not isinstance(summary, str):
        raise ValueError("Vision output has no screen_summary.")
    if not isinstance(elements, list):
        raise ValueError("Vision output has no elements list.")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError("Vision output has invalid confidence.")

    normalized_elements = []

    for element in elements:
        if not isinstance(element, dict):
            raise ValueError("Vision elements must be objects.")

        required = {"type", "text", "x", "y", "width", "height"}

        if not required.issubset(element):
            raise ValueError("Vision element is missing required fields.")

        if not isinstance(element["type"], str) or not isinstance(element["text"], str):
            raise ValueError("Vision element labels must be strings.")

        if any(
            isinstance(element[key], bool)
            or not isinstance(element[key], (int, float))
            for key in ("x", "y", "width", "height")
        ):
            raise ValueError("Vision element coordinates must be numeric.")

        normalized_elements.append(
            {
                "type": element["type"],
                "text": element["text"],
                "x": element["x"],
                "y": element["y"],
                "width": element["width"],
                "height": element["height"],
            }
        )

    return {
        "screen_summary": summary,
        "elements": normalized_elements,
        "confidence": max(0.0, min(1.0, float(confidence))),
    }


def _vision_image_path(image_path: str) -> Path:
    if not isinstance(image_path, str) or not image_path.strip():
        raise ValueError("An image path is required.")

    path = Path(image_path).expanduser().resolve()

    try:
        path.relative_to(VISION_IMAGE_ROOT)
    except ValueError as exc:
        raise PermissionError(
            "Vision images must be inside the local ULTRON scope."
        ) from exc

    if not path.is_file():
        raise FileNotFoundError(f"Vision image does not exist: {path}")

    return path


def vision_analyze(image_path: str) -> dict:
    """Analyze a local screenshot with the configured local vision backend."""

    _require(DesktopCapability.SCREEN_VISION)

    try:
        path = _vision_image_path(image_path)

        if VISION_BACKEND.casefold() != "ollama":
            raise RuntimeError(
                f"Unsupported local vision backend: {VISION_BACKEND}"
            )

        response = ollama_chat(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Analyze this screenshot locally. Return only JSON with "
                        "screen_summary, elements, and confidence. Each element "
                        "must contain type, text, x, y, width, and height."
                    ),
                    "images": [str(path)],
                }
            ],
            format="json",
        )
        content = getattr(getattr(response, "message", None), "content", None)

        if not isinstance(content, str):
            raise ValueError("Vision backend returned no JSON content.")

        result = _vision_result(json.loads(content))
    except Exception:
        _audit("vision_analyze", False)
        raise

    _audit("vision_analyze", True)
    EVENT_BUS.emit(EventType.SCREEN_VISION, operation="vision_analyze")
    return result


def vision_describe(image_path: str, timeout: float = VISION_TIMEOUT_SECONDS) -> str:
    """Return an optional local semantic description without UI coordinates."""

    _require(DesktopCapability.SCREEN_VISION)
    path = _vision_image_path(image_path)

    if VISION_BACKEND.casefold() != "ollama":
        raise RuntimeError(f"Unsupported local vision backend: {VISION_BACKEND}")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("Vision timeout must be positive.")

    result_queue = Queue(maxsize=1)

    def request_description() -> None:
        try:
            response = ollama_chat(
                model=VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Describe the visible screen content and useful UI context "
                            "in plain text. Do not return JSON or coordinates."
                        ),
                        "images": [str(path)],
                    }
                ],
            )
            content = getattr(getattr(response, "message", None), "content", None)
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Vision backend returned no semantic description.")
            result_queue.put((True, content.strip()))
        except Exception as exc:
            result_queue.put((False, exc))

    worker = threading.Thread(target=request_description, daemon=True)
    worker.start()
    worker.join(float(timeout))

    if worker.is_alive():
        _audit("vision_describe", False)
        raise TimeoutError("Local vision description timed out.")

    success, value = result_queue.get()
    if not success:
        _audit("vision_describe", False)
        raise value

    _audit("vision_describe", True)
    EVENT_BUS.emit(EventType.SCREEN_VISION, operation="vision_describe")
    return value


def _require_windows() -> None:
    if USER32 is None:
        raise RuntimeError("Desktop controls require Windows.")


def _screen_size() -> tuple[int, int]:
    _require_windows()
    return USER32.GetSystemMetrics(0), USER32.GetSystemMetrics(1)


def _validate_coordinates(x, y) -> tuple[int, int]:
    if isinstance(x, bool) or not isinstance(x, int):
        raise ValueError("x must be an integer.")
    if isinstance(y, bool) or not isinstance(y, int):
        raise ValueError("y must be an integer.")

    width, height = _screen_size()

    if not (0 <= x < width and 0 <= y < height):
        raise ValueError("Coordinates are outside the screen bounds.")

    return x, y


def screenshot() -> str:
    _require(DesktopCapability.SCREENSHOT)

    try:
        _require_windows()
        width, height = _screen_size()
        screen_dc = USER32.GetDC(0)
        memory_dc = GDI32.CreateCompatibleDC(screen_dc)
        bitmap = GDI32.CreateCompatibleBitmap(screen_dc, width, height)
        previous = GDI32.SelectObject(memory_dc, bitmap)

        if not GDI32.BitBlt(memory_dc, 0, 0, width, height, screen_dc, 0, 0, 0x00CC0020):
            raise OSError("Screen capture failed.")

        class BitmapInfoHeader(ctypes.Structure):
            _fields_ = [
                ("size", wintypes.DWORD),
                ("width", wintypes.LONG),
                ("height", wintypes.LONG),
                ("planes", wintypes.WORD),
                ("bit_count", wintypes.WORD),
                ("compression", wintypes.DWORD),
                ("size_image", wintypes.DWORD),
                ("x_pels", wintypes.LONG),
                ("y_pels", wintypes.LONG),
                ("colors_used", wintypes.DWORD),
                ("colors_important", wintypes.DWORD),
            ]

        header = BitmapInfoHeader(
            ctypes.sizeof(BitmapInfoHeader), width, -height, 1, 32, 0, 0, 0, 0, 0, 0
        )
        pixels = ctypes.create_string_buffer(width * height * 4)
        if not GDI32.GetDIBits(memory_dc, bitmap, 0, height, pixels, ctypes.byref(header), 0):
            raise OSError("Screen capture data was unavailable.")

        pixel_data = pixels.raw
        file_header_size = 14 + ctypes.sizeof(header)
        with SCREENSHOT_PATH.open("wb") as output:
            output.write(struct.pack("<2sIHHI", b"BM", file_header_size + len(pixel_data), 0, 0, file_header_size))
            output.write(bytes(header))
            output.write(pixel_data)

        GDI32.SelectObject(memory_dc, previous)
        GDI32.DeleteObject(bitmap)
        GDI32.DeleteDC(memory_dc)
        USER32.ReleaseDC(0, screen_dc)
    except Exception:
        _audit("screenshot", False)
        raise

    _audit("screenshot", True)
    return str(SCREENSHOT_PATH)


def mouse_move(x: int, y: int) -> str:
    _require(DesktopCapability.MOUSE_CONTROL)
    try:
        x, y = _validate_coordinates(x, y)
        if not USER32.SetCursorPos(x, y):
            raise OSError("Could not move the mouse.")
    except Exception:
        _audit("mouse_move", False)
        raise
    _audit("mouse_move", True)
    return "Mouse moved."


def mouse_click(x: int, y: int, button: str = "left") -> str:
    _require(DesktopCapability.MOUSE_CONTROL)
    flags = {"left": (2, 4), "right": (8, 16), "middle": (32, 64)}
    try:
        x, y = _validate_coordinates(x, y)
        if button not in flags:
            raise ValueError("button must be left, right, or middle.")
        if not USER32.SetCursorPos(x, y):
            raise OSError("Could not move the mouse.")
        down, up = flags[button]
        USER32.mouse_event(down, 0, 0, 0, 0)
        USER32.mouse_event(up, 0, 0, 0, 0)
    except Exception:
        _audit("mouse_click", False)
        raise
    _audit("mouse_click", True)
    return "Mouse click completed."


def keyboard_type(text: str) -> str:
    _require(DesktopCapability.KEYBOARD_CONTROL)
    try:
        _require_windows()
        if not isinstance(text, str) or len(text) > MAX_TYPED_CHARACTERS or not text.isprintable():
            raise ValueError("text must be printable and at most 1000 characters.")
        for character in text:
            virtual_key = USER32.VkKeyScanW(ord(character)) & 0xFF
            if virtual_key == 0xFF:
                raise ValueError("Text contains an unsupported character.")
            USER32.keybd_event(virtual_key, 0, 0, 0)
            USER32.keybd_event(virtual_key, 0, 2, 0)
    except Exception:
        _audit("keyboard_type", False)
        raise
    _audit("keyboard_type", True)
    return "Keyboard input completed."


def keyboard_press(key: str) -> str:
    _require(DesktopCapability.KEYBOARD_CONTROL)
    try:
        _require_windows()
        if not isinstance(key, str) or not key:
            raise ValueError("A key is required.")
        virtual_key = ALLOWED_KEYS.get(key.casefold())
        if virtual_key is None and len(key) == 1 and key.isprintable():
            virtual_key = USER32.VkKeyScanW(ord(key)) & 0xFF
        if virtual_key is None or virtual_key == 0xFF:
            raise ValueError("Unsupported key.")
        USER32.keybd_event(virtual_key, 0, 0, 0)
        USER32.keybd_event(virtual_key, 0, 2, 0)
    except Exception:
        _audit("keyboard_press", False)
        raise
    _audit("keyboard_press", True)
    return "Key press completed."


def get_windows() -> list[dict]:
    _require(DesktopCapability.WINDOW_CONTROL)
    try:
        windows = _enumerate_windows()
    except Exception:
        _audit("get_windows", False)
        raise
    _audit("get_windows", True)
    return windows


def _enumerate_windows() -> list[dict]:
    windows = []
    _require_windows()
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        if USER32.IsWindowVisible(hwnd):
            length = USER32.GetWindowTextLengthW(hwnd)
            title = ctypes.create_unicode_buffer(length + 1)
            USER32.GetWindowTextW(hwnd, title, length + 1)
            if title.value:
                windows.append({"window_id": int(hwnd), "title": title.value})
        return True
    USER32.EnumWindows(callback_type(callback), 0)
    return windows


def analyze_screen() -> dict:
    """Return local structured screen and window metadata without screen pixels."""

    _require(DesktopCapability.SCREEN_VISION)
    try:
        screenshot_path = screenshot()
        windows = _enumerate_windows()
        width, height = _screen_size()
        result = {
            "screenshot_path": screenshot_path,
            "screen_size": {"width": width, "height": height},
            "windows": windows,
            "ocr_available": False,
        }
    except Exception:
        _audit("analyze_screen", False)
        raise
    _audit("analyze_screen", True)
    EVENT_BUS.emit(EventType.SCREEN_VISION, operation="analyze_screen")
    return result


def find_window(title: str) -> list[dict]:
    _require(DesktopCapability.SCREEN_VISION)
    try:
        if not isinstance(title, str) or not title.strip():
            raise ValueError("A window title is required.")
        query = title.casefold()
        matches = [
            window
            for window in _enumerate_windows()
            if query in window["title"].casefold()
        ]
    except Exception:
        _audit("find_window", False)
        raise
    _audit("find_window", True)
    EVENT_BUS.emit(EventType.SCREEN_VISION, operation="find_window")
    return matches


def get_screen_text(image_path: str | None = None) -> dict:
    """Use only an installed local OCR library, if available."""

    _require(DesktopCapability.SCREEN_VISION)
    try:
        screenshot_path = image_path or screenshot()
        screenshot_path = str(_vision_image_path(screenshot_path))

        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            RapidOCR = None

        if RapidOCR is not None:
            detector = RapidOCR()
            raw_results, _ = detector(str(screenshot_path))
            normalized_results = []
            text_parts = []

            if raw_results:
                for item in raw_results:
                    if not isinstance(item, (list, tuple)) or len(item) < 3:
                        continue
                    coords, text, confidence = item
                    text_value = str(text).strip()
                    if not text_value:
                        continue
                    normalized_results.append(
                        {
                            "bbox": coords,
                            "text": text_value,
                            "confidence": float(confidence),
                        }
                    )
                    text_parts.append(text_value)

            result = {
                "available": True,
                "text": "\n".join(text_parts).strip(),
                "ocr_engine": "rapidocr_onnxruntime",
                "results": normalized_results,
                "screenshot_path": screenshot_path,
            }
        else:
            try:
                import pytesseract
                from PIL import Image
            except ImportError:
                result = {
                    "available": False,
                    "text": "",
                    "reason": "No local OCR library is installed.",
                    "screenshot_path": screenshot_path,
                }
            else:
                text = pytesseract.image_to_string(Image.open(screenshot_path)).strip()
                result = {
                    "available": True,
                    "text": text,
                    "ocr_engine": "pytesseract",
                    "results": [],
                    "screenshot_path": screenshot_path,
                }
    except Exception:
        _audit("get_screen_text", False)
        raise
    _audit("get_screen_text", True)
    EVENT_BUS.emit(EventType.SCREEN_VISION, operation="get_screen_text")
    return result


def _ocr_box_to_rect(box) -> tuple[int, int, int, int] | None:
    if not isinstance(box, (list, tuple)) or len(box) < 4:
        return None
    points = []
    for point in box[:4]:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return None
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in point[:2]):
            return None
        points.append((float(point[0]), float(point[1])))
    left = int(min(point[0] for point in points))
    top = int(min(point[1] for point in points))
    right = int(max(point[0] for point in points))
    bottom = int(max(point[1] for point in points))
    return left, top, max(0, right - left), max(0, bottom - top)


def combined_observation(
    *,
    vision_timeout: float = VISION_TIMEOUT_SECONDS,
) -> dict:
    """Combine authoritative local OCR/window data with optional semantics."""

    _require(DesktopCapability.SCREEN_VISION)
    try:
        screenshot_path = screenshot()
        ocr_result = get_screen_text(screenshot_path)
        width, height = _screen_size()
        windows = _enumerate_windows()
        ocr = []
        for item in ocr_result.get("results", []):
            rectangle = _ocr_box_to_rect(item.get("bbox"))
            text = item.get("text")
            confidence = item.get("confidence")
            if rectangle is None or not isinstance(text, str):
                continue
            if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
                continue
            x, y, item_width, item_height = rectangle
            ocr.append(
                {
                    "text": text,
                    "x": x,
                    "y": y,
                    "width": item_width,
                    "height": item_height,
                    "confidence": float(confidence),
                }
            )

        semantic_description = ""
        vision_available = False
        try:
            semantic_description = vision_describe(screenshot_path, vision_timeout)
            vision_available = True
        except Exception:
            pass

        result = {
            "screenshot": screenshot_path,
            "screen_size": {"width": width, "height": height},
            "ocr": ocr,
            "windows": windows,
            "semantic_description": semantic_description,
            "vision_available": vision_available,
        }
    except Exception:
        _audit("combined_observation", False)
        raise

    _audit("combined_observation", True)
    EVENT_BUS.emit(EventType.SCREEN_VISION, operation="combined_observation")
    return result


def focus_window(window_id=None, title: str | None = None) -> str:
    _require(DesktopCapability.WINDOW_CONTROL)
    try:
        _require_windows()
        hwnd = window_id
        if hwnd is None and isinstance(title, str) and title:
            matches = [window for window in _enumerate_windows() if window["title"] == title]
            if not matches:
                raise ValueError("Window was not found.")
            hwnd = matches[0]["window_id"]
        if isinstance(hwnd, bool) or not isinstance(hwnd, int) or hwnd <= 0:
            raise ValueError("A valid window_id or title is required.")
        if not USER32.SetForegroundWindow(hwnd):
            raise OSError("Could not focus window.")
    except Exception:
        _audit("focus_window", False)
        raise
    _audit("focus_window", True)
    return "Window focused."