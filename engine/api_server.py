"""
engine/api_server.py
FastAPI backend for Aegis AI Dungeon Master.
Provides REST and WebSocket endpoints for Generative UI, audio synthesis, and DM interaction.
"""

import os
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from audio_synth import generate_all_sfx
from campaign_core import CampaignStore, character_catalog
from d20_rules import AdvantageMode, DamageType, resolve_attack
from engine.character_service import create_character, delete_character, get_current_character
from engine.scene_visuals import render_scene_illustration
from engine.story_engine import PlayerCharacter, StoryEngine
from engine.world_generator import generate_procedural_world

app = FastAPI(title="Aegis AI Dungeon Master Engine", version="1.0.0")

# Enable CORS for local Vite development and mobile apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SFX_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audio_output")
sfx_cache = generate_all_sfx(SFX_DIR)

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
campaign_store = CampaignStore(os.path.join(_DATA_DIR, "campaigns.db"))


class SessionState:
    """Per-session play state: one story engine and one active-campaign pointer.

    Campaign persistence (campaign_store, below) is shared across sessions by
    design -- only in-memory gameplay state needs isolating so that two
    sessions activating different characters don't clobber each other's
    turn, combat, or world state.
    """

    def __init__(self) -> None:
        self.engine: StoryEngine = StoryEngine()
        self.active_campaign_id: str | None = None


_sessions: dict[str, SessionState] = {}
_DEFAULT_SESSION_ID = "default"


def get_session_id(x_session_id: str | None = Header(default=None, alias="X-Session-ID")) -> str:
    return x_session_id or _DEFAULT_SESSION_ID


def get_session(session_id: str = Depends(get_session_id)) -> SessionState:
    state = _sessions.get(session_id)
    if state is None:
        state = SessionState()
        _sessions[session_id] = state
    return state


class CreateCharacterRequest(BaseModel):
    name: str
    concept: str = ""
    appearance: str = ""
    portrait_id: str = ""
    character_class: str = Field(default="Fighter", alias="class")
    species: str = "Human"
    level: int = 1

    model_config = ConfigDict(populate_by_name=True)


class PlayerActionRequest(BaseModel):
    action: str
    card_id: str | None = None
    roll_result: int | None = None


class AttackRequest(BaseModel):
    attacker: str
    target: str
    attack_modifier: int = 5
    target_ac: int = 14
    damage_dice_count: int = 1
    damage_die_sides: int = 8
    damage_modifier: int = 3
    damage_type: str = "Slashing"
    advantage: str = "Normal"


@app.get("/api/health")
def get_health(session: Annotated[SessionState, Depends(get_session)]):
    engine = session.engine
    ollama_ok = engine.check_ollama_available()
    models = engine.list_ollama_models() if ollama_ok else []
    return {
        "status": "healthy",
        "world_name": engine.world.name,
        "ollama_available": ollama_ok,
        "available_models": models,
        "tension_level": engine.tension_curve,
        "current_location": engine.get_current_location().name,
    }


@app.get("/api/world/current")
def get_world(session: Annotated[SessionState, Depends(get_session)]):
    engine = session.engine
    return {
        "world": {
            "id": engine.world.id,
            "name": engine.world.name,
            "epoch": engine.world.epoch,
            "cosmology": engine.world.cosmology,
            "cataclysm_lore": engine.world.cataclysm_lore,
            "active_quest": engine.world.active_quest,
            "tension_level": engine.tension_curve,
            "current_location_id": engine.world.current_location_id,
            "factions": [f.__dict__ for f in engine.world.factions],
            "locations": [loc.__dict__ for loc in engine.world.locations],
        }
    }


@app.post("/api/world/generate")
def regenerate_world(session: Annotated[SessionState, Depends(get_session)]):
    engine = session.engine
    engine.world = generate_procedural_world()
    engine.active_combat_enemy = None
    engine.active_combat_grid = None
    engine.active_npc = None
    engine.tension_curve = 20
    return {"message": "New world forged", "world_name": engine.world.name}



@app.get("/api/scene/current")
def get_current_scene(session: Annotated[SessionState, Depends(get_session)]):
    loc = session.engine.get_current_location()
    illustration = render_scene_illustration(
        location_name=loc.name,
        biome=loc.biome,
        description=loc.description,
        tension_level=session.engine.tension_curve,
    )
    return {"illustration": illustration.to_dict()}


@app.get("/api/scene/image/{location_name}")
def get_scene_image(location_name: str, session: Annotated[SessionState, Depends(get_session)]):
    target_loc = None
    for loc in session.engine.world.locations:
        if loc.name.lower() == location_name.lower():
            target_loc = loc
            break
    if target_loc is None:
        target_loc = session.engine.get_current_location()

    illustration = render_scene_illustration(
        location_name=target_loc.name,
        biome=target_loc.biome,
        description=target_loc.description,
        tension_level=session.engine.tension_curve,
    )
    return Response(
        content=illustration.svg_data,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/api/player")
def get_player(session: Annotated[SessionState, Depends(get_session)]):
    player = session.engine.player
    return {
        "player": {
            "name": player.name,
            "class_title": player.class_title,
            "current_hp": player.current_hp,
            "max_hp": player.max_hp,
            "ac": player.ac,
            "spell_slots": player.spell_slots,
            "max_spell_slots": player.max_spell_slots,
            "attack_bonus": player.attack_bonus,
            "level": player.level,
            "inventory": player.inventory,
            "gold": player.gold,
            "portrait_id": player.portrait_id,
        }
    }


@app.get("/api/characters/catalog")
def get_character_catalog():
    return character_catalog()


@app.get("/api/characters")
def list_characters():
    return {"campaigns": campaign_store.list_summaries()}


@app.post("/api/characters")
def create_new_character(
    req: CreateCharacterRequest,
    session: Annotated[SessionState, Depends(get_session)],
):
    try:
        campaign = create_character(campaign_store, {
            "name": req.name,
            "concept": req.concept,
            "appearance": req.appearance,
            "portrait_id": req.portrait_id,
            "class": req.character_class,
            "species": req.species,
            "level": req.level,
        })
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    session.active_campaign_id = campaign["id"]
    session.engine.player = PlayerCharacter.from_sheet(campaign["character"])
    session.engine.narrative_history = []
    session.engine._initialize_story()
    return {"campaign_id": campaign["id"], "character": campaign["character"]}


@app.get("/api/characters/current")
def get_active_character(session: Annotated[SessionState, Depends(get_session)]):
    if session.active_campaign_id is None:
        return {"campaign_id": None, "character": None}
    character = get_current_character(campaign_store, session.active_campaign_id)
    return {"campaign_id": session.active_campaign_id, "character": character}


@app.post("/api/characters/{campaign_id}/activate")
def activate_character(campaign_id: str, session: Annotated[SessionState, Depends(get_session)]):
    try:
        character = get_current_character(campaign_store, campaign_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid campaign id")
    if character is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    session.active_campaign_id = campaign_id
    session.engine.player = PlayerCharacter.from_sheet(character)
    return {"campaign_id": campaign_id, "character": character}


@app.delete("/api/characters/{campaign_id}")
def remove_character(campaign_id: str):
    try:
        deleted = delete_character(campaign_store, campaign_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid campaign id")
    if not deleted:
        raise HTTPException(status_code=404, detail="Campaign not found")
    for state in _sessions.values():
        if state.active_campaign_id == campaign_id:
            state.active_campaign_id = None
    return {"campaign_id": campaign_id, "deleted": True}


@app.post("/api/dm/interact")
def player_interact(
    req: PlayerActionRequest,
    session: Annotated[SessionState, Depends(get_session)],
):
    ui_package = session.engine.process_turn(req.action)
    return {"response": ui_package.to_dict()}


@app.post("/api/combat/attack")
def execute_combat_attack(req: AttackRequest):
    adv_mode = AdvantageMode.NORMAL
    if req.advantage.lower() == "advantage":
        adv_mode = AdvantageMode.ADVANTAGE
    elif req.advantage.lower() == "disadvantage":
        adv_mode = AdvantageMode.DISADVANTAGE

    dmg_type = DamageType.SLASHING
    for dt in DamageType:
        if dt.value.lower() == req.damage_type.lower():
            dmg_type = dt
            break

    res = resolve_attack(
        attacker=req.attacker,
        target=req.target,
        attack_modifier=req.attack_modifier,
        target_ac=req.target_ac,
        damage_dice_count=req.damage_dice_count,
        damage_die_sides=req.damage_die_sides,
        damage_modifier=req.damage_modifier,
        damage_type=dmg_type,
        advantage=adv_mode,
    )
    return {
        "is_hit": res.is_hit,
        "is_critical": res.is_critical,
        "damage_dealt": res.damage_dealt,
        "combat_message": res.combat_message,
        "roll": {
            "d20_roll": res.roll.d20_roll,
            "total": res.roll.total,
            "is_nat_20": res.roll.is_natural_20,
            "is_nat_1": res.roll.is_natural_1,
        },
    }


@app.get("/api/audio/sfx/{sound_name}")
def get_sfx(sound_name: str):
    if sound_name not in sfx_cache or not os.path.exists(sfx_cache[sound_name]):
        raise HTTPException(status_code=404, detail="SFX not found")
    return FileResponse(sfx_cache[sound_name], media_type="audio/wav")


# Mount client distribution directory if built
client_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "client", "dist")
if os.path.exists(client_dist):
    app.mount("/", StaticFiles(directory=client_dist, html=True), name="static")
