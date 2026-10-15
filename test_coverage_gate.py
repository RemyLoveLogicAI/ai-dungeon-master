import json
import os
from pathlib import Path

from coverage_gate import FLOORS, find_stale_modules, find_violations, main, read_percentages


def _report(tmp_path, percentages):
    path = tmp_path / "coverage.json"
    path.write_text(
        json.dumps(
            {
                "files": {
                    name: {"summary": {"percent_covered": value}}
                    for name, value in percentages.items()
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def test_read_percentages_extracts_each_module(tmp_path):
    report = _report(tmp_path, {"a.py": 88.5, "b.py": 100.0})
    assert read_percentages(report) == {"a.py": 88.5, "b.py": 100.0}


def test_no_violations_when_every_module_meets_its_floor():
    assert find_violations({"a.py": 90.0}, {"a.py": 90.0}) == []


def test_a_module_below_its_floor_is_reported_with_both_numbers():
    problems = find_violations({"a.py": 50.0}, {"a.py": 90.0})
    assert len(problems) == 1
    assert "a.py" in problems[0]
    assert "50.0%" in problems[0]
    assert "90.0%" in problems[0]


def test_a_floor_for_an_absent_module_is_reported():
    """A floor that no longer matches anything means the gate stopped guarding."""
    problems = find_violations({"a.py": 100.0}, {"a.py": 90.0, "renamed.py": 90.0})
    assert len(problems) == 1
    assert "renamed.py" in problems[0]


def test_a_measured_module_without_a_floor_is_reported():
    problems = find_violations({"a.py": 100.0, "new.py": 10.0}, {"a.py": 90.0})
    assert len(problems) == 1
    assert "new.py" in problems[0]
    assert "no floor" in problems[0]


def test_every_violation_is_reported_not_only_the_first():
    problems = find_violations(
        {"a.py": 10.0, "b.py": 20.0, "c.py": 100.0},
        {"a.py": 90.0, "b.py": 90.0, "renamed.py": 90.0},
    )
    # a below floor, b below floor, renamed absent, c unfloored
    assert len(problems) == 4


def test_main_passes_when_the_real_floors_are_all_met(tmp_path, capsys):
    report = _report(tmp_path, dict.fromkeys(FLOORS, 100.0))
    assert main([str(report)]) == 0
    assert f"all {len(FLOORS)} module floors met" in capsys.readouterr().out


def test_main_fails_and_lists_every_offending_module(tmp_path, capsys):
    report = _report(tmp_path, dict.fromkeys(FLOORS, 0.0))
    assert main([str(report)]) == 1
    stderr = capsys.readouterr().err
    assert "failed" in stderr
    for module in FLOORS:
        assert module in stderr


def test_main_fails_closed_when_the_report_is_missing(tmp_path, capsys):
    assert main([str(tmp_path / "coverage.json")]) == 1
    assert "is missing" in capsys.readouterr().err


def test_every_configured_floor_names_a_module_that_exists():
    for module in FLOORS:
        assert Path(module).is_file(), f"{module} has a floor but no such module"


def _age_report_behind(module: Path, report: Path) -> None:
    """Make ``report`` older than ``module``, as a stale run would leave it."""
    older = module.stat().st_mtime - 10
    os.utime(report, (older, older))


def test_a_report_older_than_its_source_is_stale(tmp_path):
    module = tmp_path / "a.py"
    module.write_text("x = 1\n", encoding="utf-8")
    report = _report(tmp_path, {"a.py": 100.0})
    _age_report_behind(module, report)
    assert find_stale_modules({"a.py": 100.0}, report) == ["a.py"]


def test_a_report_newer_than_its_sources_is_not_stale(tmp_path):
    module = tmp_path / "a.py"
    module.write_text("x = 1\n", encoding="utf-8")
    report = _report(tmp_path, {"a.py": 100.0})
    assert find_stale_modules({"a.py": 100.0}, report) == []


def test_a_module_absent_from_disk_is_not_treated_as_stale(tmp_path):
    # Deleted modules are find_violations' business, not staleness'.
    report = _report(tmp_path, {"gone.py": 100.0})
    assert find_stale_modules({"gone.py": 100.0}, report) == []


def test_a_missing_report_has_no_stale_modules(tmp_path):
    # The missing-report case is main()'s to report; staleness stays silent.
    assert find_stale_modules({"a.py": 100.0}, tmp_path / "coverage.json") == []


def test_main_refuses_a_stale_report_even_when_floors_would_pass(tmp_path, capsys):
    """A stale report can show a false pass, so it must fail closed."""
    module = tmp_path / "a.py"
    module.write_text("x = 1\n", encoding="utf-8")
    report = _report(tmp_path, {"a.py": 100.0})
    _age_report_behind(module, report)
    assert main([str(report)], floors={"a.py": 90.0}) == 1
    assert "older than the code" in capsys.readouterr().err
