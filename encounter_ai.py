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
    """What the enemy intends to do this turn.

    The decision carries the *cost* of the action rather than applying it: a
    spell decision reports ``spell_slots_spent=1`` and leaves the enemy's slots
    untouched, so the caller commits the cost only once the turn is really taken.
    """

    action: CombatActionType
    action_name: str
    attack_modifier: int = 0
    damage_dice_count: int = 0
    damage_die_sides: int = 0
    damage_modifier: int = 0
    damage_type: DamageType = DamageType.SLASHING
    rationale: str = ""
    spell_slots_spent: int = 0

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

    def compute_stance(self) -> AIStance:
        """Return the stance this enemy's current state implies, without storing it.

        Keeping this separate lets a query answer "what should this enemy do?"
        without writing ``self.stance``.
        """
        if self.max_hp <= 0:
            return AIStance.FLEEING

        hp_pct = self.current_hp / self.max_hp
        if hp_pct <= 0.20:
            return AIStance.FLEEING
        if hp_pct <= 0.45:
            return AIStance.DEFENSIVE
        if self.spell_slots > 0:
            return AIStance.TACTICAL
        return AIStance.AGGRESSIVE

    def update_stance(self):
        self.stance = self.compute_stance()

    def commit_decision(self, decision: AICombatDecision) -> None:
        """Apply a decision's resource cost to this enemy.

        ``decide_turn_action`` is a query: it reports what a turn would spend and
        lets the caller commit it here. Previewing a turn - or deciding twice -
        therefore cannot change the game.
        """
        spent = max(0, int(decision.spell_slots_spent))
        if spent:
            self.spell_slots = max(0, self.spell_slots - spent)
            self.update_stance()

    def decide_turn_action(self, distance_to_player: float) -> AICombatDecision:
        """Choose this turn's action from current state, changing nothing.

        The stance is computed rather than stored, and a spell's slot cost is
        reported on the decision rather than deducted, so calling this repeatedly
        returns the same answer until the caller commits a turn via
        :meth:`commit_decision`.
        """
        distance_to_player = max(0.0, float(distance_to_player))
        stance = self.compute_stance()

        if stance == AIStance.FLEEING:
            return AICombatDecision(
                action=CombatActionType.FLEE,
                action_name="Disengage & Retreat",
                rationale=f"{self.name} is near death ({self.current_hp}/{self.max_hp} HP) and disengages to escape!"
            )
        elif stance == AIStance.DEFENSIVE:
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
        elif stance == AIStance.TACTICAL:
            if self.spell_slots > 0 and distance_to_player >= 3.0:
                return AICombatDecision(
                    action=CombatActionType.SPELL,
                    action_name="Shadow Flame",
                    attack_modifier=6,
                    damage_dice_count=3,
                    damage_die_sides=6,
                    damage_modifier=3,
                    damage_type=DamageType.FIRE,
                    rationale=f"{self.name} unleashes a blast of dark pyromancy.",
                    spell_slots_spent=1,
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
