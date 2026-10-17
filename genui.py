"""Generative UI & TUI Surface Engine for AI Dungeon Master.

Implements:
1. Declarative GenUI DSL Blueprint generation (A2UI / Agent Surface specs) for Web, Tauri, and Mobile.
2. Terminal UI (TUI) surface renderer inspired by Leaf MCP/CLI and Television TUI,
   rendering ANSI split panes, dynamic tactical ASCII/Unicode maps, health meters,
   action economy badges, and contextual intent menus.
3. Declarative Intent Router definitions for zero-eval client/host two-way synchronization.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from game_foundation import validate_agentsurface_v01


class UIComponentType(Enum):
    SURFACE = "Surface"
    CARD = "Card"
    ROW = "Row"
    COLUMN = "Column"
    METRIC = "Metric"
    BADGE = "Badge"
    PROGRESS_BAR = "ProgressBar"
    TACTICAL_GRID = "TacticalGrid"
    DICE_TRAY = "DiceTray"
    ACTION_BUTTON = "ActionButton"
    TEXT = "Text"


class BadgeVariant(Enum):
    NEUTRAL = "neutral"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    ACCENT = "accent"


@dataclass
class UIComponent:
    id: str
    type: str
    parentId: str | None = None
    props: dict[str, Any] = field(default_factory=dict)


@dataclass
class SurfaceBlueprint:
    """A local, build-time description of one surface.

    ``to_dict`` is the builder's own view: a parent-pointer tree with a local
    ``surfaceId``/``theme`` vocabulary. The *canonical* interoperable form is
    :meth:`to_agentsurface_v01`, which emits the shared
    ``agentsurface-blueprint/0.1`` envelope and is validated against the same
    contract the scenario adapter uses.
    """

    surfaceId: str
    title: str
    theme: str = "dark-dungeon"
    subtitle: str = ""
    components: list[UIComponent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "surfaceId": self.surfaceId,
            "title": self.title,
            "theme": self.theme,
            "components": [
                {
                    "id": c.id,
                    "type": c.type,
                    "parentId": c.parentId,
                    "props": c.props,
                }
                for c in self.components
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_agentsurface_v01(self) -> dict[str, Any]:
        """Export the local component tree using the shared AgentSurface DSL."""
        data_model: dict[str, Any] = {}
        intents: list[str] = []
        exported: list[dict[str, Any]] = []
        generated: list[dict[str, Any]] = []
        children: dict[str, list[str]] = {}
        for component in self.components:
            if component.parentId is not None:
                children.setdefault(component.parentId, []).append(component.id)

        for component in self.components:
            source_type = component.type
            props = dict(component.props)
            component_type = source_type
            extra_children: list[str] = []
            if source_type == UIComponentType.SURFACE.value:
                component_type, props = "Stack", {"direction": "column", "gap": "16"}
            elif source_type == UIComponentType.ROW.value:
                component_type, props = "Stack", {"direction": "row", "gap": props.get("gap", "12")}
            elif source_type == UIComponentType.COLUMN.value:
                component_type, props = (
                    "Stack",
                    {"direction": "column", "gap": props.get("gap", "12")},
                )
            elif source_type == UIComponentType.CARD.value:
                title = props.pop("title", None)
                badge = props.pop("badge", None)
                props = {"padding": "16"}
                for suffix, kind, item_props in (
                    ("title", "Heading", {"text": title, "level": 3}),
                    ("badge", "Badge", {"text": badge, "tone": "accent"}),
                ):
                    if item_props.get("text") is not None:
                        child_id = f"{component.id}-{suffix}"
                        extra_children.append(child_id)
                        generated.append({"id": child_id, "type": kind, "props": item_props})
            elif source_type == UIComponentType.METRIC.value:
                trend = props.pop("trend", None)
                props.pop("variant", None)
                component_type = "Stat"
                if trend:
                    child_id = f"{component.id}-trend"
                    extra_children.append(child_id)
                    generated.append(
                        {
                            "id": child_id,
                            "type": "Badge",
                            "props": {
                                "text": trend,
                                "tone": "warn" if trend == "CRITICAL" else "accent",
                            },
                        }
                    )
            elif source_type == UIComponentType.BADGE.value:
                variant = props.get("variant")
                component_type = "Badge"
                props = {
                    "text": props.get("label", ""),
                    "tone": {
                        "warning": "warn",
                        "danger": "warn",
                        "success": "accent",
                    }.get(variant, "default")
                    if isinstance(variant, str)
                    else "default",
                }
            elif source_type == UIComponentType.PROGRESS_BAR.value:
                component_type = "ProgressBar"
                props = {
                    "label": f"{props.get('label', '')} ({props.get('current', 0)} / "
                    f"{props.get('max', 0)} {props.get('unit', '')})".strip(),
                    "value": props.get("current", 0),
                    "max": props.get("max", 0),
                }
            elif source_type == UIComponentType.TACTICAL_GRID.value:
                component_type = "Table"
                width = props.get("gridWidth", 0)
                height = props.get("gridHeight", 0)
                hero = props.get("heroPos", [])
                enemy = props.get("enemyPos", [])
                covers = {tuple(pos) for pos in props.get("covers", [])}
                rows = []
                for y in range(height):
                    row = "".join(
                        "@"
                        if [x, y] == hero
                        else "G"
                        if [x, y] == enemy
                        else "#"
                        if (x, y) in covers
                        else "·"
                        for x in range(width)
                    )
                    rows.append({"row": row})
                component_type = "Table"
                props = {
                    "columns": [{"key": "row", "label": props.get("lighting", "Map")}],
                    "rows": rows,
                    "dense": True,
                }
            elif source_type == UIComponentType.DICE_TRAY.value:
                component_type, props = "Text", {"text": props.get("label", "Dice")}
            elif source_type == UIComponentType.ACTION_BUTTON.value:
                label = props.pop("label", "")
                enabled = props.pop("enabled", True)
                if not enabled:
                    component_type, props = "Text", {"text": f"{label} — unavailable"}
                else:
                    intent = props.pop("intent", "")
                    if intent not in intents:
                        intents.append(intent)
                    params = props.pop("params", {}) or {}
                    payload_keys = []
                    for key, value in params.items():
                        model_key = f"{component.id}.{key}"
                        data_model[model_key] = value
                        payload_keys.append(model_key)
                    props = {
                        "label": label,
                        "action": {"intent": intent, "payloadKeys": payload_keys},
                    }
                    component_type = "Button"
            elif source_type == UIComponentType.TEXT.value:
                component_type = "Text"
                props = {"text": props.get("content", props.get("text", ""))}
            child_ids = [*extra_children, *children.get(component.id, [])]
            entry = {"id": component.id, "type": component_type, "props": props}
            if child_ids:
                entry["children"] = child_ids
            exported.append(entry)

        exported.extend(generated)
        payload = {
            "surface": {
                "id": self.surfaceId,
                "title": self.title,
                "subtitle": self.subtitle,
                "width": "wide",
            },
            "dataModel": data_model,
            "components": exported,
            "intents": intents,
        }
        validate_agentsurface_v01(payload)
        return payload


@dataclass
class IntentEnvelope:
    event: str = "INTENT_FIRED"
    surfaceId: str = "dungeon-surface"
    intent: str = ""
    timestamp: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


# ANSI Color Codes for Terminal UI
class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_DARK = "\033[48;5;234m"
    BG_PANEL = "\033[48;5;236m"
    FG_GOLD = "\033[38;5;220m"
    FG_CRIMSON = "\033[38;5;196m"
    FG_EMERALD = "\033[38;5;46m"
    FG_PURPLE = "\033[38;5;141m"
    FG_MUTED = "\033[38;5;244m"


class TerminalSurfaceRenderer:
    """Renders high-density, stylized TUI game surfaces in the terminal."""

    @staticmethod
    def render_health_bar(current: int, maximum: int, width: int = 16) -> str:
        pct = max(0.0, min(1.0, current / maximum if maximum > 0 else 0.0))
        filled = round(pct * width)
        empty = width - filled

        if pct > 0.5:
            color = ANSI.FG_EMERALD
        elif pct > 0.2:
            color = ANSI.YELLOW
        else:
            color = ANSI.FG_CRIMSON

        bar = f"{color}{'█' * filled}{ANSI.FG_MUTED}{'░' * empty}{ANSI.RESET}"
        return f"[{bar}] {color}{current}/{maximum} HP{ANSI.RESET}"

    @staticmethod
    def render_tactical_grid(
        width: int = 12,
        height: int = 6,
        hero_pos: tuple[int, int] = (2, 3),
        enemy_pos: tuple[int, int] = (9, 3),
        cover_positions: list[tuple[int, int]] | None = None,
        biome: str = "Dungeon Crypt",
    ) -> list[str]:
        covers = cover_positions or [(5, 2), (5, 3), (6, 4)]
        lines = []
        lines.append(
            f"{ANSI.FG_GOLD}┌── TACTICAL GRID [{biome}] {'─' * max(0, width * 2 - 20)}┐{ANSI.RESET}"
        )

        for y in range(height):
            row_chars = []
            for x in range(width):
                if (x, y) == hero_pos:
                    row_chars.append(f"{ANSI.FG_EMERALD}{ANSI.BOLD} @{ANSI.RESET}")
                elif (x, y) == enemy_pos:
                    row_chars.append(f"{ANSI.FG_CRIMSON}{ANSI.BOLD} G{ANSI.RESET}")
                elif (x, y) in covers:
                    row_chars.append(f"{ANSI.FG_MUTED} #{ANSI.RESET}")
                else:
                    # Alternating subtle floor grid dot
                    row_chars.append(f"{ANSI.DIM} . {ANSI.RESET}")
            row_str = "".join(row_chars)
            lines.append(f"{ANSI.FG_GOLD}│{ANSI.RESET}{row_str}{ANSI.FG_GOLD}│{ANSI.RESET}")

        legend = (
            f"{ANSI.FG_GOLD}└─ Legend: {ANSI.FG_EMERALD}@{ANSI.RESET} Hero "
            f"{ANSI.FG_CRIMSON}G{ANSI.RESET} Gargoyle "
            f"{ANSI.FG_MUTED}#{ANSI.RESET} Half-Cover "
            f"{ANSI.DIM}.{ANSI.RESET} 5ft Tile ─┘{ANSI.RESET}"
        )
        lines.append(legend)
        return lines

    @staticmethod
    def render_panel(
        title: str, content_lines: list[str], width: int = 60, color: str = ANSI.CYAN
    ) -> str:
        border_top = f"{color}┌─ {ANSI.BOLD}{title}{ANSI.RESET}{color} {'─' * max(0, width - len(title) - 5)}┐{ANSI.RESET}"
        border_bot = f"{color}└{'─' * (width - 2)}┘{ANSI.RESET}"

        formatted = [border_top]
        for line in content_lines:
            # Strip simple ANSI for length calculation
            clean_len = len(
                line.replace(ANSI.BOLD, "")
                .replace(ANSI.RESET, "")
                .replace(ANSI.DIM, "")
                .replace(ANSI.FG_GOLD, "")
                .replace(ANSI.FG_EMERALD, "")
                .replace(ANSI.FG_CRIMSON, "")
                .replace(ANSI.CYAN, "")
                .replace(ANSI.YELLOW, "")
            )
            pad = max(0, width - 4 - clean_len)
            formatted.append(f"{color}│{ANSI.RESET} {line}{' ' * pad} {color}│{ANSI.RESET}")
        formatted.append(border_bot)
        return "\n".join(formatted)


class GenUIBlueprintFactory:
    """Constructs sovereign Declarative GenUI Blueprints for the DM platform."""

    @staticmethod
    def create_encounter_surface(
        surface_id: str,
        title: str,
        round_num: int,
        hero_name: str,
        hero_hp: int,
        hero_max_hp: int,
        hero_conditions: list[str],
        hero_actions_available: dict[str, bool],
        enemy_name: str,
        enemy_hp: int,
        enemy_max_hp: int,
        enemy_stance: str,
        combat_log: list[str],
        tension_level: float,
    ) -> SurfaceBlueprint:
        blueprint = SurfaceBlueprint(surfaceId=surface_id, title=title)
        c = blueprint.components

        # Root Surface Container
        c.append(
            UIComponent(
                id="root",
                type=UIComponentType.SURFACE.value,
                props={"maxWidth": "960px", "padding": "24px"},
            )
        )

        # Top Header Card with Tension Metric and Round info
        c.append(
            UIComponent(
                id="header-card",
                type=UIComponentType.CARD.value,
                parentId="root",
                props={"title": title, "badge": f"Round {round_num}"},
            )
        )
        c.append(
            UIComponent(
                id="header-row",
                type=UIComponentType.ROW.value,
                parentId="header-card",
                props={"gap": "16px"},
            )
        )
        c.append(
            UIComponent(
                id="metric-tension",
                type=UIComponentType.METRIC.value,
                parentId="header-row",
                props={
                    "label": "Tension Index",
                    "value": f"{int(tension_level * 100)}%",
                    "trend": "CRITICAL"
                    if tension_level > 0.7
                    else ("ELEVATED" if tension_level > 0.4 else "STABLE"),
                    "variant": "danger" if tension_level > 0.7 else "warning",
                },
            )
        )
        c.append(
            UIComponent(
                id="metric-stance",
                type=UIComponentType.METRIC.value,
                parentId="header-row",
                props={"label": "Enemy Stance", "value": enemy_stance, "variant": "accent"},
            )
        )

        # Split Column Layout: Left Column = Tactical Grid & Log; Right Column = Combatants & Action Bar
        c.append(
            UIComponent(
                id="main-split",
                type=UIComponentType.ROW.value,
                parentId="root",
                props={"gap": "20px"},
            )
        )
        c.append(
            UIComponent(
                id="left-col",
                type=UIComponentType.COLUMN.value,
                parentId="main-split",
                props={"flex": "3"},
            )
        )
        c.append(
            UIComponent(
                id="right-col",
                type=UIComponentType.COLUMN.value,
                parentId="main-split",
                props={"flex": "2"},
            )
        )

        # Tactical Map Component
        c.append(
            UIComponent(
                id="tactical-card",
                type=UIComponentType.CARD.value,
                parentId="left-col",
                props={"title": "Tactical Arena"},
            )
        )
        c.append(
            UIComponent(
                id="tactical-grid",
                type=UIComponentType.TACTICAL_GRID.value,
                parentId="tactical-card",
                props={
                    "gridWidth": 12,
                    "gridHeight": 6,
                    "heroPos": [2, 3],
                    "enemyPos": [9, 3],
                    "covers": [[5, 2], [5, 3], [6, 4]],
                    "lighting": "Dim Light (Cavern)",
                },
            )
        )

        # Narrative / Combat Feed Card
        c.append(
            UIComponent(
                id="feed-card",
                type=UIComponentType.CARD.value,
                parentId="left-col",
                props={"title": "Chronicle Feed"},
            )
        )
        recent_log = combat_log[-4:]
        for idx, entry in enumerate(recent_log):
            c.append(
                UIComponent(
                    id=f"log-entry-{idx}",
                    type=UIComponentType.TEXT.value,
                    parentId="feed-card",
                    props={
                        "content": entry,
                        "variant": "caption" if idx < len(recent_log) - 1 else "body",
                    },
                )
            )

        # Right Column: Combatant Status Cards
        # Hero Status Card
        c.append(
            UIComponent(
                id="hero-card",
                type=UIComponentType.CARD.value,
                parentId="right-col",
                props={"title": f"Hero: {hero_name}"},
            )
        )
        c.append(
            UIComponent(
                id="hero-hp-bar",
                type=UIComponentType.PROGRESS_BAR.value,
                parentId="hero-card",
                props={
                    "label": "Hit Points",
                    "current": hero_hp,
                    "max": hero_max_hp,
                    "unit": "HP",
                },
            )
        )
        for cond in hero_conditions:
            c.append(
                UIComponent(
                    id=f"cond-{cond}",
                    type=UIComponentType.BADGE.value,
                    parentId="hero-card",
                    props={
                        "label": cond,
                        "variant": BadgeVariant.WARNING.value,
                    },
                )
            )

        # Action Economy Tracker Badges
        c.append(
            UIComponent(
                id="economy-row",
                type=UIComponentType.ROW.value,
                parentId="hero-card",
                props={"gap": "8px", "marginTop": "10px"},
            )
        )
        for act_name, available in hero_actions_available.items():
            c.append(
                UIComponent(
                    id=f"eco-{act_name}",
                    type=UIComponentType.BADGE.value,
                    parentId="economy-row",
                    props={
                        "label": act_name,
                        "variant": BadgeVariant.SUCCESS.value
                        if available
                        else BadgeVariant.NEUTRAL.value,
                    },
                )
            )

        # Enemy Status Card
        c.append(
            UIComponent(
                id="enemy-card",
                type=UIComponentType.CARD.value,
                parentId="right-col",
                props={"title": f"Adversary: {enemy_name}"},
            )
        )
        c.append(
            UIComponent(
                id="enemy-hp-bar",
                type=UIComponentType.PROGRESS_BAR.value,
                parentId="enemy-card",
                props={
                    "label": "Threat Integrity",
                    "current": enemy_hp,
                    "max": enemy_max_hp,
                    "unit": "HP",
                },
            )
        )

        # Declarative Interactive Action Tray (Zero-Eval Intent Dispatch)
        c.append(
            UIComponent(
                id="action-card",
                type=UIComponentType.CARD.value,
                parentId="right-col",
                props={"title": "Action Matrix"},
            )
        )
        c.append(
            UIComponent(
                id="btn-attack",
                type=UIComponentType.ACTION_BUTTON.value,
                parentId="action-card",
                props={
                    "label": "⚔️ Attack (Action)",
                    "intent": "HERO_ATTACK",
                    "enabled": hero_actions_available.get("Action", True),
                    "params": {"attackType": "Melee", "target": enemy_name},
                },
            )
        )
        c.append(
            UIComponent(
                id="btn-dodge",
                type=UIComponentType.ACTION_BUTTON.value,
                parentId="action-card",
                props={
                    "label": "🛡️ Dodge (Action)",
                    "intent": "HERO_DODGE",
                    "enabled": hero_actions_available.get("Action", True),
                    "params": {},
                },
            )
        )
        c.append(
            UIComponent(
                id="btn-spell",
                type=UIComponentType.ACTION_BUTTON.value,
                parentId="action-card",
                props={
                    "label": "🔥 Cast Spell (Action)",
                    "intent": "HERO_CAST_SPELL",
                    "enabled": hero_actions_available.get("Action", True),
                    "params": {"spell": "Guiding Bolt", "target": enemy_name},
                },
            )
        )
        c.append(
            UIComponent(
                id="btn-rest",
                type=UIComponentType.ACTION_BUTTON.value,
                parentId="action-card",
                props={
                    "label": "🏕️ Short Rest",
                    "intent": "TAKE_REST",
                    "enabled": True,
                    "params": {"type": "Short"},
                },
            )
        )

        return blueprint

    @staticmethod
    def create_onboarding_surface(
        surface_id: str = "onboarding-stage-1-2",
        title: str = "Meet Your Dungeon Master",
        player_familiarity: str = "Beginner (New to D&D)",
        guidance_level: str = "Full Guidance",
        edition: str = "D&D 5th Edition (Revised 2024)",
        character_name: str = "Kaelen Ironheart",
        archetype: str = "Fighter",
        species: str = "Human",
        background: str = "Soldier",
        origin_feat: str = "Savage Attacker",
        level: int = 1,
        hp: int = 12,
        max_hp: int = 12,
        ac: int = 16,
        ability_scores: dict[str, int] | None = None,
        weapon_mastery: str = "Longsword (Sap / Flex)",
    ) -> SurfaceBlueprint:
        blueprint = SurfaceBlueprint(
            surfaceId=surface_id,
            title=title,
            subtitle="Stage 1 & 2: Introduction, Calibration & Character Draft",
        )
        c = blueprint.components
        scores = ability_scores or {
            "STR": 16,
            "DEX": 13,
            "CON": 15,
            "INT": 10,
            "WIS": 12,
            "CHA": 8,
        }

        # Root Surface
        c.append(UIComponent(id="root", type=UIComponentType.SURFACE.value, props={"theme": "dark-dungeon"}))

        # Welcome Card (Stage 1: Meet the AI DM)
        c.append(
            UIComponent(
                id="welcome-card",
                type=UIComponentType.CARD.value,
                parentId="root",
                props={"title": "Table Welcome & DM Introduction"},
            )
        )
        c.append(
            UIComponent(
                id="welcome-text",
                type=UIComponentType.TEXT.value,
                parentId="welcome-card",
                props={
                    "text": (
                        "Welcome to the table! I'm your AI Dungeon Master. I'll bring the world and its people "
                        "to life, referee the rules, and describe what happens when you act—while you decide what "
                        "your character attempts. Let's calibrate your experience and draft your starting hero."
                    )
                },
            )
        )

        # Calibration Badges (Stage 2: Learn the player)
        c.append(
            UIComponent(
                id="calibration-row",
                type=UIComponentType.ROW.value,
                parentId="welcome-card",
                props={"gap": "10px", "marginTop": "8px"},
            )
        )
        c.append(
            UIComponent(
                id="badge-familiarity",
                type=UIComponentType.BADGE.value,
                parentId="calibration-row",
                props={"label": f"Familiarity: {player_familiarity}", "variant": BadgeVariant.ACCENT.value},
            )
        )
        c.append(
            UIComponent(
                id="badge-guidance",
                type=UIComponentType.BADGE.value,
                parentId="calibration-row",
                props={"label": f"Guidance: {guidance_level}", "variant": BadgeVariant.SUCCESS.value},
            )
        )
        c.append(
            UIComponent(
                id="badge-edition",
                type=UIComponentType.BADGE.value,
                parentId="calibration-row",
                props={"label": f"Rules: {edition}", "variant": BadgeVariant.WARNING.value},
            )
        )

        # Main Split: Left Column = Draft Character Sheet; Right Column = Controls & Archetypes
        c.append(
            UIComponent(
                id="main-split",
                type=UIComponentType.ROW.value,
                parentId="root",
                props={"gap": "20px"},
            )
        )
        c.append(
            UIComponent(
                id="left-col",
                type=UIComponentType.COLUMN.value,
                parentId="main-split",
                props={"flex": "3"},
            )
        )
        c.append(
            UIComponent(
                id="right-col",
                type=UIComponentType.COLUMN.value,
                parentId="main-split",
                props={"flex": "2"},
            )
        )

        # Character Draft Card
        c.append(
            UIComponent(
                id="draft-card",
                type=UIComponentType.CARD.value,
                parentId="left-col",
                props={"title": f"Starting Draft: {character_name}"},
            )
        )
        c.append(
            UIComponent(
                id="draft-summary",
                type=UIComponentType.TEXT.value,
                parentId="draft-card",
                props={
                    "text": (
                        f"Level {level} {species} {archetype} · Background: {background} · "
                        f"Origin Feat: {origin_feat} · Mastery: {weapon_mastery}"
                    )
                },
            )
        )

        # Ability Score Metrics
        c.append(
            UIComponent(
                id="abilities-row",
                type=UIComponentType.ROW.value,
                parentId="draft-card",
                props={"gap": "12px", "marginTop": "8px"},
            )
        )
        for stat_name, score in scores.items():
            mod = (score - 10) // 2
            sign = "+" if mod >= 0 else ""
            c.append(
                UIComponent(
                    id=f"stat-{stat_name.lower()}",
                    type=UIComponentType.METRIC.value,
                    parentId="abilities-row",
                    props={
                        "label": stat_name,
                        "value": f"{score} ({sign}{mod})",
                    },
                )
            )

        # Combat Vitals
        c.append(
            UIComponent(
                id="vitals-row",
                type=UIComponentType.ROW.value,
                parentId="draft-card",
                props={"gap": "16px", "marginTop": "10px"},
            )
        )
        c.append(
            UIComponent(
                id="draft-hp-bar",
                type=UIComponentType.PROGRESS_BAR.value,
                parentId="vitals-row",
                props={
                    "label": "Hit Points",
                    "current": hp,
                    "max": max_hp,
                    "unit": "HP",
                },
            )
        )
        c.append(
            UIComponent(
                id="metric-ac",
                type=UIComponentType.METRIC.value,
                parentId="vitals-row",
                props={"label": "Armor Class", "value": f"{ac} (Chain Mail)"},
            )
        )

        # Right Column: Actions and Archetype Switcher
        c.append(
            UIComponent(
                id="action-card",
                type=UIComponentType.CARD.value,
                parentId="right-col",
                props={"title": "Calibration & Decisions"},
            )
        )
        c.append(
            UIComponent(
                id="btn-confirm",
                type=UIComponentType.ACTION_BUTTON.value,
                parentId="action-card",
                props={
                    "label": "✨ Confirm Character & Enter Adventure",
                    "intent": "CONFIRM_CHARACTER_DRAFT",
                    "enabled": True,
                    "params": {
                        "characterName": character_name,
                        "archetype": archetype,
                        "edition": edition,
                        "guidance": guidance_level,
                    },
                },
            )
        )
        c.append(
            UIComponent(
                id="btn-switch-archetype",
                type=UIComponentType.ACTION_BUTTON.value,
                parentId="action-card",
                props={
                    "label": f"🎲 Switch to {'Wizard' if archetype != 'Wizard' else 'Fighter'} Archetype",
                    "intent": "SWITCH_STARTER_ARCHETYPE",
                    "enabled": True,
                    "params": {"archetype": "Wizard" if archetype != "Wizard" else "Fighter"},
                },
            )
        )
        c.append(
            UIComponent(
                id="btn-adjust-guidance",
                type=UIComponentType.ACTION_BUTTON.value,
                parentId="action-card",
                props={
                    "label": "⚙️ Toggle Guidance Level",
                    "intent": "ADJUST_GUIDANCE",
                    "enabled": True,
                    "params": {"current": guidance_level},
                },
            )
        )

        return blueprint

