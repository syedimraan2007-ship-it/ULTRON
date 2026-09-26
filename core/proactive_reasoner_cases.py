"""Fixed, private-data-free cases for evaluating proactive reasoning."""

from collections.abc import Mapping, Sequence
from types import MappingProxyType


MAX_MESSAGE_LENGTH = 512
MAX_TEXT_LENGTH = 256
MAX_REASON_LENGTH = 128


def _case(
    case_id: str,
    application: str,
    window_title: str,
    message: str,
    category: str,
) -> Mapping[str, object]:
    return MappingProxyType({
        "id": case_id,
        "candidate": MappingProxyType({
            "application": application,
            "window_title": window_title,
            "message": message,
            "reason": "desktop_context_change",
        }),
        "category": category,
    })


_LONG_TITLE = "Project window " + ("x" * 241)

PROACTIVE_REASONER_CASES: tuple[Mapping[str, object], ...] = (
    _case("browser_switch", "chrome.exe", "Example", "Browser is active.", "browser"),
    _case("code_editor_switch", "Code.exe", "main.py", "Code editor is active.", "code_editor"),
    _case("terminal_switch", "PowerShell.exe", "PowerShell", "Terminal is active.", "terminal"),
    _case("file_explorer_switch", "explorer.exe", "Documents", "File Explorer is active.", "file_explorer"),
    _case("chat_application", "Discord", "Discord", "Discord is active.", "chat"),
    _case("browser_media", "chrome.exe", "YouTube", "Browser is active.", "browser_media"),
    _case("same_app_title_change", "Code.exe", "tests.py", "The Code.exe window changed context.", "title_change"),
    _case("repeated_context", "Code.exe", "tests.py", "Code editor is active.", "repeated_context"),
    _case("unknown_application", "notepad.exe", "notes", "notepad.exe is active.", "unknown_application"),
    _case("security_utility", "Taskmgr.exe", "Task Manager", "Task Manager is active.", "security_admin"),
    _case("system_settings", "SystemSettings.exe", "Settings", "Settings is active.", "system_settings"),
    _case("lock_security_window", "LockApp.exe", "Windows Sign-in", "Security window is active.", "lock_security"),
    _case("search_transient_ui", "SearchHost.exe", "Search", "Search is active.", "transient_search"),
    _case("long_window_title", "Code.exe", _LONG_TITLE, "Code editor is active.", "long_title"),
    _case("metadata_only", "Code.exe", "main.py", "Code editor is active.", "metadata_only"),
)


def is_valid_candidate(candidate: object) -> bool:
    """Validate the bounded candidate contract supplied to the reasoner."""

    if not isinstance(candidate, Mapping):
        return False
    if set(candidate) != {"application", "window_title", "message", "reason"}:
        return False

    application = candidate.get("application")
    window_title = candidate.get("window_title")
    message = candidate.get("message")
    reason = candidate.get("reason")
    return (
        isinstance(application, str)
        and bool(application.strip())
        and len(application) <= MAX_TEXT_LENGTH
        and isinstance(window_title, str)
        and bool(window_title.strip())
        and len(window_title) <= MAX_TEXT_LENGTH
        and isinstance(message, str)
        and bool(message.strip())
        and len(message) <= MAX_MESSAGE_LENGTH
        and isinstance(reason, str)
        and bool(reason.strip())
        and len(reason) <= MAX_REASON_LENGTH
    )


def evaluate_cases(
    reasoner,
    cases: Sequence[Mapping[str, object]] = PROACTIVE_REASONER_CASES,
) -> list[dict[str, object]]:
    """Evaluate cases and return only IDs plus public reasoner results."""

    results = []
    for case in cases:
        case_id = case.get("id")
        candidate = case.get("candidate")
        try:
            result = reasoner.evaluate({
                field: candidate[field]
                for field in ("application", "window_title", "message")
            })
            if not isinstance(result, dict):
                raise ValueError("invalid reasoner result")
            if set(result) != {"should_speak", "message", "reason"}:
                raise ValueError("invalid reasoner result")
            if not isinstance(result["should_speak"], bool):
                raise ValueError("invalid reasoner result")
            if not isinstance(result["message"], str) or not isinstance(result["reason"], str):
                raise ValueError("invalid reasoner result")
            results.append({
                "id": case_id,
                "result": {
                    "should_speak": result["should_speak"],
                    "message": result["message"],
                    "reason": result["reason"],
                },
            })
        except Exception:
            results.append({
                "id": case_id,
                "result": {
                    "should_speak": False,
                    "message": "",
                    "reason": "reasoner_error",
                },
            })

    return results