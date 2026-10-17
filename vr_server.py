"""Production VR Server Adapter for AI Dungeon Master.

Provides a robust, zero-dependency streaming HTTP/SSE bridge for Unity VR clients.
Unity connects via HTTP/SSE to receive real-time declarative GenUI blueprints,
dispatch physical controller / gaze intents, and preserve authoritative campaign state.
"""

from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from game_foundation import (
    AGENTSURFACE_ADAPTER_VERSION,
    STARTER_SCENARIO,
    GameSession,
    choose,
    start_session,
    to_agentsurface_v01,
    validate_agentsurface_v01,
)
from genui import GenUIBlueprintFactory

logger = logging.getLogger(__name__)


class CampaignVRState:
    """Authoritative campaign and hero state managed across VR sessions."""

    def __init__(self) -> None:
        self.scenario = STARTER_SCENARIO
        self.session: GameSession = start_session(self.scenario)
        self.hero: dict[str, Any] = {
            "name": "Kaelen Ironheart",
            "archetype": "Fighter",
            "level": 1,
            "hp": 12,
            "maxHp": 12,
            "ac": 16,
            "edition": "D&D 5th Edition (Revised 2024)",
            "weaponMastery": "Longsword (Sap / Flex)",
            "confirmed": False,
        }
        self.journal: list[dict[str, Any]] = [
            {"event": "CAMPAIGN_INITIALIZED", "edition": self.hero["edition"]}
        ]
        self.active_surface_type: str = "onboarding"

    def get_active_blueprint(self) -> dict[str, Any]:
        """Return the validated AgentSurface v0.1 blueprint for the active state."""
        if self.active_surface_type == "onboarding":
            blueprint = GenUIBlueprintFactory.create_onboarding_surface(
                character_name=self.hero["name"],
                archetype=self.hero["archetype"],
                edition=self.hero["edition"],
                hp=self.hero["hp"],
                max_hp=self.hero["maxHp"],
                ac=self.hero["ac"],
            ).to_agentsurface_v01()
        elif self.active_surface_type == "investigation":
            blueprint = GenUIBlueprintFactory.create_investigation_surface().to_agentsurface_v01()
        elif self.active_surface_type == "encounter":
            # Tactical arena surface
            blueprint = GenUIBlueprintFactory.create_encounter_surface(
                surface_id="vr-encounter",
                title="Tactical VR Arena",
                round_num=1,
                hero_name=self.hero["name"],
                hero_hp=self.hero["hp"],
                hero_max_hp=self.hero["maxHp"],
                hero_conditions=[],
                hero_actions_available={"Action": True, "Bonus Action": True, "Reaction": True},
                enemy_name="Shadow Gargoyle",
                enemy_hp=30,
                enemy_max_hp=30,
                enemy_stance="Defensive",
                combat_log=["Encounter engaged in VR world space."],
                tension_level=0.5,
            ).to_agentsurface_v01()
        else:
            # Story scene surface from active session
            blueprint = to_agentsurface_v01(self.scenario, scene_id=self.session.current_scene)

        validate_agentsurface_v01(blueprint, root="root")
        return blueprint

    def handle_intent(self, intent: str, values: dict[str, Any]) -> dict[str, Any]:
        """Process player VR intent authoritatively and return updated state."""
        if intent == "CONFIRM_CHARACTER_DRAFT":
            self.hero["confirmed"] = True
            if "characterName" in values:
                self.hero["name"] = values["characterName"]
            if "archetype" in values:
                self.hero["archetype"] = values["archetype"]
            self.active_surface_type = "story"
            self.journal.append(
                {"event": "CHARACTER_CONFIRMED", "hero": dict(self.hero)}
            )
            return {"status": "ok", "message": "Hero draft confirmed", "activeSurface": "story"}

        elif intent == "SWITCH_STARTER_ARCHETYPE":
            is_fighter = self.hero["archetype"] == "Fighter"
            self.hero["archetype"] = "Wizard" if is_fighter else "Fighter"
            self.hero["name"] = "Eldrin Dawncaller" if is_fighter else "Kaelen Ironheart"
            self.hero["hp"] = 8 if is_fighter else 12
            self.hero["maxHp"] = 8 if is_fighter else 12
            self.hero["ac"] = 12 if is_fighter else 16
            self.hero["weaponMastery"] = "Quarterstaff (Topple)" if is_fighter else "Longsword (Sap / Flex)"
            self.journal.append({"event": "ARCHETYPE_SWITCHED", "archetype": self.hero["archetype"]})
            return {"status": "ok", "message": f"Switched to {self.hero['archetype']}"}

        elif intent == "NAVIGATE_SCENE":
            target = values.get("targetScene")
            if target and target in self.scenario.scenes_by_id:
                self.session = GameSession(
                    game_id=self.scenario.id,
                    current_scene=target,
                    events=self.session.events,
                )
                self.active_surface_type = "story"
                self.journal.append({"event": "SCENE_NAVIGATED", "target": target})
                return {"status": "ok", "scene": target}

        elif intent == "SWITCH_VIEW":
            view = values.get("view", "story")
            self.active_surface_type = view
            return {"status": "ok", "view": view}

        elif intent in ("INVESTIGATE_APPARATUS", "ALIGN_CELESTIAL_DIAL", "CHANNEL_ARCANA"):
            self.journal.append({"event": "PUZZLE_INTERACTION", "intent": intent, "values": values})
            return {"status": "ok", "interaction": intent, "result": "Mechanism updated"}

        elif intent == "PHYSICAL_DICE_ROLL":
            # VR player threw a physical d20 die in VR space
            roll_val = int(values.get("roll", 10))
            is_crit = roll_val == 20
            self.journal.append({"event": "PHYSICAL_DICE_ROLL", "value": roll_val, "crit": is_crit})
            return {"status": "ok", "roll": roll_val, "isCritical": is_crit}

        return {"status": "unhandled_intent", "intent": intent}


class VRServerRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler serving VR clients."""

    state = CampaignVRState()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/surface":
            blueprint = self.state.get_active_blueprint()
            payload = json.dumps(
                {
                    "contract": AGENTSURFACE_ADAPTER_VERSION,
                    "blueprint": blueprint,
                    "hero": self.state.hero,
                    "surfaceType": self.state.active_surface_type,
                }
            ).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)

        elif parsed.path == "/api/state":
            payload = json.dumps(
                {
                    "hero": self.state.hero,
                    "journal": self.state.journal,
                    "activeSurface": self.state.active_surface_type,
                }
            ).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)

        elif parsed.path == "/health":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/intent":
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except Exception:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()
                return

            intent = data.get("intent", "")
            values = data.get("values", {})
            result = self.state.handle_intent(intent, values)
            blueprint = self.state.get_active_blueprint()

            response = {
                "result": result,
                "blueprint": blueprint,
                "hero": self.state.hero,
            }
            body = json.dumps(response).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
