"""Accessibility contract tests for the static web clients.

The MVP-1.0 gate requires accessible alternatives to audio/visual cues and
expected failure behavior to be *documented and tested*. These tests pin the
markup/ARIA contract the clients already implement so it cannot silently rot:
live regions for async narration, alert roles for failures, labelled controls,
text alternatives for decorative media, and keyboard-reachable actions.
"""

from __future__ import annotations

import os
import re
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_WEB = os.path.join(_HERE, "web")


def _read(name: str) -> str:
    with open(os.path.join(_WEB, name), encoding="utf-8") as handle:
        return handle.read()


class TestLiveRegionsAnnounceAsyncContent(unittest.TestCase):
    """Screen readers must be told when narration/surfaces change."""

    def test_demo_stage_is_a_live_region(self):
        self.assertIn('id="stage" aria-live="polite"', _read("index.html"))

    def test_demo_toast_has_status_role(self):
        self.assertIn('id="toast" class="toast" role="status"', _read("index.html"))

    def test_play_narration_turn_has_status_role(self):
        html = _read("play.html")
        self.assertIn('id="turn-status" role="status"', html)
        self.assertIn('id="provider-status" class="connection" role="status"', html)

    def test_play_notice_is_an_alert_region(self):
        """Failure messages must interrupt, not wait for focus."""
        self.assertIn('id="notice" class="notice" role="alert"', _read("play.html"))

    def test_play_js_marks_composer_busy_during_dm_turns(self):
        play_js = _read("play.js")
        self.assertIn("setAttribute('aria-busy'", play_js)


class TestFailureBehaviorIsExposed(unittest.TestCase):
    """Expected failures must surface as text a non-visual user can perceive."""

    def test_play_notice_element_is_wired_to_error_path(self):
        play_js = _read("play.js")
        # notice() writes into the role=alert element; errors call notice().
        self.assertIn("function notice(message", play_js)
        self.assertIn("notice(error.message", play_js)
        self.assertIn("connection was interrupted", play_js)

    def test_play_has_a_retry_control_for_failures(self):
        html = _read("play.html")
        self.assertIn('id="retry" hidden', html)
        self.assertIn("$('retry')", _read("play.js"))

    def test_demo_renderer_rejects_rather_than_renders_partially(self):
        """app.js throws on unsupported component types instead of silent drop."""
        app_js = _read("app.js")
        self.assertIn("SUPPORTED_TYPES", app_js)
        self.assertIn("throw", app_js)


class TestControlsAreLabelledAndKeyboardReachable(unittest.TestCase):
    def test_play_composer_input_has_label(self):
        html = _read("play.html")
        self.assertIn('for="action"', html)
        self.assertIn('id="action"', html)

    def test_play_campaign_select_has_label(self):
        html = _read("play.html")
        self.assertIn('for="campaign-select"', html)

    def test_help_toggle_controls_its_panel(self):
        html = _read("play.html")
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('aria-controls="help"', html)

    def test_demo_nav_is_labelled(self):
        self.assertIn('aria-label="Views"', _read("index.html"))


class TestMediaHasTextAlternatives(unittest.TestCase):
    def test_scene_image_has_alt_attribute(self):
        html = _read("play.html")
        match = re.search(r'<img id="scene-art"[^>]*>', html)
        self.assertIsNotNone(match)
        self.assertIn("alt=", match.group(0))

    def test_scene_image_alt_is_filled_when_art_loads(self):
        """Empty alt is only valid while decorative; play.js must set real alt."""
        play_js = _read("play.js")
        self.assertRegex(play_js, r"scene-art.*alt|alt.*scene-art")

    def test_generated_surface_is_a_labelled_region(self):
        self.assertIn('aria-label="Choices from your Dungeon Master"', _read("play.html"))


class TestNonColorCuesAndFocusVisibility(unittest.TestCase):
    def test_stylesheet_defines_focus_visible(self):
        css = _read("style.css") + _read("play.css")
        self.assertIn(":focus-visible", css)

    def test_connection_status_is_text_not_color_only(self):
        """Provider state must be readable without seeing the color."""
        play_js = _read("play.js")
        self.assertIn("Live AI DM", play_js)
        self.assertIn("AI provider not configured", play_js)


if __name__ == "__main__":
    unittest.main()
