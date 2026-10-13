import random
from dataclasses import dataclass
from enum import Enum


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
    RADIANT = "Radiant"
    NECROTIC = "Necrotic"

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

def roll_dice(count: int, sides: int) -> int:
    return sum(random.randint(1, sides) for _ in range(count))

def roll_d20(modifier: int = 0, mode: AdvantageMode = AdvantageMode.NORMAL) -> RollResult:
    r1 = random.randint(1, 20)
    r2 = random.randint(1, 20)
    if mode == AdvantageMode.ADVANTAGE:
        selected = max(r1, r2)
    elif mode == AdvantageMode.DISADVANTAGE:
        selected = min(r1, r2)
    else:
        selected = r1

    return RollResult(
        d20_roll=selected,
        first_die=r1,
        second_die=r2,
        mode=mode,
        modifier=modifier
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
    advantage: AdvantageMode = AdvantageMode.NORMAL
) -> AttackResolution:
    roll = roll_d20(attack_modifier, advantage)
    is_hit = False
    is_critical = False
    damage = 0

    if roll.is_natural_1:
        is_hit = False
        is_critical = False
        msg = f"[FUMBLE] {attacker} rolled a Natural 1 and misses {target} completely!"
    elif roll.is_natural_20:
        is_hit = True
        is_critical = True
        # Crits double the damage dice count
        damage = roll_dice(damage_dice_count * 2, damage_die_sides) + damage_modifier
        damage = max(1, damage)
        msg = f"[CRITICAL HIT] {attacker} rolls a Natural 20 vs {target} (AC {target_ac}) for {damage} {damage_type.value} damage!"
    else:
        is_hit = (roll.total >= target_ac)
        if is_hit:
            damage = roll_dice(damage_dice_count, damage_die_sides) + damage_modifier
            damage = max(1, damage)
            msg = f"[HIT] {attacker} attacks {target}: Rolled {roll.d20_roll}+{attack_modifier}={roll.total} vs AC {target_ac} -> Deals {damage} {damage_type.value} damage."
        else:
            msg = f"[MISS] {attacker} attacks {target}: Rolled {roll.d20_roll}+{attack_modifier}={roll.total} vs AC {target_ac} -> Attack deflected."

    return AttackResolution(
        attacker=attacker,
        target=target,
        roll=roll,
        target_ac=target_ac,
        is_hit=is_hit,
        is_critical=is_critical,
        damage_dealt=damage if is_hit else 0,
        damage_type=damage_type,
        combat_message=msg
    )
