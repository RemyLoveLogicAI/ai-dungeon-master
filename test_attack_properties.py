"""Property-based tests over attack resolution.

The example-based suite pins the specific cases the rules care about. These
properties instead assert the invariants the rules must hold for *every* attack:
min-1 damage, the AC threshold, the supremacy of naturals, monotonicity in AC and
in the attack modifier, and replay purity. Hypothesis supplies the inputs, so the
generator - not a hand-picked list - is what tries to break the claim.

Every property drives resolution through a ``ScriptedDiceSource``, so these tests
never touch the global ``random`` stream and cannot perturb the seeded tests
elsewhere in the suite.
"""

from dataclasses import replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from combat_events import is_replayable, record_attack, replay_attack
from d20_rules import (
    AdvantageMode,
    AttackRequest,
    CoverType,
    DamageType,
    ScriptedDiceSource,
    calculate_cover_bonus,
    resolve_attack_request,
)

PROPERTIES = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


@st.composite
def attacks(draw):
    """An arbitrary attack plus the exact dice it will consume.

    Two d20 results are always supplied because ``roll_d20`` consumes both dice
    regardless of advantage mode; damage dice are sized for a critical (twice the
    weapon's dice), the largest number any resolution can spend.
    """
    count = draw(st.integers(min_value=0, max_value=4))
    sides = draw(st.integers(min_value=2, max_value=12))
    request = AttackRequest(
        attacker="Hero",
        target="Orc",
        attack_modifier=draw(st.integers(min_value=-10, max_value=15)),
        target_ac=draw(st.integers(min_value=1, max_value=25)),
        damage_dice_count=count,
        damage_die_sides=sides,
        damage_modifier=draw(st.integers(min_value=-10, max_value=10)),
        damage_type=draw(st.sampled_from(list(DamageType))),
        advantage=draw(st.sampled_from(list(AdvantageMode))),
        cover=draw(st.sampled_from(list(CoverType))),
        is_incapacitated_or_unconscious=draw(st.booleans()),
    )
    d20 = draw(st.lists(st.integers(min_value=1, max_value=20), min_size=2, max_size=2))
    damage = draw(
        st.lists(
            st.integers(min_value=1, max_value=sides),
            min_size=2 * count,
            max_size=2 * count,
        )
    )
    return request, [*d20, *damage]


@st.composite
def weapon_damage(draw):
    """A weapon's dice pool plus a modifier, sized for a critical roll."""
    count = draw(st.integers(min_value=1, max_value=4))
    sides = draw(st.integers(min_value=2, max_value=12))
    return (
        count,
        sides,
        draw(st.integers(min_value=-10, max_value=10)),
        draw(
            st.lists(
                st.integers(min_value=1, max_value=sides),
                min_size=2 * count,
                max_size=2 * count,
            )
        ),
    )


def resolve(request: AttackRequest, rolls: list[int]):
    return resolve_attack_request(request, dice=ScriptedDiceSource(rolls))


@given(attacks())
@PROPERTIES
def test_damage_appears_only_on_a_hit_and_never_falls_below_one(case):
    request, rolls = case
    result = resolve(request, rolls)
    if result.is_hit:
        assert result.damage_dealt >= 1
    else:
        assert result.damage_dealt == 0


@given(attacks())
@PROPERTIES
def test_the_effective_ac_is_the_target_ac_plus_its_cover_bonus(case):
    request, rolls = case
    result = resolve(request, rolls)
    if request.cover is CoverType.TOTAL:
        assert result.target_ac == request.target_ac
    else:
        assert result.target_ac == request.target_ac + calculate_cover_bonus(request.cover)


@given(attacks())
@PROPERTIES
def test_total_cover_never_hits_and_consumes_no_dice(case):
    request, rolls = case
    request = replace(request, cover=CoverType.TOTAL)
    dice = ScriptedDiceSource(rolls)

    result = resolve_attack_request(request, dice=dice)

    assert not result.is_hit
    assert not result.is_critical
    assert result.damage_dealt == 0
    assert dice.remaining == len(rolls), "total cover must not roll anything"


@given(attacks())
@PROPERTIES
def test_a_natural_twenty_always_hits_and_crits_and_a_natural_one_always_misses(case):
    request, rolls = case
    if request.cover is CoverType.TOTAL:
        return  # cannot be targeted at all; the natural never applies
    result = resolve(request, rolls)
    if result.roll.is_natural_20:
        assert result.is_hit
        assert result.is_critical
    if result.roll.is_natural_1:
        assert not result.is_hit
        assert result.damage_dealt == 0


@given(attacks())
@PROPERTIES
def test_a_plain_hit_is_exactly_the_roll_total_meeting_the_effective_ac(case):
    request, rolls = case
    if request.cover is CoverType.TOTAL or request.is_incapacitated_or_unconscious:
        return
    result = resolve(request, rolls)
    if result.roll.is_natural_1 or result.roll.is_natural_20:
        return
    # Neither extreme applies, so the ordinary threshold rule decides, and a
    # plain hit is never a critical.
    assert result.is_hit == (result.roll.total >= result.target_ac)
    assert not result.is_critical


@given(attacks(), st.integers(min_value=1, max_value=10))
@PROPERTIES
def test_raising_the_target_ac_never_creates_a_hit(case, bump):
    request, rolls = case
    lower = resolve(request, rolls)
    higher = resolve(replace(request, target_ac=request.target_ac + bump), rolls)
    assert not (higher.is_hit and not lower.is_hit)


@given(attacks(), st.integers(min_value=1, max_value=10))
@PROPERTIES
def test_raising_the_attack_modifier_never_loses_a_hit(case, bump):
    request, rolls = case
    lower = resolve(request, rolls)
    higher = resolve(replace(request, attack_modifier=request.attack_modifier + bump), rolls)
    assert not (lower.is_hit and not higher.is_hit)


@given(attacks())
@PROPERTIES
def test_the_dice_order_is_normal_between_disadvantage_and_advantage(case):
    request, rolls = case
    if request.cover is CoverType.TOTAL:
        return
    normal = resolve(replace(request, advantage=AdvantageMode.NORMAL), rolls)
    advantage = resolve(replace(request, advantage=AdvantageMode.ADVANTAGE), rolls)
    disadvantage = resolve(replace(request, advantage=AdvantageMode.DISADVANTAGE), rolls)

    assert advantage.roll.d20_roll >= normal.roll.d20_roll >= disadvantage.roll.d20_roll
    assert advantage.roll.total >= normal.roll.total >= disadvantage.roll.total


@given(weapon_damage())
@PROPERTIES
def test_a_critical_deals_at_least_what_an_ordinary_hit_would(case):
    count, sides, modifier, damage = case
    base = {
        "attacker": "Hero",
        "target": "Orc",
        "attack_modifier": 50,
        "target_ac": 1,
        "damage_dice_count": count,
        "damage_die_sides": sides,
        "damage_modifier": modifier,
        "damage_type": DamageType.SLASHING,
    }
    # 10 + 50 clears AC 1 without a natural 20; 20 is a critical on the same dice.
    ordinary = resolve_attack_request(
        AttackRequest(**base), dice=ScriptedDiceSource([10, 10, *damage])
    )
    critical = resolve_attack_request(
        AttackRequest(**base), dice=ScriptedDiceSource([20, 20, *damage])
    )

    assert ordinary.is_hit and not ordinary.is_critical
    assert critical.is_hit and critical.is_critical
    assert critical.damage_dealt >= ordinary.damage_dealt


@given(attacks())
@PROPERTIES
def test_a_resolution_is_a_pure_function_of_its_request_and_rolls(case):
    request, rolls = case
    assert resolve(request, rolls) == resolve(request, rolls)


@given(attacks())
@PROPERTIES
def test_every_recorded_attack_replays_to_an_identical_resolution(case):
    request, rolls = case
    event, result = record_attack(request, sequence=1, dice=ScriptedDiceSource(rolls))

    assert is_replayable(event, result)
    assert replay_attack(event) == result
    # The record stores what was spent, never the generator behind it.
    assert len(event.rolls) <= len(rolls)
