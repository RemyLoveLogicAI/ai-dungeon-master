"""Tests for the FastAPI transport layer: session isolation and character deletion."""

import pytest
from fastapi.testclient import TestClient

import engine.api_server as api_server
from campaign_core import CampaignStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api_server, "campaign_store", CampaignStore(tmp_path / "campaigns.sqlite3"))
    api_server._sessions.clear()
    return TestClient(api_server.app)


def test_concurrent_sessions_activate_different_characters_without_clobbering(client):
    aria = client.post("/api/characters", json={"name": "Aria", "class": "Wizard"}).json()
    borin = client.post("/api/characters", json={"name": "Borin", "class": "Fighter"}).json()

    client.post(f"/api/characters/{aria['campaign_id']}/activate", headers={"X-Session-ID": "session-a"})
    client.post(f"/api/characters/{borin['campaign_id']}/activate", headers={"X-Session-ID": "session-b"})

    current_a = client.get("/api/characters/current", headers={"X-Session-ID": "session-a"}).json()
    current_b = client.get("/api/characters/current", headers={"X-Session-ID": "session-b"}).json()
    assert current_a["campaign_id"] == aria["campaign_id"]
    assert current_b["campaign_id"] == borin["campaign_id"]

    player_a = client.get("/api/player", headers={"X-Session-ID": "session-a"}).json()["player"]
    player_b = client.get("/api/player", headers={"X-Session-ID": "session-b"}).json()["player"]
    assert player_a["name"] == "Aria"
    assert player_b["name"] == "Borin"


def test_missing_session_header_falls_back_to_a_shared_default_session(client):
    created = client.post("/api/characters", json={"name": "Default Dave", "class": "Cleric"}).json()
    current = client.get("/api/characters/current").json()
    assert current["campaign_id"] == created["campaign_id"]


def test_delete_character_removes_campaign_and_clears_sessions_pointing_at_it(client):
    created = client.post("/api/characters", json={"name": "Temp Hero", "class": "Rogue"}).json()
    campaign_id = created["campaign_id"]
    client.post(f"/api/characters/{campaign_id}/activate", headers={"X-Session-ID": "s1"})

    response = client.delete(f"/api/characters/{campaign_id}")
    assert response.status_code == 200
    assert response.json() == {"campaign_id": campaign_id, "deleted": True}

    current = client.get("/api/characters/current", headers={"X-Session-ID": "s1"}).json()
    assert current["campaign_id"] is None

    assert client.delete(f"/api/characters/{campaign_id}").status_code == 404


def test_delete_character_rejects_malformed_id(client):
    response = client.delete("/api/characters/not-a-uuid")
    assert response.status_code == 400
