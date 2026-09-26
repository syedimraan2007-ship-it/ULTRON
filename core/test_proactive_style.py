from copy import deepcopy

from core.proactive_style import ProactiveStyle


def test_browser_message_is_concise():
    assert ProactiveStyle().format(
        "A browser window is now active.",
        "chrome.exe",
        "Example",
        "meaningful_change",
    ) == "Browser is active."


def test_code_editor_message_is_concise():
    assert ProactiveStyle().format(
        "A code editor is now active.",
        "Code.exe",
        "main.py",
        "meaningful_change",
    ) == "Code editor is active."


def test_terminal_message_is_concise():
    assert ProactiveStyle().format(
        "A terminal is now active.",
        "PowerShell.exe",
        "PowerShell",
        "meaningful_change",
    ) == "Terminal is active."


def test_file_explorer_message_is_concise():
    assert ProactiveStyle().format(
        "File Explorer is now active.",
        "explorer.exe",
        "Documents",
        "meaningful_change",
    ) == "File Explorer is active."


def test_unknown_application_message_is_concise():
    assert ProactiveStyle().format(
        "You switched to Discord.",
        "Discord",
        "Friends",
        "meaningful_change",
    ) == "Discord is active."


def test_title_change_message_is_preserved():
    message = "The Visual Studio Code window changed context."

    assert ProactiveStyle().format(
        message,
        "Visual Studio Code",
        "other.py",
        "meaningful_change",
    ) == message


def test_invalid_message_uses_deterministic_fallback():
    style = ProactiveStyle()

    assert style.format(None, "Code.exe", "main.py", "reason") == (
        "Desktop context changed."
    )
    assert style.format("x" * 513, "Code.exe", "main.py", "reason") == (
        "Desktop context changed."
    )


def test_invalid_metadata_preserves_valid_message():
    message = "A browser window is now active."

    assert ProactiveStyle().format(message, None, "title", "reason") == message


def test_output_is_bounded():
    message = "You switched to " + ("x" * 490)

    result = ProactiveStyle().format(message, "unknown", "title", "reason")

    assert len(result) <= 512


def test_output_is_deterministic():
    arguments = (
        "A code editor is now active.",
        "Code.exe",
        "main.py",
        "meaningful_change",
    )

    assert ProactiveStyle().format(*arguments) == ProactiveStyle().format(*arguments)


def test_no_screen_claims_or_process_ids_are_added():
    result = ProactiveStyle().format(
        "You switched to Code.exe.",
        "Code.exe",
        "main.py",
        "process_id=1234 inspect screen",
    )

    assert "screen" not in result.casefold()
    assert "see" not in result.casefold()
    assert "1234" not in result


def test_inputs_are_not_mutated():
    values = ["A terminal is now active.", "PowerShell.exe", "PowerShell", "reason"]
    before = deepcopy(values)

    ProactiveStyle().format(*values)

    assert values == before