"""Executable local test surface for the strict generated-encounter bridge."""

import json
import random
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

import combat_runner
from combat_log import load_log, verify_log


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard", "deadly"])
def test_demo_runs_each_difficulty_with_explicit_stats(difficulty):
    result = combat_runner.run_generated_demo(difficulty=difficulty, seed=7)
    assert result["data_source"] == "explicit-local-demo"
    assert result["encounter"]["target_difficulty"] == difficulty
    assert result["encounter"]["party"]["levels"] == [3, 3]
    assert result["outcome"] in {"victory", "mercy_rule", "stalemate"}
    assert result["game_events"]
    assert verify_log(result["log"])
    assert all(enemy["hp"]["max"] in {7, 11, 24} for enemy in result["enemies"])


def test_demo_seed_reproduces_full_combat_without_global_random_changes():
    state = random.getstate()
    first = combat_runner.run_generated_demo(seed=7)
    second = combat_runner.run_generated_demo(seed=7)
    assert first == second
    assert random.getstate() == state


def test_no_argument_script_preserves_existing_simulation():
    with mock.patch.object(combat_runner, "run_simulated_encounter") as legacy:
        assert combat_runner.main([]) is None
    legacy.assert_called_once_with()


def test_terminal_demo_explains_scope_and_reports_combat(capsys):
    assert combat_runner.main(["generated", "--difficulty", "easy", "--seed", "7"]) is None
    text = capsys.readouterr().out
    assert "AUTO-PLAY LOCAL DEMO" in text
    assert "Difficulty: easy" in text
    assert "Seed: 7" in text
    assert "Outcome:" in text
    assert "HP" in text
    assert "not the remote Bible" in text


def test_json_demo_and_saved_log_replay(tmp_path, capsys):
    path = tmp_path / "encounter.json"
    combat_runner.main(["generated", "--json", "--seed", "7", "--log", str(path)])
    payload = json.loads(capsys.readouterr().out)
    assert payload["data_source"] == "explicit-local-demo"
    assert payload["log"]["schema"] == "combat-encounter-log/1"
    assert load_log(path).to_dict() == payload["log"]
    assert verify_log(load_log(path))


@pytest.mark.parametrize("argv", [
    ["generated", "--difficulty", "impossible"],
    ["generated", "--rounds", "0"],
    ["generated", "--seed", "not-an-integer"],
])
def test_bad_cli_inputs_fail_clearly(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        combat_runner.main(argv)
    assert exc.value.code == 2
    assert "error:" in capsys.readouterr().err


def test_log_save_failure_is_a_clear_cli_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        combat_runner.main(["generated", "--log", str(tmp_path)])
    assert exc.value.code == 2
    assert "error:" in capsys.readouterr().err


def test_real_script_launch_returns_valid_json():
    completed = subprocess.run(
        [sys.executable, str(Path(combat_runner.__file__)), "generated",
         "--difficulty", "medium", "--seed", "7", "--json"],
        check=True, capture_output=True, text=True, timeout=15,
    )
    result = json.loads(completed.stdout)
    assert result["data_source"] == "explicit-local-demo"
    assert result["encounter"]["metadata"]["seed"] == 7
    assert result["game_events"]
