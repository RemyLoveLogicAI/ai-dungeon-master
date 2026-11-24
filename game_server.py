"""Loopback HTTP API and static hosting for the playable campaign client.

Serves the endpoints ``web/play.js`` and ``campaign_mcp.py`` already target:

* ``GET  /api/status``                  — provider state, write token, chronicle list
* ``POST /api/campaigns``               — open a chronicle
* ``GET  /api/campaigns/{id}``          — fetch current state
* ``POST /api/campaigns/{id}/actions``  — submit one player action
* ``POST /api/campaigns/{id}/reset``    — return to the start scene

Campaign execution is delegated to ``campaign_service.CampaignService``, which
runs the deterministic MCP Games definition over ``campaign_core.CampaignStore``.
There is no language model on this path: every turn is a deterministic function
of the game definition, so sessions replay identically.

Security model: the server binds to loopback only. Mutations that arrive with a
browser ``Origin`` header must carry the per-process ``X-Game-Token`` issued by
``/api/status`` (CSRF defense for the same-origin web client). Non-browser
clients — the MCP stdio adapter, curl, tests — send no ``Origin`` and are
trusted by virtue of already having local access. CORS is intentionally not
configured: the web client is served same-origin by this app.

Run::

    uv run uvicorn game_server:app --host 127.0.0.1 --port 8766
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from campaign_core import CampaignStore, ConflictError, NotFoundError
from campaign_service import CampaignService

_LOOKUP_ERRORS = (NotFoundError, ValueError)

_HERE = Path(__file__).resolve().parent
_WEB_DIR = _HERE / "web"
_DB_PATH = os.environ.get("AI_DM_CAMPAIGN_DB", str(_HERE / "data" / "campaigns.db"))

app = FastAPI(title="AI Dungeon Master Game Server", version="0.1.0")

_store = CampaignStore(_DB_PATH)
_service = CampaignService(_store)
_WRITE_TOKEN = secrets.token_hex(16)


class CampaignCreateRequest(BaseModel):
    profile: dict = {}
    request_id: str | None = None


class ActionRequest(BaseModel):
    revision: int
    request_id: str
    action: str = ""
    intent: str = "act"


def _check_write_token(request: Request, x_game_token: str | None) -> None:
    """Browser-origin mutations must carry the session write token."""
    if request.headers.get("origin") and x_game_token != _WRITE_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid write token")


@app.get("/api/status")
def status() -> dict:
    return {
        "configured": True,
        "dm_label": "Built-in scenario DM",
        "provider": "deterministic",
        "write_token": _WRITE_TOKEN,
        "campaigns": _store.list_summaries(),
    }


@app.post("/api/campaigns")
def create_campaign(
    body: CampaignCreateRequest,
    request: Request,
    x_game_token: str | None = Header(default=None),
) -> dict:
    _check_write_token(request, x_game_token)
    return _service.create(body.profile, body.request_id)


@app.get("/api/campaigns/{campaign_id}")
def get_campaign(campaign_id: str) -> dict:
    try:
        return _service.get(campaign_id)
    except _LOOKUP_ERRORS as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/campaigns/{campaign_id}/actions", response_model=None)
def act_on_campaign(
    campaign_id: str,
    body: ActionRequest,
    request: Request,
    x_game_token: str | None = Header(default=None),
) -> dict | JSONResponse:
    _check_write_token(request, x_game_token)
    try:
        return _service.act(campaign_id, body.revision, body.request_id, body.action, body.intent)
    except ConflictError as error:
        return JSONResponse(status_code=409, content={"error": {"message": str(error)}})
    except _LOOKUP_ERRORS as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/campaigns/{campaign_id}/reset")
def reset_campaign(
    campaign_id: str,
    request: Request,
    x_game_token: str | None = Header(default=None),
) -> dict:
    _check_write_token(request, x_game_token)
    try:
        return _service.reset(campaign_id)
    except _LOOKUP_ERRORS as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


if _WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
