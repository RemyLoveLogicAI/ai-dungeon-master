"""HTTP contract tests for the loopback game server."""

from __future__ import annotations

import os
import tempfile
import unittest

os.environ["AI_DM_CAMPAIGN_DB"] = os.path.join(tempfile.mkdtemp(), "test-campaigns.db")

from fastapi.testclient import TestClient

import game_server


class TestStatusAndTokenContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(game_server.app)
        cls.status = cls.client.get("/api/status").json()

    def test_status_reports_configured_deterministic_dm(self):
        self.assertTrue(self.status["configured"])
        self.assertEqual(self.status["provider"], "deterministic")
        self.assertTrue(self.status["write_token"])

    def test_status_lists_campaigns(self):
        self.assertIsInstance(self.status["campaigns"], list)

    def test_browser_origin_mutation_requires_write_token(self):
        origin = {"Origin": "http://localhost:8766"}
        response = self.client.post("/api/campaigns", json={}, headers=origin)
        self.assertEqual(response.status_code, 403)

    def test_browser_origin_with_valid_token_is_accepted(self):
        origin = {"Origin": "http://localhost:8766", "X-Game-Token": self.status["write_token"]}
        response = self.client.post("/api/campaigns", json={}, headers=origin)
        self.assertEqual(response.status_code, 200)

    def test_non_browser_client_needs_no_token(self):
        response = self.client.post("/api/campaigns", json={})
        self.assertEqual(response.status_code, 200)


class TestCampaignLifecycleOverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(game_server.app)
        cls.campaign = cls.client.post(
            "/api/campaigns", json={"profile": {"edition": "2024"}}
        ).json()

    def test_create_returns_playable_state(self):
        state = self.campaign
        self.assertIn("id", state)
        self.assertEqual(state["revision"], 0)
        self.assertEqual(state["stage"], "adventure")
        self.assertEqual(state["presentation"]["status"], "ready")
        self.assertTrue(state["presentation"]["surface"]["components"])

    def test_get_returns_same_campaign(self):
        response = self.client.get(f"/api/campaigns/{self.campaign['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.campaign["id"])

    def test_action_advances_scene_and_increments_revision(self):
        scene = game_server._service._scenes[self.campaign["scene"]]
        choice = scene["choices"][0]
        response = self.client.post(
            f"/api/campaigns/{self.campaign['id']}/actions",
            json={
                "revision": self.campaign["revision"],
                "request_id": "http-req-1",
                "action": choice["id"],
                "intent": "act",
            },
        )
        self.assertEqual(response.status_code, 200)
        state = response.json()
        self.assertEqual(state["scene"], choice["targetScene"])
        self.assertEqual(state["revision"], 1)
        self.assertEqual(len(state["journal"]), 1)

    def test_stale_revision_returns_409_with_error_body(self):
        response = self.client.post(
            f"/api/campaigns/{self.campaign['id']}/actions",
            json={
                "revision": 0,
                "request_id": "http-req-stale",
                "action": "x",
                "intent": "act",
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("error", response.json())

    def test_unknown_campaign_returns_404(self):
        response = self.client.get("/api/campaigns/nope")
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            "/api/campaigns/nope/actions",
            json={"revision": 0, "request_id": "r", "action": "x"},
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.post("/api/campaigns/nope/reset")
        self.assertEqual(response.status_code, 404)

    def test_reset_returns_to_start(self):
        response = self.client.post(f"/api/campaigns/{self.campaign['id']}/reset")
        self.assertEqual(response.status_code, 200)
        state = response.json()
        self.assertEqual(state["scene"], game_server._service.game["startScene"])
        self.assertEqual(state["journal"], [])

    def test_static_web_client_is_served(self):
        response = self.client.get("/play.html")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])


if __name__ == "__main__":
    unittest.main()
