"""Explicit synchronous boundary for passive proactive presentation."""

from copy import deepcopy

from core.proactive_consumer import ProactiveConsumer
from core.proactive_cooldown import ProactiveCooldown
from core.proactive_presenter import ProactivePresenter
from core.proactive_relevance import ProactiveRelevance
from core.proactive_dispatch_result import ProactiveDispatchResult
from core.proactive_policy import ProactivePolicy
from core.proactive_reasoner import ProactiveReasoner
from core.proactive_observability import ProactiveDecision, decision_from


class ProactiveDispatcher:
    """Attempt one consumer-to-presenter handoff without performing actions."""

    def __init__(
        self,
        consumer: ProactiveConsumer,
        presenter: ProactivePresenter,
        cooldown: ProactiveCooldown | None = None,
        relevance: ProactiveRelevance | None = None,
        policy: ProactivePolicy | None = None,
        reasoner: ProactiveReasoner | None = None,
    ) -> None:
        self._consumer = consumer
        self._presenter = presenter
        self._cooldown = cooldown
        self._relevance = relevance
        self._policy = policy
        self._reasoner = reasoner
        self._last_decision: ProactiveDecision | None = None

    def last_decision(self) -> ProactiveDecision | None:
        """Return the latest immutable public dispatch decision."""

        return self._last_decision

    def dispatch_once(self) -> dict[str, str] | None:
        """Return the payload from one successful dispatch, if any."""

        result = self.dispatch_once_result()
        if result.status == "presented":
            return dict(result.payload)
        return None

    def dispatch_once_result(self) -> ProactiveDispatchResult:
        """Return sanitized diagnostics for one synchronous dispatch attempt."""

        if self._cooldown is not None:
            try:
                if not self._cooldown.is_allowed():
                    return self._finish(
                        ProactiveDispatchResult("cooldown"),
                        reason="cooldown",
                    )
            except Exception:
                return self._finish(
                    ProactiveDispatchResult("rejected"),
                    reason="cooldown_error",
                )

        try:
            candidate = self._consumer.consume_next()
        except Exception:
            return self._finish(
                ProactiveDispatchResult("rejected"),
                reason="consumer_error",
            )

        if candidate is None:
            return self._finish(
                ProactiveDispatchResult("no_candidate"),
                reason="no_candidate",
            )

        if self._relevance is not None:
            try:
                if not self._relevance.is_relevant(candidate):
                    return self._finish(
                        ProactiveDispatchResult("irrelevant"),
                        source=candidate,
                        reason="irrelevant",
                    )
            except Exception:
                return self._finish(
                    ProactiveDispatchResult("rejected"),
                    source=candidate,
                    reason="relevance_error",
                )

        try:
            presenter_candidate = deepcopy(candidate)
            presentation = self._presenter.present(presenter_candidate)
        except Exception:
            return self._finish(
                ProactiveDispatchResult("rejected"),
                source=candidate,
                reason="presenter_error",
            )

        if presentation is None:
            return self._finish(
                ProactiveDispatchResult("rejected"),
                source=candidate,
                reason="presenter_rejected",
            )

        if self._reasoner is not None:
            try:
                reasoning = self._reasoner.evaluate(presentation)
            except Exception:
                return self._finish(
                    ProactiveDispatchResult("reasoner_rejected"),
                    source=presentation,
                    reason="reasoner_error",
                )

            if not self._valid_reasoning_result(reasoning):
                return self._finish(
                    ProactiveDispatchResult("reasoner_rejected"),
                    source=presentation,
                    reason="reasoner_rejected",
                )
            if not reasoning["should_speak"]:
                return self._finish(
                    ProactiveDispatchResult("reasoner_rejected"),
                    source=presentation,
                    reason="reasoner_rejected",
                    reasoner_reason=reasoning["reason"],
                )

            presentation = {
                **presentation,
                "message": reasoning["message"],
            }

        if self._policy is not None:
            try:
                if not self._policy.allow(presentation):
                    return self._finish(
                        ProactiveDispatchResult("rejected"),
                        source=presentation,
                        reason="policy_rejected",
                    )
            except Exception:
                return self._finish(
                    ProactiveDispatchResult("rejected"),
                    source=presentation,
                    reason="policy_error",
                )

        try:
            result = ProactiveDispatchResult("presented", presentation)
        except Exception:
            return self._finish(
                ProactiveDispatchResult("rejected"),
                source=presentation,
                reason="result_error",
            )

        if self._cooldown is not None:
            try:
                self._cooldown.record()
            except Exception:
                return self._finish(
                    ProactiveDispatchResult("rejected"),
                    source=presentation,
                    reason="cooldown_record_error",
                )

        return self._finish(
            result,
            source=presentation,
            reason="presented",
            reasoner_reason=(
                reasoning["reason"]
                if self._reasoner is not None
                else ""
            ),
        )

    def _finish(
        self,
        result: ProactiveDispatchResult,
        source: object = None,
        *,
        reason: str = "",
        reasoner_reason: str = "",
    ) -> ProactiveDispatchResult:
        self._last_decision = decision_from(
            result.status,
            source,
            reason=reason,
            reasoner_reason=reasoner_reason,
        )
        return result

    @staticmethod
    def _valid_reasoning_result(result: object) -> bool:
        if not isinstance(result, dict):
            return False
        if set(result) != {"should_speak", "message", "reason"}:
            return False

        should_speak = result.get("should_speak")
        message = result.get("message")
        reason = result.get("reason")
        return (
            isinstance(should_speak, bool)
            and isinstance(message, str)
            and len(message) <= 512
            and isinstance(reason, str)
            and len(reason) <= 128
            and (not should_speak or bool(message.strip()))
        )