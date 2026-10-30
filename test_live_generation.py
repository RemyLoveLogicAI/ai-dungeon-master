"""Provider and generated-surface boundaries for the live game."""

import base64
import json
from unittest.mock import patch

import pytest

from live_generation import GeminiProvider, GenerationError, validate_presentation


def valid_presentation():
    return {
        "title": "The observatory",
        "narration": "A bronze telescope points toward the broken dome.",
        "art_prompt": "An ancient observatory beneath stars.",
        "music_prompt": "Sparse harp and distant bells, instrumental.",
        "surface": {
            "surface": {"id": "observatory", "title": "Explore", "subtitle": "", "width": "wide"},
            "dataModel": {"look": "Examine the telescope"},
            "components": [
                {"id": "root", "type": "Stack", "props": {"direction": "column"}, "children": ["look"]},
                {"id": "look", "type": "Button", "props": {"label": "Examine", "action": {"intent": "act", "payloadKeys": ["look"]}}},
            ],
            "intents": ["act"],
        },
    }


def test_generated_surface_validates_and_remains_data():
    output = valid_presentation()
    assert validate_presentation(output)["title"] == "The observatory"


def test_generated_actions_cannot_invent_mutating_intents():
    output = valid_presentation()
    output["surface"]["intents"] = ["set_hit_points"]
    output["surface"]["components"][1]["props"]["action"]["intent"] = "set_hit_points"
    with pytest.raises(GenerationError):
        validate_presentation(output)


def test_generated_surface_rejects_remote_images_and_unsafe_styles():
    output = valid_presentation()
    output["surface"]["components"][1] = {
        "id": "look", "type": "Image", "props": {"src": "https://example.org/private", "alt": "scene"}
    }
    with pytest.raises(GenerationError):
        validate_presentation(output)


def test_provider_extracts_json_without_thought_content():
    provider = GeminiProvider(api_key="test-only")
    response = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
        {"thought": True, "text": "private intermediate reasoning"},
        {"text": json.dumps({"title": "Welcome"})},
    ]}}]}
    with patch.object(provider, "_post", return_value=response):
        assert provider.generate_json("Say hello", "Be a DM") == {"title": "Welcome"}


def test_provider_block_is_explicit():
    provider = GeminiProvider(api_key="test-only")
    with patch.object(provider, "_post", return_value={"promptFeedback": {"blockReason": "SAFETY"}}), pytest.raises(GenerationError):
        provider.generate_json("request", "system")


def test_image_and_music_use_their_documented_response_shapes():
    provider = GeminiProvider(api_key="test-only")
    encoded = base64.b64encode(b"test media bytes").decode()
    image = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": encoded}}]}}]}
    music = {"steps": [{"type": "model_output", "content": [{"type": "audio", "data": encoded}]}]}
    with patch.object(provider, "_post", return_value=image):
        assert provider.generate_image("paint a scene") == (b"test media bytes", "image/png")
    with patch.object(provider, "_post", return_value=music) as call:
        assert provider.generate_music("quiet harp") == (b"test media bytes", "audio/mpeg")
        assert "interactions" in call.call_args.args[0]


def test_invalid_provider_media_is_not_saved_as_an_image():
    provider = GeminiProvider(api_key="test-only")
    with (
        patch.object(provider, "_post", return_value={"candidates": [{"content": {"parts": [{"text": "I cannot draw that"}]}}]}),
        pytest.raises(GenerationError),
    ):
        provider.generate_image("paint")


def test_validation_and_provider_error_edge_cases():
    # 1. Non-dict presentation
    with pytest.raises(GenerationError, match="must be a dictionary"):
        validate_presentation("not-a-dict")

    # 2. Missing required field
    with pytest.raises(GenerationError, match="missing required field"):
        validate_presentation({"title": "T"})

    # 3. Invalid surface blueprint
    with pytest.raises(GenerationError, match="invalid surface blueprint"):
        validate_presentation({
            "title": "T", "narration": "N", "art_prompt": "A", "music_prompt": "M",
            "surface": {"invalid": True},
        })

    provider = GeminiProvider(api_key="test-only")
    # 4. Default _post returns empty dict
    assert provider._post({}) == {}

    # 5. generate_json with no candidates
    with patch.object(provider, "_post", return_value={"candidates": []}), pytest.raises(GenerationError, match="No candidates returned"):
        provider.generate_json("prompt")

    # 6. generate_json with candidate having no text
    with patch.object(provider, "_post", return_value={"candidates": [{"content": {"parts": []}}]}), pytest.raises(GenerationError, match="No text output in response"):
        provider.generate_json("prompt")

    # 7. generate_json with malformed JSON
    with patch.object(provider, "_post", return_value={"candidates": [{"content": {"parts": [{"text": "{bad-json"}]}}]}), pytest.raises(GenerationError, match="Malformed JSON"):
        provider.generate_json("prompt")

    # 8. generate_image with no candidates
    with patch.object(provider, "_post", return_value={"candidates": []}), pytest.raises(GenerationError, match="No image candidates returned"):
        provider.generate_image("prompt")

    # 9. generate_image with invalid base64
    with (
        patch.object(provider, "_post", return_value={"candidates": [{"content": {"parts": [{"inlineData": {"data": "???not-base64???"}}]}}]}),
        pytest.raises(GenerationError, match="Invalid base64 image data"),
    ):
        provider.generate_image("prompt")

    # 10. generate_music with invalid base64
    with (
        patch.object(provider, "_post", return_value={"steps": [{"content": [{"type": "audio", "data": "???not-base64???"}]}]}),
        pytest.raises(GenerationError, match="Invalid base64 audio data"),
    ):
        provider.generate_music("prompt")

    # 11. generate_music with no audio data
    with (
        patch.object(provider, "_post", return_value={"steps": [{"content": [{"type": "text", "data": "no audio"}]}]}),
        pytest.raises(GenerationError, match="No audio data found"),
    ):
        provider.generate_music("prompt")
