from dataclasses import dataclass
from enum import Enum

from d20_rules import DamageType


class AIStance(Enum):
    AGGRESSIVE = "Aggressive"
    TACTICAL = "Tactical"
    DEFENSIVE = "Defensive"
    FLEEING = "Fleeing"

class CombatActionType(Enum):
    MELEE = "Melee Attack"
    RANGED = "Ranged Attack"
    SPELL = "Cast Spell"
    DODGE = "Defensive Dodge"
    FLEE = "Flee"

@dataclass
class AICombatDecision:
    action: CombatActionType
    action_name: str
    attack_modifier: int = 0
    damage_dice_count: int = 0
    damage_die_sides: int = 0
    damage_modifier: int = 0
    damage_type: DamageType = DamageType.SLASHING
    rationale: str = ""

class EncounterEnemy:
    def __init__(self, name: str = "Shadow Gargoyle", max_hp: int = 40, ac: int = 14, spell_slots: int = 2):
        self.name = name
        self.max_hp = max(0, int(max_hp))
        self.current_hp = self.max_hp
        self.ac = max(0, int(ac))
        self.spell_slots = max(0, int(spell_slots))
        self.stance = AIStance.AGGRESSIVE
        self.update_stance()

    def apply_damage(self, amount: int):
        amount = max(amount, 0)
        self.current_hp = max(0, self.current_hp - amount)
        self.update_stance()

    def update_stance(self):
        if self.max_hp <= 0:
            self.stance = AIStance.FLEEING
            return

        hp_pct = self.current_hp / self.max_hp
        if hp_pct <= 0.20:
            self.stance = AIStance.FLEEING
        elif hp_pct <= 0.45:
            self.stance = AIStance.DEFENSIVE
        elif self.spell_slots > 0:
            self.stance = AIStance.TACTICAL
        else:
            self.stance = AIStance.AGGRESSIVE

    def decide_turn_action(self, distance_to_player: float) -> AICombatDecision:
        distance_to_player = max(0.0, float(distance_to_player))
        self.update_stance()

        if self.stance == AIStance.FLEEING:
            return AICombatDecision(
                action=CombatActionType.FLEE,
                action_name="Disengage & Retreat",
                rationale=f"{self.name} is near death ({self.current_hp}/{self.max_hp} HP) and disengages to escape!"
            )
        elif self.stance == AIStance.DEFENSIVE:
            if distance_to_player < 2.0:
                return AICombatDecision(
                    action=CombatActionType.DODGE,
                    action_name="Defensive Guard",
                    rationale=f"{self.name} assumes a defensive guard, parrying incoming strikes."
                )
            else:
                return AICombatDecision(
                    action=CombatActionType.RANGED,
                    action_name="Stone Hurled",
                    attack_modifier=4,
                    damage_dice_count=1,
                    damage_die_sides=6,
                    damage_modifier=2,
                    damage_type=DamageType.BLUDGEONING,
                    rationale=f"{self.name} keeps defensive distance and hurls a fragment of stone."
                )
        elif self.stance == AIStance.TACTICAL:
            if self.spell_slots > 0 and distance_to_player >= 3.0:
                self.spell_slots -= 1
                return AICombatDecision(
                    action=CombatActionType.SPELL,
                    action_name="Shadow Flame",
                    attack_modifier=6,
                    damage_dice_count=3,
                    damage_die_sides=6,
                    damage_modifier=3,
                    damage_type=DamageType.FIRE,
                    rationale=f"{self.name} unleashes a blast of dark pyromancy."
                )
            else:
                return AICombatDecision(
                    action=CombatActionType.MELEE,
                    action_name="Rending Talons",
                    attack_modifier=5,
                    damage_dice_count=2,
                    damage_die_sides=6,
                    damage_modifier=3,
                    damage_type=DamageType.SLASHING,
                    rationale=f"{self.name} strikes with razor talons."
                )
        else: # AGGRESSIVE
            return AICombatDecision(
                action=CombatActionType.MELEE,
                action_name="Rending Talons",
                attack_modifier=5,
                damage_dice_count=2,
                damage_die_sides=6,
                damage_modifier=3,
                damage_type=DamageType.SLASHING,
                rationale=f"{self.name} ferociously lunges in close quarters."
            )
