"""Turn Orchestrator: End-to-end multimodal decision loop for AI Dungeon Master.

Implements Step 3 of the product roadmap:
Takes an authoritative player decision, resolves legal rules & mechanics,
and emits a coordinated multimodal turn envelope:
1. Coherent DM Narration
2. Visual Scene Art Direction (prompt & framing metadata)
3. Dynamic Audio & Ambient Cue (procedural synthesis / tension tagging)
4. Contextual Generative UI (validated agentsurface-blueprint/0.1)
5. Durable Campaign State & Journal Commit
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from d20_rules import SeededDiceSource
from game_foundation import validate_agentsurface_v01
from genui import GenUIBlueprintFactory


@dataclass
class VisualArtDirection:
    prompt: str
    negative_prompt: str
    aspect_ratio: str = "16:9"
    mood: str = "atmospheric fantasy"
    lighting: str = "dim moonlight with arcane bioluminescence"


@dataclass
class AudioCue:
    cue_type: str  # e.g. "dice_roll", "sword_clash", "crit_fanfare", "ambient_drone"
    tension_level: float  # 0.0 to 1.0
    drone_root_freq: float = 55.0
    duration: float = 2.0


@dataclass
class MultimodalTurnResult:
    turn_number: int
    intent: str
    mechanic_resolution: dict[str, Any]
    narration: str
    visual: VisualArtDirection
    audio: AudioCue
    surface: dict[str, Any]  # agentsurface-blueprint/0.1
    timestamp: float = field(default_factory=time.time)


class TurnOrchestrator:
    """Coordinates the authoritative turn loop across rules, narration, visuals, audio, and UI."""

    def __init__(self, dice_seed: int = 42) -> None:
        self.dice = SeededDiceSource(dice_seed)
        self.turn_count = 0
        self.campaign_flags: dict[str, Any] = {
            "observatory_discovered": True,
            "dragon_dial_aligned": False,
            "arcane_spark_lit": False,
            "dungeon_map_projected": False,
        }

    def execute_turn(
        self,
        hero: dict[str, Any],
        intent: str,
        params: dict[str, Any] | None = None,
    ) -> MultimodalTurnResult:
        self.turn_count += 1
        params = params or {}

        # 1. Authoritative Rules & Mechanics Resolution
        resolution: dict[str, Any] = {}
        narration = ""
        visual_prompt = ""
        cue_type = "ambient_drone"
        tension = 0.3

        if intent == "INVESTIGATE_APPARATUS":
            # Arcana check (d20 + INT modifier)
            d20 = self.dice.roll(20)
            int_mod = (hero.get("INT", 10) - 10) // 2
            total = d20 + int_mod
            dc = 12
            success = total >= dc
            resolution = {
                "skill": "Arcana",
                "d20": d20,
                "modifier": int_mod,
                "total": total,
                "dc": dc,
                "success": success,
            }
            if success:
                narration = (
                    f"You trace the silver inlay across the primary brass housing (Arcana check: {total} vs DC {dc}). "
                    "The celestial runes resolve into the ancient Draconic script: 'When the Silver Dragon crowns the zenith, "
                    "the eye of heaven opens.' The outer dial can now be turned to lock into alignment."
                )
                visual_prompt = (
                    "Close-up of an ancient brass astrolabe inscribed with glowing draconic runes, "
                    "fingers tracing silver inlays under a moonlit sky, 8k fantasy art, sharp focus."
                )
                cue_type = "crit_fanfare" if d20 == 20 else "dice_roll"
                tension = 0.25
            else:
                narration = (
                    f"You inspect the brass rings (Arcana check: {total} vs DC {dc}), but the ancient script is weathered "
                    "and clouded by centuries of mountain frost. You can tell it requires a celestial alignment, but the exact "
                    "sequence remains elusive."
                )
                visual_prompt = (
                    "Weathered brass mechanisms coated in hoarfrost inside a ruined observatory, "
                    "shattered stone dome overhead, dark starry night, fantasy atmosphere."
                )
                cue_type = "dice_roll"
                tension = 0.45

        elif intent == "ALIGN_CELESTIAL_DIAL":
            self.campaign_flags["dragon_dial_aligned"] = True
            resolution = {"action": "ALIGN_DIAL", "success": True, "dial": "Silver Dragon"}
            narration = (
                "With a firm grip on the central counterbalance, you rotate the heavy brass ring. "
                "Cogs click and groan as counterweights shift deep within the stone plinth. "
                "A heavy mechanical *thud* echoes through the terrace as the Silver Dragon emblem locks at the apex. "
                "The focusing crystal at the center begins to pulse with latent magical charge."
            )
            visual_prompt = (
                "Interlocking brass clockwork rings aligning with a mechanical click, "
                "a glowing quartz crystal at the center beginning to shine with celestial light, "
                "epic fantasy illustration, cinematic lighting."
            )
            cue_type = "crit_fanfare"
            tension = 0.2

        elif intent == "CHANNEL_ARCANA":
            self.campaign_flags["arcane_spark_lit"] = True
            self.campaign_flags["dungeon_map_projected"] = True
            resolution = {
                "action": "CHANNEL_ARCANA",
                "success": True,
                "unlocked": "dungeon_map",
            }
            narration = (
                "You channel an arcane spark into the primary lens. The crystal blazes to life! "
                "Beams of concentrated starlight shoot upward into the shattered dome, reflecting across glass shards "
                "to cast a brilliant, luminous map of the crypt levels across the flagstones beneath your feet. "
                "The hidden catacombs are revealed."
            )
            visual_prompt = (
                "A brilliant beam of starlight bursting from an observatory telescope, "
                "projecting a luminous glowing 3D blueprint map of subterranean catacombs across stone floor, "
                "breathtaking visual, high fantasy."
            )
            cue_type = "fireball_impact"
            tension = 0.65

        else:
            # General narrative exploration turn
            resolution = {"action": intent, "success": True}
            narration = (
                f"You focus your attention on {intent.lower().replace('_', ' ')}. "
                "The quiet mountain wind whispers through the shattered archways of the observatory, "
                "awaiting your next command."
            )
            visual_prompt = (
                "Ruined mountain observatory overlooking moonlit cloud banks and ancient pine forests, "
                "solitary hero standing at the parapet, atmospheric concept art."
            )
            cue_type = "ambient_drone"
            tension = 0.35

        # 2. Contextual Generative UI Composition
        status_text = (
            "Dials Aligned & Map Projected"
            if self.campaign_flags["dungeon_map_projected"]
            else (
                "Silver Dragon Dial Locked"
                if self.campaign_flags["dragon_dial_aligned"]
                else "Dials Misaligned (3 of 4 Locked)"
            )
        )
        surface_blueprint = GenUIBlueprintFactory.create_investigation_surface(
            surface_id=f"observatory-turn-{self.turn_count}",
            title="The Ruined Celestial Observatory",
            apparatus_state=status_text,
            investigation_clues=[
                "Ancient astrolabe lenses are cracked but functional.",
                "Brass rings bear celestial glyphs corresponding to the lunar equinox.",
                "Starlight projection active: catacomb layout identified."
                if self.campaign_flags["dungeon_map_projected"]
                else "A faint arcane hum emanates from the central focusing crystal.",
            ],
        ).to_agentsurface_v01()
        validate_agentsurface_v01(surface_blueprint, root="root")

        # 3. Assemble and return coordinated multimodal result
        return MultimodalTurnResult(
            turn_number=self.turn_count,
            intent=intent,
            mechanic_resolution=resolution,
            narration=narration,
            visual=VisualArtDirection(prompt=visual_prompt, negative_prompt="blurry, distorted, low resolution"),
            audio=AudioCue(cue_type=cue_type, tension_level=tension),
            surface=surface_blueprint,
        )
