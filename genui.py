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
    surfaceId: str
    title: str
    theme: str = "dark-dungeon"
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
        lines.append(f"{ANSI.FG_GOLD}┌── TACTICAL GRID [{biome}] {'─' * max(0, width * 2 - 20)}┐{ANSI.RESET}")

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

        legend = (f"{ANSI.FG_GOLD}└─ Legend: {ANSI.FG_EMERALD}@{ANSI.RESET} Hero "
                  f"{ANSI.FG_CRIMSON}G{ANSI.RESET} Gargoyle "
                  f"{ANSI.FG_MUTED}#{ANSI.RESET} Half-Cover "
                  f"{ANSI.DIM}.{ANSI.RESET} 5ft Tile ─┘{ANSI.RESET}")
        lines.append(legend)
        return lines

    @staticmethod
    def render_panel(title: str, content_lines: list[str], width: int = 60, color: str = ANSI.CYAN) -> str:
        border_top = f"{color}┌─ {ANSI.BOLD}{title}{ANSI.RESET}{color} {'─' * max(0, width - len(title) - 5)}┐{ANSI.RESET}"
        border_bot = f"{color}└{'─' * (width - 2)}┘{ANSI.RESET}"

        formatted = [border_top]
        for line in content_lines:
            # Strip simple ANSI for length calculation
            clean_len = len(line.replace(ANSI.BOLD, "").replace(ANSI.RESET, "")
                            .replace(ANSI.DIM, "").replace(ANSI.FG_GOLD, "")
                            .replace(ANSI.FG_EMERALD, "").replace(ANSI.FG_CRIMSON, "")
                            .replace(ANSI.CYAN, "").replace(ANSI.YELLOW, ""))
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
        c.append(UIComponent(id="root", type=UIComponentType.SURFACE.value, props={"maxWidth": "960px", "padding": "24px"}))

        # Top Header Card with Tension Metric and Round info
        c.append(UIComponent(id="header-card", type=UIComponentType.CARD.value, parentId="root", props={"title": title, "badge": f"Round {round_num}"}))
        c.append(UIComponent(id="header-row", type=UIComponentType.ROW.value, parentId="header-card", props={"gap": "16px"}))
        c.append(UIComponent(id="metric-tension", type=UIComponentType.METRIC.value, parentId="header-row", props={
            "label": "Tension Index",
            "value": f"{int(tension_level * 100)}%",
            "trend": "CRITICAL" if tension_level > 0.7 else ("ELEVATED" if tension_level > 0.4 else "STABLE"),
            "variant": "danger" if tension_level > 0.7 else "warning"
        }))
        c.append(UIComponent(id="metric-stance", type=UIComponentType.METRIC.value, parentId="header-row", props={
            "label": "Enemy Stance",
            "value": enemy_stance,
            "variant": "accent"
        }))

        # Split Column Layout: Left Column = Tactical Grid & Log; Right Column = Combatants & Action Bar
        c.append(UIComponent(id="main-split", type=UIComponentType.ROW.value, parentId="root", props={"gap": "20px"}))
        c.append(UIComponent(id="left-col", type=UIComponentType.COLUMN.value, parentId="main-split", props={"flex": "3"}))
        c.append(UIComponent(id="right-col", type=UIComponentType.COLUMN.value, parentId="main-split", props={"flex": "2"}))

        # Tactical Map Component
        c.append(UIComponent(id="tactical-card", type=UIComponentType.CARD.value, parentId="left-col", props={"title": "Tactical Arena"}))
        c.append(UIComponent(id="tactical-grid", type=UIComponentType.TACTICAL_GRID.value, parentId="tactical-card", props={
            "gridWidth": 12,
            "gridHeight": 6,
            "heroPos": [2, 3],
            "enemyPos": [9, 3],
            "covers": [[5, 2], [5, 3], [6, 4]],
            "lighting": "Dim Light (Cavern)",
        }))

        # Narrative / Combat Feed Card
        c.append(UIComponent(id="feed-card", type=UIComponentType.CARD.value, parentId="left-col", props={"title": "Chronicle Feed"}))
        recent_log = combat_log[-4:]
        for idx, entry in enumerate(recent_log):
            c.append(UIComponent(id=f"log-entry-{idx}", type=UIComponentType.TEXT.value, parentId="feed-card", props={
                "content": entry,
                "variant": "caption" if idx < len(recent_log) - 1 else "body",
            }))

        # Right Column: Combatant Status Cards
        # Hero Status Card
        c.append(UIComponent(id="hero-card", type=UIComponentType.CARD.value, parentId="right-col", props={"title": f"Hero: {hero_name}"}))
        c.append(UIComponent(id="hero-hp-bar", type=UIComponentType.PROGRESS_BAR.value, parentId="hero-card", props={
            "label": "Hit Points",
            "current": hero_hp,
            "max": hero_max_hp,
            "unit": "HP",
        }))
        for cond in hero_conditions:
            c.append(UIComponent(id=f"cond-{cond}", type=UIComponentType.BADGE.value, parentId="hero-card", props={
                "label": cond,
                "variant": BadgeVariant.WARNING.value,
            }))

        # Action Economy Tracker Badges
        c.append(UIComponent(id="economy-row", type=UIComponentType.ROW.value, parentId="hero-card", props={"gap": "8px", "marginTop": "10px"}))
        for act_name, available in hero_actions_available.items():
            c.append(UIComponent(id=f"eco-{act_name}", type=UIComponentType.BADGE.value, parentId="economy-row", props={
                "label": act_name,
                "variant": BadgeVariant.SUCCESS.value if available else BadgeVariant.NEUTRAL.value,
            }))

        # Enemy Status Card
        c.append(UIComponent(id="enemy-card", type=UIComponentType.CARD.value, parentId="right-col", props={"title": f"Adversary: {enemy_name}"}))
        c.append(UIComponent(id="enemy-hp-bar", type=UIComponentType.PROGRESS_BAR.value, parentId="enemy-card", props={
            "label": "Threat Integrity",
            "current": enemy_hp,
            "max": enemy_max_hp,
            "unit": "HP",
        }))

        # Declarative Interactive Action Tray (Zero-Eval Intent Dispatch)
        c.append(UIComponent(id="action-card", type=UIComponentType.CARD.value, parentId="right-col", props={"title": "Action Matrix"}))
        c.append(UIComponent(id="btn-attack", type=UIComponentType.ACTION_BUTTON.value, parentId="action-card", props={
            "label": "⚔️ Attack (Action)",
            "intent": "HERO_ATTACK",
            "enabled": hero_actions_available.get("Action", True),
            "params": {"attackType": "Melee", "target": enemy_name},
        }))
        c.append(UIComponent(id="btn-dodge", type=UIComponentType.ACTION_BUTTON.value, parentId="action-card", props={
            "label": "🛡️ Dodge (Action)",
            "intent": "HERO_DODGE",
            "enabled": hero_actions_available.get("Action", True),
            "params": {},
        }))
        c.append(UIComponent(id="btn-spell", type=UIComponentType.ACTION_BUTTON.value, parentId="action-card", props={
            "label": "🔥 Cast Spell (Action)",
            "intent": "HERO_CAST_SPELL",
            "enabled": hero_actions_available.get("Action", True),
            "params": {"spell": "Guiding Bolt", "target": enemy_name},
        }))
        c.append(UIComponent(id="btn-rest", type=UIComponentType.ACTION_BUTTON.value, parentId="action-card", props={
            "label": "🏕️ Short Rest",
            "intent": "TAKE_REST",
            "enabled": True,
            "params": {"type": "Short"},
        }))

        return blueprint
