from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class EventType(Enum):
    WAKE_DETECTED = "WAKE_DETECTED"
    LISTENING_STARTED = "LISTENING_STARTED"
    TRANSCRIPTION_READY = "TRANSCRIPTION_READY"
    THINKING_STARTED = "THINKING_STARTED"
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_COMPLETED = "TOOL_COMPLETED"
    SPEAKING_STARTED = "SPEAKING_STARTED"
    SPEAKING_COMPLETED = "SPEAKING_COMPLETED"
    BARGE_IN = "BARGE_IN"
    ERROR = "ERROR"
    SESSION_ENDED = "SESSION_ENDED"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_CANCELLED = "TASK_CANCELLED"
    FILE_OPERATION = "FILE_OPERATION"
    PROCESS_OPERATION = "PROCESS_OPERATION"
    DESKTOP_OPERATION = "DESKTOP_OPERATION"
    SCREEN_VISION = "SCREEN_VISION"
    PROACTIVE_DESKTOP_EVENT = "PROACTIVE_DESKTOP_EVENT"


@dataclass(frozen=True)
class Event:
    type: EventType
    data: dict = field(default_factory=dict)


class EventBus:
    def __init__(self):
        self._subscribers: dict[EventType, list[Callable]] = {}

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None],
    ) -> None:
        handlers = self._subscribers.setdefault(event_type, [])

        if handler not in handlers:
            handlers.append(handler)

    def unsubscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None],
    ) -> None:
        handlers = self._subscribers.get(event_type, [])

        if handler in handlers:
            handlers.remove(handler)

    def emit(self, event_type: EventType, **data) -> None:
        event = Event(event_type, data)

        for handler in tuple(self._subscribers.get(event_type, [])):
            try:
                handler(event)
            except Exception as exc:
                print(f"ULTRON EVENT ERROR > {type(exc).__name__}")


EVENT_BUS = EventBus()