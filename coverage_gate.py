"""Enforce per-module coverage floors, which coverage.py cannot express.

``fail_under`` (applied through ``pytest --cov``) guards only the project
total, so a single module can slide from 100% to 0% while the other modules
carry the average, and the run still passes. This applies a floor to every
module and reports *all* violations rather than stopping at the first, so one
run tells you everything that broke.

Usage::

    uv run pytest --cov --cov-report=json
    uv run python coverage_gate.py

Exit status is 0 when every floor holds, 1 when any does not.

The report is refused when it is older than the modules it describes. A stale
report is worse than no report: it can show a module passing on numbers
measured before the very change that broke it, so the gate fails closed rather
than answering from evidence it cannot vouch for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

#: Minimum percent covered, per module. Each floor sits two points below the
#: value measured when it was set: enough room for a new helper to land before
#: its test without reddening CI, tight enough that a real regression fails.
#: When a module improves, raise its floor. Never lower one to make a change
#: pass: that removes the guarantee the gate exists to provide.
FLOORS: dict[str, float] = {
    "audio_synth.py": 94.0,
    "combat_events.py": 93.0,
    "combat_log.py": 95.0,
    "combat_runner.py": 90.0,
    "combat_schema.py": 98.0,
    # Excludes the ``__main__`` line, which only runs when this file is executed
    # as a script rather than imported by its tests.
    "coverage_gate.py": 95.0,
    "d20_rules.py": 98.0,
    "encounter_ai.py": 96.0,
    "game_foundation.py": 98.0,
    "genui.py": 98.0,
    "scripts/verify_release.py": 98.0,
    "tui_runner.py": 97.0,
    "web/build_demo.py": 87.0,
}

DEFAULT_REPORT = Path(__file__).with_name("coverage.json")


def read_percentages(report: Path) -> dict[str, float]:
    """Return ``{module: percent covered}`` from a coverage JSON report."""
    payload: dict[str, Any] = json.loads(report.read_text(encoding="utf-8"))
    files: dict[str, Any] = payload["files"]
    return {
        name: float(entry["summary"]["percent_covered"])
        for name, entry in files.items()
    }


def find_stale_modules(reported: dict[str, float], report: Path) -> list[str]:
    """Return modules whose source file is newer than ``report``.

    Paths are resolved relative to the report, which is how coverage writes
    them and where the report itself lives.
    """
    if not report.exists():
        return []
    report_time = report.stat().st_mtime
    stale: list[str] = []
    for module in sorted(reported):
        source = report.parent / module
        if source.is_file() and source.stat().st_mtime > report_time:
            stale.append(module)
    return stale


def find_violations(
    percentages: dict[str, float],
    floors: dict[str, float] | None = None,
) -> list[str]:
    """Return one message per module that breaks the gate, in a stable order.

    Three ways to break it, and the last two matter as much as the first: a
    floor that no longer matches a measured module means the gate has silently
    stopped guarding something, and a measured module with no floor at all is
    guarded by nothing.
    """
    configured = FLOORS if floors is None else floors
    problems: list[str] = []
    for module in sorted(configured):
        floor = configured[module]
        if module not in percentages:
            problems.append(
                f"{module}: floor {floor:.1f}% is configured but the module is absent "
                "from the report (renamed, moved, or no longer measured)"
            )
        elif percentages[module] < floor:
            problems.append(
                f"{module}: {percentages[module]:.1f}% is below its floor of {floor:.1f}%"
            )
    for module in sorted(set(percentages) - set(configured)):
        problems.append(
            f"{module}: {percentages[module]:.1f}% has no floor, so nothing guards "
            "it; add an entry to FLOORS"
        )
    return problems


def main(
    argv: list[str] | None = None,
    floors: dict[str, float] | None = None,
) -> int:
    """Run the gate over a coverage JSON report. Returns the process exit code."""
    configured = FLOORS if floors is None else floors
    args = sys.argv[1:] if argv is None else argv
    report = Path(args[0]) if args else DEFAULT_REPORT
    if not report.exists():
        print(
            f"coverage gate: {report} is missing; run "
            "`pytest --cov --cov-report=json` first",
            file=sys.stderr,
        )
        return 1
    percentages = read_percentages(report)
    stale = find_stale_modules(percentages, report)
    if stale:
        # Floor numbers from a stale report are not evidence, so stop here
        # rather than reporting passes or failures the run cannot support.
        print(
            f"coverage gate: {report} is older than the code it describes; "
            "re-run `pytest --cov --cov-report=json` before trusting it:",
            file=sys.stderr,
        )
        for module in stale:
            print(f"  - {module}", file=sys.stderr)
        return 1
    problems = find_violations(percentages, configured)
    if problems:
        print(f"coverage gate: {len(problems)} module(s) failed:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"coverage gate: all {len(configured)} module floors met")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
