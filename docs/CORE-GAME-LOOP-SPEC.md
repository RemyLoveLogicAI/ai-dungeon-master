# Core Game Loop & State Spec

**Status:** grounded in shipped artifacts, not a proposal.
Anchors: encounter generation and combat loop implemented and verified locally;
Devin D20 engine (`combat_runner.py`, `d20_rules.py`, full CI test suite green);
external GPF / remote D&D Bible corpus integration pending (949 records, facet schemas in `FACETS.md`).

## The loop

```
EXPLORE → TRIGGER → RESOLVE → REWARD → EXPLORE
```

## Core stats (5)

Every combatant — PC or monster — runs on five numbers. The six abilities
(STR/DEX/CON/INT/WIS/CHA) sit underneath as the derivation layer; the Bible
requires each as score *and* modifier, never a bare number. But the loop itself
only needs:

1. **HP** — the single defeat clock. 0 HP = down. (Mercy rule per kether-fused:
   narrative intervention at 0 HP, not death.)
2. **AC** — armor class; the number an attack roll must meet or beat.
3. **Attack modifier** — the bonus added to the d20 (derived from STR/DEX +
   proficiency per the ability facets).
4. **Damage profile** — dice + modifier + type, e.g. `1d8+3 slashing`.
   Crits double the *dice*, not the modifier.
5. **Initiative / stance** — turn order plus the engine's stance-based enemy AI
   (aggressive / defensive), which decides target selection each round.

## Resolution check

```
d20 + attack_modifier  vs  target AC
```

- Advantage/disadvantage: roll twice, take the higher/lower.
- **Natural 1:** automatic miss, no math.
- **Natural 20:** automatic hit and critical — roll double damage dice.
- Otherwise: hit iff `roll + modifier >= AC`.
- Damage = `dice + modifier`, minimum 1; subtract from target HP.

This is `resolve_attack()` in the engine — implemented, tested, live. Not a design
proposal; the contract the game already runs on.

## Encounter flow (trigger → reward)

1. **Trigger** — an exploration event or DM beat fires an encounter seed.
   Monster(s) are pulled from the Bible corpus against a **CR/XP budget** —
   challenge rating is the single number the whole encounter economy prices in.
2. **Setup** — roll initiative; load each combatant's 5-stat block;
   assign stance per enemy AI.
3. **Turn loop** — each combatant: move → action (attack → `resolve_attack`)
   → bonus action. Every action's result is appended to the append-only
   game-event stream (`gpf/game-event.v1`).
4. **Resolution** — all enemies at 0 HP = victory; all PCs at 0 = defeat →
   mercy-rule narrative intervention.
5. **Reward** — XP per the Bible's CR→XP mapping; loot rolled against the
   magic-item facets; full state checkpointed.
6. **Return** — back to EXPLORE with updated state. The loop never ends;
   history only grows.

## State block

```json
{
  "name": "Goblin Ambusher",
  "hp": { "current": 7, "max": 7, "formula": "2d6" },
  "ac": 15,
  "ac_source": "leather armor, shield",
  "attack_modifier": 4,
  "damage": { "dice": 1, "sides": 6, "modifier": 2, "type": "piercing" },
  "abilities": {
    "str": { "score": 8, "mod": -1 },
    "dex": { "score": 14, "mod": 2 },
    "con": { "score": 10, "mod": 0 },
    "int": { "score": 10, "mod": 0 },
    "wis": { "score": 8, "mod": -1 },
    "cha": { "score": 8, "mod": -1 }
  },
  "cr": 0.25,
  "xp": 50,
  "stance": "aggressive",
  "initiative": 2
}
```

Every field above maps to a Bible facet (`armor_class`, `hit_points`,
`abilities`, `challenge_rating` + `xp`) or an engine parameter (`initiative` is
derived from DEX mod (+2) or rolled/assigned). A generator that emits a stat block
missing any of these is emitting a sketch, not a combatant.

## What's real vs. what's next

- **Real:** D20 resolution (tested), local encounter generation and 5-stat combatant contract.
- **Next:** wire local encounter generator to the authoritative remote Bible corpus archive keyed by CR
  budget; feed the event stream into the surface renderer per turn.
