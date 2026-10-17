# Encounter Generator v0.1 Implementation Specification

**Version:** 0.1  
**Target Module:** `encounter_generator.py`  
**Test Suite:** `test_encounter_generator.py`  
**Schema Identifier:** `gpf/encounter.v1` (Local Contract Envelope)  
**Status:** Implemented locally; unverified against external GPF/D&D Bible schemas  

---

## 1. Executive Summary & Status Boundary

This specification defines the contract, algorithm, data shapes, and operational boundaries of the deterministic D&D 5e encounter generator implemented in `encounter_generator.py`.

### 1.1 Local Scope vs. External Conformance Boundary
- **Implemented Local Contract:** The generator provides seeded, reproducible encounter generation conforming to standard D&D 5th Edition encounter math (Dungeon Master's Guide p. 82).
- **`gpf/encounter.v1` Status:** The output format identifies itself as `gpf/encounter.v1`. In the current repository, this is an **internal, minimal version label and dictionary payload**. Formal external conformance against an authoritative GPF (Generative Platform Foundation) schema is **unverified** because no formal external GPF JSON schema or validator is present in this worktree.
- **D&D Bible & SRD Data Decoupling:** The generator is completely decoupled from any hardcoded creature database or specific SRD release. It accepts an arbitrary sequence of `CreatureCandidate` records. Caller-supplied `facets` (e.g. lore, biome, sensory cues, statblock references) are passed through verbatim. Full integration with external candidate datasets (such as the reported 949-record SRD 5.1 Bible or facet catalogs) remains planned and unverified. The official SRD 5.1 release is an unstructured CC BY 4.0 PDF and does not itself verify that corpus or facet schema; no local corpus or loader exists. See the [evidence record](dnd-bible-facet-review-pack-2026-10-15.md) for official sources and the unverified-report distinction.

---

## 2. Core Domain Models & Signatures

### 2.1 Python Signatures

```python
from typing import Sequence, Mapping, Any
from enum import Enum
from dataclasses import dataclass, field

class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    DEADLY = "deadly"

@dataclass(frozen=True)
class CreatureCandidate:
    name: str
    xp: int
    cr: str | float | int = ""
    facets: Mapping[str, Any] = field(default_factory=dict)

def generate_encounter(
    party: Sequence[int],
    candidates: Sequence[CreatureCandidate],
    target_difficulty: str | Difficulty = Difficulty.MEDIUM,
    seed: int | None = None,
    max_monsters: int = 8,
    max_creature_types: int = 3,
) -> dict[str, Any]:
    ...
```

### 2.2 Input Parameters
| Parameter | Type | Required | Default | Validation & Semantics |
|---|---|---|---|---|
| `party` | `Sequence[int]` | Yes | — | Non-empty. The threshold helper requires levels in 1–20; `generate_encounter` checks integer type before calling it. |
| `candidates` | `Sequence[CreatureCandidate]` | Yes | — | Non-empty pool. Candidate construction rejects blank names and negative XP. |
| `target_difficulty` | `str \| Difficulty` | No | `Difficulty.MEDIUM` | Accepts easy/medium/hard/deadly; strings are lowercased before validation. |
| `seed` | `int \| None` | No | `None` | Passed to a private `random.Random(seed)`; a supplied seed reproduces output for the same inputs/runtime. |
| `max_monsters` | `int` | No | `8` | Must be >= 1. |
| `max_creature_types` | `int` | No | `3` | Must be >= 1. |

`CreatureCandidate` is frozen. `name` must be nonempty/nonblank; `xp` must be nonnegative. `cr` and `facets` are caller-provided metadata; no CR interpretation or facet vocabulary is imposed.

## 3. Mathematical Rules & Selection Algorithm

### 3.1 Party XP Threshold Calculation
The generator calculates combined party XP thresholds by summing the per-character XP thresholds from DMG p. 82:

$$\text{Threshold}_{\text{difficulty}}(\text{party}) = \sum_{c \in \text{party}} \text{XP\_THRESHOLDS}[c][\text{difficulty}]$$

#### XP Threshold Table (Levels 1–20)
- **Level 1:** Easy: 25, Medium: 50, Hard: 75, Deadly: 100
- **Level 2:** Easy: 50, Medium: 100, Hard: 150, Deadly: 200
- **Level 3:** Easy: 75, Medium: 150, Hard: 225, Deadly: 400
- **Level 4:** Easy: 125, Medium: 250, Hard: 375, Deadly: 500
- **Level 5:** Easy: 250, Medium: 500, Hard: 750, Deadly: 1,100
- **Level 6:** Easy: 300, Medium: 600, Hard: 900, Deadly: 1,400
- **Level 7:** Easy: 350, Medium: 750, Hard: 1,100, Deadly: 1,700
- **Level 8:** Easy: 450, Medium: 900, Hard: 1,400, Deadly: 2,100
- **Level 9:** Easy: 550, Medium: 1,100, Hard: 1,600, Deadly: 2,400
- **Level 10:** Easy: 600, Medium: 1,200, Hard: 1,900, Deadly: 2,800
- **Level 11:** Easy: 800, Medium: 1,600, Hard: 2,400, Deadly: 3,600
- **Level 12:** Easy: 1,000, Medium: 2,000, Hard: 3,000, Deadly: 4,500
- **Level 13:** Easy: 1,100, Medium: 2,200, Hard: 3,400, Deadly: 5,100
- **Level 14:** Easy: 1,250, Medium: 2,500, Hard: 3,800, Deadly: 5,700
- **Level 15:** Easy: 1,400, Medium: 2,800, Hard: 4,300, Deadly: 6,400
- **Level 16:** Easy: 1,600, Medium: 3,200, Hard: 4,800, Deadly: 7,200
- **Level 17:** Easy: 2,000, Medium: 3,900, Hard: 5,900, Deadly: 8,800
- **Level 18:** Easy: 2,100, Medium: 4,200, Hard: 6,300, Deadly: 9,500
- **Level 19:** Easy: 2,400, Medium: 4,900, Hard: 7,300, Deadly: 10,900
- **Level 20:** Easy: 2,800, Medium: 5,700, Hard: 8,500, Deadly: 12,700

### 3.2 Monster Count Multipliers & Party Size Shifts
Standard 5e encounter multipliers adjust raw creature XP based on action economy:

| Monster Count | Base Multiplier | Multiplier Index |
|---|---|---|
| 1 monster | 1.0× | 0 |
| 2 monsters | 1.5× | 1 |
| 3–6 monsters | 2.0× | 2 |
| 7–10 monsters | 2.5× | 3 |
| 11–14 monsters | 3.0× | 4 |
| 15+ monsters | 4.0× | 5 |

#### Party Size Shifts
- If party size `< 3`: The multiplier steps up one tier (index $\min(5, \text{idx} + 1)$).
- If party size `> 5`: The multiplier steps down one tier (index $\max(0, \text{idx} - 1)$).
- If party size is 3 to 5: Base multiplier index is used without shift.

$$\text{Raw XP} = \sum_{m \in \text{Encounter}} m.\text{xp}$$

$$\text{Adjusted XP} = \lfloor \text{Raw XP} \times \text{Multiplier}(\text{count}, |\text{party}|) \rfloor$$

### 3.3 Difficulty Classification
Given party thresholds:
- $\text{Adjusted XP} < \text{Threshold}_{\text{easy}} \implies \text{"trivial"}$
- $\text{Threshold}_{\text{easy}} \le \text{Adjusted XP} < \text{Threshold}_{\text{medium}} \implies \text{"easy"}$
- $\text{Threshold}_{\text{medium}} \le \text{Adjusted XP} < \text{Threshold}_{\text{hard}} \implies \text{"medium"}$
- $\text{Threshold}_{\text{hard}} \le \text{Adjusted XP} < \text{Threshold}_{\text{deadly}} \implies \text{"hard"}$
- $\text{Adjusted XP} \ge \text{Threshold}_{\text{deadly}} \implies \text{"deadly"}$

### 3.4 Deterministic Sampling & Selection Algorithm
1. **Isolated RNG:** Initializes `rng = random.Random(seed)`. Does not pollute or read global `random` state.
2. **Target Window Definition:**
   - Easy: $[\text{easy}, \text{medium} - 1]$
   - Medium: $[\text{medium}, \text{hard} - 1]$
   - Hard: $[\text{hard}, \text{deadly} - 1]$
   - Deadly: $[\text{deadly}, \lfloor 1.6 \times \text{deadly} \rfloor]$
3. **Candidate Pruning:** Candidates whose single-creature adjusted XP exceeds `max_xp` are pruned. If all candidates exceed `max_xp`, the single candidate with lowest adjusted XP is retained as the sole viable candidate.
4. **Deterministic Sorting:** Valid candidates are sorted deterministically by `(c.xp, c.name)` before sampling to eliminate nondeterministic set/dictionary iteration order.
5. **Monte-Carlo Search (60 Trials):**
   - Chooses random creature type count: $k \in [1, \min(\text{max\_creature\_types}, |\text{candidates}|, \text{max\_monsters})]$.
   - Samples $k$ creature types using `rng.sample()`.
   - Seeds encounter with 1 creature of each chosen type.
   - Greedily attempts to add creatures from the chosen types until reaching target difficulty or max monster budget.
   - Rejects additions that would exceed `max_xp`.
   - Terminates early if an encounter exactly hits `target_difficulty`. Otherwise tracks candidate encounter minimizing distance to target midpoint.
6. **Fallback:** If no candidate encounter is constructed, falls back to a single creature whose XP is closest to `min_xp`.

---

## 4. Output Contract (`gpf/encounter.v1`)

The output is a Python dictionary structured into clear semantic sections:

```json
{
  "version": "gpf/encounter.v1",
  "party": {
    "size": 4,
    "levels": [3, 3, 3, 3],
    "thresholds": {
      "easy": 300,
      "medium": 600,
      "hard": 900,
      "deadly": 1600
    }
  },
  "target_difficulty": "medium",
  "achieved_difficulty": "medium",
  "budget": {
    "raw_xp": 400,
    "adjusted_xp": 600,
    "multiplier": 1.5
  },
  "monsters": [
    {
      "name": "Goblin",
      "count": 1,
      "xp_per_unit": 50,
      "cr": "1/4",
      "facets": {
        "role": "skirmisher",
        "environment": "dungeon",
        "sensory_cues": ["cackling", "rusting daggers"]
      }
    }
  ],
  "metadata": {
    "seed": 42,
    "total_monsters": 2
  }
}
```

### 4.1 Field Definitions & Facet Preservation
- `version` (`str`): Set to `"gpf/encounter.v1"`.
- `party.thresholds` (`dict[str, int]`): Party XP thresholds for all 4 difficulty levels.
- `target_difficulty` (`str`): Requested difficulty string.
- `achieved_difficulty` (`str`): Actual evaluated difficulty based on `budget.adjusted_xp`.
- `budget.raw_xp` (`int`): Sum of creature base XP.
- `budget.adjusted_xp` (`int`): Action-economy adjusted XP.
- `budget.multiplier` (`float`): Multiplier applied to raw XP.
- `monsters` (`list[dict]`): List of monster entries.
  - `facets`: `dict(creature.facets)`. Passed through verbatim from input `CreatureCandidate`. Any caller-specified metadata (statblocks, sensory descriptions, tactical tags, AI stances) is preserved without mutation or data loss.
- `metadata.seed` (`int | None`): RNG seed used.
- `metadata.total_monsters` (`int`): Total count of monsters in the encounter.

---

## 5. Error Boundaries & Validation

| Condition | Error Type | Error Message Pattern |
|---|---|---|
| Empty party list | `ValueError` | `"party cannot be empty"` or `"Party must contain at least one character"` |
| Non-integer party level | `TypeError` | `"party levels must be integers"` |
| Party level < 1 | `ValueError` | `"Character level must be >= 1, got <lvl>"` |
| Empty candidates list | `ValueError` | `"candidates cannot be empty"` |
| Candidate name empty/blank | `ValueError` | `"CreatureCandidate must have a non-empty name"` |
| Candidate XP < 0 | `ValueError` | `"CreatureCandidate xp must be non-negative, got <xp>"` |
| Candidate XP non-int | `TypeError` | `"candidate xp must be integers"` |
| Target difficulty unknown | `ValueError` | `"Invalid target difficulty '<target>'. Must be one of easy, medium, hard, deadly."` |
| `max_monsters` < 1 | `ValueError` | `"max_monsters must be >= 1"` |
| `max_creature_types` < 1 | `ValueError` | `"max_creature_types must be >= 1"` |

---

## 6. Current Test Criteria & Verification

Existing verification in `test_encounter_generator.py` validates the following invariant criteria:

1. **Seed Determinism:** Calling `generate_encounter` twice with identical parameters and seed yields identical outputs (`test_same_seed_and_inputs_produce_identical_encounter`).
2. **Facet Preservation:** Caller facets on candidates (`role`, `environment`, tags) are present in `encounter["monsters"][i]["facets"]` without alteration (`test_facets_are_preserved_exactly`).
3. **Threshold Boundaries:** Correct classification of adjusted XP into trivial, easy, medium, hard, deadly (`test_threshold_and_difficulty_boundaries`).
4. **Multiplier Steps & Party Adjustment:** Verification of 1-monster, 2-monster, and party size scaling rules (`test_encounter_xp_uses_monster_count_and_party_adjustment`).
5. **Strict Input Validation:** Asserting proper `ValueError` and `TypeError` handling (`test_input_validation`).
6. **Bounds Safety:** Total creature types generated never exceeds `max_monsters` or `max_creature_types` (`test_max_types_cannot_exceed_encounter_size`).
7. **Small/Large Party Feasibility:** A large party size shifts multipliers down, allowing feasible monsters to remain eligible (`test_party_size_adjusted_budget_keeps_feasible_creature`).
8. **100-Seed Acceptance Benchmark:** Over 100 consecutive seeds with a balanced candidate pool, achieved difficulty matches requested medium difficulty at least 90% of the time (`test_100_seed_medium_difficulty_acceptance`).

---

## 7. Future Integration & Schema Roadmap

```
+-------------------------------------------------------------+
|                     Current v0.1 Scope                      |
|  - encounter_generator.py (deterministic seeded math)       |
|  - Output envelope labeled 'gpf/encounter.v1'               |
|  - Pass-through facet preservation                          |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                 Planned Next Integration Phase              |
|  1. Authoritative Schema Conformance:                       |
|     - Validate output envelope against official GPF JSON    |
|       schema once published.                                |
|  2. SRD 5.1 Bible Ingestion:                                |
|     - Ingest the reported 949-record SRD 5.1 corpus (not verified or |
|       present locally) and filter by source-provided facets.         |
|  3. Downstream Consumers:                                   |
|     - Feed generated monsters directly to combat_runner.py  |
|       and encounter_ai.py (EncounterEnemy).                 |
|     - Surface encounter summary via genui.py blueprints.    |
+-------------------------------------------------------------+
```

### 7.1 Gap Analysis (Current vs. Upstream Target)
1. **Schema Validation:** Current `combat_schema.py` validates `combat-encounter-log-1.schema.json`. It does not yet include an `encounter-v1.schema.json`. Once GPF releases the official JSON schema, schema validation should be added to `combat_schema.py`.
2. **Dynamic Biome / Tag Filtering:** A filter layer should wrap `candidates` prior to passing them into `generate_encounter` (e.g. `filter_by_facet(candidates, environment="swamp")`).
3. **Combat Runner Bridge:** Adapter function converting `encounter_payload["monsters"]` into `combat_runner` actor instances / `EncounterEnemy` states.

---

## 8. Concrete Acceptance Criteria & Next Action

### 8.1 Acceptance Criteria
- [x] Document defines inputs, determinism, math rules, multipliers, output shape, and error boundaries matching actual `encounter_generator.py` code.
- [x] Clear demarcation that `gpf/encounter.v1` is an unverified local contract pending external GPF schema availability.
- [x] Preserves caller facets explicitly without inventing external D&D Bible schemas.
- [x] Conforms to existing unit test assertions in `test_encounter_generator.py`.

### 8.2 Immediate Next Action
Create or import the official `gpf/encounter.v1` JSON Schema into `schemas/` and wire schema validation into `test_encounter_generator.py` once upstream schema artifacts are available.
