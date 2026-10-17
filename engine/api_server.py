"""
engine/api_server.py
FastAPI backend for Aegis AI Dungeon Master.
Provides REST and WebSocket endpoints for Generative UI, audio synthesis, and DM interaction.
"""

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from audio_synth import generate_all_sfx
from d20_rules import AdvantageMode, DamageType, resolve_attack
from engine.story_engine import StoryEngine
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

engine = StoryEngine()
SFX_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audio_output")
sfx_cache = generate_all_sfx(SFX_DIR)


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
def get_health():
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
def get_world():
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
def regenerate_world():
    engine.world = generate_procedural_world()
    engine.active_combat_enemy = None
    engine.active_combat_grid = None
    engine.active_npc = None
    engine.tension_curve = 20
    return {"message": "New world forged", "world_name": engine.world.name}


@app.get("/api/player")
def get_player():
    return {
        "player": {
            "name": engine.player.name,
            "class_title": engine.player.class_title,
            "current_hp": engine.player.current_hp,
            "max_hp": engine.player.max_hp,
            "ac": engine.player.ac,
            "spell_slots": engine.player.spell_slots,
            "max_spell_slots": engine.player.max_spell_slots,
            "attack_bonus": engine.player.attack_bonus,
            "level": engine.player.level,
            "inventory": engine.player.inventory,
            "gold": engine.player.gold,
        }
    }


@app.post("/api/dm/interact")
def player_interact(req: PlayerActionRequest):
    ui_package = engine.process_turn(req.action)
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
