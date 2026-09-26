from enum import Enum
import threading


class FileCapability(Enum):
    FILE_READ = "FILE_READ"
    FILE_WRITE = "FILE_WRITE"
    FILE_DELETE = "FILE_DELETE"


class FilePermissionError(PermissionError):
    pass


class SystemCapability(Enum):
    SYSTEM_INFO = "SYSTEM_INFO"
    PROCESS_INFO = "PROCESS_INFO"
    PROCESS_START = "PROCESS_START"
    PROCESS_STOP = "PROCESS_STOP"
    APP_LAUNCH = "APP_LAUNCH"


class SystemPermissionError(PermissionError):
    pass


class FileCapabilityLayer:
    def __init__(self, granted=None):
        self._granted = set(
            granted
            if granted is not None
            else FileCapability
        )
        self._lock = threading.Lock()

    def grant(self, capability: FileCapability) -> None:
        with self._lock:
            self._granted.add(capability)

    def revoke(self, capability: FileCapability) -> None:
        with self._lock:
            self._granted.discard(capability)

    def require(self, capability: FileCapability) -> None:
        with self._lock:
            if capability not in self._granted:
                raise FilePermissionError(
                    f"Missing capability: {capability.value}"
                )


FILE_CAPABILITIES = FileCapabilityLayer()


class SystemCapabilityLayer:
    def __init__(self, granted=None):
        self._granted = set(
            granted
            if granted is not None
            else SystemCapability
        )
        self._lock = threading.Lock()

    def grant(self, capability: SystemCapability) -> None:
        with self._lock:
            self._granted.add(capability)

    def revoke(self, capability: SystemCapability) -> None:
        with self._lock:
            self._granted.discard(capability)

    def require(self, capability: SystemCapability) -> None:
        with self._lock:
            if capability not in self._granted:
                raise SystemPermissionError(
                    f"Missing capability: {capability.value}"
                )


SYSTEM_CAPABILITIES = SystemCapabilityLayer()


class DesktopCapability(Enum):
    SCREENSHOT = "SCREENSHOT"
    SCREEN_VISION = "SCREEN_VISION"
    MOUSE_CONTROL = "MOUSE_CONTROL"
    KEYBOARD_CONTROL = "KEYBOARD_CONTROL"
    WINDOW_CONTROL = "WINDOW_CONTROL"


class DesktopPermissionError(PermissionError):
    pass


class DesktopCapabilityLayer:
    def __init__(self, granted=None):
        self._granted = set(
            granted
            if granted is not None
            else DesktopCapability
        )
        self._lock = threading.Lock()

    def grant(self, capability: DesktopCapability) -> None:
        with self._lock:
            self._granted.add(capability)

    def revoke(self, capability: DesktopCapability) -> None:
        with self._lock:
            self._granted.discard(capability)

    def require(self, capability: DesktopCapability) -> None:
        with self._lock:
            if capability not in self._granted:
                raise DesktopPermissionError(
                    f"Missing capability: {capability.value}"
                )


DESKTOP_CAPABILITIES = DesktopCapabilityLayer()