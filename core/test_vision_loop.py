from core import vision_loop
from core.file_permissions import (
    DESKTOP_CAPABILITIES,
    DesktopCapability,
)


def _visual(label: str) -> dict:
    return {
        "screenshot": "D:\\ultron\\ultron_screenshot.bmp",
        "screen_size": {"width": 1920, "height": 1080},
        "ocr": [
            {
                "text": label,
                "x": 10,
                "y": 10,
                "width": 100,
                "height": 20,
                "confidence": 0.99,
            }
        ],
        "windows": [{"window_id": 1, "title": "Test"}],
        "semantic_description": "A visible test button.",
        "vision_available": True,
    }


def test_mock_vision_qwen_action_and_verification(monkeypatch) -> None:
    observations = iter([_visual("before"), _visual("after")])
    monkeypatch.setattr(vision_loop, "combined_observation", lambda: next(observations))

    def fake_run_agent(_prompt, _messages, **kwargs):
        kwargs["on_tool_result"]("mouse_click", "Mouse click completed.")
        return "done"

    monkeypatch.setattr(vision_loop, "run_agent", fake_run_agent)

    result = vision_loop.run_vision_action_loop("click the button", [{}])

    assert result["ok"] is True
    assert result["action"]["tool"] == "mouse_click"
    assert result["after"]["ocr"][0]["text"] == "after"


def test_qwen_receives_combined_observation(monkeypatch) -> None:
    observation = _visual("button")
    monkeypatch.setattr(vision_loop, "combined_observation", lambda: observation)
    captured = {}

    def fake_run_agent(prompt, _messages, **kwargs):
        captured["prompt"] = prompt
        kwargs["on_tool_result"]("keyboard_press", "Key press completed.")

    monkeypatch.setattr(vision_loop, "run_agent", fake_run_agent)

    result = vision_loop.run_vision_action_loop("press the key", [{}])

    assert result["ok"] is True
    assert '"ocr"' in captured["prompt"]
    assert '"windows"' in captured["prompt"]
    assert '"semantic_description"' in captured["prompt"]


def test_invalid_action_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(vision_loop, "combined_observation", lambda: _visual("screen"))

    def fake_run_agent(_prompt, _messages, **kwargs):
        kwargs["on_tool_result"]("delete_file", "Tool error: tool is not allowed")

    monkeypatch.setattr(vision_loop, "run_agent", fake_run_agent)

    result = vision_loop.run_vision_action_loop("delete something", [{}])

    assert result["ok"] is False
    assert result["stage"] == "action"


def test_low_confidence_observation_stops_before_qwen(monkeypatch) -> None:
    observation = _visual("uncertain")
    observation["ocr"][0]["confidence"] = 0.1
    observation["semantic_description"] = ""
    observation["windows"] = []
    monkeypatch.setattr(vision_loop, "combined_observation", lambda: observation)
    called = []
    monkeypatch.setattr(vision_loop, "run_agent", lambda *_args, **_kwargs: called.append(True))

    result = vision_loop.run_vision_action_loop("click target", [{}])

    assert result["ok"] is False
    assert result["stage"] == "before_action"
    assert called == []


def test_capability_denial_blocks_action(monkeypatch) -> None:
    monkeypatch.setattr(vision_loop, "combined_observation", lambda: _visual("screen"))

    def fake_run_agent(_prompt, _messages, **kwargs):
        DESKTOP_CAPABILITIES.revoke(DesktopCapability.MOUSE_CONTROL)
        kwargs["on_tool_result"]("mouse_click", "Tool error: Missing capability")

    monkeypatch.setattr(vision_loop, "run_agent", fake_run_agent)

    try:
        result = vision_loop.run_vision_action_loop("click", [{}])
        assert result["ok"] is False
        assert result["stage"] == "action"
    finally:
        DESKTOP_CAPABILITIES.grant(DesktopCapability.MOUSE_CONTROL)


def test_malformed_vision_output_is_reported(monkeypatch) -> None:
    monkeypatch.setattr(vision_loop, "combined_observation", lambda: {"broken": True})

    result = vision_loop.run_vision_action_loop("click", [{}])

    assert result["ok"] is False
    assert result["stage"] == "before_action"


def test_action_loop_limit_is_forwarded(monkeypatch) -> None:
    observed = {}
    monkeypatch.setattr(vision_loop, "combined_observation", lambda: _visual("screen"))

    def fake_run_agent(_prompt, _messages, **kwargs):
        observed["limit"] = kwargs["max_tool_iterations"]

    monkeypatch.setattr(vision_loop, "run_agent", fake_run_agent)

    result = vision_loop.run_vision_action_loop("click", [{}], max_actions=2)

    assert result["ok"] is False
    assert result["stage"] == "action"
    assert observed["limit"] == 2


def test_action_loop_limit_stops_additional_actions(monkeypatch) -> None:
    monkeypatch.setattr(vision_loop, "combined_observation", lambda: _visual("screen"))

    def fake_run_agent(_prompt, _messages, **kwargs):
        kwargs["on_tool_result"]("mouse_move", "Mouse moved.")
        kwargs["on_tool_result"]("mouse_move", "Mouse moved.")

    monkeypatch.setattr(vision_loop, "run_agent", fake_run_agent)

    result = vision_loop.run_vision_action_loop("move once", [{}], max_actions=1)

    assert result["ok"] is False
    assert result["stage"] == "action"