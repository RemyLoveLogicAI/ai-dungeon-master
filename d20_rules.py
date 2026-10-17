import random
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class AdvantageMode(Enum):
    NORMAL = "Normal"
    ADVANTAGE = "Advantage"
    DISADVANTAGE = "Disadvantage"


class DamageType(Enum):
    SLASHING = "Slashing"
    PIERCING = "Piercing"
    BLUDGEONING = "Bludgeoning"
    FIRE = "Fire"
    COLD = "Cold"
    LIGHTNING = "Lightning"
    THUNDER = "Thunder"
    POISON = "Poison"
    ACID = "Acid"
    PSYCHIC = "Psychic"
    RADIANT = "Radiant"
    NECROTIC = "Necrotic"
    FORCE = "Force"


class AbilityScore(Enum):
    STRENGTH = "Strength"
    DEXTERITY = "Dexterity"
    CONSTITUTION = "Constitution"
    INTELLIGENCE = "Intelligence"
    WISDOM = "Wisdom"
    CHARISMA = "Charisma"


class Condition(Enum):
    BLINDED = "Blinded"
    CHARMED = "Charmed"
    DEAFENED = "Deafened"
    EXHAUSTION = "Exhaustion"
    FRIGHTENED = "Frightened"
    GRAPPLED = "Grappled"
    INCAPACITATED = "Incapacitated"
    INVISIBLE = "Invisible"
    PARALYZED = "Paralyzed"
    PETRIFIED = "Petrified"
    POISONED = "Poisoned"
    PRONE = "Prone"
    RESTRAINED = "Restrained"
    STUNNED = "Stunned"
    UNCONSCIOUS = "Unconscious"


class CoverType(Enum):
    NONE = "None"
    HALF = "Half"  # +2 AC and Dex saving throws
    THREE_QUARTERS = "Three-Quarters"  # +5 AC and Dex saving throws
    TOTAL = "Total"  # Cannot be targeted directly


class LightingLevel(Enum):
    BRIGHT = "Bright Light"
    DIM = "Dim Light"  # Lightly obscured, disadvantage on Perception
    DARKNESS = "Darkness"  # Heavily obscured, effectively blinded without darkvision


class RestType(Enum):
    SHORT = "Short Rest"  # 1 hour: spend Hit Dice to recover HP
    LONG = "Long Rest"  # 8 hours: recover all HP, half hit dice, reset spell slots


@dataclass
class RollResult:
    d20_roll: int
    first_die: int
    second_die: int
    mode: AdvantageMode
    modifier: int

    @property
    def total(self) -> int:
        return self.d20_roll + self.modifier

    @property
    def is_natural_20(self) -> bool:
        return self.d20_roll == 20

    @property
    def is_natural_1(self) -> bool:
        return self.d20_roll == 1


@dataclass
class SavingThrowResult:
    ability: AbilityScore
    roll: RollResult
    dc: int
    is_success: bool
    message: str


@dataclass
class AttackResolution:
    attacker: str
    target: str
    roll: RollResult
    target_ac: int
    is_hit: bool
    is_critical: bool
    damage_dealt: int
    damage_type: DamageType
    combat_message: str
    applied_conditions: list[Condition] = field(default_factory=list)


@dataclass(frozen=True)
class AttackRequest:
    """The complete, self-contained input to a single attack resolution.

    Every stochastic input lives in the dice source, not here, so a request plus
    a recorded roll sequence is enough to reproduce a resolution exactly.
    """

    attacker: str
    target: str
    attack_modifier: int
    target_ac: int
    damage_dice_count: int
    damage_die_sides: int
    damage_modifier: int
    damage_type: DamageType
    advantage: AdvantageMode = AdvantageMode.NORMAL
    cover: CoverType = CoverType.NONE
    is_incapacitated_or_unconscious: bool = False


@dataclass
class ActionEconomy:
    """Tracks action resource expenditure per turn under 5e action economy."""

    has_action: bool = True
    has_bonus_action: bool = True
    has_reaction: bool = True
    movement_speed: float = 30.0
    movement_remaining: float = 30.0

    def reset_turn(self, speed: float | None = None):
        self.has_action = True
        self.has_bonus_action = True
        self.has_reaction = True
        if speed is not None:
            self.movement_speed = speed
        self.movement_remaining = self.movement_speed

    def use_action(self) -> bool:
        if not self.has_action:
            return False
        self.has_action = False
        return True

    def use_bonus_action(self) -> bool:
        if not self.has_bonus_action:
            return False
        self.has_bonus_action = False
        return True

    def use_reaction(self) -> bool:
        if not self.has_reaction:
            return False
        self.has_reaction = False
        return True

    def move(self, distance: float, is_difficult_terrain: bool = False) -> bool:
        cost = distance * (2.0 if is_difficult_terrain else 1.0)
        if self.movement_remaining >= cost:
            self.movement_remaining -= cost
            return True
        return False


@dataclass
class RestRecovery:
    rest_type: RestType
    hp_recovered: int
    hit_dice_spent: int
    hit_dice_recovered: int
    spell_slots_restored: int
    exhaustion_reduced: int
    summary: str


class DiceSource(Protocol):
    """A supply of individual die results.

    A source is pure with respect to game state: the only observable effect of
    ``roll`` is its return value, so any resolution is reproducible whenever the
    same sequence of results is supplied again.
    """

    def roll(self, sides: int) -> int:
        """Return one result in the inclusive range ``1..sides``."""
        ...


class ModuleRandomDiceSource(DiceSource):
    """Default source. Draws from the ``random`` module's shared generator."""

    def roll(self, sides: int) -> int:
        return random.randint(1, sides)


class SeededDiceSource(DiceSource):
    """A private generator whose stream depends only on ``seed``.

    Unlike ``random.seed``, constructing this never disturbs global random
    state, so two runs with the same seed produce identical results regardless
    of what else the process rolls in between.
    """

    def __init__(self, seed: int | None = None):
        self._random = random.Random(seed)

    def roll(self, sides: int) -> int:
        return self._random.randint(1, sides)


class ScriptedDiceSource(DiceSource):
    """Replays a fixed sequence of die results, for deterministic replay."""

    def __init__(self, rolls: Iterable[int]):
        self._rolls = tuple(int(value) for value in rolls)
        self._index = 0

    @property
    def remaining(self) -> int:
        return len(self._rolls) - self._index

    def roll(self, sides: int) -> int:
        if self._index >= len(self._rolls):
            raise RuntimeError("scripted dice source is exhausted")
        value = self._rolls[self._index]
        self._index += 1
        if not 1 <= value <= sides:
            raise ValueError(f"scripted result {value} is not a valid d{sides} roll")
        return value


class RecordingDiceSource(DiceSource):
    """Wraps another source and records every result, in order."""

    def __init__(self, source: DiceSource | None = None):
        self._source: DiceSource = (
            source if source is not None else ModuleRandomDiceSource()
        )
        self._rolls: list[int] = []

    @property
    def rolls(self) -> tuple[int, ...]:
        return tuple(self._rolls)

    def roll(self, sides: int) -> int:
        value = self._source.roll(sides)
        self._rolls.append(value)
        return value


_DEFAULT_DICE_SOURCE: DiceSource = ModuleRandomDiceSource()


def _resolve_dice(dice: DiceSource | None) -> DiceSource:
    return dice if dice is not None else _DEFAULT_DICE_SOURCE


def roll_dice(count: int, sides: int, dice: DiceSource | None = None) -> int:
    if count < 0:
        raise ValueError("count must be non-negative")
    if sides <= 0:
        raise ValueError("sides must be positive")
    source = _resolve_dice(dice)
    return sum(source.roll(sides) for _ in range(count))


def roll_d20(
    modifier: int = 0,
    mode: AdvantageMode = AdvantageMode.NORMAL,
    dice: DiceSource | None = None,
) -> RollResult:
    source = _resolve_dice(dice)
    r1 = source.roll(20)
    r2 = source.roll(20)
    if mode == AdvantageMode.ADVANTAGE:
        selected = max(r1, r2)
    elif mode == AdvantageMode.DISADVANTAGE:
        selected = min(r1, r2)
    else:
        selected = r1

    return RollResult(
        d20_roll=selected, first_die=r1, second_die=r2, mode=mode, modifier=modifier
    )


def compute_effective_advantage(
    base_mode: AdvantageMode,
    attacker_conditions: set[Condition] | None = None,
    target_conditions: set[Condition] | None = None,
    distance_ft: float = 5.0,
    is_melee: bool = True,
) -> AdvantageMode:
    """Calculates final AdvantageMode following D&D 5e rule: any advantage + any disadvantage = Normal."""
    has_adv = base_mode == AdvantageMode.ADVANTAGE
    has_dis = base_mode == AdvantageMode.DISADVANTAGE

    att = attacker_conditions or set()
    tgt = target_conditions or set()

    # Attacker conditions
    if (
        Condition.BLINDED in att
        or Condition.POISONED in att
        or Condition.FRIGHTENED in att
        or Condition.RESTRAINED in att
    ):
        has_dis = True
    if Condition.INVISIBLE in att:
        has_adv = True

    # Target conditions
    if (
        Condition.BLINDED in tgt
        or Condition.PARALYZED in tgt
        or Condition.PETRIFIED in tgt
        or Condition.STUNNED in tgt
        or Condition.UNCONSCIOUS in tgt
        or Condition.RESTRAINED in tgt
    ):
        has_adv = True
    if Condition.INVISIBLE in tgt:
        has_dis = True

    if Condition.PRONE in tgt:
        if distance_ft <= 5.0:
            has_adv = True
        else:
            has_dis = True

    if has_adv and has_dis:
        return AdvantageMode.NORMAL
    if has_adv:
        return AdvantageMode.ADVANTAGE
    if has_dis:
        return AdvantageMode.DISADVANTAGE
    return AdvantageMode.NORMAL


def calculate_cover_bonus(cover: CoverType) -> int:
    if cover == CoverType.HALF:
        return 2
    elif cover == CoverType.THREE_QUARTERS:
        return 5
    return 0


def resolve_saving_throw(
    character_name: str,
    ability: AbilityScore,
    modifier: int,
    dc: int,
    mode: AdvantageMode = AdvantageMode.NORMAL,
    dice: DiceSource | None = None,
) -> SavingThrowResult:
    roll = roll_d20(modifier=modifier, mode=mode, dice=dice)
    is_success = roll.total >= dc
    status_str = "SUCCESS" if is_success else "FAILURE"
    msg = (
        f"[{status_str}] {character_name} {ability.value} Saving Throw: "
        f"rolled {roll.d20_roll}+{modifier}={roll.total} vs DC {dc}."
    )
    return SavingThrowResult(
        ability=ability, roll=roll, dc=dc, is_success=is_success, message=msg
    )


def resolve_rest(
    character_name: str,
    rest_type: RestType,
    current_hp: int,
    max_hp: int,
    hit_dice_available: int,
    total_hit_dice: int,
    hit_die_sides: int,
    con_modifier: int,
    current_spell_slots: int,
    max_spell_slots: int,
    exhaustion_level: int = 0,
    dice: DiceSource | None = None,
) -> RestRecovery:
    # Fail closed at the boundary, the same way the combat-log readers do: a
    # wrong type raises TypeError, a wrong value raises ValueError. An
    # unvalidated max_hp silently produced a negative heal (current_hp above
    # max_hp) or a divide-by-nothing recovery summary, so the caller never
    # learned the rest was computed from impossible state.
    for field_name, value in (("max_hp", max_hp), ("current_hp", current_hp)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{field_name} must be an integer")
    if max_hp <= 0:
        raise ValueError("max_hp must be positive")
    if current_hp < 0 or current_hp > max_hp:
        raise ValueError("current_hp must be between 0 and max_hp")
    if rest_type == RestType.SHORT:
        # Spend 1 Hit Die if available
        if hit_dice_available > 0 and current_hp < max_hp:
            heal_amount = max(1, roll_dice(1, hit_die_sides, dice=dice) + con_modifier)
            new_hp = min(max_hp, current_hp + heal_amount)
            recovered = new_hp - current_hp
            summary = f"{character_name} took a Short Rest, spent 1d{hit_die_sides} Hit Die, and recovered {recovered} HP ({new_hp}/{max_hp})."
            return RestRecovery(
                rest_type=RestType.SHORT,
                hp_recovered=recovered,
                hit_dice_spent=1,
                hit_dice_recovered=0,
                spell_slots_restored=0,
                exhaustion_reduced=0,
                summary=summary,
            )
        else:
            return RestRecovery(
                rest_type=RestType.SHORT,
                hp_recovered=0,
                hit_dice_spent=0,
                hit_dice_recovered=0,
                spell_slots_restored=0,
                exhaustion_reduced=0,
                summary=f"{character_name} rested briefly, catching breath with no Hit Dice spent.",
            )
    else:  # LONG REST
        recovered_hp = max_hp - current_hp
        recovered_hd = max(1, total_hit_dice // 2)
        restored_slots = max_spell_slots - current_spell_slots
        reduced_exhaustion = 1 if exhaustion_level > 0 else 0
        summary = (
            f"{character_name} completed an 8-hour Long Rest: recovered {recovered_hp} HP (full), "
            f"{restored_slots} spell slots, {recovered_hd} Hit Dice, and reduced exhaustion by {reduced_exhaustion}."
        )
        return RestRecovery(
            rest_type=RestType.LONG,
            hp_recovered=recovered_hp,
            hit_dice_spent=0,
            hit_dice_recovered=recovered_hd,
            spell_slots_restored=restored_slots,
            exhaustion_reduced=reduced_exhaustion,
            summary=summary,
        )


def resolve_attack(
    attacker: str,
    target: str,
    attack_modifier: int,
    target_ac: int,
    damage_dice_count: int,
    damage_die_sides: int,
    damage_modifier: int,
    damage_type: DamageType,
    advantage: AdvantageMode = AdvantageMode.NORMAL,
    cover: CoverType = CoverType.NONE,
    is_incapacitated_or_unconscious: bool = False,
    dice: DiceSource | None = None,
) -> AttackResolution:
    """Resolve one attack.

    Pass ``dice`` with a seeded, scripted, or recording source to make the
    resolution reproducible; the default draws from the shared ``random``
    generator, matching the historical behavior.
    """
    return resolve_attack_request(
        AttackRequest(
            attacker=attacker,
            target=target,
            attack_modifier=attack_modifier,
            target_ac=target_ac,
            damage_dice_count=damage_dice_count,
            damage_die_sides=damage_die_sides,
            damage_modifier=damage_modifier,
            damage_type=damage_type,
            advantage=advantage,
            cover=cover,
            is_incapacitated_or_unconscious=is_incapacitated_or_unconscious,
        ),
        dice=dice,
    )


def resolve_attack_request(
    request: AttackRequest, dice: DiceSource | None = None
) -> AttackResolution:
    """Resolve a fully specified ``AttackRequest`` against ``dice``."""
    if request.damage_dice_count < 0:
        raise ValueError("damage dice count must be nonnegative")
    if request.damage_die_sides <= 0:
        raise ValueError("damage die sides must be positive")
    attacker = request.attacker
    target = request.target
    damage_type = request.damage_type

    if request.cover == CoverType.TOTAL:
        return AttackResolution(
            attacker=attacker,
            target=target,
            roll=RollResult(0, 0, 0, request.advantage, 0),
            target_ac=request.target_ac,
            is_hit=False,
            is_critical=False,
            damage_dealt=0,
            damage_type=damage_type,
            combat_message=f"[TOTAL COVER] {attacker} cannot target {target} through total cover!",
        )

    effective_ac = request.target_ac + calculate_cover_bonus(request.cover)
    roll = roll_d20(request.attack_modifier, request.advantage, dice=dice)
    is_hit = False
    is_critical = False
    damage = 0

    attack_modifier = request.attack_modifier
    damage_die_sides = request.damage_die_sides
    damage_dice_count = request.damage_dice_count
    damage_modifier = request.damage_modifier

    if roll.is_natural_1:
        is_hit = False
        is_critical = False
        msg = f"[FUMBLE] {attacker} rolled a Natural 1 and misses {target} completely!"
    elif roll.is_natural_20:
        is_hit = True
        is_critical = True
        damage = (
            roll_dice(damage_dice_count * 2, damage_die_sides, dice=dice)
            + damage_modifier
        )
        damage = max(1, damage)
        msg = f"[CRITICAL HIT] {attacker} rolls a Natural 20 vs {target} (AC {effective_ac}) for {damage} {damage_type.value} damage!"
    else:
        is_hit = roll.total >= effective_ac
        if is_hit:
            # If target is incapacitated/paralyzed/unconscious within melee range, hit becomes an automatic crit
            if request.is_incapacitated_or_unconscious:
                is_critical = True
                damage = (
                    roll_dice(damage_dice_count * 2, damage_die_sides, dice=dice)
                    + damage_modifier
                )
                damage = max(1, damage)
                msg = f"[CRITICAL HIT - VULNERABLE] {attacker} strikes helpless {target} (AC {effective_ac}) for {damage} {damage_type.value} damage!"
            else:
                damage = (
                    roll_dice(damage_dice_count, damage_die_sides, dice=dice)
                    + damage_modifier
                )
                damage = max(1, damage)
                msg = f"[HIT] {attacker} attacks {target}: Rolled {roll.d20_roll}+{attack_modifier}={roll.total} vs AC {effective_ac} -> Deals {damage} {damage_type.value} damage."
        else:
            msg = f"[MISS] {attacker} attacks {target}: Rolled {roll.d20_roll}+{attack_modifier}={roll.total} vs AC {effective_ac} -> Attack deflected."

    return AttackResolution(
        attacker=attacker,
        target=target,
        roll=roll,
        target_ac=effective_ac,
        is_hit=is_hit,
        is_critical=is_critical,
        damage_dealt=damage if is_hit else 0,
        damage_type=damage_type,
        combat_message=msg,
    )
