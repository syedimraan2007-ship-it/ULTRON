from datetime import datetime


def get_datetime() -> str:
    """Return the computer's current local date and time."""

    current_datetime = datetime.now()
    return current_datetime.strftime(
        "Local date and time: %A, %Y-%m-%d %H:%M:%S"
    )