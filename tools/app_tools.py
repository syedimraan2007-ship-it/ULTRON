import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

from core.events import EVENT_BUS, EventType
from core.file_permissions import (
    SYSTEM_CAPABILITIES,
    SystemCapability,
)


# Common Windows application locations.
SEARCH_ROOTS = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    Path(os.environ.get("LOCALAPPDATA", "")),
]

ULTRON_ROOT = Path(r"D:\ultron").resolve()
PROTECTED_EXECUTABLES = {
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "wscript.exe",
    "cscript.exe",
    "mshta.exe",
    "rundll32.exe",
    "system.exe",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "services.exe",
    "lsass.exe",
    "winlogon.exe",
    "svchost.exe",
}


ALIASES = {
    "google chrome": "chrome",
    "chrome.exe": "chrome",
    "microsoft edge": "edge",
    "edge.exe": "edge",
    "visual studio code": "code",
    "vs code": "code",
    "code.exe": "code",
    "discord.exe": "discord",
    "steam.exe": "steam",
    "spotify.exe": "spotify",
    "notepad.exe": "notepad",
    "calculator": "calculator",
    "calculator.exe": "calculator",
    "calc": "calculator",
    "calc.exe": "calculator",
}


def normalize_application_name(name: str) -> str:
    """Normalize an application name."""
    name = name.lower().strip()

    return ALIASES.get(name, name)


def find_executable(paths: list[str]) -> str | None:
    """Find the first executable that exists."""
    for path in paths:
        if "\\" in path or "/" in path:
            if Path(path).exists():
                return path
        else:
            executable = shutil.which(path)

            if executable:
                return executable

    return None


def search_windows_apps(name: str) -> str | None:
    """
    Search common Windows application directories
    for an executable matching the requested name.
    """

    normalized = normalize_application_name(name)

    # First check PATH.
    executable = shutil.which(normalized)

    if executable:
        return executable

    # Direct executable-name search.
    executable_names = {
        normalized,
        f"{normalized}.exe",
    }

    for root in SEARCH_ROOTS:
        if not root.exists():
            continue

        try:
            for executable_name in executable_names:
                matches = root.rglob(executable_name)

                for match in matches:
                    if match.is_file():
                        return str(match)

        except (OSError, PermissionError):
            continue

    return None


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _approved_application(path: Path) -> bool:
    roots = [ULTRON_ROOT, *(root.resolve() for root in SEARCH_ROOTS)]
    return any(_is_within(path, root) for root in roots)


def _audit_launch(path: str, pid: int | None, success: bool) -> None:
    EVENT_BUS.emit(
        EventType.PROCESS_OPERATION,
        operation="launch_application",
        pid=pid,
        path=path,
        success=success,
    )


def launch_application(app_name: str) -> str:
    """Launch one resolved, approved Windows executable without arguments."""

    SYSTEM_CAPABILITIES.require(SystemCapability.APP_LAUNCH)

    try:
        if not isinstance(app_name, str) or not app_name.strip():
            raise ValueError("An application name is required.")

        value = app_name.strip()

        if any(character in value for character in "\x00\r\n;&|<>`$"):
            raise ValueError("Invalid application name.")

        executable_value = search_windows_apps(value)

        if executable_value is None:
            raise FileNotFoundError(
                f"Application was not found: {value}"
            )

        executable = Path(executable_value).expanduser().resolve()

        if executable.suffix.casefold() != ".exe":
            raise ValueError("Only executable .exe files may be launched.")

        if executable.name.casefold() in PROTECTED_EXECUTABLES:
            raise PermissionError(
                "Protected system executables cannot be launched."
            )

        if not executable.is_file() or not _approved_application(executable):
            raise PermissionError(
                "Application executable is outside approved locations."
            )

        process = subprocess.Popen(
            [str(executable)],
            shell=False,
        )

    except (OSError, PermissionError, ValueError) as exc:
        _audit_launch(str(app_name), None, False)
        return f"Could not launch application: {exc}"

    pid = getattr(process, "pid", None)
    _audit_launch(str(executable), pid, True)
    pid_text = f" (PID {pid})" if pid is not None else ""
    return f"Application launched: {executable}{pid_text}"


def open_application(name: str) -> str:
    """
    Open a Windows application by executable name.
    """

    name = name.strip()

    if not name:
        return "No application name was provided."

    normalized = normalize_application_name(name)

    executable = search_windows_apps(normalized)

    if executable is None:
        return (
            f"I could not find an installed application "
            f"matching '{name}'."
        )

    try:
        subprocess.Popen(
            [executable],
            shell=False,
        )

        return (
            f"{normalized} has been launched."
        )

    except OSError as exc:
        return (
            f"Could not launch {normalized}: {exc}"
        )


def open_url(url: str) -> str:
    """Open a validated HTTP/HTTPS URL in the default browser."""

    url = url.strip()

    if not url:
        return "No URL was provided."

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return "Only HTTP and HTTPS URLs are allowed."

    if not parsed.netloc:
        return "The URL is invalid."

    try:
        opened = webbrowser.open(url)

        if opened:
            return f"Opened {url}"

        return f"Could not open {url}"

    except Exception as exc:
        return f"Could not open URL: {exc}"