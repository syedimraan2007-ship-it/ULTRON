from copy import deepcopy

from core.proactive_message import ProactiveMessage


def test_browser_message_is_deterministic_and_metadata_only():
    generator = ProactiveMessage()

    assert generator.generate("chrome.exe", "Example", "meaningful_change") == (
        "A browser window is now active."
    )


def test_code_editor_message_is_coding_related():
    assert ProactiveMessage().generate(
        "Code.exe",
        "main.py - Visual Studio Code",
        "meaningful_change",
    ) == "A code editor is now active."


def test_terminal_message_is_terminal_related():
    assert ProactiveMessage().generate(
        "PowerShell.exe",
        "PowerShell",
        "meaningful_change",
    ) == "A terminal is now active."


def test_file_explorer_message_is_file_management_related():
    assert ProactiveMessage().generate(
        "explorer.exe",
        "Documents",
        "meaningful_change",
    ) == "File Explorer is now active."


def test_unknown_application_has_generic_acknowledgement():
    assert ProactiveMessage().generate(
        "notepad.exe",
        "notes.txt",
        "meaningful_change",
    ) == "You switched to notepad.exe."


def test_same_application_with_changed_title_gets_context_acknowledgement():
    generator = ProactiveMessage()
    generator.generate("Code.exe", "first.py", "meaningful_change")

    assert generator.generate("Code.exe", "second.py", "meaningful_change") == (
        "The Code.exe window changed context."
    )


def test_invalid_inputs_return_safe_generic_message():
    generator = ProactiveMessage()

    assert generator.generate(None, "title", "reason") == "Desktop context changed."
    assert generator.generate("Code.exe", "", "reason") == "Desktop context changed."
    assert generator.generate("x" * 257, "title", "reason") == "Desktop context changed."


def test_message_is_bounded():
    generator = ProactiveMessage()

    message = generator.generate("A" * 256, "title", "reason")

    assert isinstance(message, str)
    assert len(message) <= 512


def test_process_id_and_unsupported_claims_are_not_leaked():
    message = ProactiveMessage().generate(
        "Code.exe",
        "main.py - Visual Studio Code",
        "process_id=1234; inspect screen",
    )

    assert "1234" not in message
    assert "process" not in message.casefold()
    assert "screen" not in message.casefold()
    assert "see" not in message.casefold()


def test_same_input_is_deterministic_for_fresh_instances():
    arguments = ("PowerShell.exe", "PowerShell", "meaningful_change")

    assert ProactiveMessage().generate(*arguments) == ProactiveMessage().generate(*arguments)


def test_generator_does_not_mutate_input_values():
    values = ["Code.exe", "main.py", "meaningful_change"]
    before = deepcopy(values)

    ProactiveMessage().generate(*values)

    assert values == before