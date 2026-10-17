"""Tests for the authoritative VR server: rules, validation, and HTTP transport."""

from __future__ import annotations

import http.client
import json
import threading
import unittest
from http import HTTPStatus
from typing import Any
from unittest import mock

import vr_server
from game_foundation import AGENTSURFACE_ADAPTER_VERSION, validate_agentsurface_v01
from vr_server import ARCHETYPES, SUPPORTED_INTENTS, CampaignVRState, make_server


def confirmed_state(archetype: str = "Fighter") -> CampaignVRState:
    state = CampaignVRState()
    if archetype != state.hero["archetype"]:
        state.apply("SWITCH_STARTER_ARCHETYPE", {})
    state.apply("CONFIRM_CHARACTER_DRAFT", {"characterName": "Theron"})
    return state


def pending_state(archetype: str = "Fighter") -> CampaignVRState:
    state = confirmed_state(archetype)
    status, _ = state.apply("choose", {"choice_id": "follow_the_bell"})
    assert status == HTTPStatus.OK
    return state


def assert_stats_match(case: unittest.TestCase, hero: dict[str, Any]) -> None:
    for key, value in ARCHETYPES[hero["archetype"]].items():
        if key != "name":
            case.assertEqual(hero[key], value, key)


class TestOnboarding(unittest.TestCase):
    def test_initial_surface_is_valid_onboarding_blueprint(self) -> None:
        state = CampaignVRState()
        blueprint = state.get_active_blueprint()
        validate_agentsurface_v01(blueprint, root="root")
        self.assertEqual(blueprint["surface"]["id"], "onboarding-stage-1-2")
        self.assertFalse(state.hero["confirmed"])

    def test_switch_archetype_copies_the_archetype_row(self) -> None:
        state = CampaignVRState()
        status, body = state.apply("SWITCH_STARTER_ARCHETYPE", {})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(body["hero"]["archetype"], "Wizard")
        assert_stats_match(self, body["hero"])
        self.assertEqual(body["hero"]["name"], ARCHETYPES["Wizard"]["name"])
        _, body = state.apply("SWITCH_STARTER_ARCHETYPE", {})
        self.assertEqual(body["hero"]["archetype"], "Fighter")
        assert_stats_match(self, body["hero"])

    def test_confirm_draft_transitions_to_story_surface(self) -> None:
        state = CampaignVRState()
        status, body = state.apply("CONFIRM_CHARACTER_DRAFT", {"characterName": " Theron "})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(body["hero"]["confirmed"])
        self.assertEqual(body["hero"]["name"], "Theron")
        self.assertEqual(body["surfaceType"], "story")
        validate_agentsurface_v01(body["blueprint"], root="root")

    def test_confirm_keeps_default_name_when_omitted(self) -> None:
        state = CampaignVRState()
        _, body = state.apply("CONFIRM_CHARACTER_DRAFT", {})
        self.assertEqual(body["hero"]["name"], ARCHETYPES["Fighter"]["name"])

    def test_confirm_ignores_client_archetype(self) -> None:
        state = CampaignVRState()
        _, body = state.apply("CONFIRM_CHARACTER_DRAFT", {"archetype": "Wizard"})
        self.assertEqual(body["hero"]["archetype"], "Fighter")
        assert_stats_match(self, body["hero"])

    def test_confirm_rejects_bad_names(self) -> None:
        for name in ("", "   ", 7, None):
            with self.subTest(name=name):
                status, body = CampaignVRState().apply(
                    "CONFIRM_CHARACTER_DRAFT", {"characterName": name}
                )
                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertIn("error", body)

    def test_switch_archetype_after_confirm_conflicts(self) -> None:
        status, body = confirmed_state().apply("SWITCH_STARTER_ARCHETYPE", {})
        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(body["error"], "character already confirmed")


class TestChecks(unittest.TestCase):
    def test_choose_before_confirm_conflicts(self) -> None:
        status, body = CampaignVRState().apply("choose", {"choice_id": "follow_the_bell"})
        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(body["error"], "confirm character first")

    def test_choice_into_checked_scene_sets_pending_check(self) -> None:
        state = confirmed_state()
        status, body = state.apply("choose", {"choice_id": "follow_the_bell"})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(body["pendingCheck"]["dc"], 12)
        self.assertEqual(body["pendingCheck"]["sceneId"], "sunken_shrine")
        self.assertIsNone(body["lastRoll"])

    def test_choice_into_unchecked_scene_has_no_check(self) -> None:
        _, body = confirmed_state().apply("choose", {"choice_id": "help_the_courier"})
        self.assertEqual(body["result"]["scene"], "watchers_camp")
        self.assertIsNone(body["pendingCheck"])

    def test_choose_while_pending_conflicts(self) -> None:
        status, body = pending_state().apply("choose", {"choice_id": "anything"})
        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(body["error"], "resolve pending check first")

    def test_invalid_choice_is_rejected_and_scene_unchanged(self) -> None:
        state = confirmed_state()
        before = state.session.current_scene
        for choice_id in ("no_such_choice", 3, None):
            with self.subTest(choice_id=choice_id):
                status, _ = state.apply("choose", {"choice_id": choice_id})
                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertEqual(state.session.current_scene, before)

    def test_roll_without_pending_check_is_rejected(self) -> None:
        status, body = confirmed_state().apply("PHYSICAL_DICE_ROLL", {"roll": 12})
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(body["error"], "no pending check")

    def test_invalid_rolls_are_rejected(self) -> None:
        for roll in (True, "7", 0, 21, 7.0, None):
            with self.subTest(roll=roll):
                state = pending_state()
                status, _ = state.apply("PHYSICAL_DICE_ROLL", {"roll": roll})
                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertIsNotNone(state.pending_check)

    def test_roll_resolves_against_archetype_modifier(self) -> None:
        cases = [("Fighter", 9, 3, 12, True), ("Wizard", 12, -1, 11, False)]
        for archetype, roll, modifier, total, success in cases:
            with self.subTest(archetype=archetype):
                state = pending_state(archetype)
                status, body = state.apply("PHYSICAL_DICE_ROLL", {"roll": roll})
                self.assertEqual(status, HTTPStatus.OK)
                last = body["lastRoll"]
                self.assertEqual(
                    (last["modifier"], last["total"], last["success"]), (modifier, total, success)
                )
                self.assertFalse(last["isCritical"])
                self.assertIsNone(body["pendingCheck"])

    def test_physical_dice_roll_handled_authoritatively(self) -> None:
        state = pending_state()
        status, body = state.apply("PHYSICAL_DICE_ROLL", {"roll": 20})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(body["lastRoll"]["value"], 20)
        self.assertTrue(body["lastRoll"]["isCritical"])
        self.assertEqual(state.journal[-1]["event"], "PHYSICAL_DICE_ROLL")


class TestViewsAndIntents(unittest.TestCase):
    def test_unknown_intent_is_rejected(self) -> None:
        for intent in ("NAVIGATE_SCENE", "ALIGN_CELESTIAL_DIAL", ""):
            with self.subTest(intent=intent):
                status, _ = CampaignVRState().apply(intent, {})
                self.assertEqual(status, HTTPStatus.BAD_REQUEST)

    def test_switch_view_limited_to_slice_views(self) -> None:
        for view in ("investigation", "encounter", "bogus", None):
            with self.subTest(view=view):
                status, _ = CampaignVRState().apply("SWITCH_VIEW", {"view": view})
                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
        state = confirmed_state()
        status, body = state.apply("SWITCH_VIEW", {"view": "onboarding"})
        self.assertEqual((status, body["surfaceType"]), (HTTPStatus.OK, "onboarding"))

    def test_every_ok_body_has_supported_intents(self) -> None:
        state = CampaignVRState()
        for intent, values in [
            ("SWITCH_STARTER_ARCHETYPE", {}),
            ("CONFIRM_CHARACTER_DRAFT", {}),
            ("choose", {"choice_id": "follow_the_bell"}),
            ("PHYSICAL_DICE_ROLL", {"roll": 5}),
            ("SWITCH_VIEW", {"view": "story"}),
        ]:
            with self.subTest(intent=intent):
                status, body = state.apply(intent, values)
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(body["supportedIntents"], list(SUPPORTED_INTENTS))
                self.assertEqual(body["contract"], AGENTSURFACE_ADAPTER_VERSION)

    def test_ability_modifier(self) -> None:
        for score, mod in ((8, -1), (10, 0), (11, 0), (16, 3), (20, 5)):
            self.assertEqual(vr_server.ability_modifier(score), mod)


class TestHTTP(unittest.TestCase):
    def setUp(self) -> None:
        self.server = make_server(port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def post(self, payload: Any) -> tuple[int, dict[str, Any]]:
        status, raw = self.request("POST", "/api/intent", json.dumps(payload).encode())
        return status, json.loads(raw)

    def test_each_server_owns_fresh_state(self) -> None:
        other = make_server(port=0)
        try:
            self.assertIsNot(other.state, self.server.state)
        finally:
            other.server_close()
        shared = CampaignVRState()
        reuse = make_server(port=0, state=shared)
        try:
            self.assertIs(reuse.state, shared)
        finally:
            reuse.server_close()

    def test_health_surface_state_and_intent_round_trip(self) -> None:
        self.assertEqual(self.request("GET", "/health"), (200, b"OK"))
        status, raw = self.request("GET", "/api/surface")
        surface = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertEqual(surface["surfaceType"], "onboarding")
        self.assertIsNone(surface["pendingCheck"])
        validate_agentsurface_v01(surface["blueprint"], root="root")
        status, body = self.post(
            {"intent": "CONFIRM_CHARACTER_DRAFT", "values": {"characterName": "Ada"}}
        )
        self.assertEqual((status, body["hero"]["name"]), (200, "Ada"))
        status, raw = self.request("GET", "/api/state")
        self.assertEqual(json.loads(raw)["journal"][-1]["event"], "CHARACTER_CONFIRMED")

    def test_values_default_to_empty(self) -> None:
        status, body = self.post({"intent": "SWITCH_STARTER_ARCHETYPE"})
        self.assertEqual((status, body["hero"]["archetype"]), (200, "Wizard"))

    def test_bad_bodies_are_rejected(self) -> None:
        cases = [
            (b"{not json", 400),
            (b"\xff\xfe", 400),
            (b"[1, 2]", 400),
            (json.dumps({"intent": 5}).encode(), 400),
            (json.dumps({"intent": "SWITCH_VIEW", "values": [1]}).encode(), 400),
            (json.dumps({"intent": "NAVIGATE_SCENE"}).encode(), 400),
        ]
        for body, expected in cases:
            with self.subTest(body=body):
                status, raw = self.request("POST", "/api/intent", body)
                self.assertEqual(status, expected)
                self.assertIn("error", json.loads(raw))

    def test_content_length_is_guarded(self) -> None:
        for length, expected in (
            ("abc", 400),
            ("-1", 400),
            (str(vr_server.MAX_BODY_BYTES + 1), 413),
        ):
            with self.subTest(length=length):
                status, raw = self.request("POST", "/api/intent", b"", {"Content-Length": length})
                self.assertEqual(status, expected)
                self.assertIn("error", json.loads(raw))

    def test_roll_true_returns_400_over_http(self) -> None:
        status, body = self.post({"intent": "PHYSICAL_DICE_ROLL", "values": {"roll": True}})
        self.assertEqual(status, 400)
        self.assertIn("error", body)

    def test_unknown_paths_return_404(self) -> None:
        self.assertEqual(self.request("GET", "/nope")[0], 404)
        self.assertEqual(self.request("POST", "/nope", b"{}")[0], 404)

    def test_options_preflight(self) -> None:
        self.assertEqual(self.request("OPTIONS", "/api/intent")[0], 204)

    def test_handler_exception_returns_json_500(self) -> None:
        with mock.patch.object(
            self.server.state, "handle_intent", side_effect=RuntimeError("boom")
        ):
            status, body = self.post({"intent": "SWITCH_VIEW", "values": {"view": "story"}})
        self.assertEqual((status, body), (500, {"error": "internal"}))
        self.assertFalse(self.server.state.lock.locked())
        with mock.patch.object(self.server.state, "snapshot", side_effect=RuntimeError("boom")):
            status, raw = self.request("GET", "/api/surface")
        self.assertEqual((status, json.loads(raw)), (500, {"error": "internal"}))

    def test_concurrent_switches_all_answer_and_stay_consistent(self) -> None:
        statuses: list[int] = []

        def switch() -> None:
            statuses.append(self.post({"intent": "SWITCH_STARTER_ARCHETYPE", "values": {}})[0])

        threads = [threading.Thread(target=switch) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(statuses, [200] * 20)
        hero = self.server.state.hero
        assert_stats_match(self, hero)
        self.assertEqual(hero["name"], ARCHETYPES[hero["archetype"]]["name"])
        self.assertEqual(hero["archetype"], "Fighter")  # 20 toggles return to the start


class TestMain(unittest.TestCase):
    def run_main(self, argv: list[str]) -> tuple[mock.MagicMock, Any]:
        fake = mock.MagicMock()
        fake.server_address = ("127.0.0.1", 8000)
        fake.serve_forever.side_effect = KeyboardInterrupt
        with (
            mock.patch.object(vr_server, "make_server", return_value=fake) as factory,
            self.assertLogs("vr_server", level="INFO") as logs,
        ):
            vr_server.main(argv)
        fake.server_close.assert_called_once()
        return factory, logs

    def test_defaults_to_loopback_without_warning(self) -> None:
        factory, logs = self.run_main([])
        factory.assert_called_once_with("127.0.0.1", 8000)
        self.assertFalse([line for line in logs.output if line.startswith("WARNING")])

    def test_non_loopback_host_warns(self) -> None:
        factory, logs = self.run_main(["--host", "0.0.0.0", "--port", "9001"])
        factory.assert_called_once_with("0.0.0.0", 9001)
        self.assertTrue([line for line in logs.output if line.startswith("WARNING")])


if __name__ == "__main__":
    unittest.main()
