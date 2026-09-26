"""Local screenshot -> vision -> Qwen desktop action loop."""

import json

from core.ultron import run_agent
from tools.desktop_tools import (
    combined_observation,
)


DESKTOP_ACTIONS = frozenset(
    {
        "mouse_move",
        "mouse_click",
        "keyboard_type",
        "keyboard_press",
        "focus_window",
    }
)
DEFAULT_ACTION_LIMIT = 1


def _failure(stage: str, error: Exception | str) -> dict:
    return {
        "ok": False,
        "stage": stage,
        "error": str(error),
    }


def _validate_observation(observation: dict) -> dict:
    required = {"screenshot", "screen_size", "ocr", "windows", "semantic_description", "vision_available"}
    if not isinstance(observation, dict) or not required.issubset(observation):
        raise ValueError("Combined visual observation is malformed.")
    if not isinstance(observation["ocr"], list) or not isinstance(observation["windows"], list):
        raise ValueError("Combined visual observation has invalid OCR or windows.")
    if not isinstance(observation["semantic_description"], str):
        raise ValueError("Combined visual observation has invalid semantics.")
    if not isinstance(observation["vision_available"], bool):
        raise ValueError("Combined visual observation has invalid vision availability.")
    return observation


def _observation_is_actionable(observation: dict) -> bool:
    confident_text = [
        item for item in observation["ocr"]
        if isinstance(item, dict) and item.get("confidence", 0) >= 0.5
    ]
    return bool(
        confident_text
        or (observation["semantic_description"] and len(observation["windows"]) == 1)
    )


def run_vision_action_loop(
    user_goal: str,
    messages: list,
    *,
    max_actions: int = DEFAULT_ACTION_LIMIT,
) -> dict:
    """Perform at most a bounded local visual action and verify its result."""

    if not isinstance(user_goal, str) or not user_goal.strip():
        return _failure("input", "A visual action goal is required.")
    if max_actions < 1:
        return _failure("input", "max_actions must be at least 1.")

    try:
        before = _validate_observation(combined_observation())
    except Exception as exc:
        return _failure("before_action", exc)

    if not _observation_is_actionable(before):
        return _failure("before_action", "Visual target is low-confidence or ambiguous.")

    visual_context = json.dumps(before, ensure_ascii=True, sort_keys=True)
    action_results = []

    def record_action(tool_name: str, result: str) -> None:
        if tool_name in DESKTOP_ACTIONS:
            action_results.append({"tool": tool_name, "result": result})

    try:
        run_agent(
            (
                f"Use the desktop tools to accomplish this goal: {user_goal}\n"
                "Here is the current local visual state as structured JSON:\n"
                f"{visual_context}\n"
                "Choose at most one desktop action. Do not use non-desktop tools."
            ),
            messages,
            allowed_tools=DESKTOP_ACTIONS,
            max_tool_iterations=max_actions,
            on_tool_result=record_action,
        )
    except Exception as exc:
        return _failure("qwen", exc)

    if not action_results:
        return _failure("action", "Qwen did not select a permitted desktop action.")

    if len(action_results) > max_actions:
        return _failure("action", "Visual action limit was exceeded.")

    if any(str(action["result"]).startswith("Tool error:") for action in action_results):
        return _failure("action", action_results[-1]["result"])

    try:
        after = _validate_observation(combined_observation())
    except Exception as exc:
        return _failure("after_action", exc)

    return {
        "ok": True,
        "action": action_results[-1],
        "before": before,
        "after": after,
    }