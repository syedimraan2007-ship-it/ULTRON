"""In-memory recording boundary for eligible proactive events."""

from collections import deque
from collections.abc import Callable

from core.events import EVENT_BUS, Event, EventBus, EventType


class ProactiveEventQueue:
    """Bounded FIFO storage for sanitized proactive event metadata."""

    DEFAULT_CAPACITY = 32
    MAX_TEXT_LENGTH = 256

    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")

        self._capacity = capacity
        self._events: deque[dict[str, str]] = deque(maxlen=capacity)
        self._subscriptions: list[tuple[EventBus, Callable]] = []

    def push(self, event: Event) -> None:
        """Record a valid proactive event, silently rejecting other events."""

        metadata = self._metadata_from_event(event)
        if metadata is not None:
            self._events.append(metadata)

    def pop(self) -> dict[str, str] | None:
        if not self._events:
            return None

        return self._events.popleft().copy()

    def peek(self) -> dict[str, str] | None:
        if not self._events:
            return None

        return self._events[0].copy()

    def clear(self) -> None:
        self._events.clear()

    def subscribe(self, event_bus: EventBus = EVENT_BUS) -> None:
        """Register this queue once with an event bus."""

        if any(bus is event_bus for bus, _handler in self._subscriptions):
            return

        handler = self._handle_event
        event_bus.subscribe(EventType.PROACTIVE_DESKTOP_EVENT, handler)
        self._subscriptions.append((event_bus, handler))

    def unsubscribe(self, event_bus: EventBus = EVENT_BUS) -> None:
        for index, (bus, handler) in enumerate(self._subscriptions):
            if bus is event_bus:
                bus.unsubscribe(EventType.PROACTIVE_DESKTOP_EVENT, handler)
                self._subscriptions.pop(index)
                return

    def __len__(self) -> int:
        return len(self._events)

    def _handle_event(self, event: Event) -> None:
        self.push(event)

    @classmethod
    def _metadata_from_event(cls, event: Event) -> dict[str, str] | None:
        if not isinstance(event, Event):
            return None
        if event.type is not EventType.PROACTIVE_DESKTOP_EVENT:
            return None
        if not isinstance(event.data, dict):
            return None

        values = {
            field: event.data.get(field)
            for field in ("event", "reason", "application", "window_title")
        }
        if not all(
            isinstance(value, str) and value.strip()
            for value in values.values()
        ):
            return None

        return {
            field: value.strip()[: cls.MAX_TEXT_LENGTH]
            for field, value in values.items()
        }