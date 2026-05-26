from __future__ import annotations

import csv
import json
import random
from dataclasses import asdict
from html import escape
from pathlib import Path
from typing import Any

from objectnav_core.memory.usability import (
    DecisionContext,
    DecisionType,
    EvidenceEvent,
    EvidenceType,
    MemoryBelief,
    UsabilityDecisionPolicy,
    UsabilityUpdater,
)


def run_usability_stress(
    output_dir: str | Path,
    *,
    seed: int = 0,
    monte_carlo_runs: int = 200,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    updater = UsabilityUpdater()
    policy = UsabilityDecisionPolicy()
    scenarios = _run_scenarios(updater)
    sweep_rows = _run_decision_sweep(policy, seed=seed, runs=monte_carlo_runs)
    decision_counts = _count_decisions(sweep_rows)

    summary: dict[str, Any] = {
        "seed": seed,
        "monte_carlo_runs": monte_carlo_runs,
        "scenarios": scenarios,
        "decision_sweep": {
            "decision_counts": decision_counts,
        },
        "artifact_files": {
            "summary": "summary.json",
            "decision_boundary": "decision_boundary.csv",
            "report": "stress_report.html",
        },
    }

    _write_json(output_path / "summary.json", summary)
    _write_boundary_csv(output_path / "decision_boundary.csv", sweep_rows)
    _write_report(output_path / "stress_report.html", summary, sweep_rows)
    return summary


def _run_scenarios(updater: UsabilityUpdater) -> dict[str, Any]:
    ghost = MemoryBelief(p_existence=0.95, p_location_valid=0.9, p_usable=0.9)
    for _ in range(5):
        ghost = updater.apply(ghost, EvidenceEvent(EvidenceType.NON_CONFIRMATION))
    for _ in range(2):
        ghost = updater.apply(ghost, EvidenceEvent(EvidenceType.ACCESS_BLOCKED))

    guarded = MemoryBelief(p_existence=0.92, p_location_valid=0.88, p_usable=0.85)
    for _ in range(4):
        guarded = updater.apply(guarded, EvidenceEvent(EvidenceType.OCCLUDED))
        guarded = updater.apply(guarded, EvidenceEvent(EvidenceType.UNKNOWN))
    guarded = updater.apply(guarded, EvidenceEvent(EvidenceType.POSITIVE, strength=1.5))

    quarantined = MemoryBelief(p_existence=0.9, p_location_valid=0.9, p_usable=0.9)
    for _ in range(20):
        quarantined = updater.apply(
            quarantined,
            EvidenceEvent(EvidenceType.FREE, quarantined=True),
        )

    return {
        "ghost_retirement": {
            "description": "Repeated non-confirmation and access-blocked evidence should retire a ghost memory without claiming non-existence.",
            "final_belief": _belief_dict(ghost),
            "retired": updater.should_retire(ghost),
        },
        "false_deletion_guard": {
            "description": "Occluded and unknown evidence should not erase existence, and positive evidence should revive usability.",
            "final_belief": _belief_dict(guarded),
            "retired": updater.should_retire(guarded),
        },
        "ood_quarantine": {
            "description": "Quarantined negative evidence from a suspected bad sensor batch must not clear memory.",
            "final_belief": _belief_dict(quarantined),
            "retired": updater.should_retire(quarantined),
        },
    }


def _run_decision_sweep(
    policy: UsabilityDecisionPolicy,
    *,
    seed: int,
    runs: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for _ in range(runs):
        belief = MemoryBelief(
            p_existence=rng.uniform(0.35, 0.99),
            p_location_valid=rng.uniform(0.1, 0.99),
            p_usable=rng.uniform(0.02, 0.99),
        )
        context = DecisionContext(
            d_nav=rng.uniform(2.0, 30.0),
            d_verify=rng.uniform(1.0, 20.0),
            c_fail=rng.uniform(2.0, 12.0),
            c_search=rng.uniform(8.0, 60.0),
            b_remaining=rng.uniform(20.0, 90.0),
            verification_repeatedly_failed=rng.random() < 0.15,
        )
        result = policy.choose(belief, context)
        row: dict[str, Any] = {
            **_belief_dict(belief),
            "p_valid": result.p_valid,
            "d_nav": context.d_nav,
            "d_verify": context.d_verify,
            "c_fail": context.c_fail,
            "c_search": context.c_search,
            "b_remaining": context.b_remaining,
            "verification_repeatedly_failed": context.verification_repeatedly_failed,
            "decision": result.decision.value,
        }
        row.update(
            {
                f"cost_{decision.value}": cost
                for decision, cost in result.expected_costs.items()
            }
        )
        rows.append(row)
    return rows


def _count_decisions(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {decision.value: 0 for decision in DecisionType}
    for row in rows:
        counts[str(row["decision"])] += 1
    return counts


def _belief_dict(belief: MemoryBelief) -> dict[str, float]:
    return asdict(belief)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_boundary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_report(
    path: Path,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    scenario_rows = "\n".join(
        _render_scenario_row(name, payload)
        for name, payload in summary["scenarios"].items()
    )
    count_rows = "\n".join(
        f"<tr><td>{escape(decision)}</td><td>{count}</td></tr>"
        for decision, count in summary["decision_sweep"]["decision_counts"].items()
    )
    sample_rows = "\n".join(_render_sweep_row(row) for row in rows[:20])
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Usability Memory Stress Report</title>
  <style>
    body {{
      margin: 0 auto;
      max-width: 1040px;
      padding: 36px 28px 64px;
      color: #172026;
      background: #f7f6f1;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.58;
    }}
    h1, h2 {{ color: #235f8f; }}
    table {{ width: 100%; border-collapse: collapse; margin: 14px 0 26px; background: #fff; }}
    th, td {{ border: 1px solid #d8d5ca; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #ece9df; }}
    code {{ background: #f1eee6; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Usability Memory Stress Report</h1>
  <p>Seed: <code>{summary["seed"]}</code>; Monte Carlo runs: <code>{summary["monte_carlo_runs"]}</code>.</p>
  <h2>Scenario Checks</h2>
  <table>
    <tr><th>Scenario</th><th>Description</th><th>Final Belief</th><th>Retired</th></tr>
    {scenario_rows}
  </table>
  <h2>Decision Counts</h2>
  <table>
    <tr><th>Decision</th><th>Count</th></tr>
    {count_rows}
  </table>
  <h2>Decision Boundary Samples</h2>
  <table>
    <tr><th>p_valid</th><th>d_nav</th><th>d_verify</th><th>c_search</th><th>decision</th></tr>
    {sample_rows}
  </table>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def _render_scenario_row(name: str, payload: dict[str, Any]) -> str:
    belief = payload["final_belief"]
    belief_text = (
        f"p_existence={belief['p_existence']:.3f}, "
        f"p_location_valid={belief['p_location_valid']:.3f}, "
        f"p_usable={belief['p_usable']:.3f}"
    )
    return (
        "<tr>"
        f"<td><code>{escape(name)}</code></td>"
        f"<td>{escape(str(payload['description']))}</td>"
        f"<td>{escape(belief_text)}</td>"
        f"<td>{escape(str(payload['retired']))}</td>"
        "</tr>"
    )


def _render_sweep_row(row: dict[str, Any]) -> str:
    return (
        "<tr>"
        f"<td>{row['p_valid']:.3f}</td>"
        f"<td>{row['d_nav']:.2f}</td>"
        f"<td>{row['d_verify']:.2f}</td>"
        f"<td>{row['c_search']:.2f}</td>"
        f"<td><code>{escape(str(row['decision']))}</code></td>"
        "</tr>"
    )
