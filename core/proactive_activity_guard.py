"""Explicit activity gate for future proactive output."""

from enum import Enum
from typing import Callable

from core.events import EVENT_BUS, Event, EventBus, EventType


class ProactiveActivityState(Enum):
    """Activity vocabulary aligned with the existing voice session states."""

    UNKNOWN = "UNKNOWN"
    IDLE = "IDLE"
    USER_ACTIVE = "USER_ACTIVE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"


class ProactiveActivityGuard:
    """Allow proactive output only after an explicit transition to idle."""

    @property
    def state(self) -> ProactiveActivityState:
        return self._state

    def is_allowed(self) -> bool:
        return self._state is ProactiveActivityState.IDLE

    def set_user_active(self) -> None:
        self._set_state(ProactiveActivityState.USER_ACTIVE)

    def set_idle(self) -> None:
        self._set_state(ProactiveActivityState.IDLE)

    def set_listening(self) -> None:
        self._set_state(ProactiveActivityState.LISTENING)

    def set_transcribing(self) -> None:
        self._set_state(ProactiveActivityState.TRANSCRIBING)

    def set_thinking(self) -> None:
        self._set_state(ProactiveActivityState.THINKING)

    def set_speaking(self) -> None:
        self._set_state(ProactiveActivityState.SPEAKING)

    def set_barge_in(self) -> None:
        self._set_state(ProactiveActivityState.INTERRUPTED)

    def subscribe(self, event_bus: EventBus = EVENT_BUS) -> None:
        """Observe voice lifecycle events once for the supplied event bus."""

        if any(bus is event_bus for bus, _handler in self._subscriptions):
            return

        handler = self._handle_event
        event_bus.subscribe(
            EventType.WAKE_DETECTED,
            handler,
        )
        for event_type in self._LIFECYCLE_EVENTS:
            event_bus.subscribe(event_type, handler)
        self._subscriptions.append((event_bus, handler))

    def unsubscribe(self, event_bus: EventBus = EVENT_BUS) -> None:
        for index, (bus, handler) in enumerate(self._subscriptions):
            if bus is event_bus:
                for event_type in self._LIFECYCLE_EVENTS:
                    bus.unsubscribe(event_type, handler)
                bus.unsubscribe(EventType.WAKE_DETECTED, handler)
                self._subscriptions.pop(index)
                return

    def _set_state(self, state: ProactiveActivityState) -> None:
        self._state = state

    def _handle_event(self, event: Event) -> None:
        if not isinstance(event, Event):
            return

        if event.type is EventType.WAKE_DETECTED:
            self.set_user_active()
        elif event.type is EventType.LISTENING_STARTED:
            self.set_listening()
        elif event.type is EventType.TRANSCRIPTION_READY:
            self.set_transcribing()
        elif event.type is EventType.THINKING_STARTED:
            self.set_thinking()
        elif event.type is EventType.SPEAKING_STARTED:
            self.set_speaking()
        elif event.type is EventType.SPEAKING_COMPLETED:
            interrupted = (
                isinstance(event.data, dict)
                and event.data.get("interrupted") is True
            )
            if interrupted:
                self.set_barge_in()
            else:
                self.set_user_active()
        elif event.type is EventType.BARGE_IN:
            self.set_barge_in()
        elif event.type is EventType.ERROR:
            self.set_user_active()
        elif event.type is EventType.SESSION_ENDED:
            self.set_idle()

    _LIFECYCLE_EVENTS = (
        EventType.LISTENING_STARTED,
        EventType.TRANSCRIPTION_READY,
        EventType.THINKING_STARTED,
        EventType.SPEAKING_STARTED,
        EventType.SPEAKING_COMPLETED,
        EventType.BARGE_IN,
        EventType.ERROR,
        EventType.SESSION_ENDED,
    )

    def __init__(self) -> None:
        self._state = ProactiveActivityState.UNKNOWN
        self._subscriptions: list[tuple[EventBus, Callable]] = []