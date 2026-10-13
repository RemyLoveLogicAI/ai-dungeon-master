"""Pins the resume screen's copy, word for word.

``RESUME_NOTES`` is the only thing that tells a player what a reloaded save
cannot restore, and the resume tests compare ``state.notes`` against that same
constant, so rewording it would pass every existing test while silently changing
what the player reads. The literals below are therefore deliberate duplicates of
it: they are the contract. If the copy is meant to change, it changes here too,
in the same commit, rather than drifting.

The last test drives the real resume path instead of the constant, so the notes
becoming unhooked from the screen is a failure as well.
"""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tui_runner
from combat_log import CombatLog, record_entry, save_log
from d20_rules import AttackRequest, DamageType, ScriptedDiceSource
from tui_runner import (
    ENEMY_AC,
    ENEMY_NAME,
    HERO_ATTACK_MODIFIER,
    HERO_NAME,
    RESUME_NOTES,
    ResumedEncounter,
)

#: What the resume screen prints in front of every note.
RENDER_PREFIX = "rebuilt, not stored: "

#: A hit for 11 (d20 15 + 6 against AC 14), so a one-entry log leaves the enemy
#: standing and the encounter resumable whatever the next roll is.
HERO_ROLLS = (15, 3, 8)

EXPECTED_NOTES = (
    "spell slots are counted back from the recorded attacks, not stored",
    "enemy narrative lines are not in the envelope, so the feed is rebuilt from messages",
    "the hero's conditions and action economy reset each round and are not stored",
)


def hero_request() -> AttackRequest:
    return AttackRequest(
        attacker=HERO_NAME,
        target=ENEMY_NAME,
        attack_modifier=HERO_ATTACK_MODIFIER,
        target_ac=ENEMY_AC,
        damage_dice_count=1,
        damage_die_sides=8,
        damage_modifier=3,
        damage_type=DamageType.SLASHING,
    )


class ResumeNoteCopyTest(unittest.TestCase):
    def test_the_notes_are_word_for_word_the_pinned_copy(self):
        self.assertEqual(RESUME_NOTES, EXPECTED_NOTES)

    def test_a_resumed_encounter_carries_the_pinned_copy_by_default(self):
        state = ResumedEncounter(
            round_num=3, hero_hp=11, enemy_hp=5, distance=1.0, spell_slots=1, feed=()
        )
        self.assertEqual(state.notes, EXPECTED_NOTES)

    def test_the_resume_screen_prints_every_pinned_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "encounter.json"
            entry = record_entry(
                hero_request(), sequence=1, dice=ScriptedDiceSource(HERO_ROLLS)
            )[0]
            save_log(CombatLog(entries=(entry,), dropped=0), path)
            printed = self._resume_screen(path)

        for note in EXPECTED_NOTES:
            self.assertIn(f"{RENDER_PREFIX}{note}", printed)

    def _resume_screen(self, path: Path) -> str:
        """Run the real ``--resume`` path and return everything it printed."""
        output = io.StringIO()
        with (
            tempfile.TemporaryDirectory() as audio,
            # Keep the synthesised SFX out of the user's cache directory.
            mock.patch.dict(os.environ, {"AI_DM_AUDIO_DIR": audio}),
            contextlib.redirect_stdout(output),
        ):
            tui_runner.main(["--log", str(path), "--resume", "--rounds", "1"])
        return output.getvalue()
