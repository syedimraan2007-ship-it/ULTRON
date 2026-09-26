from tools import desktop_tools


def test_get_screen_text_uses_local_ocr() -> None:
    result = desktop_tools.get_screen_text()

    assert result["available"] is True
    assert isinstance(result["text"], str)
    assert result["screenshot_path"].endswith("ultron_screenshot.bmp")
    assert result["ocr_engine"] == "rapidocr_onnxruntime"


def _observation_dependencies(monkeypatch):
    monkeypatch.setattr(desktop_tools, "screenshot", lambda: "D:\\ultron\\screen.bmp")
    monkeypatch.setattr(
        desktop_tools,
        "get_screen_text",
        lambda _path: {
            "results": [
                {
                    "bbox": [[10, 20], [110, 20], [110, 40], [10, 40]],
                    "text": "Button",
                    "confidence": 0.95,
                }
            ]
        },
    )
    monkeypatch.setattr(desktop_tools, "_screen_size", lambda: (1920, 1080))
    monkeypatch.setattr(desktop_tools, "_enumerate_windows", lambda: [{"window_id": 1, "title": "Test"}])


def test_combined_observation_uses_ocr_when_vision_fails(monkeypatch) -> None:
    _observation_dependencies(monkeypatch)
    monkeypatch.setattr(desktop_tools, "vision_describe", lambda *_args: (_ for _ in ()).throw(RuntimeError("offline")))

    result = desktop_tools.combined_observation()

    assert result["vision_available"] is False
    assert result["semantic_description"] == ""
    assert result["ocr"] == [
        {
            "text": "Button",
            "x": 10,
            "y": 20,
            "width": 100,
            "height": 20,
            "confidence": 0.95,
        }
    ]
    assert result["windows"] == [{"window_id": 1, "title": "Test"}]


def test_combined_observation_includes_semantic_description(monkeypatch) -> None:
    _observation_dependencies(monkeypatch)
    monkeypatch.setattr(desktop_tools, "vision_describe", lambda *_args: "A test button is visible.")

    result = desktop_tools.combined_observation()

    assert result["vision_available"] is True
    assert result["semantic_description"] == "A test button is visible."


def test_combined_observation_timeout_does_not_break_ocr(monkeypatch) -> None:
    _observation_dependencies(monkeypatch)
    monkeypatch.setattr(
        desktop_tools,
        "vision_describe",
        lambda *_args: (_ for _ in ()).throw(TimeoutError("timed out")),
    )

    result = desktop_tools.combined_observation()

    assert result["vision_available"] is False
    assert result["ocr"][0]["text"] == "Button"


def test_combined_observation_audit_does_not_include_screen_content(monkeypatch) -> None:
    _observation_dependencies(monkeypatch)
    monkeypatch.setattr(desktop_tools, "vision_describe", lambda *_args: "Secret screen text")
    emitted = []
    monkeypatch.setattr(desktop_tools.EVENT_BUS, "emit", lambda event, **data: emitted.append(data))

    desktop_tools.combined_observation()

    assert all("Button" not in str(data) and "Secret" not in str(data) for data in emitted)
