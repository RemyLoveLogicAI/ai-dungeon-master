"""Deterministic, seeded D&D 5e encounter generator complying with gpf/encounter.v1.

Calculates standard D&D 5e party XP thresholds (Easy, Medium, Hard, Deadly),
evaluates candidate creature groups against encounter multipliers, and outputs
a versioned encounter payload preserving all caller-provided creature facets.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# D&D 5e standard encounter difficulty thresholds per character level (DMG p. 82)
XP_THRESHOLDS_PER_LEVEL: dict[int, dict[str, int]] = {
    1: {"easy": 25, "medium": 50, "hard": 75, "deadly": 100},
    2: {"easy": 50, "medium": 100, "hard": 150, "deadly": 200},
    3: {"easy": 75, "medium": 150, "hard": 225, "deadly": 400},
    4: {"easy": 125, "medium": 250, "hard": 375, "deadly": 500},
    5: {"easy": 250, "medium": 500, "hard": 750, "deadly": 1100},
    6: {"easy": 300, "medium": 600, "hard": 900, "deadly": 1400},
    7: {"easy": 350, "medium": 750, "hard": 1100, "deadly": 1700},
    8: {"easy": 450, "medium": 900, "hard": 1400, "deadly": 2100},
    9: {"easy": 550, "medium": 1100, "hard": 1600, "deadly": 2400},
    10: {"easy": 600, "medium": 1200, "hard": 1900, "deadly": 2800},
    11: {"easy": 800, "medium": 1600, "hard": 2400, "deadly": 3600},
    12: {"easy": 1000, "medium": 2000, "hard": 3000, "deadly": 4500},
    13: {"easy": 1100, "medium": 2200, "hard": 3400, "deadly": 5100},
    14: {"easy": 1250, "medium": 2500, "hard": 3800, "deadly": 5700},
    15: {"easy": 1400, "medium": 2800, "hard": 4300, "deadly": 6400},
    16: {"easy": 1600, "medium": 3200, "hard": 4800, "deadly": 7200},
    17: {"easy": 2000, "medium": 3900, "hard": 5900, "deadly": 8800},
    18: {"easy": 2100, "medium": 4200, "hard": 6300, "deadly": 9500},
    19: {"easy": 2400, "medium": 4900, "hard": 7300, "deadly": 10900},
    20: {"easy": 2800, "medium": 5700, "hard": 8500, "deadly": 12700},
}

ENCOUNTER_SCHEMA_VERSION = "gpf/encounter.v1"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    DEADLY = "deadly"


@dataclass(frozen=True)
class CreatureCandidate:
    """Caller-provided creature template with combat values and custom facets.

    No D&D Bible schema is hardcoded here: `facets` carries arbitrary user metadata
    (lore, environment, tags, statblock, sensory cues) which is preserved verbatim
    in the generated encounter output.
    """

    name: str
    xp: int
    cr: str | float | int = ""
    facets: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("CreatureCandidate must have a non-empty name")
        if self.xp < 0:
            raise ValueError(f"CreatureCandidate xp must be non-negative, got {self.xp}")


def get_party_xp_thresholds(party_levels: Sequence[int]) -> dict[str, int]:
    """Calculate combined XP thresholds for a party given each member's level."""
    if not party_levels:
        raise ValueError("Party must contain at least one character")
    totals = {"easy": 0, "medium": 0, "hard": 0, "deadly": 0}
    for lvl in party_levels:
        if lvl < 1 or lvl > 20:
            raise ValueError(f"Character level must be between 1 and 20, got {lvl}")
        thresholds = XP_THRESHOLDS_PER_LEVEL[lvl]
        for diff in totals:
            totals[diff] += thresholds[diff]
    return totals


def get_encounter_multiplier(monster_count: int, party_size: int) -> float:
    """Return standard D&D 5e encounter multiplier based on monster count and party size."""
    if monster_count <= 0:
        return 1.0

    if monster_count == 1:
        base = 1.0
    elif monster_count == 2:
        base = 1.5
    elif 3 <= monster_count <= 6:
        base = 2.0
    elif 7 <= monster_count <= 10:
        base = 2.5
    elif 11 <= monster_count <= 14:
        base = 3.0
    else:
        base = 4.0

    # Adjust multiplier if party is fewer than 3 or 6 or more members (DMG p. 83)
    multiplier_steps = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    idx = multiplier_steps.index(base)
    if party_size < 3:
        # Step up
        idx = min(len(multiplier_steps) - 1, idx + 1)
    elif party_size >= 6:
        # Step down
        idx = max(0, idx - 1)
    return multiplier_steps[idx]
def calculate_adjusted_xp(creatures: Sequence[CreatureCandidate], party_size: int) -> tuple[int, int]:
    """Calculate (raw_xp, adjusted_xp) for a list of creatures."""
    raw_xp = sum(c.xp for c in creatures)
    multiplier = get_encounter_multiplier(len(creatures), party_size)
    adjusted_xp = int(raw_xp * multiplier)
    return raw_xp, adjusted_xp


def classify_difficulty(adjusted_xp: int, thresholds: Mapping[str, int]) -> str:
    """Classify adjusted XP into 'trivial', 'easy', 'medium', 'hard', or 'deadly'."""
    if adjusted_xp >= thresholds["deadly"]:
        return "deadly"
    if adjusted_xp >= thresholds["hard"]:
        return "hard"
    if adjusted_xp >= thresholds["medium"]:
        return "medium"
    if adjusted_xp >= thresholds["easy"]:
        return "easy"
    return "trivial"


def generate_encounter(
    party: Sequence[int],
    candidates: Sequence[CreatureCandidate],
    target_difficulty: str | Difficulty = Difficulty.MEDIUM,
    seed: int | None = None,
    max_monsters: int = 8,
    max_creature_types: int = 3,
) -> dict[str, Any]:
    """Generate a deterministic D&D 5e encounter meeting target difficulty.

    Args:
        party: Sequence of character levels, e.g. [3, 3, 3, 3]
        candidates: Sequence of CreatureCandidate available for selection
        target_difficulty: Desired difficulty ('easy', 'medium', 'hard', 'deadly')
        seed: Optional RNG seed for deterministic reproduction
        max_monsters: Maximum total monster count in the encounter
        max_creature_types: Maximum distinct creature varieties

    Returns:
        A dictionary compliant with the 'gpf/encounter.v1' contract preserving all
        caller-provided facets.
    """
    if isinstance(target_difficulty, Difficulty):
        target_diff_str = target_difficulty.value
    else:
        target_diff_str = str(target_difficulty).lower()

    if target_diff_str not in {"easy", "medium", "hard", "deadly"}:
        raise ValueError(
            f"Invalid target difficulty '{target_difficulty}'. Must be one of easy, medium, hard, deadly."
        )

    if not party:
        raise ValueError("party cannot be empty")
    if not candidates:
        raise ValueError("candidates cannot be empty")
    if max_monsters < 1:
        raise ValueError("max_monsters must be >= 1")
    if max_creature_types < 1:
        raise ValueError("max_creature_types must be >= 1")
    if any(not isinstance(level, int) for level in party):
        raise TypeError("party levels must be integers")
    if any(not isinstance(c.xp, int) for c in candidates):
        raise TypeError("candidate xp must be integers")

    # Local deterministic RNG instance (does not mutate global random state)
    rng = random.Random(seed)

    thresholds = get_party_xp_thresholds(party)
    party_size = len(party)

    # Determine acceptable XP range for the target difficulty
    if target_diff_str == "easy":
        min_xp = thresholds["easy"]
        max_xp = thresholds["medium"] - 1
    elif target_diff_str == "medium":
        min_xp = thresholds["medium"]
        max_xp = thresholds["hard"] - 1
    elif target_diff_str == "hard":
        min_xp = thresholds["hard"]
        max_xp = thresholds["deadly"] - 1
    else:  # deadly
        min_xp = thresholds["deadly"]
        max_xp = int(thresholds["deadly"] * 1.6)

    # Filter candidates using their one-monster adjusted XP, not raw XP.
    valid_candidates = [
        c for c in candidates if calculate_adjusted_xp([c], party_size)[1] <= max_xp
    ]
    if not valid_candidates:
        valid_candidates = [min(candidates, key=lambda c: calculate_adjusted_xp([c], party_size)[1])]

    # Attempt search to build an encounter matching target difficulty
    best_encounter: list[CreatureCandidate] = []
    best_diff_dist = float("inf")

    # Order candidates deterministically for reproducibility before shuffling
    sorted_candidates = sorted(valid_candidates, key=lambda c: (c.xp, c.name))

    # Monte-Carlo / greedy sampling over trials
    trials = 60
    for _ in range(trials):
        # Never seed more creature types than the encounter can contain.
        num_types = rng.randint(1, min(max_creature_types, len(sorted_candidates), max_monsters))
        chosen_types = rng.sample(sorted_candidates, num_types)

        # Seed each chosen type with at least 1 creature
        current_creatures: list[CreatureCandidate] = list(chosen_types)

        # Iteratively add creatures while under budget and under max_monsters
        for _ in range(max_monsters - len(current_creatures)):
            _, adj_xp = calculate_adjusted_xp(current_creatures, party_size)
            if adj_xp >= min_xp and classify_difficulty(adj_xp, thresholds) == target_diff_str:
                break
            pick = rng.choice(chosen_types)
            test_creatures = current_creatures + [pick]
            _, test_adj = calculate_adjusted_xp(test_creatures, party_size)
            if test_adj > max_xp:
                # Adding would blow past target upper bound
                continue
            current_creatures.append(pick)

        _, adj_xp = calculate_adjusted_xp(current_creatures, party_size)
        diff = classify_difficulty(adj_xp, thresholds)
        if diff == target_diff_str:
            best_encounter = current_creatures
            break
        target_mid = (min_xp + max_xp) / 2.0
        dist = abs(adj_xp - target_mid)
        if dist < best_diff_dist:
            best_diff_dist = dist
            best_encounter = current_creatures

    # If no encounter constructed, fallback to single candidate closest to min_xp
    if not best_encounter:
        best_encounter = [min(sorted_candidates, key=lambda c: abs(c.xp - min_xp))]

    raw_xp, adjusted_xp = calculate_adjusted_xp(best_encounter, party_size)
    achieved_difficulty = classify_difficulty(adjusted_xp, thresholds)

    monsters_output: list[dict[str, Any]] = []
    for creature in best_encounter:
        monsters_output.append(
            {
                "name": creature.name,
                "count": 1,
                "xp_per_unit": creature.xp,
                "cr": creature.cr,
                "facets": dict(creature.facets),
            }
        )

    # Construct the gpf/encounter.v1 envelope
    encounter_payload: dict[str, Any] = {
        "version": ENCOUNTER_SCHEMA_VERSION,
        "party": {
            "size": party_size,
            "levels": list(party),
            "thresholds": thresholds,
        },
        "target_difficulty": target_diff_str,
        "achieved_difficulty": achieved_difficulty,
        "budget": {
            "raw_xp": raw_xp,
            "adjusted_xp": adjusted_xp,
            "multiplier": get_encounter_multiplier(len(best_encounter), party_size),
        },
        "monsters": monsters_output,
        "metadata": {
            "seed": seed,
            "total_monsters": len(best_encounter),
        },
    }

    return encounter_payload
