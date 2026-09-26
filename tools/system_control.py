import subprocess


def lock_computer() -> str:
    """Lock the Windows computer."""
    try:
        subprocess.run(
            ["rundll32.exe", "user32.dll,LockWorkStation"],
            check=True,
        )
        return "Computer locked."

    except Exception as exc:
        return f"Could not lock the computer: {exc}"


def mute_audio() -> str:
    """Mute Windows system audio using PowerShell."""
    try:
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "(New-Object -ComObject WScript.Shell).SendKeys([char]173)",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return "System audio toggled."

    except Exception as exc:
        return f"Could not toggle system audio: {exc}"


def open_task_manager() -> str:
    """Open Windows Task Manager."""
    try:
        subprocess.Popen(
            ["taskmgr.exe"],
            shell=False,
        )
        return "Task Manager has been launched."

    except Exception as exc:
        return f"Could not launch Task Manager: {exc}"


def open_settings() -> str:
    """Open Windows Settings."""
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "", "ms-settings:"],
            shell=False,
        )
        return "Windows Settings has been opened."

    except Exception as exc:
        return f"Could not open Windows Settings: {exc}"