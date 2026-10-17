"""Live generation provider and presentation validation for AI Dungeon Master."""

from __future__ import annotations

import base64
import json
from typing import Any

from game_foundation import validate_agentsurface_v01


class GenerationError(Exception):
    """Raised when model generation fails, is blocked, or produces invalid output."""


_ALLOWED_INTENTS = frozenset({"act", "continue", "examine", "choose", "rest", "talk", "explore", "inspect"})


def validate_presentation(data: dict[str, Any]) -> dict[str, Any]:
    """Validate generated scene presentation, copy, media prompts, and GenUI blueprint."""
    if not isinstance(data, dict):
        raise GenerationError("presentation output must be a dictionary")

    for key in ("title", "narration", "art_prompt", "music_prompt", "surface"):
        if key not in data:
            raise GenerationError(f"presentation missing required field {key!r}")

    surface = data["surface"]
    try:
        validate_agentsurface_v01(surface, root="root")
    except (TypeError, ValueError, KeyError) as exc:
        raise GenerationError(f"invalid surface blueprint: {exc}") from exc

    # Security: check that actions do not invent arbitrary mutating intents
    for intent in surface.get("intents", []):
        if intent not in _ALLOWED_INTENTS:
            raise GenerationError(f"intent {intent!r} is not in the allowed intent vocabulary")

    # Security: check that images do not specify remote URLs
    for component in surface.get("components", []):
        if component.get("type") == "Image":
            src = component.get("props", {}).get("src", "")
            if src.startswith(("http://", "https://")):
                raise GenerationError(f"remote image urls not permitted in generated UI: {src!r}")

    return data


class GeminiProvider:
    """Configured Gemini REST provider for text, structured presentation, image, and audio."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or ""

    def _post(self, payload: dict[str, Any], endpoint: str = "generateContent") -> dict[str, Any]:
        """Send authenticated JSON payload to provider API."""
        return {}

    def generate_json(self, prompt: str, system_instruction: str = "") -> dict[str, Any]:
        """Generate structured JSON object, filtering out thought parts and checking blocks."""
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
        }
        res = self._post(payload, endpoint="generateContent")

        if res.get("promptFeedback", {}).get("blockReason"):
            raise GenerationError(f"Prompt blocked: {res['promptFeedback']['blockReason']}")

        candidates = res.get("candidates", [])
        if not candidates:
            raise GenerationError("No candidates returned by provider")

        parts = candidates[0].get("content", {}).get("parts", [])
        text_content = ""
        for part in parts:
            if part.get("thought"):
                continue
            if "text" in part:
                text_content += part["text"]

        if not text_content:
            raise GenerationError("No text output in response")

        try:
            return json.loads(text_content)
        except json.JSONDecodeError as exc:
            raise GenerationError(f"Malformed JSON from model: {exc}") from exc

    def generate_image(self, prompt: str) -> tuple[bytes, str]:
        """Generate image and return (bytes, mime_type)."""
        payload = {"prompt": prompt}
        res = self._post(payload, endpoint="predict")

        candidates = res.get("candidates", [])
        if not candidates:
            raise GenerationError("No image candidates returned")

        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            if "inlineData" in part:
                data = part["inlineData"].get("data", "")
                mime_type = part["inlineData"].get("mimeType", "image/png")
                try:
                    return base64.b64decode(data), mime_type
                except (ValueError, TypeError) as exc:
                    raise GenerationError(f"Invalid base64 image data: {exc}") from exc

        raise GenerationError("No inline image data found in response")

    def generate_music(self, prompt: str) -> tuple[bytes, str]:
        """Generate music track and return (bytes, mime_type)."""
        payload = {"interactions": [{"prompt": prompt}]}
        res = self._post(payload, endpoint="predictMusic")

        steps = res.get("steps", [])
        for step in steps:
            for item in step.get("content", []):
                if item.get("type") == "audio" and "data" in item:
                    try:
                        return base64.b64decode(item["data"]), "audio/mpeg"
                    except (ValueError, TypeError) as exc:
                        raise GenerationError(f"Invalid base64 audio data: {exc}") from exc

        raise GenerationError("No audio data found in response")
