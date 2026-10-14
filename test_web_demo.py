"""Tests for the browser demo's generated data and its renderer contract.

These are not "does the JSON parse" checks. They pin the things that would
otherwise rot silently:

- the committed ``web/demo-data.json`` matches a fresh build (no drift);
- every scene blueprint satisfies ``agentsurface-blueprint/0.1``;
- the JavaScript renderer declares support for every component type the
  producers actually emit, so a new Python component cannot ship unrendered;
- the renderer keeps the contract's text-only guarantee (no ``innerHTML``);
- choice targets name exported scenes, so the demo has no dead links;
- the encountered run is deterministic.
"""

from __future__ import annotations

import json
import os
import re
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_WEB = os.path.join(_HERE, "web")
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _WEB not in sys.path:
    sys.path.insert(0, _WEB)

import build_demo  # imported after the path setup above

from game_foundation import AGENTSURFACE_ADAPTER_VERSION, validate_agentsurface_v01

DEMO_JSON = os.path.join(_WEB, "demo-data.json")
APP_JS = os.path.join(_WEB, "app.js")


def _component_types(payload: dict) -> set[str]:
    return {component["type"] for component in payload["components"]}


class TestDemoDataIsInSync(unittest.TestCase):
    def test_committed_artifact_matches_a_fresh_build(self):
        """Regenerate in memory and compare - catches a stale committed file."""
        with open(DEMO_JSON, encoding="utf-8") as handle:
            committed = handle.read()
        fresh = json.dumps(build_demo.build_demo_data(), indent=2, sort_keys=True) + "\n"
        self.assertEqual(
            committed,
            fresh,
            "web/demo-data.json is stale; run `python web/build_demo.py`",
        )

    def test_contract_identifier_is_the_adapter_version(self):
        self.assertEqual(build_demo.build_demo_data()["contract"], AGENTSURFACE_ADAPTER_VERSION)

    def test_write_demo_data_round_trips(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "demo-data.json")
            written = build_demo.write_demo_data(path)
            self.assertTrue(os.path.exists(written))
            with open(written, encoding="utf-8") as handle:
                reloaded = json.load(handle)
            self.assertEqual(reloaded, build_demo.build_demo_data())


class TestBlueprintsSatisfyTheContract(unittest.TestCase):
    def setUp(self):
        self.data = build_demo.build_demo_data()

    def test_every_scene_blueprint_validates(self):
        scenes = self.data["scenario"]["scenes"]
        self.assertTrue(scenes, "the demo must export at least one scene")
        for scene_id, entry in scenes.items():
            with self.subTest(scene=scene_id):
                validate_agentsurface_v01(entry["blueprint"], root="root")

    def test_encounter_surface_validates(self):
        validate_agentsurface_v01(self.data["encounter"]["surface"], root="root")

    def test_start_scene_is_exported(self):
        start = self.data["scenario"]["startScene"]
        self.assertIn(start, self.data["scenario"]["scenes"])

    def test_choice_targets_name_exported_scenes(self):
        scenes = self.data["scenario"]["scenes"]
        for scene_id, entry in scenes.items():
            for choice_id, target in entry["targets"].items():
                with self.subTest(scene=scene_id, choice=choice_id):
                    self.assertIn(target, scenes, "a choice points at an unexported scene")


class TestRendererCoversEveryEmittedType(unittest.TestCase):
    """The renderer must handle every component type the producers emit."""

    @classmethod
    def setUpClass(cls):
        with open(APP_JS, encoding="utf-8") as handle:
            cls.app_js = handle.read()
        # SUPPORTED_TYPES is the declared vocabulary; read it from the source so
        # the two cannot drift without this test noticing.
        block = re.search(r"const SUPPORTED_TYPES = \[(.*?)\];", cls.app_js, re.DOTALL)
        assert block is not None, "app.js must declare SUPPORTED_TYPES"
        cls.supported = set(re.findall(r'"([^"]+)"', block.group(1)))

    def test_supported_types_were_parsed(self):
        self.assertIn("Button", self.supported)
        self.assertGreater(len(self.supported), 5)

    def test_every_emitted_component_type_is_supported(self):
        data = build_demo.build_demo_data()
        emitted: set[str] = set()
        for entry in data["scenario"]["scenes"].values():
            emitted |= _component_types(entry["blueprint"])
        emitted |= _component_types(data["encounter"]["surface"])
        self.assertTrue(emitted <= self.supported, f"unrendered types: {sorted(emitted - self.supported)}")

    def test_renderer_never_builds_markup_from_data(self):
        """The contract requires text-only rendering (textContent, not HTML).

        Check real usage rather than prose: `.innerHTML` (read or write) or an
        `innerHTML =` assignment means markup is being built from data. A bare
        mention of the word inside a comment is not the thing being prevented.
        """
        self.assertNotIn(".innerHTML", self.app_js)
        self.assertNotIn("innerHTML =", self.app_js)
        self.assertIn("textContent", self.app_js)


class TestEncounterIsDeterministic(unittest.TestCase):
    def test_two_builds_agree(self):
        first = build_demo.simulate_encounter()
        second = build_demo.simulate_encounter()
        self.assertEqual(first["outcome"], second["outcome"])
        self.assertEqual(first["rounds"], second["rounds"])
        self.assertEqual(first["feed"], second["feed"])

    def test_the_run_reaches_a_real_outcome(self):
        result = build_demo.simulate_encounter()
        self.assertIn(result["outcome"], {"victory", "defeat", "enemy-fled"})
        self.assertGreater(result["rounds"], 0)
        self.assertTrue(result["feed"])


if __name__ == "__main__":
    unittest.main()
