"""Track meaningful changes in normalized desktop-context snapshots."""

from collections.abc import Mapping


_MEANINGFUL_FIELDS = (
    "application",
    "window_title",
    "process_id",
)


def _meaningful_context(context: Mapping[str, object] | None) -> dict[str, object]:
    active_window = context.get("active_window") if isinstance(context, Mapping) else None

    if not isinstance(active_window, Mapping):
        active_window = {}

    return {
        field: active_window.get(field)
        for field in _MEANINGFUL_FIELDS
    }


class DesktopContextTracker:
    """Compare successive normalized desktop-context snapshots in memory."""

    def __init__(self) -> None:
        self._previous_context: dict[str, object] | None = None

    def update(self, context: Mapping[str, object] | None) -> dict[str, object]:
        """Record a snapshot and compare it with the immediately previous one."""

        current_context = _meaningful_context(context)
        previous_context = self._previous_context
        is_first = previous_context is None
        changed = not is_first and current_context != previous_context

        self._previous_context = current_context.copy()

        return {
            "is_first": is_first,
            "changed": changed,
            "previous": previous_context.copy() if previous_context else None,
            "current": current_context.copy(),
        }
