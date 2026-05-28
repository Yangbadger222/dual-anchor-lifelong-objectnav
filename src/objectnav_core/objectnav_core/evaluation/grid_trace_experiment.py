from __future__ import annotations

import csv
import json
import math
import random
from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path
from typing import Any, Iterable

from objectnav_core.memory.usability import (
    DecisionContext,
    DecisionType,
    EvidenceEvent,
    EvidenceType,
    MemoryBelief,
    UsabilityDecisionPolicy,
    UsabilityUpdater,
)


SCENARIOS = (
    "stable_visible",
    "removed_or_moved",
    "occluded_then_revealed",
    "blocked_access",
    "ood_depth_failure",
    "nearby_same_class",
    "inflated_corridor_block",
    "stale_path_cost",
    "multi_object_association",
)
NAIVE_COUNT_POSITIVES_TO_TRUST = 2
USABILITY_MEMORY_POLICY = "usability_memory"
NAIVE_COUNT_POLICY = "naive_count"


@dataclass(frozen=True)
class GridTraceEvent:
    episode_id: int
    scenario: str
    step_index: int
    robot_x: float
    robot_y: float
    robot_yaw: float
    target_x: float
    target_y: float
    evidence_type: EvidenceType
    evidence_strength: float
    path_blocked: bool
    association_candidates: int
    d_nav: float
    d_verify: float
    c_fail: float
    c_search: float
    b_remaining: float
    obstacle_intersects_path: bool = False
    inflation_intersects_path: bool = False
    stale_cost: bool = False
    cached_d_nav: float | None = None
    cached_d_verify: float | None = None
    fresh_d_nav: float | None = None
    fresh_d_verify: float | None = None
    costmap_revision: int = 0
    quarantined: bool = False
    true_memory_id: str = "target"
    nearest_memory_id: str = "target"
    jpda_memory_id: str = "target"
    association_margin: float = 1.0
    association_entropy: float = 0.0
    false_positive: bool = False

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["evidence_type"] = self.evidence_type.value
        return row


def generate_grid_trace(
    *,
    seed: int = 0,
    episodes: int = 12,
    steps_per_episode: int = 8,
) -> list[GridTraceEvent]:
    return list(
        iter_grid_trace(
            seed=seed,
            episodes=episodes,
            steps_per_episode=steps_per_episode,
        )
    )


def iter_grid_trace(
    *,
    seed: int = 0,
    episodes: int = 12,
    steps_per_episode: int = 8,
) -> Iterable[GridTraceEvent]:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    if steps_per_episode <= 0:
        raise ValueError("steps_per_episode must be positive")

    rng = random.Random(seed)
    for episode_id in range(episodes):
        scenario = SCENARIOS[episode_id % len(SCENARIOS)]
        target_x = 7.5 + rng.uniform(-0.8, 0.8)
        target_y = 3.5 + rng.uniform(-0.8, 0.8)
        for step_index in range(steps_per_episode):
            progress = step_index / max(1, steps_per_episode - 1)
            robot_x = 1.0 + progress * 5.0 + rng.uniform(-0.12, 0.12)
            robot_y = 1.0 + rng.uniform(-0.2, 0.2)
            evidence_type, strength, blocked, candidates, quarantined = _sample_evidence(
                scenario=scenario,
                step_index=step_index,
                steps_per_episode=steps_per_episode,
                rng=rng,
            )
            distance = math.hypot(target_x - robot_x, target_y - robot_y)
            costs = _path_costs(
                scenario=scenario,
                distance=distance,
                step_index=step_index,
                blocked=blocked,
                rng=rng,
            )
            association = _association_fields(
                scenario=scenario,
                step_index=step_index,
                candidates=candidates,
                rng=rng,
            )
            yield GridTraceEvent(
                episode_id=episode_id,
                scenario=scenario,
                step_index=step_index,
                robot_x=round(robot_x, 4),
                robot_y=round(robot_y, 4),
                robot_yaw=0.0,
                target_x=round(target_x, 4),
                target_y=round(target_y, 4),
                evidence_type=evidence_type,
                evidence_strength=round(strength, 4),
                path_blocked=blocked,
                association_candidates=candidates,
                d_nav=round(costs["fresh_d_nav"], 4),
                d_verify=round(costs["fresh_d_verify"], 4),
                c_fail=round(costs["c_fail"], 4),
                c_search=round(_search_cost(scenario, rng), 4),
                b_remaining=round(max(5.0, 80.0 - episode_id * 0.0002 - step_index * 5.0), 4),
                obstacle_intersects_path=costs["obstacle_intersects_path"],
                inflation_intersects_path=costs["inflation_intersects_path"],
                stale_cost=costs["stale_cost"],
                cached_d_nav=round(costs["cached_d_nav"], 4),
                cached_d_verify=round(costs["cached_d_verify"], 4),
                fresh_d_nav=round(costs["fresh_d_nav"], 4),
                fresh_d_verify=round(costs["fresh_d_verify"], 4),
                costmap_revision=costs["costmap_revision"],
                quarantined=quarantined,
                true_memory_id=association["true_memory_id"],
                nearest_memory_id=association["nearest_memory_id"],
                jpda_memory_id=association["jpda_memory_id"],
                association_margin=round(association["association_margin"], 4),
                association_entropy=round(association["association_entropy"], 4),
                false_positive=association["false_positive"],
            )


def run_grid_trace_experiment(
    output_dir: str | Path,
    *,
    seed: int = 0,
    episodes: int = 12,
    steps_per_episode: int = 8,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    runner = _StreamingReplay(output_path / "events.csv")
    for event in iter_grid_trace(
        seed=seed,
        episodes=episodes,
        steps_per_episode=steps_per_episode,
    ):
        runner.consume(event)
    replay = runner.finish()

    summary: dict[str, Any] = {
        "seed": seed,
        "episodes": episodes,
        "steps_per_episode": steps_per_episode,
        "total_events": replay["total_events"],
        "evidence_counts": replay["evidence_counts"],
        "decision_counts": replay["decision_counts"],
        "decision_rates": replay["decision_rates"],
        "path_cost_metrics": replay["path_cost_metrics"],
        "association_metrics": replay["association_metrics"],
        "baseline_comparison": replay["baseline_comparison"],
        "scenario_summaries": replay["scenario_summaries"],
        "policy_scenario_summaries": replay["policy_scenario_summaries"],
        "artifact_files": {
            "summary": "summary.json",
            "events": "events.csv",
            "report": "trace_report.html",
        },
    }

    _write_json(output_path / "summary.json", summary)
    _write_report(output_path / "trace_report.html", summary)
    return summary


class _StreamingReplay:
    def __init__(self, events_path: Path) -> None:
        self.updater = UsabilityUpdater()
        self.policy = UsabilityDecisionPolicy()
        self.events_path = events_path
        self.handle = events_path.open("w", encoding="utf-8", newline="")
        self.writer: csv.DictWriter[str] | None = None
        self.beliefs: dict[tuple[int, str], MemoryBelief] = {}
        self.naive_positive_counts: dict[tuple[int, str], int] = {}
        self.total_events = 0
        self.evidence_counts: dict[str, int] = {}
        self.decision_counts: dict[str, int] = {}
        self.scenario_summaries: dict[str, Any] = {}
        self.baseline_comparison = {
            USABILITY_MEMORY_POLICY: _new_policy_summary(),
            NAIVE_COUNT_POLICY: {
                **_new_policy_summary(),
                "positive_count_threshold": NAIVE_COUNT_POSITIVES_TO_TRUST,
            },
        }
        self.policy_scenario_summaries: dict[str, dict[str, Any]] = {}
        self.inflation_blocked_events = 0
        self.stale_cost_events = 0
        self.decision_flip_after_refresh = 0
        self.stale_cache_errors = 0
        self.cached_to_fresh_ratio_sum = 0.0
        self.cached_to_fresh_ratio_count = 0
        self.association_events = 0
        self.nearest_wrong_association_events = 0
        self.jpda_rejected_ambiguous_events = 0
        self.ghost_positive_writes_prevented = 0
        self.association_margin_sum = 0.0

    def consume(self, event: GridTraceEvent) -> None:
        belief_key = (
            event.episode_id,
            event.jpda_memory_id if event.jpda_memory_id != "unassigned" else "unassigned",
        )
        belief = self.beliefs.get(
            belief_key,
            MemoryBelief(p_existence=0.9, p_location_valid=0.9, p_usable=0.9),
        )
        effective_evidence_type = event.evidence_type
        if event.jpda_memory_id == "unassigned" and event.evidence_type is EvidenceType.POSITIVE:
            effective_evidence_type = EvidenceType.UNKNOWN
        belief = self.updater.apply(
            belief,
            EvidenceEvent(
                effective_evidence_type,
                strength=event.evidence_strength,
                quarantined=event.quarantined,
            ),
        )
        if event.jpda_memory_id != "unassigned":
            self.beliefs[belief_key] = belief

        cached_context = DecisionContext(
            d_nav=event.cached_d_nav if event.cached_d_nav is not None else event.d_nav,
            d_verify=event.cached_d_verify if event.cached_d_verify is not None else event.d_verify,
            c_fail=event.c_fail,
            c_search=event.c_search,
            b_remaining=event.b_remaining,
            verification_repeatedly_failed=_is_repeated_failure(event),
        )
        refreshed_context = DecisionContext(
            d_nav=event.fresh_d_nav if event.fresh_d_nav is not None else event.d_nav,
            d_verify=event.fresh_d_verify if event.fresh_d_verify is not None else event.d_verify,
            c_fail=event.c_fail,
            c_search=event.c_search,
            b_remaining=event.b_remaining,
            verification_repeatedly_failed=_is_repeated_failure(event),
        )
        stale_result = self.policy.choose(
            belief,
            cached_context,
        )
        refreshed_result = self.policy.choose(
            belief,
            refreshed_context,
        )
        usability_gated_decision = _gated_decision(refreshed_result.decision, event)
        usability_gate_reason = _gate_reason(refreshed_result.decision, event)

        naive_positive_count, naive_false_positive_write = self._update_naive_count(event)
        naive_result = self.policy.choose(
            _naive_count_belief(naive_positive_count),
            refreshed_context,
        )
        naive_gated_decision = _gated_decision(naive_result.decision, event)
        naive_gate_reason = _gate_reason(naive_result.decision, event)
        flipped = stale_result.decision is not refreshed_result.decision
        stale_cache_error = event.stale_cost and flipped and stale_result.decision.value in {
            "trust",
            "verify",
        }
        association_event = event.association_candidates > 1
        nearest_wrong = (
            association_event
            and not event.false_positive
            and event.nearest_memory_id != event.true_memory_id
        )
        jpda_rejected = association_event and event.jpda_memory_id == "unassigned"
        ghost_prevented = (
            event.false_positive
            and event.evidence_type is EvidenceType.POSITIVE
            and event.nearest_memory_id != "unassigned"
            and event.jpda_memory_id == "unassigned"
        )

        row = {
            **event.to_row(),
            "p_existence": belief.p_existence,
            "p_location_valid": belief.p_location_valid,
            "p_usable": belief.p_usable,
            "p_valid": refreshed_result.p_valid,
            "decision": refreshed_result.decision.value,
            "usability_memory_raw_decision": refreshed_result.decision.value,
            "usability_memory_decision": usability_gated_decision.value,
            "usability_memory_gate_reason": usability_gate_reason,
            "naive_count_positive_count": naive_positive_count,
            "naive_count_raw_decision": naive_result.decision.value,
            "naive_count_decision": naive_gated_decision.value,
            "naive_count_gate_reason": naive_gate_reason,
            "naive_count_false_positive_write": naive_false_positive_write,
            "decision_stale": stale_result.decision.value,
            "decision_refreshed": refreshed_result.decision.value,
            "decision_flipped_after_refresh": flipped,
            "stale_cache_error": stale_cache_error,
            "nearest_wrong_association": nearest_wrong,
            "jpda_rejected_ambiguous": jpda_rejected,
            "ghost_positive_write_prevented": ghost_prevented,
        }
        row.update(
            {
                f"cost_{decision.value}": cost
                for decision, cost in refreshed_result.expected_costs.items()
            }
        )
        self._write_row(row)
        self._update_counts(
            event,
            belief,
            refreshed_result.decision.value,
            flipped,
            stale_cache_error,
            nearest_wrong,
            jpda_rejected,
            ghost_prevented,
        )
        self._update_policy_counts(
            event,
            USABILITY_MEMORY_POLICY,
            refreshed_result.decision,
            usability_gated_decision,
            false_positive_write=False,
        )
        self._update_policy_counts(
            event,
            NAIVE_COUNT_POLICY,
            naive_result.decision,
            naive_gated_decision,
            false_positive_write=naive_false_positive_write,
        )

    def finish(self) -> dict[str, Any]:
        self.handle.close()
        return {
            "total_events": self.total_events,
            "evidence_counts": self.evidence_counts,
            "decision_counts": self.decision_counts,
            "decision_rates": _rates(self.decision_counts, self.total_events),
            "scenario_summaries": self.scenario_summaries,
            "path_cost_metrics": {
                "inflation_blocked_events": self.inflation_blocked_events,
                "stale_cost_events": self.stale_cost_events,
                "decision_flip_after_refresh": self.decision_flip_after_refresh,
                "stale_cache_error_rate": _safe_div(
                    self.stale_cache_errors,
                    self.stale_cost_events,
                ),
                "mean_cached_to_fresh_cost_ratio": _safe_div(
                    self.cached_to_fresh_ratio_sum,
                    self.cached_to_fresh_ratio_count,
                ),
            },
            "association_metrics": {
                "association_events": self.association_events,
                "nearest_wrong_association_events": self.nearest_wrong_association_events,
                "nearest_wrong_association_rate": _safe_div(
                    self.nearest_wrong_association_events,
                    self.association_events,
                ),
                "jpda_rejected_ambiguous_events": self.jpda_rejected_ambiguous_events,
                "ghost_positive_writes_prevented": self.ghost_positive_writes_prevented,
                "mean_association_margin": _safe_div(
                    self.association_margin_sum,
                    self.association_events,
                ),
            },
            "baseline_comparison": self.baseline_comparison,
            "policy_scenario_summaries": self.policy_scenario_summaries,
        }

    def _write_row(self, row: dict[str, Any]) -> None:
        if self.writer is None:
            self.writer = csv.DictWriter(self.handle, fieldnames=list(row))
            self.writer.writeheader()
        self.writer.writerow(row)

    def _update_counts(
        self,
        event: GridTraceEvent,
        belief: MemoryBelief,
        decision: str,
        flipped: bool,
        stale_cache_error: bool,
        nearest_wrong: bool,
        jpda_rejected: bool,
        ghost_prevented: bool,
    ) -> None:
        self.total_events += 1
        _increment(self.evidence_counts, event.evidence_type.value)
        _increment(self.decision_counts, decision)
        self.inflation_blocked_events += int(
            event.inflation_intersects_path and event.path_blocked
        )
        self.stale_cost_events += int(event.stale_cost)
        self.decision_flip_after_refresh += int(flipped)
        self.stale_cache_errors += int(stale_cache_error)
        cached_total = (event.cached_d_nav or event.d_nav) + (event.cached_d_verify or event.d_verify)
        fresh_total = (event.fresh_d_nav or event.d_nav) + (event.fresh_d_verify or event.d_verify)
        if event.stale_cost and cached_total > 0.0:
            self.cached_to_fresh_ratio_sum += fresh_total / cached_total
            self.cached_to_fresh_ratio_count += 1
        association_event = event.association_candidates > 1
        self.association_events += int(association_event)
        self.nearest_wrong_association_events += int(nearest_wrong)
        self.jpda_rejected_ambiguous_events += int(jpda_rejected)
        self.ghost_positive_writes_prevented += int(ghost_prevented)
        if association_event:
            self.association_margin_sum += event.association_margin

        scenario_summary = self.scenario_summaries.setdefault(
            event.scenario,
            {
                "events": 0,
                "quarantined_events": 0,
                "path_blocked_events": 0,
                "inflation_blocked_events": 0,
                "stale_cost_events": 0,
                "decision_flip_after_refresh": 0,
                "nearest_wrong_association_events": 0,
                "jpda_rejected_ambiguous_events": 0,
                "ghost_positive_writes_prevented": 0,
                "max_association_candidates": 0,
                "final_belief": {},
                "final_decision": decision,
            },
        )
        scenario_summary["events"] += 1
        scenario_summary["quarantined_events"] += int(event.quarantined)
        scenario_summary["path_blocked_events"] += int(event.path_blocked)
        scenario_summary["inflation_blocked_events"] += int(
            event.inflation_intersects_path and event.path_blocked
        )
        scenario_summary["stale_cost_events"] += int(event.stale_cost)
        scenario_summary["decision_flip_after_refresh"] += int(flipped)
        scenario_summary["nearest_wrong_association_events"] += int(nearest_wrong)
        scenario_summary["jpda_rejected_ambiguous_events"] += int(jpda_rejected)
        scenario_summary["ghost_positive_writes_prevented"] += int(ghost_prevented)
        scenario_summary["max_association_candidates"] = max(
            scenario_summary["max_association_candidates"],
            event.association_candidates,
        )
        scenario_summary["final_belief"] = _belief_dict(belief)
        scenario_summary["final_decision"] = decision

    def _update_naive_count(self, event: GridTraceEvent) -> tuple[int, bool]:
        memory_id = event.nearest_memory_id if event.nearest_memory_id != "unassigned" else "target"
        key = (event.episode_id, memory_id)
        positive_count = self.naive_positive_counts.get(key, 0)
        false_positive_write = False
        if event.evidence_type is EvidenceType.POSITIVE:
            positive_count += 1
            self.naive_positive_counts[key] = positive_count
            false_positive_write = event.false_positive
        return positive_count, false_positive_write

    def _update_policy_counts(
        self,
        event: GridTraceEvent,
        policy_name: str,
        raw_decision: DecisionType,
        gated_decision: DecisionType,
        *,
        false_positive_write: bool,
    ) -> None:
        summary = self.baseline_comparison[policy_name]
        _update_policy_summary(
            summary,
            event,
            raw_decision,
            gated_decision,
            false_positive_write=false_positive_write,
        )
        scenario_summary = self.policy_scenario_summaries.setdefault(event.scenario, {})
        policy_summary = scenario_summary.setdefault(
            policy_name,
            {
                **_new_policy_summary(),
                **(
                    {"positive_count_threshold": NAIVE_COUNT_POSITIVES_TO_TRUST}
                    if policy_name == NAIVE_COUNT_POLICY
                    else {}
                ),
            },
        )
        _update_policy_summary(
            policy_summary,
            event,
            raw_decision,
            gated_decision,
            false_positive_write=false_positive_write,
        )


def _sample_evidence(
    *,
    scenario: str,
    step_index: int,
    steps_per_episode: int,
    rng: random.Random,
) -> tuple[EvidenceType, float, bool, int, bool]:
    if scenario == "stable_visible":
        if rng.random() < 0.82:
            return EvidenceType.POSITIVE, 1.0, False, 1, False
        return EvidenceType.UNKNOWN, 0.6, False, 1, False
    if scenario == "removed_or_moved":
        if step_index < 2:
            return EvidenceType.POSITIVE, 1.0, False, 1, False
        if step_index == steps_per_episode - 1:
            return EvidenceType.SCENE_CHANGED, 1.2, False, 1, False
        evidence = EvidenceType.ACCESS_BLOCKED if rng.random() < 0.35 else EvidenceType.NON_CONFIRMATION
        return evidence, 1.0, False, 1, False
    if scenario == "occluded_then_revealed":
        if step_index < steps_per_episode - 2:
            return EvidenceType.OCCLUDED if step_index % 2 == 0 else EvidenceType.UNKNOWN, 0.9, False, 1, False
        return EvidenceType.POSITIVE, 1.3, False, 1, False
    if scenario == "blocked_access":
        return EvidenceType.ACCESS_BLOCKED if step_index % 2 == 0 else EvidenceType.OCCLUDED, 1.0, True, 1, False
    if scenario == "ood_depth_failure":
        return EvidenceType.FREE if step_index % 2 == 0 else EvidenceType.UNKNOWN, 1.4, False, 1, True
    if scenario == "nearby_same_class":
        candidates = 2 + int(rng.random() < 0.45)
        if step_index < 3:
            return EvidenceType.UNKNOWN, 0.8, False, candidates, False
        if rng.random() < 0.35:
            return EvidenceType.POSITIVE, 0.7, False, candidates, False
        return EvidenceType.NON_CONFIRMATION, 0.7, False, candidates, False
    if scenario == "inflated_corridor_block":
        evidence = EvidenceType.ACCESS_BLOCKED if step_index % 2 == 0 else EvidenceType.OCCLUDED
        return evidence, 1.15, True, 1, False
    if scenario == "stale_path_cost":
        if step_index < 2:
            return EvidenceType.UNKNOWN, 0.6, False, 1, False
        evidence = EvidenceType.NON_CONFIRMATION if step_index < steps_per_episode - 1 else EvidenceType.ACCESS_BLOCKED
        return evidence, 1.0, True, 1, False
    if scenario == "multi_object_association":
        if step_index in {2, 5}:
            return EvidenceType.POSITIVE, 0.8, False, 3, False
        if step_index in {3, 6}:
            return EvidenceType.UNKNOWN, 0.75, False, 3, False
        if step_index == 7:
            return EvidenceType.NON_CONFIRMATION, 0.9, False, 2, False
        return EvidenceType.POSITIVE, 0.7, False, 3, False
    raise ValueError(f"unknown scenario: {scenario}")


def _association_fields(
    *,
    scenario: str,
    step_index: int,
    candidates: int,
    rng: random.Random,
) -> dict[str, Any]:
    if scenario != "multi_object_association":
        return {
            "true_memory_id": "target",
            "nearest_memory_id": "target",
            "jpda_memory_id": "target",
            "association_margin": 1.0,
            "association_entropy": 0.0,
            "false_positive": False,
        }

    true_memory_id = "memory_a" if step_index in {0, 1, 3, 6} else "memory_b"
    false_positive = step_index in {2, 5}
    if false_positive:
        true_memory_id = "clutter"

    ambiguous = step_index in {1, 2, 5, 6}
    nearest_memory_id = true_memory_id
    if step_index in {1, 6}:
        nearest_memory_id = "memory_b" if true_memory_id == "memory_a" else "memory_a"
    if false_positive:
        nearest_memory_id = "memory_a" if step_index == 2 else "memory_b"

    association_margin = rng.uniform(0.03, 0.14) if ambiguous else rng.uniform(0.28, 0.62)
    association_entropy = 1.0 - min(1.0, association_margin)
    if false_positive or association_margin < 0.16:
        jpda_memory_id = "unassigned"
    else:
        jpda_memory_id = true_memory_id

    return {
        "true_memory_id": true_memory_id,
        "nearest_memory_id": nearest_memory_id,
        "jpda_memory_id": jpda_memory_id,
        "association_margin": association_margin,
        "association_entropy": association_entropy,
        "false_positive": false_positive,
    }


def _path_costs(
    *,
    scenario: str,
    distance: float,
    step_index: int,
    blocked: bool,
    rng: random.Random,
) -> dict[str, Any]:
    d_nav = distance * (1.4 if blocked else 1.0)
    d_verify = _verification_cost(scenario, distance, rng)
    c_fail = 6.0 + rng.uniform(0.0, 7.0) + (6.0 if blocked else 0.0)
    costs: dict[str, Any] = {
        "cached_d_nav": d_nav,
        "cached_d_verify": d_verify,
        "fresh_d_nav": d_nav,
        "fresh_d_verify": d_verify,
        "c_fail": c_fail,
        "obstacle_intersects_path": blocked,
        "inflation_intersects_path": False,
        "stale_cost": False,
        "costmap_revision": 1,
    }
    if scenario == "inflated_corridor_block":
        inflation_penalty = 18.0 + rng.uniform(5.0, 15.0)
        costs.update(
            {
                "cached_d_nav": max(0.8, distance * 0.9),
                "cached_d_verify": max(0.6, distance * 0.35 + rng.uniform(0.2, 1.0)),
                "fresh_d_nav": d_nav + inflation_penalty,
                "fresh_d_verify": d_verify + inflation_penalty * 0.9,
                "obstacle_intersects_path": False,
                "inflation_intersects_path": True,
                "costmap_revision": 2 + step_index,
            }
        )
    if scenario == "stale_path_cost":
        stale_multiplier = 3.5 + rng.uniform(0.5, 2.5)
        costs.update(
            {
                "cached_d_nav": max(0.8, distance * 0.75),
                "cached_d_verify": max(0.6, distance * 0.25 + rng.uniform(0.2, 1.0)),
                "fresh_d_nav": max(d_nav * stale_multiplier, d_nav + 12.0),
                "fresh_d_verify": max(d_verify * stale_multiplier, d_verify + 10.0),
                "obstacle_intersects_path": step_index >= 3,
                "inflation_intersects_path": step_index >= 2,
                "stale_cost": True,
                "costmap_revision": 10 + step_index,
            }
        )
    return costs


def _verification_cost(scenario: str, distance: float, rng: random.Random) -> float:
    if scenario in {"stable_visible", "occluded_then_revealed", "nearby_same_class"}:
        return max(0.6, distance * 0.35 + rng.uniform(0.2, 1.2))
    if scenario == "blocked_access":
        return distance * 0.75 + rng.uniform(3.0, 7.0)
    if scenario in {"inflated_corridor_block", "stale_path_cost"}:
        return distance * 0.8 + rng.uniform(4.0, 9.0)
    if scenario == "multi_object_association":
        return distance * 0.5 + rng.uniform(1.5, 4.5)
    return distance * 0.45 + rng.uniform(0.8, 2.5)


def _search_cost(scenario: str, rng: random.Random) -> float:
    base = {
        "stable_visible": 38.0,
        "removed_or_moved": 58.0,
        "occluded_then_revealed": 42.0,
        "blocked_access": 50.0,
        "ood_depth_failure": 46.0,
        "nearby_same_class": 54.0,
        "inflated_corridor_block": 36.0,
        "stale_path_cost": 34.0,
        "multi_object_association": 48.0,
    }[scenario]
    return base + rng.uniform(-5.0, 5.0)


def _is_repeated_failure(event: GridTraceEvent) -> bool:
    repeated_failure_scenarios = {
        "removed_or_moved",
        "blocked_access",
        "inflated_corridor_block",
        "stale_path_cost",
        "multi_object_association",
    }
    return event.scenario in repeated_failure_scenarios and event.step_index >= 5


def _naive_count_belief(positive_count: int) -> MemoryBelief:
    if positive_count >= NAIVE_COUNT_POSITIVES_TO_TRUST:
        return MemoryBelief(
            p_existence=0.98,
            p_location_valid=0.98,
            p_usable=0.98,
        )
    return MemoryBelief(
        p_existence=0.05,
        p_location_valid=0.95,
        p_usable=0.95,
    )


def _gated_decision(decision: DecisionType, event: GridTraceEvent) -> DecisionType:
    if decision is not DecisionType.TRUST:
        return decision
    if _is_current_positive(event):
        return DecisionType.TRUST
    return DecisionType.VERIFY


def _gate_reason(decision: DecisionType, event: GridTraceEvent) -> str:
    if decision is not DecisionType.TRUST:
        return "raw_decision_not_trust"
    if _is_current_positive(event):
        return "current_positive"
    if event.evidence_type is not EvidenceType.POSITIVE:
        return "missing_current_positive"
    if event.false_positive:
        return "false_positive"
    return "trust_rejected"


def _is_current_positive(event: GridTraceEvent) -> bool:
    return event.evidence_type is EvidenceType.POSITIVE and not event.false_positive


def _new_policy_summary() -> dict[str, Any]:
    return {
        "events": 0,
        "raw_trust_count": 0,
        "gated_trust_count": 0,
        "gate_rejection_count": 0,
        "unsafe_raw_trust_count": 0,
        "false_positive_write_pressure": 0,
        "raw_decision_counts": {},
        "decision_counts": {},
        "final_raw_decision": "",
        "final_decision": "",
    }


def _update_policy_summary(
    summary: dict[str, Any],
    event: GridTraceEvent,
    raw_decision: DecisionType,
    gated_decision: DecisionType,
    *,
    false_positive_write: bool,
) -> None:
    summary["events"] += 1
    summary["raw_trust_count"] += int(raw_decision is DecisionType.TRUST)
    summary["gated_trust_count"] += int(gated_decision is DecisionType.TRUST)
    rejected_trust = raw_decision is DecisionType.TRUST and gated_decision is not DecisionType.TRUST
    summary["gate_rejection_count"] += int(rejected_trust)
    summary["unsafe_raw_trust_count"] += int(
        raw_decision is DecisionType.TRUST and not _is_current_positive(event)
    )
    summary["false_positive_write_pressure"] += int(false_positive_write)
    _increment(summary["raw_decision_counts"], raw_decision.value)
    _increment(summary["decision_counts"], gated_decision.value)
    summary["final_raw_decision"] = raw_decision.value
    summary["final_decision"] = gated_decision.value


def _increment(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _rates(counts: dict[str, int], total: int) -> dict[str, float]:
    return {key: _safe_div(value, total) for key, value in counts.items()}


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def _belief_dict(belief: MemoryBelief) -> dict[str, float]:
    return asdict(belief)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    evidence_rows = "\n".join(
        f"<tr><td>{escape(name)}</td><td>{count}</td></tr>"
        for name, count in sorted(summary["evidence_counts"].items())
    )
    decision_rows = "\n".join(
        f"<tr><td>{escape(name)}</td><td>{count}</td><td>{summary['decision_rates'][name]:.3f}</td></tr>"
        for name, count in sorted(summary["decision_counts"].items())
    )
    metric_rows = "\n".join(
        f"<tr><td>{escape(name)}</td><td>{value}</td></tr>"
        for name, value in sorted(summary["path_cost_metrics"].items())
    )
    association_rows = "\n".join(
        f"<tr><td>{escape(name)}</td><td>{value}</td></tr>"
        for name, value in sorted(summary["association_metrics"].items())
    )
    baseline_rows = "\n".join(
        _render_baseline_row(name, payload)
        for name, payload in sorted(summary["baseline_comparison"].items())
    )
    scenario_rows = "\n".join(
        _render_scenario_row(name, payload)
        for name, payload in sorted(summary["scenario_summaries"].items())
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>2D Grid Trace Experiment</title>
  <style>
    body {{
      margin: 0 auto;
      max-width: 1040px;
      padding: 36px 28px 64px;
      color: #172026;
      background: #f8f7f2;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.58;
    }}
    h1, h2 {{ color: #245f73; }}
    table {{ width: 100%; border-collapse: collapse; margin: 14px 0 26px; background: #fff; }}
    th, td {{ border: 1px solid #d8d5ca; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #ece9df; }}
    code {{ background: #f1eee6; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>2D Grid Trace Experiment</h1>
  <p>Seed: <code>{summary["seed"]}</code>; episodes: <code>{summary["episodes"]}</code>; events: <code>{summary["total_events"]}</code>.</p>
  <h2>Evidence Counts</h2>
  <table><tr><th>Evidence</th><th>Count</th></tr>{evidence_rows}</table>
  <h2>Decision Counts</h2>
  <table><tr><th>Decision</th><th>Count</th><th>Rate</th></tr>{decision_rows}</table>
  <h2>Inflation & Stale Cost Metrics</h2>
  <table><tr><th>Metric</th><th>Value</th></tr>{metric_rows}</table>
  <h2>Association Metrics</h2>
  <table><tr><th>Metric</th><th>Value</th></tr>{association_rows}</table>
  <h2>Baseline Comparison</h2>
  <table><tr><th>Policy</th><th>Raw Trust</th><th>Gated Trust</th><th>Gate Rejections</th><th>Unsafe Raw Trust</th><th>False Positive Writes</th><th>Final Raw</th><th>Final Gated</th></tr>{baseline_rows}</table>
  <h2>Scenario Summaries</h2>
  <table><tr><th>Scenario</th><th>Events</th><th>Quarantined</th><th>Blocked</th><th>Inflation Blocked</th><th>Stale Events</th><th>Flips</th><th>Wrong NN</th><th>JPDA Reject</th><th>Ghost Prevented</th><th>Final Belief</th><th>Final Decision</th></tr>{scenario_rows}</table>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def _render_baseline_row(name: str, payload: dict[str, Any]) -> str:
    return (
        "<tr>"
        f"<td><code>{escape(name)}</code></td>"
        f"<td>{payload['raw_trust_count']}</td>"
        f"<td>{payload['gated_trust_count']}</td>"
        f"<td>{payload['gate_rejection_count']}</td>"
        f"<td>{payload['unsafe_raw_trust_count']}</td>"
        f"<td>{payload['false_positive_write_pressure']}</td>"
        f"<td><code>{escape(str(payload['final_raw_decision']))}</code></td>"
        f"<td><code>{escape(str(payload['final_decision']))}</code></td>"
        "</tr>"
    )


def _render_scenario_row(name: str, payload: dict[str, Any]) -> str:
    belief = payload["final_belief"]
    belief_text = (
        f"p_e={belief['p_existence']:.3f}, "
        f"p_l={belief['p_location_valid']:.3f}, "
        f"p_u={belief['p_usable']:.3f}"
    )
    return (
        "<tr>"
        f"<td><code>{escape(name)}</code></td>"
        f"<td>{payload['events']}</td>"
        f"<td>{payload['quarantined_events']}</td>"
        f"<td>{payload['path_blocked_events']}</td>"
        f"<td>{payload['inflation_blocked_events']}</td>"
        f"<td>{payload['stale_cost_events']}</td>"
        f"<td>{payload['decision_flip_after_refresh']}</td>"
        f"<td>{payload['nearest_wrong_association_events']}</td>"
        f"<td>{payload['jpda_rejected_ambiguous_events']}</td>"
        f"<td>{payload['ghost_positive_writes_prevented']}</td>"
        f"<td>{escape(belief_text)}</td>"
        f"<td><code>{escape(str(payload['final_decision']))}</code></td>"
        "</tr>"
    )
