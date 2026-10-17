import unittest

from encounter_generator import (
    CreatureCandidate,
    Difficulty,
    calculate_adjusted_xp,
    classify_difficulty,
    generate_encounter,
    get_encounter_multiplier,
    get_party_xp_thresholds,
)


class TestEncounterGenerator(unittest.TestCase):
    def setUp(self):
        self.party = [3, 3, 3, 3]
        self.candidates = [
            CreatureCandidate("Goblin", 50, "1/4", {"biome": ["forest"], "tags": {"role": "scout"}}),
            CreatureCandidate("Orc", 100, "1/2", {"biome": ["hills"], "tags": ["brute"]}),
            CreatureCandidate("Hobgoblin", 200, "1/2", {"faction": "red", "gear": ["spear"]}),
        ]

    def test_same_seed_and_inputs_produce_identical_encounter(self):
        first = generate_encounter(self.party, self.candidates, Difficulty.HARD, seed=42)
        second = generate_encounter(self.party, self.candidates, Difficulty.HARD, seed=42)
        self.assertEqual(first, second)

    def test_facets_are_preserved_exactly(self):
        encounter = generate_encounter(self.party, self.candidates, seed=42)
        by_name = {m["name"]: m for m in encounter["monsters"]}
        for candidate in self.candidates:
            if candidate.name in by_name:
                self.assertEqual(by_name[candidate.name]["facets"], dict(candidate.facets))
        self.assertEqual(encounter["version"], "gpf/encounter.v1")

    def test_threshold_and_difficulty_boundaries(self):
        thresholds = get_party_xp_thresholds(self.party)
        self.assertEqual(thresholds, {"easy": 300, "medium": 600, "hard": 900, "deadly": 1600})
        self.assertEqual(classify_difficulty(0, thresholds), "trivial")
        self.assertEqual(classify_difficulty(299, thresholds), "trivial")
        self.assertEqual(classify_difficulty(300, thresholds), "easy")
        self.assertEqual(classify_difficulty(599, thresholds), "easy")
        self.assertEqual(classify_difficulty(600, thresholds), "medium")
        self.assertEqual(classify_difficulty(899, thresholds), "medium")
        self.assertEqual(classify_difficulty(900, thresholds), "hard")
        self.assertEqual(classify_difficulty(1599, thresholds), "hard")
        self.assertEqual(classify_difficulty(1600, thresholds), "deadly")

    def test_encounter_xp_uses_monster_count_and_party_adjustment(self):
        self.assertEqual(get_encounter_multiplier(1, 4), 1.0)
        self.assertEqual(get_encounter_multiplier(2, 4), 1.5)
        self.assertEqual(get_encounter_multiplier(3, 4), 2.0)
        self.assertEqual(get_encounter_multiplier(3, 2), 2.5)
        self.assertEqual(get_encounter_multiplier(3, 6), 1.5)
        one = [CreatureCandidate("Goblin", 50)]
        two = [CreatureCandidate("Goblin", 50), CreatureCandidate("Goblin", 50)]
        self.assertEqual(calculate_adjusted_xp(one, 4), (50, 50))
        self.assertEqual(calculate_adjusted_xp(two, 4), (100, 150))

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            get_party_xp_thresholds([])
        with self.assertRaises(ValueError):
            get_party_xp_thresholds([21])
        with self.assertRaises(ValueError):
            generate_encounter([], self.candidates)
        with self.assertRaises(ValueError):
            generate_encounter(self.party, [], seed=1)
        with self.assertRaises(ValueError):
            generate_encounter(self.party, self.candidates, "impossible")
        with self.assertRaises(ValueError):
            generate_encounter(self.party, self.candidates, max_monsters=0)
        with self.assertRaises(ValueError):
            generate_encounter(self.party, self.candidates, max_creature_types=0)
        with self.assertRaises(ValueError):
            CreatureCandidate("", 1)
        with self.assertRaises(ValueError):
            CreatureCandidate("Goblin", -1)


    def test_max_types_cannot_exceed_encounter_size(self):
        encounter = generate_encounter(
            self.party,
            self.candidates,
            max_monsters=1,
            max_creature_types=3,
            seed=1,
        )
        self.assertEqual(encounter["metadata"]["total_monsters"], 1)

    def test_party_size_adjusted_budget_keeps_feasible_creature(self):
        party = [1] * 6
        candidates = [CreatureCandidate("Goblin", 25), CreatureCandidate("Troll", 300)]
        encounter = generate_encounter(
            party,
            candidates,
            Difficulty.EASY,
            max_monsters=1,
            seed=1,
        )
        self.assertEqual(encounter["achieved_difficulty"], Difficulty.EASY.value)
        self.assertEqual(encounter["monsters"][0]["name"], "Troll")

    def test_100_seed_medium_difficulty_acceptance(self):
        # A sufficient, explicitly supplied candidate set exercises the stated
        # aggregate criterion without claiming support for unspecified Bible data.
        candidates = [CreatureCandidate("Goblin", xp) for xp in (25, 50, 75, 100, 200)]
        matched = sum(
            generate_encounter(self.party, candidates, Difficulty.MEDIUM, seed=seed)[
                "achieved_difficulty"
            ]
            == Difficulty.MEDIUM.value
            for seed in range(100)
        )
        self.assertGreaterEqual(matched, 90)


if __name__ == "__main__":
    unittest.main()
