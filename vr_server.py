"""Authoritative VR server adapter for AI Dungeon Master.

A zero-dependency HTTP request/response bridge (no SSE, no streaming). XR clients
fetch declarative AgentSurface blueprints and post intents; every rule decision
(scene transitions, checks, dice resolution) is made here, never on the client.

Run with ``python -m vr_server`` (binds 127.0.0.1:8000 by default). Reach it
from a Quest over USB with ``adb reverse tcp:8000 tcp:8000``.
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

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

EDITION = "D&D 5th Edition (Revised 2024)"
MAX_BODY_BYTES = 65536
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

#: The only source of starter stats. Switching archetype copies a row wholesale,
#: so HP, AC and ability scores can never drift apart.
ARCHETYPES: dict[str, dict[str, Any]] = {
    "Fighter": {
        "name": "Kaelen Ironheart",
        "hp": 12,
        "maxHp": 12,
        "ac": 16,
        "weaponMastery": "Longsword (Sap / Flex)",
        "STR": 16,
    },
    "Wizard": {
        "name": "Eldrin Dawncaller",
        "hp": 8,
        "maxHp": 8,
        "ac": 12,
        "weaponMastery": "Quarterstaff (Topple)",
        "STR": 8,
    },
}

# ponytail: one hardcoded check; move into Scenario data when a second check exists.
CHECKS: dict[str, dict[str, Any]] = {
    "sunken_shrine": {"skill": "Athletics", "ability": "STR", "dc": 12},
}

#: Intents this server handles. Clients render only actions whose intent is listed.
SUPPORTED_INTENTS: tuple[str, ...] = (
    "CONFIRM_CHARACTER_DRAFT",
    "SWITCH_STARTER_ARCHETYPE",
    "choose",
    "PHYSICAL_DICE_ROLL",
    "SWITCH_VIEW",
)

#: Views reachable in this slice; investigation/encounter advertise intents the
#: server cannot handle yet.
ALLOWED_VIEWS: tuple[str, ...] = ("onboarding", "story")


class IntentError(Exception):
    """An intent the server refuses, carrying the HTTP status to answer with."""

    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def ability_modifier(score: int) -> int:
    """5e ability modifier, the same formula TurnOrchestrator uses."""
    return (score - 10) // 2


def _hero_for(archetype: str) -> dict[str, Any]:
    return {
        "archetype": archetype,
        "level": 1,
        "edition": EDITION,
        "confirmed": False,
        **ARCHETYPES[archetype],
    }


class CampaignVRState:
    """Authoritative campaign and hero state for one server instance."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.scenario = STARTER_SCENARIO
        self.session: GameSession = start_session(self.scenario)
        self.hero: dict[str, Any] = _hero_for("Fighter")
        self.journal: list[dict[str, Any]] = [{"event": "CAMPAIGN_INITIALIZED", "edition": EDITION}]
        self.active_surface_type: str = "onboarding"
        self.pending_check: dict[str, Any] | None = None
        self.last_roll: dict[str, Any] | None = None

    def get_active_blueprint(self) -> dict[str, Any]:
        """Return the validated AgentSurface v0.1 blueprint for the active view."""
        if self.active_surface_type == "onboarding":
            blueprint = GenUIBlueprintFactory.create_onboarding_surface(
                character_name=self.hero["name"],
                archetype=self.hero["archetype"],
                edition=self.hero["edition"],
                hp=self.hero["hp"],
                max_hp=self.hero["maxHp"],
                ac=self.hero["ac"],
            ).to_agentsurface_v01()
        else:
            blueprint = to_agentsurface_v01(self.scenario, scene_id=self.session.current_scene)
        validate_agentsurface_v01(blueprint, root="root")
        return blueprint

    def snapshot(self) -> dict[str, Any]:
        """Everything a client needs to render; call with ``lock`` held."""
        return {
            "contract": AGENTSURFACE_ADAPTER_VERSION,
            "blueprint": self.get_active_blueprint(),
            "hero": dict(self.hero),
            "surfaceType": self.active_surface_type,
            "supportedIntents": list(SUPPORTED_INTENTS),
            "pendingCheck": self.pending_check,
            "lastRoll": self.last_roll,
        }

    def apply(self, intent: str, values: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
        """Handle one intent and snapshot the result atomically."""
        with self.lock:
            try:
                result = self.handle_intent(intent, values)
            except IntentError as exc:
                return exc.status, {"error": exc.message}
            return HTTPStatus.OK, {**self.snapshot(), "result": result}

    def handle_intent(self, intent: str, values: dict[str, Any]) -> dict[str, Any]:
        """Apply a player intent or raise ``IntentError``; call with ``lock`` held."""
        handlers = {
            "CONFIRM_CHARACTER_DRAFT": self._confirm_character,
            "SWITCH_STARTER_ARCHETYPE": self._switch_archetype,
            "choose": self._choose,
            "PHYSICAL_DICE_ROLL": self._resolve_roll,
            "SWITCH_VIEW": self._switch_view,
        }
        handler = handlers.get(intent)
        if handler is None:
            raise IntentError(HTTPStatus.BAD_REQUEST, f"unknown intent {intent!r}")
        return handler(values)

    def _confirm_character(self, values: dict[str, Any]) -> dict[str, Any]:
        name = values.get("characterName", self.hero["name"])
        if not isinstance(name, str) or not name.strip():
            raise IntentError(HTTPStatus.BAD_REQUEST, "characterName must be a non-empty string")
        # archetype is deliberately ignored: only SWITCH_STARTER_ARCHETYPE changes it.
        self.hero = {**self.hero, "name": name.strip(), "confirmed": True}
        self.active_surface_type = "story"
        self.journal.append({"event": "CHARACTER_CONFIRMED", "hero": dict(self.hero)})
        return {"status": "ok", "message": "Hero draft confirmed", "activeSurface": "story"}

    def _switch_archetype(self, values: dict[str, Any]) -> dict[str, Any]:
        if self.hero["confirmed"]:
            raise IntentError(HTTPStatus.CONFLICT, "character already confirmed")
        archetype = "Wizard" if self.hero["archetype"] == "Fighter" else "Fighter"
        self.hero = _hero_for(archetype)
        self.journal.append({"event": "ARCHETYPE_SWITCHED", "archetype": archetype})
        return {"status": "ok", "message": f"Switched to {archetype}"}

    def _choose(self, values: dict[str, Any]) -> dict[str, Any]:
        if not self.hero["confirmed"]:
            raise IntentError(HTTPStatus.CONFLICT, "confirm character first")
        if self.pending_check is not None:
            raise IntentError(HTTPStatus.CONFLICT, "resolve pending check first")
        choice_id = values.get("choice_id")
        if not isinstance(choice_id, str):
            raise IntentError(HTTPStatus.BAD_REQUEST, "choice_id must be a string")
        try:
            self.session = choose(self.session, self.scenario, choice_id)
        except ValueError as exc:
            raise IntentError(HTTPStatus.BAD_REQUEST, str(exc)) from exc
        scene_id = self.session.current_scene
        self.active_surface_type = "story"
        check = CHECKS.get(scene_id)
        if check is not None:
            self.pending_check = {**check, "sceneId": scene_id}
        self.journal.append({"event": "CHOICE_SELECTED", "choice": choice_id, "scene": scene_id})
        return {"status": "ok", "scene": scene_id}

    def _resolve_roll(self, values: dict[str, Any]) -> dict[str, Any]:
        roll = values.get("roll")
        # type() rather than isinstance(): bool is an int subclass and True must not pass.
        if type(roll) is not int or not 1 <= roll <= 20:
            raise IntentError(HTTPStatus.BAD_REQUEST, "roll must be an integer from 1 to 20")
        check = self.pending_check
        if check is None:
            raise IntentError(HTTPStatus.BAD_REQUEST, "no pending check")
        modifier = ability_modifier(self.hero[check["ability"]])
        total = roll + modifier
        self.last_roll = {
            "value": roll,
            "modifier": modifier,
            "total": total,
            "dc": check["dc"],
            "skill": check["skill"],
            "success": total >= check["dc"],
            "isCritical": roll == 20,
        }
        self.pending_check = None
        self.journal.append({"event": "PHYSICAL_DICE_ROLL", **self.last_roll})
        return {"status": "ok", **self.last_roll}

    def _switch_view(self, values: dict[str, Any]) -> dict[str, Any]:
        view = values.get("view")
        if view not in ALLOWED_VIEWS:
            raise IntentError(HTTPStatus.BAD_REQUEST, f"view must be one of {list(ALLOWED_VIEWS)}")
        self.active_surface_type = view
        return {"status": "ok", "view": view}


class VRServer(ThreadingHTTPServer):
    """HTTP server that owns one ``CampaignVRState``."""

    daemon_threads = True
    # socketserver's default backlog of 5 resets bursts of parallel requests on macOS.
    request_queue_size = 64

    def __init__(self, address: tuple[str, int], state: CampaignVRState) -> None:
        super().__init__(address, VRServerRequestHandler)
        self.state = state


class VRServerRequestHandler(BaseHTTPRequestHandler):
    """Routes VR client requests to the server's state."""

    server: VRServer

    def _send_json(self, status: HTTPStatus, body: dict[str, Any]) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        try:
            self._route_get(urlparse(self.path).path)
        except Exception:
            logger.exception("GET %s failed", self.path)
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal"})

    def _route_get(self, path: str) -> None:
        state = self.server.state
        if path == "/api/surface":
            with state.lock:
                body = state.snapshot()
            self._send_json(HTTPStatus.OK, body)
        elif path == "/api/state":
            with state.lock:
                body = {
                    "hero": dict(state.hero),
                    "journal": list(state.journal),
                    "activeSurface": state.active_surface_type,
                }
            self._send_json(HTTPStatus.OK, body)
        elif path == "/health":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            self._route_post(urlparse(self.path).path)
        except Exception:
            logger.exception("POST %s failed", self.path)
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal"})

    def _read_json_object(self) -> dict[str, Any] | None:
        """Read and parse the body, answering 400/413 and returning None on failure."""
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid Content-Length"})
            return None
        if length > MAX_BODY_BYTES:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "body too large"})
            return None
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "body must be JSON"})
            return None
        if not isinstance(data, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "body must be a JSON object"})
            return None
        return data

    def _route_post(self, path: str) -> None:
        if path != "/api/intent":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        data = self._read_json_object()
        if data is None:
            return
        intent = data.get("intent")
        values = data.get("values", {})
        if not isinstance(intent, str):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "intent must be a string"})
        elif not isinstance(values, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "values must be an object"})
        else:
            self._send_json(*self.server.state.apply(intent, values))

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def make_server(
    host: str = "127.0.0.1", port: int = 8000, state: CampaignVRState | None = None
) -> VRServer:
    """Build a server with its own state (a fresh one unless ``state`` is given)."""
    return VRServer((host, port), state if state is not None else CampaignVRState())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Authoritative AI Dungeon Master VR server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.host not in LOOPBACK_HOSTS:
        logger.warning(
            "Binding %s exposes a mutable game with no auth and CORS '*' to the network",
            args.host,
        )
    server = make_server(args.host, args.port)
    logger.info("VR server listening on http://%s:%d", *server.server_address[:2])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":  # pragma: no cover
    main()
