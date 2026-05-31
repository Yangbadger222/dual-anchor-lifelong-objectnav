from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    FRONTIER_CLEAR_DEPTH_M,
    FRONTIER_CLEAR_DEPTH_NORMALIZED,
    OfficialObjectNavRunConfig,
    _center_depth_is_clear,
    _depth_frame_2d,
    _make_habitat_env,
)


SCHEMA_VERSION = "official-candidate-rollout-v1"
STATE_RESTORE_SCHEMA_VERSION = "official-candidate-state-restore-v1"
CANDIDATE_VIEWPOINT_RESTORE_SCHEMA_VERSION = (
    "official-candidate-viewpoint-restore-v1"
)
CANDIDATE_OPTION_VALUE_SCHEMA_VERSION = "official-candidate-option-value-v1"
DEFAULT_VIEWPOINT_GRID_SIZE_CELLS = 81
DEFAULT_VIEWPOINT_GRID_CELL_SIZE_M = 0.25
DEFAULT_VIEWPOINT_HEADING_COUNT = 8
DEFAULT_OPTION_HORIZON_STEPS = 8
DEFAULT_OPTION_SCAN_STEPS = 4
DEFAULT_OPTION_PROGRESS_THRESHOLD_M = 0.05
BRANCH_FOLLOWUP_POLICIES: tuple[str, ...] = ("left_scan", "repeat_first_action")
STATE_SAMPLING_MODES: tuple[str, ...] = (
    "trace_order",
    "top_score_desc",
    "active_phase_path",
)

STATE_FEATURE_FIELDS: tuple[str, ...] = (
    "agent_x_m",
    "agent_z_m",
    "agent_heading_rad",
    "memory_bearing_error_rad",
    "memory_anchor_bearing_error_rad",
    "memory_distance_to_anchor_m",
    "memory_path_distance_m",
    "memory_travel_distance_m",
    "memory_expected_evidence",
    "memory_belief_mass",
    "memory_score",
    "memory_active_perception_candidate_count",
    "memory_active_perception_phase_rank",
    "memory_active_perception_orient_anchor",
    "memory_active_perception_scan_anchor",
    "memory_active_perception_frontier",
    "memory_active_perception_at_viewpoint",
    "memory_active_perception_scan_steps_remaining",
    "memory_top_candidate_count",
    "memory_top_score",
    "memory_score_gap",
    "local_center_depth_clear",
    "local_center_depth_median",
    "local_center_depth_min",
    "local_center_depth_clear_fraction",
    "previous_target_visible",
    "recent_target_visible_count",
    "steps_since_last_target_visible",
    "current_detector_confidence",
    "current_bbox_area_fraction",
    "current_depth_median",
)

_CSV_FIELDS: tuple[str, ...] = (
    "source_policy_trace",
    "episode_index",
    "episode_id",
    "scene_id",
    "target_category",
    "step_index",
    "state_action",
    "state_decision",
    *STATE_FEATURE_FIELDS,
    "branch_kind",
    "branch_action",
    "candidate_rank",
    "candidate_count",
    "candidate_score",
    "expected_evidence",
    "travel_distance_m",
    "path_distance_m",
    "bearing_error_rad",
    "viewpoint_row",
    "viewpoint_col",
    "frontier_row",
    "frontier_col",
    "valid_rollout",
    "invalid_reason",
    "replay_actions",
    "rollout_actions",
    "label_available",
    "current_target_visible",
    "target_visible_within_rollout",
    "hidden_to_visible_within_rollout",
)

_STATE_RESTORE_CSV_FIELDS: tuple[str, ...] = (
    "source_policy_trace",
    "state_index",
    "episode_index",
    "episode_id",
    "scene_id",
    "target_category",
    "step_index",
    "state_action",
    "state_decision",
    *STATE_FEATURE_FIELDS,
    "candidate_rank",
    "candidate_count",
    "candidate_score",
    "expected_evidence",
    "travel_distance_m",
    "path_distance_m",
    "bearing_error_rad",
    "viewpoint_row",
    "viewpoint_col",
    "frontier_row",
    "frontier_col",
    "valid_restore",
    "invalid_reason",
    "replay_actions",
    "label_available",
    "target_visible_at_restore",
    "hidden_at_restore",
)

_CANDIDATE_VIEWPOINT_RESTORE_CSV_FIELDS: tuple[str, ...] = (
    "source_policy_trace",
    "state_index",
    "episode_index",
    "episode_id",
    "scene_id",
    "target_category",
    "step_index",
    "state_action",
    "state_decision",
    *STATE_FEATURE_FIELDS,
    "candidate_rank",
    "candidate_count",
    "candidate_score",
    "expected_evidence",
    "travel_distance_m",
    "path_distance_m",
    "bearing_error_rad",
    "viewpoint_row",
    "viewpoint_col",
    "frontier_row",
    "frontier_col",
    "grid_size_cells",
    "grid_cell_size_m",
    "grid_origin_row",
    "grid_origin_col",
    "candidate_x_m",
    "candidate_z_m",
    "viewpoint_heading_count",
    "visible_heading_count",
    "best_detector_confidence",
    "valid_state_restore",
    "valid_candidate_restore",
    "invalid_reason",
    "replay_actions",
    "label_available",
    "current_target_visible_at_restore",
    "target_visible_from_candidate_viewpoint",
    "hidden_to_visible_from_candidate_viewpoint",
)

_CANDIDATE_OPTION_VALUE_CSV_FIELDS: tuple[str, ...] = (
    "source_policy_trace",
    "state_index",
    "episode_index",
    "episode_id",
    "scene_id",
    "target_category",
    "step_index",
    "state_action",
    "state_decision",
    *STATE_FEATURE_FIELDS,
    "candidate_rank",
    "candidate_count",
    "candidate_score",
    "expected_evidence",
    "travel_distance_m",
    "path_distance_m",
    "bearing_error_rad",
    "viewpoint_row",
    "viewpoint_col",
    "frontier_row",
    "frontier_col",
    "grid_size_cells",
    "grid_cell_size_m",
    "grid_origin_row",
    "grid_origin_col",
    "candidate_x_m",
    "candidate_z_m",
    "option_horizon_steps",
    "option_scan_steps",
    "option_scan_step_count",
    "option_blocked_scan_step_count",
    "initial_detector_confidence",
    "best_detector_confidence",
    "detector_confidence_gain",
    "initial_distance_to_goal_m",
    "final_distance_to_goal_m",
    "min_distance_to_goal_m",
    "distance_to_goal_delta_m",
    "best_distance_to_goal_delta_m",
    "stop_probe_success",
    "stop_probe_spl",
    "stop_probe_softspl",
    "stop_probe_distance_to_goal_m",
    "valid_option_rollout",
    "invalid_reason",
    "replay_actions",
    "option_rollout_actions",
    "label_available",
    "current_target_visible_at_restore",
    "target_visible_within_option_rollout",
    "hidden_to_visible_within_option_rollout",
    "detector_confidence_gain_within_option_rollout",
    "official_progress_within_option_rollout",
    "official_stop_success_after_option_rollout",
)


@dataclass(frozen=True)
class _ReplayResult:
    observation: Mapping[str, Any] | None
    replay_actions: tuple[str, ...]
    valid: bool
    invalid_reason: str | None = None


@dataclass
class _CandidateOptionRolloutState:
    scan_steps_remaining: int = 0
    option_scan_step_count: int = 0
    option_blocked_scan_step_count: int = 0


def export_official_candidate_rollout_dataset(
    policy_trace_path: str | Path,
    *,
    output_dir: str | Path,
    config_path: str,
    dataset_data_path: str,
    scene_root: str,
    split: str = "val_mini",
    target_detector_adapter: Any | None = None,
    target_detector_min_confidence: float = 0.25,
    max_states: int | None = None,
    max_states_per_category: int | None = None,
    max_states_per_category_episode: int | None = None,
    state_sampling: str = "trace_order",
    candidates_per_state: int = 5,
    rollout_horizon_steps: int = 5,
    branch_actions: Sequence[str] | None = None,
    branch_followup_policy: str = "left_scan",
    seed: int = 313,
    env_factory: Callable[[OfficialObjectNavRunConfig], Any] | None = None,
) -> dict[str, Any]:
    policy_path = Path(policy_trace_path)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    safe_max_states = None if max_states is None else max(0, int(max_states))
    safe_max_states_per_category = (
        None
        if max_states_per_category is None
        else max(0, int(max_states_per_category))
    )
    safe_max_states_per_category_episode = (
        None
        if max_states_per_category_episode is None
        else max(0, int(max_states_per_category_episode))
    )
    safe_candidates_per_state = max(1, int(candidates_per_state))
    safe_horizon_steps = max(1, int(rollout_horizon_steps))
    safe_branch_actions = _branch_actions(branch_actions)
    safe_followup_policy = _branch_followup_policy(branch_followup_policy)
    safe_state_sampling = _state_sampling_mode(state_sampling)
    branch_mode = "action_matrix" if safe_branch_actions else "candidate"
    payload = _load_object(policy_path)
    steps = _policy_steps(payload)
    replay_budget_steps = max(
        safe_horizon_steps,
        _max_step_index(steps) + safe_horizon_steps + 1,
    )
    config = OfficialObjectNavRunConfig(
        config_path=str(config_path),
        dataset_data_path=str(dataset_data_path),
        scene_root=str(scene_root),
        split=split,
        policy="memory_active_perception_frontier",
        max_episodes=None,
        max_steps=replay_budget_steps,
        seed=seed,
        validate_habitat=False,
    )
    candidate_states = _candidate_states(
        steps,
        max_states=safe_max_states,
        max_states_per_category=safe_max_states_per_category,
        max_states_per_category_episode=safe_max_states_per_category_episode,
        state_sampling=safe_state_sampling,
    )
    make_env = env_factory or _make_habitat_env
    rollouts: list[dict[str, Any]] = []
    skipped_state_count = 0
    for state_index, step in enumerate(candidate_states):
        memory_prior = step.get("memory_prior", {})
        top_candidates = (
            memory_prior.get("top_candidates", [])
            if isinstance(memory_prior, Mapping)
            else []
        )
        if not isinstance(top_candidates, list) or not top_candidates:
            skipped_state_count += 1
            continue
        branch_specs = _branch_specs(
            top_candidates=top_candidates,
            candidates_per_state=safe_candidates_per_state,
            branch_actions=safe_branch_actions,
        )
        for branch_spec in branch_specs:
            env = make_env(config)
            try:
                replay = _replay_to_policy_state(env, steps=steps, target_step=step)
                rollouts.append(
                    _evaluate_candidate_rollout(
                        policy_path=policy_path,
                        state_index=state_index,
                        step=step,
                        candidate=branch_spec["candidate"],
                        candidate_rank=int(branch_spec["rank"]),
                        candidate_count=int(branch_spec["count"]),
                        branch_kind=str(branch_spec["kind"]),
                        branch_action=branch_spec.get("action"),
                        forced_first_action=branch_spec.get("action"),
                        replay=replay,
                        env=env,
                        target_detector_adapter=target_detector_adapter,
                        target_detector_min_confidence=target_detector_min_confidence,
                        rollout_horizon_steps=safe_horizon_steps,
                        branch_followup_policy=safe_followup_policy,
                    )
                )
            finally:
                close = getattr(env, "close", None)
                if callable(close):
                    close()
    return {
        "task": "habitat_official_candidate_rollout_dataset",
        "schema_version": SCHEMA_VERSION,
        "source_policy_trace": str(policy_path),
        "config": asdict(config),
        "candidate_state_limit": safe_max_states,
        "candidate_state_limit_per_category": safe_max_states_per_category,
        "candidate_state_limit_per_category_episode": (
            safe_max_states_per_category_episode
        ),
        "candidate_state_sampling": safe_state_sampling,
        "candidates_per_state": safe_candidates_per_state,
        "branch_mode": branch_mode,
        "branch_actions": list(safe_branch_actions),
        "branch_followup_policy": safe_followup_policy,
        "rollout_horizon_steps": safe_horizon_steps,
        "state_count": len(candidate_states),
        "skipped_state_count": skipped_state_count,
        "rollout_count": len(rollouts),
        "positive_rollout_count": sum(
            1
            for rollout in rollouts
            if rollout["labels"]["hidden_to_visible_within_rollout"] is True
        ),
        "invalid_rollout_count": sum(
            1 for rollout in rollouts if not rollout["valid_rollout"]
        ),
        "rollouts": rollouts,
    }


def export_official_candidate_state_restore_dataset(
    policy_trace_path: str | Path,
    *,
    output_dir: str | Path,
    config_path: str,
    dataset_data_path: str,
    scene_root: str,
    split: str = "val_mini",
    target_detector_adapter: Any | None = None,
    target_detector_min_confidence: float = 0.25,
    max_states: int | None = None,
    max_states_per_category: int | None = None,
    max_states_per_category_episode: int | None = None,
    state_sampling: str = "trace_order",
    seed: int = 313,
    env_factory: Callable[[OfficialObjectNavRunConfig], Any] | None = None,
) -> dict[str, Any]:
    policy_path = Path(policy_trace_path)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    safe_max_states = None if max_states is None else max(0, int(max_states))
    safe_max_states_per_category = (
        None
        if max_states_per_category is None
        else max(0, int(max_states_per_category))
    )
    safe_max_states_per_category_episode = (
        None
        if max_states_per_category_episode is None
        else max(0, int(max_states_per_category_episode))
    )
    safe_state_sampling = _state_sampling_mode(state_sampling)
    payload = _load_object(policy_path)
    steps = _policy_steps(payload)
    replay_budget_steps = max(1, _max_step_index(steps) + 1)
    config = OfficialObjectNavRunConfig(
        config_path=str(config_path),
        dataset_data_path=str(dataset_data_path),
        scene_root=str(scene_root),
        split=split,
        policy="memory_active_perception_frontier",
        max_episodes=None,
        max_steps=replay_budget_steps,
        seed=seed,
        validate_habitat=False,
    )
    candidate_states = _candidate_states(
        steps,
        max_states=safe_max_states,
        max_states_per_category=safe_max_states_per_category,
        max_states_per_category_episode=safe_max_states_per_category_episode,
        state_sampling=safe_state_sampling,
    )
    make_env = env_factory or _make_habitat_env
    rows: list[dict[str, Any]] = []
    skipped_state_count = 0
    for state_index, step in enumerate(candidate_states):
        memory_prior = _mapping(step.get("memory_prior"))
        top_candidates = _memory_top_candidates(memory_prior)
        if not top_candidates:
            skipped_state_count += 1
            continue
        candidate = _selected_memory_candidate(memory_prior, top_candidates)
        env = make_env(config)
        try:
            replay = _replay_to_policy_state(env, steps=steps, target_step=step)
            rows.append(
                _evaluate_state_restore(
                    policy_path=policy_path,
                    state_index=state_index,
                    step=step,
                    candidate=candidate,
                    candidate_rank=_selected_candidate_rank(
                        selected_candidate=candidate,
                        top_candidates=top_candidates,
                    ),
                    candidate_count=len(top_candidates),
                    replay=replay,
                    target_detector_adapter=target_detector_adapter,
                    target_detector_min_confidence=target_detector_min_confidence,
                )
            )
        finally:
            close = getattr(env, "close", None)
            if callable(close):
                close()
    return {
        "task": "habitat_official_candidate_state_restore_dataset",
        "schema_version": STATE_RESTORE_SCHEMA_VERSION,
        "source_policy_trace": str(policy_path),
        "config": asdict(config),
        "candidate_state_limit": safe_max_states,
        "candidate_state_limit_per_category": safe_max_states_per_category,
        "candidate_state_limit_per_category_episode": (
            safe_max_states_per_category_episode
        ),
        "candidate_state_sampling": safe_state_sampling,
        "state_count": len(candidate_states),
        "skipped_state_count": skipped_state_count,
        "restore_count": len(rows),
        "valid_restore_count": sum(1 for row in rows if row["valid_restore"]),
        "invalid_restore_count": sum(1 for row in rows if not row["valid_restore"]),
        "label_available_count": sum(
            1 for row in rows if row["labels"]["label_available"] is True
        ),
        "target_visible_state_count": sum(
            1 for row in rows if row["labels"]["target_visible_at_restore"] is True
        ),
        "states": rows,
    }


def export_official_candidate_viewpoint_restore_dataset(
    policy_trace_path: str | Path,
    *,
    output_dir: str | Path,
    config_path: str,
    dataset_data_path: str,
    scene_root: str,
    split: str = "val_mini",
    target_detector_adapter: Any | None = None,
    target_detector_min_confidence: float = 0.25,
    max_states: int | None = None,
    max_states_per_category: int | None = None,
    max_states_per_category_episode: int | None = None,
    state_sampling: str = "trace_order",
    candidates_per_state: int = 5,
    viewpoint_heading_count: int = DEFAULT_VIEWPOINT_HEADING_COUNT,
    viewpoint_grid_size_cells: int = DEFAULT_VIEWPOINT_GRID_SIZE_CELLS,
    viewpoint_grid_cell_size_m: float = DEFAULT_VIEWPOINT_GRID_CELL_SIZE_M,
    seed: int = 313,
    env_factory: Callable[[OfficialObjectNavRunConfig], Any] | None = None,
) -> dict[str, Any]:
    policy_path = Path(policy_trace_path)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    safe_max_states = None if max_states is None else max(0, int(max_states))
    safe_max_states_per_category = (
        None
        if max_states_per_category is None
        else max(0, int(max_states_per_category))
    )
    safe_max_states_per_category_episode = (
        None
        if max_states_per_category_episode is None
        else max(0, int(max_states_per_category_episode))
    )
    safe_state_sampling = _state_sampling_mode(state_sampling)
    safe_candidates_per_state = max(1, int(candidates_per_state))
    safe_heading_count = max(1, int(viewpoint_heading_count))
    safe_grid_size = _safe_viewpoint_grid_size(viewpoint_grid_size_cells)
    safe_cell_size = _safe_viewpoint_grid_cell_size(viewpoint_grid_cell_size_m)
    payload = _load_object(policy_path)
    steps = _policy_steps(payload)
    replay_budget_steps = max(1, _max_step_index(steps) + 1)
    config = OfficialObjectNavRunConfig(
        config_path=str(config_path),
        dataset_data_path=str(dataset_data_path),
        scene_root=str(scene_root),
        split=split,
        policy="memory_active_perception_frontier",
        max_episodes=None,
        max_steps=replay_budget_steps,
        seed=seed,
        validate_habitat=False,
    )
    candidate_states = _candidate_states(
        steps,
        max_states=safe_max_states,
        max_states_per_category=safe_max_states_per_category,
        max_states_per_category_episode=safe_max_states_per_category_episode,
        state_sampling=safe_state_sampling,
    )
    make_env = env_factory or _make_habitat_env
    rows: list[dict[str, Any]] = []
    skipped_state_count = 0
    for state_index, step in enumerate(candidate_states):
        memory_prior = _mapping(step.get("memory_prior"))
        top_candidates = _memory_top_candidates(memory_prior)
        if not top_candidates:
            skipped_state_count += 1
            continue
        env = make_env(config)
        try:
            replay = _replay_to_policy_state(env, steps=steps, target_step=step)
            state_features = _predecision_state_features(
                step=step,
                observation=replay.observation,
            )
            current_evidence = _current_restore_evidence(
                step=step,
                replay=replay,
                target_detector_adapter=target_detector_adapter,
                target_detector_min_confidence=target_detector_min_confidence,
            )
            for candidate_rank, candidate in enumerate(
                top_candidates[:safe_candidates_per_state]
            ):
                rows.append(
                    _evaluate_candidate_viewpoint_restore(
                        policy_path=policy_path,
                        state_index=state_index,
                        step=step,
                        candidate=candidate,
                        candidate_rank=candidate_rank,
                        candidate_count=len(top_candidates),
                        replay=replay,
                        env=env,
                        state_features=state_features,
                        current_evidence=current_evidence,
                        target_detector_adapter=target_detector_adapter,
                        target_detector_min_confidence=(
                            target_detector_min_confidence
                        ),
                        viewpoint_heading_count=safe_heading_count,
                        viewpoint_grid_size_cells=safe_grid_size,
                        viewpoint_grid_cell_size_m=safe_cell_size,
                    )
                )
        finally:
            close = getattr(env, "close", None)
            if callable(close):
                close()
    return {
        "task": "habitat_official_candidate_viewpoint_restore_dataset",
        "schema_version": CANDIDATE_VIEWPOINT_RESTORE_SCHEMA_VERSION,
        "source_policy_trace": str(policy_path),
        "config": asdict(config),
        "candidate_state_limit": safe_max_states,
        "candidate_state_limit_per_category": safe_max_states_per_category,
        "candidate_state_limit_per_category_episode": (
            safe_max_states_per_category_episode
        ),
        "candidate_state_sampling": safe_state_sampling,
        "candidates_per_state": safe_candidates_per_state,
        "viewpoint_heading_count": safe_heading_count,
        "viewpoint_grid_size_cells": safe_grid_size,
        "viewpoint_grid_cell_size_m": safe_cell_size,
        "state_count": len(candidate_states),
        "skipped_state_count": skipped_state_count,
        "candidate_viewpoint_count": len(rows),
        "valid_state_restore_count": sum(
            1 for row in rows if row["valid_state_restore"]
        ),
        "valid_candidate_restore_count": sum(
            1 for row in rows if row["valid_candidate_restore"]
        ),
        "invalid_candidate_restore_count": sum(
            1 for row in rows if not row["valid_candidate_restore"]
        ),
        "label_available_count": sum(
            1 for row in rows if row["labels"]["label_available"] is True
        ),
        "target_visible_candidate_viewpoint_count": sum(
            1
            for row in rows
            if row["labels"]["target_visible_from_candidate_viewpoint"] is True
        ),
        "hidden_to_visible_candidate_viewpoint_count": sum(
            1
            for row in rows
            if row["labels"]["hidden_to_visible_from_candidate_viewpoint"] is True
        ),
        "candidate_viewpoints": rows,
    }


def export_official_candidate_option_value_dataset(
    policy_trace_path: str | Path,
    *,
    output_dir: str | Path,
    config_path: str,
    dataset_data_path: str,
    scene_root: str,
    split: str = "val_mini",
    target_detector_adapter: Any | None = None,
    target_detector_min_confidence: float = 0.25,
    max_states: int | None = None,
    max_states_per_category: int | None = None,
    max_states_per_category_episode: int | None = None,
    state_sampling: str = "trace_order",
    candidates_per_state: int = 5,
    option_horizon_steps: int = DEFAULT_OPTION_HORIZON_STEPS,
    option_scan_steps: int = DEFAULT_OPTION_SCAN_STEPS,
    option_progress_threshold_m: float = DEFAULT_OPTION_PROGRESS_THRESHOLD_M,
    viewpoint_grid_size_cells: int = DEFAULT_VIEWPOINT_GRID_SIZE_CELLS,
    viewpoint_grid_cell_size_m: float = DEFAULT_VIEWPOINT_GRID_CELL_SIZE_M,
    seed: int = 313,
    env_factory: Callable[[OfficialObjectNavRunConfig], Any] | None = None,
) -> dict[str, Any]:
    policy_path = Path(policy_trace_path)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    safe_max_states = None if max_states is None else max(0, int(max_states))
    safe_max_states_per_category = (
        None
        if max_states_per_category is None
        else max(0, int(max_states_per_category))
    )
    safe_max_states_per_category_episode = (
        None
        if max_states_per_category_episode is None
        else max(0, int(max_states_per_category_episode))
    )
    safe_state_sampling = _state_sampling_mode(state_sampling)
    safe_candidates_per_state = max(1, int(candidates_per_state))
    safe_horizon_steps = max(1, int(option_horizon_steps))
    safe_scan_steps = max(1, int(option_scan_steps))
    safe_progress_threshold_m = max(0.0, float(option_progress_threshold_m))
    safe_grid_size = _safe_viewpoint_grid_size(viewpoint_grid_size_cells)
    safe_cell_size = _safe_viewpoint_grid_cell_size(viewpoint_grid_cell_size_m)
    payload = _load_object(policy_path)
    steps = _policy_steps(payload)
    replay_budget_steps = max(1, _max_step_index(steps) + safe_horizon_steps + 1)
    config = OfficialObjectNavRunConfig(
        config_path=str(config_path),
        dataset_data_path=str(dataset_data_path),
        scene_root=str(scene_root),
        split=split,
        policy="memory_active_perception_frontier",
        max_episodes=None,
        max_steps=replay_budget_steps,
        seed=seed,
        validate_habitat=False,
    )
    candidate_states = _candidate_states(
        steps,
        max_states=safe_max_states,
        max_states_per_category=safe_max_states_per_category,
        max_states_per_category_episode=safe_max_states_per_category_episode,
        state_sampling=safe_state_sampling,
    )
    make_env = env_factory or _make_habitat_env
    rows: list[dict[str, Any]] = []
    skipped_state_count = 0
    for state_index, step in enumerate(candidate_states):
        memory_prior = _mapping(step.get("memory_prior"))
        top_candidates = _memory_top_candidates(memory_prior)
        if not top_candidates:
            skipped_state_count += 1
            continue
        state_features: Mapping[str, Any] | None = None
        current_evidence: Mapping[str, Any] | None = None
        for candidate_rank, candidate in enumerate(
            top_candidates[:safe_candidates_per_state]
        ):
            env = make_env(config)
            try:
                replay = _replay_to_policy_state(env, steps=steps, target_step=step)
                if state_features is None:
                    state_features = _predecision_state_features(
                        step=step,
                        observation=replay.observation,
                    )
                if current_evidence is None:
                    current_evidence = _current_restore_evidence(
                        step=step,
                        replay=replay,
                        target_detector_adapter=target_detector_adapter,
                        target_detector_min_confidence=(
                            target_detector_min_confidence
                        ),
                    )
                rows.append(
                    _evaluate_candidate_option_value(
                        policy_path=policy_path,
                        state_index=state_index,
                        step=step,
                        candidate=candidate,
                        candidate_rank=candidate_rank,
                        candidate_count=len(top_candidates),
                        replay=replay,
                        env=env,
                        state_features=state_features,
                        current_evidence=current_evidence,
                        target_detector_adapter=target_detector_adapter,
                        target_detector_min_confidence=(
                            target_detector_min_confidence
                        ),
                        option_horizon_steps=safe_horizon_steps,
                        option_scan_steps=safe_scan_steps,
                        option_progress_threshold_m=safe_progress_threshold_m,
                        viewpoint_grid_size_cells=safe_grid_size,
                        viewpoint_grid_cell_size_m=safe_cell_size,
                    )
                )
            finally:
                close = getattr(env, "close", None)
                if callable(close):
                    close()
    return {
        "task": "habitat_official_candidate_option_value_dataset",
        "schema_version": CANDIDATE_OPTION_VALUE_SCHEMA_VERSION,
        "source_policy_trace": str(policy_path),
        "config": asdict(config),
        "candidate_state_limit": safe_max_states,
        "candidate_state_limit_per_category": safe_max_states_per_category,
        "candidate_state_limit_per_category_episode": (
            safe_max_states_per_category_episode
        ),
        "candidate_state_sampling": safe_state_sampling,
        "candidates_per_state": safe_candidates_per_state,
        "option_horizon_steps": safe_horizon_steps,
        "option_scan_steps": safe_scan_steps,
        "option_progress_threshold_m": safe_progress_threshold_m,
        "viewpoint_grid_size_cells": safe_grid_size,
        "viewpoint_grid_cell_size_m": safe_cell_size,
        "state_count": len(candidate_states),
        "skipped_state_count": skipped_state_count,
        "candidate_option_count": len(rows),
        "positive_option_count": sum(
            1
            for row in rows
            if row["labels"]["hidden_to_visible_within_option_rollout"] is True
        ),
        "invalid_option_count": sum(
            1 for row in rows if not row["valid_option_rollout"]
        ),
        "candidate_viewpoints": rows,
    }


def write_official_candidate_rollout_dataset_csv(
    dataset: Mapping[str, Any],
    path: str | Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = dataset.get("rollouts", [])
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        if not isinstance(rows, Sequence):
            return
        for rollout in rows:
            if not isinstance(rollout, Mapping):
                continue
            labels = rollout.get("labels", {})
            if not isinstance(labels, Mapping):
                labels = {}
            row = {field: rollout.get(field) for field in _CSV_FIELDS}
            state_features = rollout.get("state_features", {})
            if isinstance(state_features, Mapping):
                row.update(
                    {field: state_features.get(field) for field in STATE_FEATURE_FIELDS}
                )
            for field in (
                "label_available",
                "current_target_visible",
                "target_visible_within_rollout",
                "hidden_to_visible_within_rollout",
            ):
                row[field] = labels.get(field)
            writer.writerow({field: _csv_value(row.get(field)) for field in _CSV_FIELDS})


def write_official_candidate_state_restore_dataset_csv(
    dataset: Mapping[str, Any],
    path: str | Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = dataset.get("states", [])
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_STATE_RESTORE_CSV_FIELDS)
        writer.writeheader()
        if not isinstance(rows, Sequence):
            return
        for state in rows:
            if not isinstance(state, Mapping):
                continue
            labels = state.get("labels", {})
            if not isinstance(labels, Mapping):
                labels = {}
            row = {field: state.get(field) for field in _STATE_RESTORE_CSV_FIELDS}
            state_features = state.get("state_features", {})
            if isinstance(state_features, Mapping):
                row.update(
                    {field: state_features.get(field) for field in STATE_FEATURE_FIELDS}
                )
            for field in (
                "label_available",
                "target_visible_at_restore",
                "hidden_at_restore",
            ):
                row[field] = labels.get(field)
            writer.writerow(
                {
                    field: _csv_value(row.get(field))
                    for field in _STATE_RESTORE_CSV_FIELDS
                }
            )


def write_official_candidate_viewpoint_restore_dataset_csv(
    dataset: Mapping[str, Any],
    path: str | Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = dataset.get("candidate_viewpoints", [])
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=_CANDIDATE_VIEWPOINT_RESTORE_CSV_FIELDS,
        )
        writer.writeheader()
        if not isinstance(rows, Sequence):
            return
        for candidate in rows:
            if not isinstance(candidate, Mapping):
                continue
            labels = candidate.get("labels", {})
            if not isinstance(labels, Mapping):
                labels = {}
            row = {
                field: candidate.get(field)
                for field in _CANDIDATE_VIEWPOINT_RESTORE_CSV_FIELDS
            }
            state_features = candidate.get("state_features", {})
            if isinstance(state_features, Mapping):
                row.update(
                    {field: state_features.get(field) for field in STATE_FEATURE_FIELDS}
                )
            for field in (
                "label_available",
                "current_target_visible_at_restore",
                "target_visible_from_candidate_viewpoint",
                "hidden_to_visible_from_candidate_viewpoint",
            ):
                row[field] = labels.get(field)
            writer.writerow(
                {
                    field: _csv_value(row.get(field))
                    for field in _CANDIDATE_VIEWPOINT_RESTORE_CSV_FIELDS
                }
            )


def write_official_candidate_option_value_dataset_csv(
    dataset: Mapping[str, Any],
    path: str | Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = dataset.get("candidate_viewpoints", [])
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=_CANDIDATE_OPTION_VALUE_CSV_FIELDS,
        )
        writer.writeheader()
        if not isinstance(rows, Sequence):
            return
        for candidate in rows:
            if not isinstance(candidate, Mapping):
                continue
            labels = candidate.get("labels", {})
            if not isinstance(labels, Mapping):
                labels = {}
            row = {
                field: candidate.get(field)
                for field in _CANDIDATE_OPTION_VALUE_CSV_FIELDS
            }
            state_features = candidate.get("state_features", {})
            if isinstance(state_features, Mapping):
                row.update(
                    {field: state_features.get(field) for field in STATE_FEATURE_FIELDS}
                )
            for field in (
                "label_available",
                "current_target_visible_at_restore",
                "target_visible_within_option_rollout",
                "hidden_to_visible_within_option_rollout",
                "detector_confidence_gain_within_option_rollout",
                "official_progress_within_option_rollout",
                "official_stop_success_after_option_rollout",
            ):
                row[field] = labels.get(field)
            writer.writerow(
                {
                    field: _csv_value(row.get(field))
                    for field in _CANDIDATE_OPTION_VALUE_CSV_FIELDS
                }
            )


def build_official_candidate_rollout_action_matrix_report(
    datasets: Sequence[Mapping[str, Any]],
    *,
    current_hidden_only: bool = True,
    actions: Sequence[str] = ("move_forward", "turn_left", "turn_right"),
) -> dict[str, Any]:
    selected_actions = tuple(str(action) for action in actions if str(action))
    if not selected_actions:
        raise ValueError("at least one action is required")

    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    rollout_count = 0
    skipped_current_visible_count = 0
    for dataset_index, dataset in enumerate(datasets):
        rollouts = dataset.get("rollouts", [])
        if not isinstance(rollouts, Sequence):
            continue
        for rollout in rollouts:
            if not isinstance(rollout, Mapping):
                continue
            labels = rollout.get("labels", {})
            if not isinstance(labels, Mapping):
                labels = {}
            if current_hidden_only and bool(labels.get("current_target_visible")):
                skipped_current_visible_count += 1
                continue
            branch_action = str(rollout.get("branch_action") or "")
            if branch_action not in selected_actions:
                continue
            group = groups.setdefault(
                _action_matrix_state_key(dataset_index, rollout),
                _action_matrix_state_template(dataset_index, dataset, rollout),
            )
            success = bool(labels.get("hidden_to_visible_within_rollout"))
            rollout_actions = rollout.get("rollout_actions", [])
            if not isinstance(rollout_actions, Sequence) or isinstance(
                rollout_actions, (str, bytes)
            ):
                rollout_actions = []
            action_count = len(rollout_actions)
            group["actions"][branch_action] = {
                "success": success,
                "time_to_visible_steps": action_count if success else None,
                "rollout_action_count": action_count,
            }
            rollout_count += 1

    state_rows = [
        _action_matrix_state_report(group, actions=selected_actions)
        for group in groups.values()
    ]
    aggregate = _action_matrix_aggregate(state_rows, actions=selected_actions)
    return {
        "task": "habitat_official_candidate_rollout_action_matrix_report",
        "dataset_count": len(datasets),
        "current_hidden_only": bool(current_hidden_only),
        "actions": list(selected_actions),
        "state_count": len(state_rows),
        "rollout_count": rollout_count,
        "skipped_current_visible_count": skipped_current_visible_count,
        "aggregate": aggregate,
        "states": state_rows,
    }


def write_official_candidate_rollout_action_matrix_report_csv(
    report: Mapping[str, Any],
    path: str | Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    actions = [str(action) for action in report.get("actions", []) if str(action)]
    action_fields = [
        field
        for action in actions
        for field in (f"{action}_success", f"{action}_time_to_visible_steps")
    ]
    fieldnames = (
        "source_dataset",
        "source_policy_trace",
        "state_index",
        "episode_index",
        "episode_id",
        "scene_id",
        "target_category",
        "step_index",
        "state_action",
        "state_decision",
        *STATE_FEATURE_FIELDS,
        "positive_action_count",
        "fastest_actions",
        "strict_fastest_action",
        "oracle_recovered",
        *action_fields,
    )
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        states = report.get("states", [])
        if not isinstance(states, Sequence):
            return
        for state in states:
            if not isinstance(state, Mapping):
                continue
            row = {field: state.get(field) for field in fieldnames}
            state_features = state.get("state_features", {})
            if isinstance(state_features, Mapping):
                row.update(
                    {field: state_features.get(field) for field in STATE_FEATURE_FIELDS}
                )
            action_payloads = state.get("actions", {})
            if not isinstance(action_payloads, Mapping):
                action_payloads = {}
            for action in actions:
                action_payload = action_payloads.get(action, {})
                if not isinstance(action_payload, Mapping):
                    action_payload = {}
                row[f"{action}_success"] = action_payload.get("success")
                row[f"{action}_time_to_visible_steps"] = action_payload.get(
                    "time_to_visible_steps"
                )
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _evaluate_candidate_viewpoint_restore(
    *,
    policy_path: Path,
    state_index: int,
    step: Mapping[str, Any],
    candidate: Mapping[str, Any],
    candidate_rank: int,
    candidate_count: int,
    replay: _ReplayResult,
    env: Any,
    state_features: Mapping[str, Any],
    current_evidence: Mapping[str, Any],
    target_detector_adapter: Any | None,
    target_detector_min_confidence: float,
    viewpoint_heading_count: int,
    viewpoint_grid_size_cells: int,
    viewpoint_grid_cell_size_m: float,
) -> dict[str, Any]:
    pose = _candidate_viewpoint_pose_from_cell(
        candidate.get("viewpoint_cell") or candidate.get("frontier_cell"),
        grid_size_cells=viewpoint_grid_size_cells,
        grid_cell_size_m=viewpoint_grid_cell_size_m,
    )
    if not replay.valid or replay.observation is None:
        return _candidate_viewpoint_restore_row(
            policy_path=policy_path,
            state_index=state_index,
            step=step,
            candidate=candidate,
            candidate_rank=candidate_rank,
            candidate_count=candidate_count,
            replay_actions=replay.replay_actions,
            state_features=state_features,
            pose=pose,
            viewpoint_heading_count=viewpoint_heading_count,
            visible_heading_count=0,
            best_detector_confidence=None,
            valid_state_restore=False,
            valid_candidate_restore=False,
            invalid_reason=replay.invalid_reason or "replay_failed",
            labels=_candidate_viewpoint_labels(
                current_visible=False,
                current_label_available=False,
                candidate_visible=False,
                candidate_label_available=False,
            ),
        )
    if pose is None:
        return _candidate_viewpoint_restore_row(
            policy_path=policy_path,
            state_index=state_index,
            step=step,
            candidate=candidate,
            candidate_rank=candidate_rank,
            candidate_count=candidate_count,
            replay_actions=replay.replay_actions,
            state_features=state_features,
            pose=None,
            viewpoint_heading_count=viewpoint_heading_count,
            visible_heading_count=0,
            best_detector_confidence=None,
            valid_state_restore=True,
            valid_candidate_restore=False,
            invalid_reason="invalid_candidate_viewpoint_cell",
            labels=_candidate_viewpoint_labels(
                current_visible=bool(current_evidence.get("target_visible")),
                current_label_available=bool(current_evidence.get("label_available")),
                candidate_visible=False,
                candidate_label_available=False,
            ),
        )

    target_category = str(step.get("target_category", ""))
    visible_heading_count = 0
    label_available = False
    best_detector_confidence: float | None = None
    attempted_heading_count = 0
    invalid_reason: str | None = None
    for heading in _viewpoint_scan_headings(viewpoint_heading_count):
        restore = _restore_candidate_viewpoint_observation(
            env,
            x_m=float(pose["candidate_x_m"]),
            z_m=float(pose["candidate_z_m"]),
            heading_rad=heading,
        )
        if not restore.valid or restore.observation is None:
            invalid_reason = restore.invalid_reason or "candidate_restore_failed"
            break
        attempted_heading_count += 1
        evidence = _detect_target_evidence(
            restore.observation,
            target_detector_adapter=target_detector_adapter,
            target_category=target_category,
            min_confidence=target_detector_min_confidence,
        )
        label_available = label_available or bool(evidence.get("label_available"))
        if evidence.get("target_visible"):
            visible_heading_count += 1
        confidence = _optional_float(evidence.get("detector_confidence"))
        if confidence is not None:
            best_detector_confidence = (
                confidence
                if best_detector_confidence is None
                else max(best_detector_confidence, confidence)
            )

    valid_candidate_restore = invalid_reason is None and attempted_heading_count > 0
    candidate_visible = visible_heading_count > 0
    return _candidate_viewpoint_restore_row(
        policy_path=policy_path,
        state_index=state_index,
        step=step,
        candidate=candidate,
        candidate_rank=candidate_rank,
        candidate_count=candidate_count,
        replay_actions=replay.replay_actions,
        state_features=state_features,
        pose=pose,
        viewpoint_heading_count=viewpoint_heading_count,
        visible_heading_count=visible_heading_count,
        best_detector_confidence=best_detector_confidence,
        valid_state_restore=True,
        valid_candidate_restore=valid_candidate_restore,
        invalid_reason=None if valid_candidate_restore else invalid_reason,
        labels=_candidate_viewpoint_labels(
            current_visible=bool(current_evidence.get("target_visible")),
            current_label_available=bool(current_evidence.get("label_available")),
            candidate_visible=candidate_visible,
            candidate_label_available=label_available and valid_candidate_restore,
        ),
    )


def _candidate_viewpoint_restore_row(
    *,
    policy_path: Path,
    state_index: int,
    step: Mapping[str, Any],
    candidate: Mapping[str, Any],
    candidate_rank: int,
    candidate_count: int,
    replay_actions: Sequence[str],
    state_features: Mapping[str, Any],
    pose: Mapping[str, Any] | None,
    viewpoint_heading_count: int,
    visible_heading_count: int,
    best_detector_confidence: float | None,
    valid_state_restore: bool,
    valid_candidate_restore: bool,
    invalid_reason: str | None,
    labels: Mapping[str, bool],
) -> dict[str, Any]:
    viewpoint = _optional_cell(candidate.get("viewpoint_cell"))
    frontier = _optional_cell(candidate.get("frontier_cell"))
    pose_values = dict(pose or {})
    return {
        "source_policy_trace": str(policy_path),
        "state_index": int(state_index),
        "episode_index": _int(step.get("episode_index")),
        "episode_id": str(step.get("episode_id", "")),
        "scene_id": str(step.get("scene_id", "")),
        "target_category": str(step.get("target_category", "")),
        "policy": str(step.get("policy", "")),
        "policy_kind": str(step.get("policy_kind", "")),
        "step_index": _int(step.get("step_index")),
        "state_action": str(step.get("action", "")),
        "state_decision": str(step.get("decision", "")),
        "candidate_rank": int(candidate_rank),
        "candidate_count": int(candidate_count),
        "candidate_score": _optional_float(candidate.get("score")),
        "expected_evidence": _optional_float(candidate.get("expected_evidence")),
        "belief_mass": _optional_float(candidate.get("belief_mass")),
        "distance_to_anchor_m": _optional_float(candidate.get("distance_to_anchor_m")),
        "bearing_rad": _optional_float(candidate.get("bearing_rad")),
        "bearing_error_rad": _optional_float(candidate.get("bearing_error_rad")),
        "view_quality": _optional_float(candidate.get("view_quality")),
        "view_bearing_quality": _optional_float(candidate.get("view_bearing_quality")),
        "view_distance_quality": _optional_float(candidate.get("view_distance_quality")),
        "path_distance_m": _optional_float(candidate.get("path_distance_m")),
        "travel_distance_m": _optional_float(candidate.get("travel_distance_m")),
        "viewpoint_row": viewpoint[0],
        "viewpoint_col": viewpoint[1],
        "frontier_row": frontier[0],
        "frontier_col": frontier[1],
        "grid_size_cells": pose_values.get("grid_size_cells"),
        "grid_cell_size_m": pose_values.get("grid_cell_size_m"),
        "grid_origin_row": pose_values.get("grid_origin_row"),
        "grid_origin_col": pose_values.get("grid_origin_col"),
        "candidate_x_m": pose_values.get("candidate_x_m"),
        "candidate_z_m": pose_values.get("candidate_z_m"),
        "viewpoint_heading_count": int(viewpoint_heading_count),
        "visible_heading_count": int(visible_heading_count),
        "best_detector_confidence": _optional_float(best_detector_confidence),
        "valid_state_restore": bool(valid_state_restore),
        "valid_candidate_restore": bool(valid_candidate_restore),
        "invalid_reason": invalid_reason,
        "replay_actions": list(replay_actions),
        "state_features": dict(state_features),
        "labels": {
            "label_available": bool(labels.get("label_available")),
            "current_target_visible_at_restore": bool(
                labels.get("current_target_visible_at_restore")
            ),
            "target_visible_from_candidate_viewpoint": bool(
                labels.get("target_visible_from_candidate_viewpoint")
            ),
            "hidden_to_visible_from_candidate_viewpoint": bool(
                labels.get("hidden_to_visible_from_candidate_viewpoint")
            ),
        },
    }


def _current_restore_evidence(
    *,
    step: Mapping[str, Any],
    replay: _ReplayResult,
    target_detector_adapter: Any | None,
    target_detector_min_confidence: float,
) -> dict[str, Any]:
    if not replay.valid or replay.observation is None:
        return {
            "label_available": False,
            "target_visible": False,
            "target_match_count": 0,
            "detector_confidence": None,
            "missing_rgb": False,
        }
    return _detect_target_evidence(
        replay.observation,
        target_detector_adapter=target_detector_adapter,
        target_category=str(step.get("target_category", "")),
        min_confidence=target_detector_min_confidence,
    )


def _candidate_viewpoint_labels(
    *,
    current_visible: bool,
    current_label_available: bool,
    candidate_visible: bool,
    candidate_label_available: bool,
) -> dict[str, bool]:
    label_available = bool(current_label_available and candidate_label_available)
    return {
        "label_available": label_available,
        "current_target_visible_at_restore": bool(
            current_label_available and current_visible
        ),
        "target_visible_from_candidate_viewpoint": bool(
            candidate_label_available and candidate_visible
        ),
        "hidden_to_visible_from_candidate_viewpoint": bool(
            label_available and not current_visible and candidate_visible
        ),
    }


def _evaluate_state_restore(
    *,
    policy_path: Path,
    state_index: int,
    step: Mapping[str, Any],
    candidate: Mapping[str, Any],
    candidate_rank: int,
    candidate_count: int,
    replay: _ReplayResult,
    target_detector_adapter: Any | None,
    target_detector_min_confidence: float,
) -> dict[str, Any]:
    state_features = _predecision_state_features(
        step=step,
        observation=replay.observation,
    )
    if not replay.valid or replay.observation is None:
        return _state_restore_row(
            policy_path=policy_path,
            state_index=state_index,
            step=step,
            candidate=candidate,
            candidate_rank=candidate_rank,
            candidate_count=candidate_count,
            replay_actions=replay.replay_actions,
            state_features=state_features,
            valid_restore=False,
            invalid_reason=replay.invalid_reason or "replay_failed",
            labels={
                "label_available": False,
                "target_visible_at_restore": False,
                "hidden_at_restore": False,
            },
        )

    target_category = str(step.get("target_category", ""))
    evidence = _detect_target_evidence(
        replay.observation,
        target_detector_adapter=target_detector_adapter,
        target_category=target_category,
        min_confidence=target_detector_min_confidence,
    )
    label_available = bool(evidence["label_available"])
    target_visible = bool(evidence["target_visible"])
    return _state_restore_row(
        policy_path=policy_path,
        state_index=state_index,
        step=step,
        candidate=candidate,
        candidate_rank=candidate_rank,
        candidate_count=candidate_count,
        replay_actions=replay.replay_actions,
        state_features=state_features,
        valid_restore=True,
        invalid_reason=None,
        labels={
            "label_available": label_available,
            "target_visible_at_restore": target_visible,
            "hidden_at_restore": label_available and not target_visible,
        },
    )


def _state_restore_row(
    *,
    policy_path: Path,
    state_index: int,
    step: Mapping[str, Any],
    candidate: Mapping[str, Any],
    candidate_rank: int,
    candidate_count: int,
    replay_actions: Sequence[str],
    state_features: Mapping[str, Any],
    valid_restore: bool,
    invalid_reason: str | None,
    labels: Mapping[str, bool],
) -> dict[str, Any]:
    viewpoint = _optional_cell(candidate.get("viewpoint_cell"))
    frontier = _optional_cell(candidate.get("frontier_cell"))
    return {
        "source_policy_trace": str(policy_path),
        "state_index": int(state_index),
        "episode_index": _int(step.get("episode_index")),
        "episode_id": str(step.get("episode_id", "")),
        "scene_id": str(step.get("scene_id", "")),
        "target_category": str(step.get("target_category", "")),
        "policy": str(step.get("policy", "")),
        "policy_kind": str(step.get("policy_kind", "")),
        "step_index": _int(step.get("step_index")),
        "state_action": str(step.get("action", "")),
        "state_decision": str(step.get("decision", "")),
        "candidate_rank": int(candidate_rank),
        "candidate_count": int(candidate_count),
        "candidate_score": _optional_float(candidate.get("score")),
        "expected_evidence": _optional_float(candidate.get("expected_evidence")),
        "belief_mass": _optional_float(candidate.get("belief_mass")),
        "distance_to_anchor_m": _optional_float(candidate.get("distance_to_anchor_m")),
        "bearing_rad": _optional_float(candidate.get("bearing_rad")),
        "bearing_error_rad": _optional_float(candidate.get("bearing_error_rad")),
        "view_quality": _optional_float(candidate.get("view_quality")),
        "view_bearing_quality": _optional_float(candidate.get("view_bearing_quality")),
        "view_distance_quality": _optional_float(candidate.get("view_distance_quality")),
        "path_distance_m": _optional_float(candidate.get("path_distance_m")),
        "travel_distance_m": _optional_float(candidate.get("travel_distance_m")),
        "viewpoint_row": viewpoint[0],
        "viewpoint_col": viewpoint[1],
        "frontier_row": frontier[0],
        "frontier_col": frontier[1],
        "valid_restore": bool(valid_restore),
        "invalid_reason": invalid_reason,
        "replay_actions": list(replay_actions),
        "state_features": dict(state_features),
        "labels": {
            "label_available": bool(labels.get("label_available")),
            "target_visible_at_restore": bool(
                labels.get("target_visible_at_restore")
            ),
            "hidden_at_restore": bool(labels.get("hidden_at_restore")),
        },
    }


def _evaluate_candidate_option_value(
    *,
    policy_path: Path,
    state_index: int,
    step: Mapping[str, Any],
    candidate: Mapping[str, Any],
    candidate_rank: int,
    candidate_count: int,
    replay: _ReplayResult,
    env: Any,
    state_features: Mapping[str, Any],
    current_evidence: Mapping[str, Any],
    target_detector_adapter: Any | None,
    target_detector_min_confidence: float,
    option_horizon_steps: int,
    option_scan_steps: int,
    option_progress_threshold_m: float,
    viewpoint_grid_size_cells: int,
    viewpoint_grid_cell_size_m: float,
) -> dict[str, Any]:
    pose = _candidate_option_pose(
        candidate,
        grid_size_cells=viewpoint_grid_size_cells,
        grid_cell_size_m=viewpoint_grid_cell_size_m,
    )
    if not replay.valid or replay.observation is None:
        return _candidate_option_value_row(
            policy_path=policy_path,
            state_index=state_index,
            step=step,
            candidate=candidate,
            candidate_rank=candidate_rank,
            candidate_count=candidate_count,
            replay_actions=replay.replay_actions,
            option_rollout_actions=(),
            state_features=state_features,
            pose=pose,
            option_horizon_steps=option_horizon_steps,
            option_scan_steps=option_scan_steps,
            option_scan_step_count=0,
            option_blocked_scan_step_count=0,
            initial_detector_confidence=None,
            best_detector_confidence=None,
            initial_distance_to_goal_m=None,
            final_distance_to_goal_m=None,
            min_distance_to_goal_m=None,
            stop_probe_metrics=None,
            valid_option_rollout=False,
            invalid_reason=replay.invalid_reason or "replay_failed",
            labels=_candidate_option_value_labels(
                current_visible=False,
                current_label_available=False,
                option_visible=False,
                option_label_available=False,
                detector_confidence_gain=None,
                best_distance_to_goal_delta_m=None,
                option_progress_threshold_m=option_progress_threshold_m,
                stop_probe_success=None,
            ),
        )
    if pose is None:
        return _candidate_option_value_row(
            policy_path=policy_path,
            state_index=state_index,
            step=step,
            candidate=candidate,
            candidate_rank=candidate_rank,
            candidate_count=candidate_count,
            replay_actions=replay.replay_actions,
            option_rollout_actions=(),
            state_features=state_features,
            pose=None,
            option_horizon_steps=option_horizon_steps,
            option_scan_steps=option_scan_steps,
            option_scan_step_count=0,
            option_blocked_scan_step_count=0,
            initial_detector_confidence=_optional_float(
                current_evidence.get("detector_confidence")
            ),
            best_detector_confidence=None,
            initial_distance_to_goal_m=None,
            final_distance_to_goal_m=None,
            min_distance_to_goal_m=None,
            stop_probe_metrics=None,
            valid_option_rollout=False,
            invalid_reason="invalid_candidate_option_pose",
            labels=_candidate_option_value_labels(
                current_visible=bool(current_evidence.get("target_visible")),
                current_label_available=bool(current_evidence.get("label_available")),
                option_visible=False,
                option_label_available=False,
                detector_confidence_gain=None,
                best_distance_to_goal_delta_m=None,
                option_progress_threshold_m=option_progress_threshold_m,
                stop_probe_success=None,
            ),
        )

    target_category = str(step.get("target_category", ""))
    label_available = bool(current_evidence.get("label_available"))
    current_visible = bool(current_evidence.get("target_visible"))
    target_visible_within_option = current_visible
    initial_detector_confidence = _optional_float(
        current_evidence.get("detector_confidence")
    )
    best_detector_confidence = initial_detector_confidence
    initial_metrics = _official_option_metrics(env)
    initial_distance_to_goal_m = initial_metrics.get("distance_to_goal")
    final_distance_to_goal_m = initial_distance_to_goal_m
    min_distance_to_goal_m = initial_distance_to_goal_m
    option_state = _CandidateOptionRolloutState()
    option_rollout_actions: list[str] = []
    observation: Mapping[str, Any] = replay.observation
    for _ in range(max(1, int(option_horizon_steps))):
        if target_visible_within_option:
            break
        action = _candidate_option_rollout_action(
            candidate=candidate,
            observation=observation,
            pose=pose,
            option_state=option_state,
            option_scan_steps=option_scan_steps,
            viewpoint_grid_cell_size_m=viewpoint_grid_cell_size_m,
        )
        option_rollout_actions.append(action)
        observation = env.step(action)
        evidence = _detect_target_evidence(
            observation,
            target_detector_adapter=target_detector_adapter,
            target_category=target_category,
            min_confidence=target_detector_min_confidence,
        )
        label_available = label_available or bool(evidence.get("label_available"))
        target_visible_within_option = target_visible_within_option or bool(
            evidence.get("target_visible")
        )
        confidence = _optional_float(evidence.get("detector_confidence"))
        if confidence is not None:
            best_detector_confidence = (
                confidence
                if best_detector_confidence is None
                else max(best_detector_confidence, confidence)
            )
        step_metrics = _official_option_metrics(env)
        step_distance = step_metrics.get("distance_to_goal")
        if step_distance is not None:
            final_distance_to_goal_m = step_distance
            min_distance_to_goal_m = (
                step_distance
                if min_distance_to_goal_m is None
                else min(min_distance_to_goal_m, step_distance)
            )
        if bool(getattr(env, "episode_over", False)):
            break
    stop_probe_metrics = _stop_probe_official_metrics(env)
    best_distance_to_goal_delta_m = _distance_delta(
        initial_distance_to_goal_m,
        min_distance_to_goal_m,
    )

    return _candidate_option_value_row(
        policy_path=policy_path,
        state_index=state_index,
        step=step,
        candidate=candidate,
        candidate_rank=candidate_rank,
        candidate_count=candidate_count,
        replay_actions=replay.replay_actions,
        option_rollout_actions=tuple(option_rollout_actions),
        state_features=state_features,
        pose=pose,
        option_horizon_steps=option_horizon_steps,
        option_scan_steps=option_scan_steps,
        option_scan_step_count=option_state.option_scan_step_count,
        option_blocked_scan_step_count=option_state.option_blocked_scan_step_count,
        initial_detector_confidence=initial_detector_confidence,
        best_detector_confidence=best_detector_confidence,
        initial_distance_to_goal_m=initial_distance_to_goal_m,
        final_distance_to_goal_m=final_distance_to_goal_m,
        min_distance_to_goal_m=min_distance_to_goal_m,
        stop_probe_metrics=stop_probe_metrics,
        valid_option_rollout=True,
        invalid_reason=None,
        labels=_candidate_option_value_labels(
            current_visible=current_visible,
            current_label_available=bool(current_evidence.get("label_available")),
            option_visible=target_visible_within_option,
            option_label_available=label_available,
            detector_confidence_gain=_detector_confidence_gain(
                initial_detector_confidence,
                best_detector_confidence,
            ),
            best_distance_to_goal_delta_m=best_distance_to_goal_delta_m,
            option_progress_threshold_m=option_progress_threshold_m,
            stop_probe_success=stop_probe_metrics.get("success"),
        ),
    )


def _candidate_option_value_row(
    *,
    policy_path: Path,
    state_index: int,
    step: Mapping[str, Any],
    candidate: Mapping[str, Any],
    candidate_rank: int,
    candidate_count: int,
    replay_actions: Sequence[str],
    option_rollout_actions: Sequence[str],
    state_features: Mapping[str, Any],
    pose: Mapping[str, Any] | None,
    option_horizon_steps: int,
    option_scan_steps: int,
    option_scan_step_count: int,
    option_blocked_scan_step_count: int,
    initial_detector_confidence: float | None,
    best_detector_confidence: float | None,
    initial_distance_to_goal_m: float | None,
    final_distance_to_goal_m: float | None,
    min_distance_to_goal_m: float | None,
    stop_probe_metrics: Mapping[str, float | None] | None,
    valid_option_rollout: bool,
    invalid_reason: str | None,
    labels: Mapping[str, bool],
) -> dict[str, Any]:
    viewpoint = _optional_cell(candidate.get("viewpoint_cell"))
    frontier = _optional_cell(candidate.get("frontier_cell"))
    pose_values = dict(pose or {})
    detector_confidence_gain = _detector_confidence_gain(
        initial_detector_confidence,
        best_detector_confidence,
    )
    distance_to_goal_delta_m = _distance_delta(
        initial_distance_to_goal_m,
        final_distance_to_goal_m,
    )
    best_distance_to_goal_delta_m = _distance_delta(
        initial_distance_to_goal_m,
        min_distance_to_goal_m,
    )
    stop_metrics = dict(stop_probe_metrics or {})
    return {
        "source_policy_trace": str(policy_path),
        "state_index": int(state_index),
        "episode_index": _int(step.get("episode_index")),
        "episode_id": str(step.get("episode_id", "")),
        "scene_id": str(step.get("scene_id", "")),
        "target_category": str(step.get("target_category", "")),
        "policy": str(step.get("policy", "")),
        "policy_kind": str(step.get("policy_kind", "")),
        "step_index": _int(step.get("step_index")),
        "state_action": str(step.get("action", "")),
        "state_decision": str(step.get("decision", "")),
        "candidate_rank": int(candidate_rank),
        "candidate_count": int(candidate_count),
        "candidate_score": _optional_float(candidate.get("score")),
        "expected_evidence": _optional_float(candidate.get("expected_evidence")),
        "belief_mass": _optional_float(candidate.get("belief_mass")),
        "distance_to_anchor_m": _optional_float(candidate.get("distance_to_anchor_m")),
        "bearing_rad": _optional_float(candidate.get("bearing_rad")),
        "bearing_error_rad": _optional_float(candidate.get("bearing_error_rad")),
        "view_quality": _optional_float(candidate.get("view_quality")),
        "view_bearing_quality": _optional_float(candidate.get("view_bearing_quality")),
        "view_distance_quality": _optional_float(candidate.get("view_distance_quality")),
        "path_distance_m": _optional_float(candidate.get("path_distance_m")),
        "travel_distance_m": _optional_float(candidate.get("travel_distance_m")),
        "viewpoint_row": viewpoint[0],
        "viewpoint_col": viewpoint[1],
        "frontier_row": frontier[0],
        "frontier_col": frontier[1],
        "grid_size_cells": pose_values.get("grid_size_cells"),
        "grid_cell_size_m": pose_values.get("grid_cell_size_m"),
        "grid_origin_row": pose_values.get("grid_origin_row"),
        "grid_origin_col": pose_values.get("grid_origin_col"),
        "candidate_x_m": pose_values.get("candidate_x_m"),
        "candidate_z_m": pose_values.get("candidate_z_m"),
        "option_horizon_steps": int(option_horizon_steps),
        "option_scan_steps": int(option_scan_steps),
        "option_scan_step_count": int(option_scan_step_count),
        "option_blocked_scan_step_count": int(option_blocked_scan_step_count),
        "initial_detector_confidence": _optional_float(
            initial_detector_confidence
        ),
        "best_detector_confidence": _optional_float(best_detector_confidence),
        "detector_confidence_gain": _optional_float(detector_confidence_gain),
        "initial_distance_to_goal_m": _optional_float(initial_distance_to_goal_m),
        "final_distance_to_goal_m": _optional_float(final_distance_to_goal_m),
        "min_distance_to_goal_m": _optional_float(min_distance_to_goal_m),
        "distance_to_goal_delta_m": _optional_float(distance_to_goal_delta_m),
        "best_distance_to_goal_delta_m": _optional_float(
            best_distance_to_goal_delta_m
        ),
        "stop_probe_success": _optional_float(stop_metrics.get("success")),
        "stop_probe_spl": _optional_float(stop_metrics.get("spl")),
        "stop_probe_softspl": _optional_float(stop_metrics.get("soft_spl")),
        "stop_probe_distance_to_goal_m": _optional_float(
            stop_metrics.get("distance_to_goal")
        ),
        "valid_option_rollout": bool(valid_option_rollout),
        "invalid_reason": invalid_reason,
        "replay_actions": list(replay_actions),
        "option_rollout_actions": list(option_rollout_actions),
        "state_features": dict(state_features),
        "labels": {
            "label_available": bool(labels.get("label_available")),
            "current_target_visible_at_restore": bool(
                labels.get("current_target_visible_at_restore")
            ),
            "target_visible_within_option_rollout": bool(
                labels.get("target_visible_within_option_rollout")
            ),
            "hidden_to_visible_within_option_rollout": bool(
                labels.get("hidden_to_visible_within_option_rollout")
            ),
            "detector_confidence_gain_within_option_rollout": bool(
                labels.get("detector_confidence_gain_within_option_rollout")
            ),
            "official_progress_within_option_rollout": bool(
                labels.get("official_progress_within_option_rollout")
            ),
            "official_stop_success_after_option_rollout": bool(
                labels.get("official_stop_success_after_option_rollout")
            ),
        },
    }


def _candidate_option_value_labels(
    *,
    current_visible: bool,
    current_label_available: bool,
    option_visible: bool,
    option_label_available: bool,
    detector_confidence_gain: float | None,
    best_distance_to_goal_delta_m: float | None,
    option_progress_threshold_m: float,
    stop_probe_success: float | None,
) -> dict[str, bool]:
    label_available = bool(current_label_available and option_label_available)
    progress_delta = _optional_float(best_distance_to_goal_delta_m)
    stop_success = _optional_float(stop_probe_success)
    return {
        "label_available": label_available,
        "current_target_visible_at_restore": bool(
            current_label_available and current_visible
        ),
        "target_visible_within_option_rollout": bool(
            option_label_available and option_visible
        ),
        "hidden_to_visible_within_option_rollout": bool(
            label_available and not current_visible and option_visible
        ),
        "detector_confidence_gain_within_option_rollout": bool(
            label_available
            and detector_confidence_gain is not None
            and float(detector_confidence_gain) > 0.0
        ),
        "official_progress_within_option_rollout": bool(
            progress_delta is not None
            and progress_delta >= max(0.0, float(option_progress_threshold_m))
        ),
        "official_stop_success_after_option_rollout": bool(
            stop_success is not None and stop_success > 0.0
        ),
    }


def _detector_confidence_gain(
    initial_detector_confidence: float | None,
    best_detector_confidence: float | None,
) -> float | None:
    best_confidence = _optional_float(best_detector_confidence)
    if best_confidence is None:
        return None
    initial_confidence = _optional_float(initial_detector_confidence)
    if initial_confidence is None:
        return max(0.0, best_confidence)
    return max(0.0, best_confidence - initial_confidence)


def _distance_delta(
    initial_distance_m: float | None,
    later_distance_m: float | None,
) -> float | None:
    initial = _optional_float(initial_distance_m)
    later = _optional_float(later_distance_m)
    if initial is None or later is None:
        return None
    return round(initial - later, 12)


def _official_option_metrics(env: Any) -> dict[str, float | None]:
    get_metrics = getattr(env, "get_metrics", None)
    if not callable(get_metrics):
        return _empty_official_option_metrics()
    try:
        metrics = get_metrics()
    except Exception:
        return _empty_official_option_metrics()
    if not isinstance(metrics, Mapping):
        return _empty_official_option_metrics()
    return {
        "success": _optional_float(metrics.get("success")),
        "spl": _optional_float(metrics.get("spl")),
        "soft_spl": _optional_float(metrics.get("soft_spl")),
        "distance_to_goal": _optional_float(metrics.get("distance_to_goal")),
    }


def _stop_probe_official_metrics(env: Any) -> dict[str, float | None]:
    if bool(getattr(env, "episode_over", False)):
        return _official_option_metrics(env)
    step = getattr(env, "step", None)
    if not callable(step):
        return _empty_official_option_metrics()
    try:
        step("stop")
    except Exception:
        return _empty_official_option_metrics()
    return _official_option_metrics(env)


def _empty_official_option_metrics() -> dict[str, float | None]:
    return {
        "success": None,
        "spl": None,
        "soft_spl": None,
        "distance_to_goal": None,
    }


def _evaluate_candidate_rollout(
    *,
    policy_path: Path,
    state_index: int,
    step: Mapping[str, Any],
    candidate: Mapping[str, Any],
    candidate_rank: int,
    candidate_count: int,
    branch_kind: str,
    branch_action: Any,
    forced_first_action: Any,
    replay: _ReplayResult,
    env: Any,
    target_detector_adapter: Any | None,
    target_detector_min_confidence: float,
    rollout_horizon_steps: int,
    branch_followup_policy: str,
) -> dict[str, Any]:
    if not replay.valid or replay.observation is None:
        state_features = _predecision_state_features(
            step=step,
            observation=replay.observation,
        )
        return _rollout_row(
            policy_path=policy_path,
            state_index=state_index,
            step=step,
            candidate=candidate,
            candidate_rank=candidate_rank,
            candidate_count=candidate_count,
            branch_kind=branch_kind,
            branch_action=branch_action,
            replay_actions=replay.replay_actions,
            rollout_actions=(),
            state_features=state_features,
            valid_rollout=False,
            invalid_reason=replay.invalid_reason or "replay_failed",
            labels={
                "label_available": False,
                "current_target_visible": False,
                "target_visible_within_rollout": False,
                "hidden_to_visible_within_rollout": False,
            },
        )

    target_category = str(step.get("target_category", ""))
    state_features = _predecision_state_features(
        step=step,
        observation=replay.observation,
    )
    current_evidence = _detect_target_evidence(
        replay.observation,
        target_detector_adapter=target_detector_adapter,
        target_category=target_category,
        min_confidence=target_detector_min_confidence,
    )
    label_available = bool(current_evidence["label_available"])
    current_visible = bool(current_evidence["target_visible"])
    target_visible_within_rollout = current_visible
    rollout_actions: list[str] = []
    observation: Mapping[str, Any] = replay.observation
    for rollout_step in range(rollout_horizon_steps):
        if target_visible_within_rollout:
            break
        action = _candidate_rollout_action(
            candidate,
            observation,
            rollout_step=rollout_step,
            forced_first_action=forced_first_action,
            branch_followup_policy=branch_followup_policy,
        )
        rollout_actions.append(action)
        observation = env.step(action)
        evidence = _detect_target_evidence(
            observation,
            target_detector_adapter=target_detector_adapter,
            target_category=target_category,
            min_confidence=target_detector_min_confidence,
        )
        label_available = label_available or bool(evidence["label_available"])
        target_visible_within_rollout = target_visible_within_rollout or bool(
            evidence["target_visible"]
        )
        if bool(getattr(env, "episode_over", False)):
            break
    return _rollout_row(
        policy_path=policy_path,
        state_index=state_index,
        step=step,
        candidate=candidate,
        candidate_rank=candidate_rank,
        candidate_count=candidate_count,
        branch_kind=branch_kind,
        branch_action=branch_action,
        replay_actions=replay.replay_actions,
        rollout_actions=tuple(rollout_actions),
        state_features=state_features,
        valid_rollout=True,
        invalid_reason=None,
        labels={
            "label_available": label_available,
            "current_target_visible": current_visible,
            "target_visible_within_rollout": target_visible_within_rollout,
            "hidden_to_visible_within_rollout": (
                label_available
                and not current_visible
                and target_visible_within_rollout
            ),
        },
    )


def _rollout_row(
    *,
    policy_path: Path,
    state_index: int,
    step: Mapping[str, Any],
    candidate: Mapping[str, Any],
    candidate_rank: int,
    candidate_count: int,
    branch_kind: str,
    branch_action: Any,
    replay_actions: Sequence[str],
    rollout_actions: Sequence[str],
    state_features: Mapping[str, Any],
    valid_rollout: bool,
    invalid_reason: str | None,
    labels: Mapping[str, bool],
) -> dict[str, Any]:
    viewpoint = _optional_cell(candidate.get("viewpoint_cell"))
    frontier = _optional_cell(candidate.get("frontier_cell"))
    return {
        "source_policy_trace": str(policy_path),
        "state_index": int(state_index),
        "episode_index": _int(step.get("episode_index")),
        "episode_id": str(step.get("episode_id", "")),
        "scene_id": str(step.get("scene_id", "")),
        "target_category": str(step.get("target_category", "")),
        "policy": str(step.get("policy", "")),
        "policy_kind": str(step.get("policy_kind", "")),
        "step_index": _int(step.get("step_index")),
        "state_action": str(step.get("action", "")),
        "state_decision": str(step.get("decision", "")),
        "branch_kind": str(branch_kind),
        "branch_action": str(branch_action) if branch_action is not None else None,
        "candidate_rank": int(candidate_rank),
        "candidate_count": int(candidate_count),
        "candidate_score": _optional_float(candidate.get("score")),
        "expected_evidence": _optional_float(candidate.get("expected_evidence")),
        "belief_mass": _optional_float(candidate.get("belief_mass")),
        "distance_to_anchor_m": _optional_float(candidate.get("distance_to_anchor_m")),
        "bearing_rad": _optional_float(candidate.get("bearing_rad")),
        "bearing_error_rad": _optional_float(candidate.get("bearing_error_rad")),
        "view_quality": _optional_float(candidate.get("view_quality")),
        "view_bearing_quality": _optional_float(candidate.get("view_bearing_quality")),
        "view_distance_quality": _optional_float(candidate.get("view_distance_quality")),
        "path_distance_m": _optional_float(candidate.get("path_distance_m")),
        "travel_distance_m": _optional_float(candidate.get("travel_distance_m")),
        "viewpoint_row": viewpoint[0],
        "viewpoint_col": viewpoint[1],
        "frontier_row": frontier[0],
        "frontier_col": frontier[1],
        "valid_rollout": bool(valid_rollout),
        "invalid_reason": invalid_reason,
        "replay_actions": list(replay_actions),
        "rollout_actions": list(rollout_actions),
        "state_features": dict(state_features),
        "labels": {
            "current_target_visible": bool(labels.get("current_target_visible")),
            "target_visible_within_rollout": bool(
                labels.get("target_visible_within_rollout")
            ),
            "hidden_to_visible_within_rollout": bool(
                labels.get("hidden_to_visible_within_rollout")
            ),
            "label_available": bool(labels.get("label_available")),
        },
    }


def _replay_to_policy_state(
    env: Any,
    *,
    steps: Sequence[Mapping[str, Any]],
    target_step: Mapping[str, Any],
) -> _ReplayResult:
    target_episode_index = _int(target_step.get("episode_index"))
    target_step_index = _int(target_step.get("step_index"))
    observation: Mapping[str, Any] | None = None
    for _ in range(target_episode_index + 1):
        observation = env.reset()
    if observation is None:
        return _ReplayResult(
            observation=None,
            replay_actions=(),
            valid=False,
            invalid_reason="reset_returned_no_observation",
        )
    mismatch = _episode_mismatch(env, target_step)
    if mismatch is not None:
        return _ReplayResult(
            observation=observation,
            replay_actions=(),
            valid=False,
            invalid_reason=mismatch,
        )

    replay_actions: list[str] = []
    for step in steps:
        if _episode_key(step) != _episode_key(target_step):
            continue
        step_index = _int(step.get("step_index"))
        if step_index >= target_step_index:
            break
        action = str(step.get("action", ""))
        replay_actions.append(action)
        observation = env.step(action)
        if bool(getattr(env, "episode_over", False)):
            return _ReplayResult(
                observation=observation,
                replay_actions=tuple(replay_actions),
                valid=False,
                invalid_reason="episode_ended_during_replay",
            )
    return _ReplayResult(
        observation=observation,
        replay_actions=tuple(replay_actions),
        valid=True,
    )


def _episode_mismatch(env: Any, target_step: Mapping[str, Any]) -> str | None:
    episode = getattr(env, "current_episode", None)
    if episode is None:
        return None
    expected_episode_id = str(target_step.get("episode_id", ""))
    actual_episode_id = str(getattr(episode, "episode_id", ""))
    if expected_episode_id and actual_episode_id and expected_episode_id != actual_episode_id:
        return "episode_id_mismatch"
    expected_scene_id = str(target_step.get("scene_id", ""))
    actual_scene_id = str(getattr(episode, "scene_id", ""))
    if expected_scene_id and actual_scene_id and expected_scene_id != actual_scene_id:
        return "scene_id_mismatch"
    return None


def _candidate_rollout_action(
    candidate: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    rollout_step: int,
    forced_first_action: Any = None,
    branch_followup_policy: str = "left_scan",
    bearing_tolerance_rad: float = float(np.deg2rad(20.0)),
) -> str:
    if rollout_step == 0 and forced_first_action is not None:
        return str(forced_first_action)
    if rollout_step > 0:
        if (
            branch_followup_policy == "repeat_first_action"
            and forced_first_action is not None
        ):
            return str(forced_first_action)
        return "turn_left"
    bearing_error = _optional_float(candidate.get("bearing_error_rad"))
    if bearing_error is not None and abs(bearing_error) > bearing_tolerance_rad:
        return "turn_right" if bearing_error > 0.0 else "turn_left"
    if _center_depth_is_clear(observation.get("depth")):
        return "move_forward"
    return "turn_left"


def _candidate_option_rollout_action(
    *,
    candidate: Mapping[str, Any],
    observation: Mapping[str, Any],
    pose: Mapping[str, Any],
    option_state: _CandidateOptionRolloutState,
    option_scan_steps: int,
    viewpoint_grid_cell_size_m: float,
    bearing_tolerance_rad: float = float(np.deg2rad(20.0)),
) -> str:
    if option_state.scan_steps_remaining > 0:
        option_state.scan_steps_remaining -= 1
        option_state.option_scan_step_count += 1
        return "turn_left"

    candidate_x = _optional_float(pose.get("candidate_x_m"))
    candidate_z = _optional_float(pose.get("candidate_z_m"))
    agent_pose = _observation_episode_xz_heading(observation)
    if candidate_x is None or candidate_z is None or agent_pose is None:
        return _candidate_rollout_action(
            candidate,
            observation,
            rollout_step=0,
            branch_followup_policy="left_scan",
        )

    agent_x, agent_z, heading = agent_pose
    delta_x = candidate_x - agent_x
    delta_z = candidate_z - agent_z
    distance_to_candidate = float(np.hypot(delta_x, delta_z))
    if distance_to_candidate <= float(viewpoint_grid_cell_size_m) + 1e-9:
        option_state.scan_steps_remaining = max(1, int(option_scan_steps))
        option_state.scan_steps_remaining -= 1
        option_state.option_scan_step_count += 1
        return "turn_left"

    bearing = float(np.arctan2(delta_x, delta_z))
    bearing_error = _wrap_angle(bearing - heading)
    if abs(bearing_error) > bearing_tolerance_rad:
        return "turn_right" if bearing_error > 0.0 else "turn_left"
    if _center_depth_is_clear(observation.get("depth")):
        return "move_forward"

    option_state.scan_steps_remaining = max(1, int(option_scan_steps))
    option_state.scan_steps_remaining -= 1
    option_state.option_scan_step_count += 1
    option_state.option_blocked_scan_step_count += 1
    return "turn_left"


def _observation_episode_xz_heading(
    observation: Mapping[str, Any],
) -> tuple[float, float, float] | None:
    gps = observation.get("gps")
    compass = observation.get("compass")
    if gps is None or compass is None:
        return None
    try:
        gps_values = np.asarray(gps, dtype=float).reshape(-1)
        compass_values = np.asarray(compass, dtype=float).reshape(-1)
    except (TypeError, ValueError):
        return None
    if gps_values.size < 2 or compass_values.size < 1:
        return None
    z_m = float(gps_values[0])
    x_m = float(gps_values[1])
    heading = float(compass_values[0])
    return x_m, z_m, heading


def _wrap_angle(angle: float) -> float:
    return float((float(angle) + np.pi) % (2.0 * np.pi) - np.pi)


def _detect_target_evidence(
    observation: Mapping[str, Any],
    *,
    target_detector_adapter: Any | None,
    target_category: str,
    min_confidence: float,
) -> dict[str, Any]:
    if target_detector_adapter is None:
        return {
            "label_available": False,
            "target_visible": False,
            "target_match_count": 0,
            "detector_confidence": None,
            "missing_rgb": False,
        }
    rgb = observation.get("rgb")
    if rgb is None:
        return {
            "label_available": False,
            "target_visible": False,
            "target_match_count": 0,
            "detector_confidence": None,
            "missing_rgb": True,
        }
    detections = list(target_detector_adapter.detect(np.asarray(rgb)))
    matches = [
        detection
        for detection in detections
        if _detection_category(detection) == target_category
        and _detection_confidence(detection) >= float(min_confidence)
    ]
    best_confidence = max((_detection_confidence(match) for match in matches), default=None)
    return {
        "label_available": True,
        "target_visible": bool(matches),
        "target_match_count": len(matches),
        "detector_confidence": best_confidence,
        "missing_rgb": False,
    }


def _predecision_state_features(
    *,
    step: Mapping[str, Any],
    observation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    memory_prior = _mapping(step.get("memory_prior"))
    top_candidates = _memory_top_candidates(memory_prior)
    selected_candidate = _selected_memory_candidate(memory_prior, top_candidates)
    features: dict[str, Any] = {
        "agent_x_m": _optional_float(step.get("x_m")),
        "agent_z_m": _optional_float(step.get("z_m")),
        "agent_heading_rad": _optional_float(step.get("heading_rad")),
        "memory_bearing_error_rad": _first_optional_float(
            memory_prior.get("bearing_error_rad"),
            selected_candidate.get("bearing_error_rad"),
        ),
        "memory_anchor_bearing_error_rad": _first_optional_float(
            memory_prior.get("anchor_bearing_error_rad"),
            memory_prior.get("bearing_error_rad"),
            selected_candidate.get("bearing_error_rad"),
        ),
        "memory_distance_to_anchor_m": _first_optional_float(
            memory_prior.get("distance_to_anchor_m"),
            selected_candidate.get("distance_to_anchor_m"),
        ),
        "memory_path_distance_m": _first_optional_float(
            memory_prior.get("path_distance_m"),
            selected_candidate.get("path_distance_m"),
        ),
        "memory_travel_distance_m": _first_optional_float(
            memory_prior.get("travel_distance_m"),
            selected_candidate.get("travel_distance_m"),
        ),
        "memory_expected_evidence": _first_optional_float(
            memory_prior.get("expected_evidence"),
            selected_candidate.get("expected_evidence"),
        ),
        "memory_belief_mass": _first_optional_float(
            memory_prior.get("belief_mass"),
            selected_candidate.get("belief_mass"),
        ),
        "memory_score": _first_optional_float(
            memory_prior.get("score"),
            selected_candidate.get("score"),
        ),
        "memory_active_perception_candidate_count": _first_optional_float(
            memory_prior.get("active_perception_candidate_count"),
            memory_prior.get("candidate_count"),
            len(top_candidates) if top_candidates else None,
        ),
        **_active_phase_state_features(
            step=step,
            memory_prior=memory_prior,
            selected_candidate=selected_candidate,
        ),
        "memory_top_candidate_count": len(top_candidates),
        "memory_top_score": _memory_top_score(top_candidates),
        "memory_score_gap": _memory_score_gap(top_candidates),
        "previous_target_visible": _optional_bool(
            memory_prior.get("previous_target_visible")
        ),
        "recent_target_visible_count": _optional_float(
            memory_prior.get("recent_target_visible_count")
        ),
        "steps_since_last_target_visible": _optional_float(
            memory_prior.get("steps_since_last_target_visible")
        ),
        "current_detector_confidence": _optional_float(
            memory_prior.get("current_detector_confidence")
        ),
        "current_bbox_area_fraction": _optional_float(
            memory_prior.get("current_bbox_area_fraction")
        ),
        "current_depth_median": _optional_float(memory_prior.get("current_depth_median")),
    }
    features.update(_local_depth_state_features(observation))
    return features


def _memory_top_candidates(memory_prior: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw_candidates = memory_prior.get("top_candidates", [])
    if not isinstance(raw_candidates, Sequence) or isinstance(
        raw_candidates,
        (str, bytes),
    ):
        return []
    return [candidate for candidate in raw_candidates if isinstance(candidate, Mapping)]


def _selected_memory_candidate(
    memory_prior: Mapping[str, Any],
    top_candidates: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    selected = memory_prior.get("selected_candidate")
    if isinstance(selected, Mapping):
        return selected
    return top_candidates[0] if top_candidates else {}


def _selected_candidate_rank(
    *,
    selected_candidate: Mapping[str, Any],
    top_candidates: Sequence[Mapping[str, Any]],
) -> int:
    selected_viewpoint = _optional_cell(selected_candidate.get("viewpoint_cell"))
    selected_frontier = _optional_cell(selected_candidate.get("frontier_cell"))
    for index, candidate in enumerate(top_candidates):
        if candidate is selected_candidate:
            return index
        if (
            _optional_cell(candidate.get("viewpoint_cell")) == selected_viewpoint
            and _optional_cell(candidate.get("frontier_cell")) == selected_frontier
        ):
            return index
    return 0


def _memory_top_score(top_candidates: Sequence[Mapping[str, Any]]) -> float | None:
    if not top_candidates:
        return None
    return _optional_float(top_candidates[0].get("score"))


def _memory_score_gap(top_candidates: Sequence[Mapping[str, Any]]) -> float | None:
    if len(top_candidates) < 2:
        return None
    first = _optional_float(top_candidates[0].get("score"))
    second = _optional_float(top_candidates[1].get("score"))
    if first is None or second is None:
        return None
    return _optional_float(first - second)


def _local_depth_state_features(
    observation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    depth = _mapping(observation).get("depth")
    frame = _depth_frame_2d(depth)
    if frame is None:
        return {
            "local_center_depth_clear": False,
            "local_center_depth_median": None,
            "local_center_depth_min": None,
            "local_center_depth_clear_fraction": None,
        }
    center = _center_depth_window(frame)
    finite = center[np.isfinite(center)]
    if finite.size == 0:
        return {
            "local_center_depth_clear": False,
            "local_center_depth_median": None,
            "local_center_depth_min": None,
            "local_center_depth_clear_fraction": None,
        }
    finite_frame = frame[np.isfinite(frame)]
    threshold = (
        FRONTIER_CLEAR_DEPTH_NORMALIZED
        if finite_frame.size and float(np.nanmax(finite_frame)) <= 1.0
        else FRONTIER_CLEAR_DEPTH_M
    )
    clear = finite >= threshold
    return {
        "local_center_depth_clear": bool(_center_depth_is_clear(depth)),
        "local_center_depth_median": _optional_float(float(np.median(finite))),
        "local_center_depth_min": _optional_float(float(np.min(finite))),
        "local_center_depth_clear_fraction": _optional_float(
            float(clear.sum()) / float(finite.size)
        ),
    }


def _center_depth_window(depth: np.ndarray) -> np.ndarray:
    height, width = depth.shape
    row_start = height // 3
    row_end = max(row_start + 1, (2 * height) // 3)
    col_start = width // 3
    col_end = max(col_start + 1, (2 * width) // 3)
    return depth[row_start:row_end, col_start:col_end]


def _detection_category(detection: Any) -> str:
    if isinstance(detection, Mapping):
        return str(detection.get("category", ""))
    return str(getattr(detection, "category", ""))


def _detection_confidence(detection: Any) -> float:
    raw = detection.get("confidence") if isinstance(detection, Mapping) else getattr(
        detection,
        "confidence",
        0.0,
    )
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _candidate_states(
    steps: Sequence[Mapping[str, Any]],
    *,
    max_states: int | None,
    max_states_per_category: int | None = None,
    max_states_per_category_episode: int | None = None,
    state_sampling: str = "trace_order",
) -> list[Mapping[str, Any]]:
    safe_state_sampling = _state_sampling_mode(state_sampling)
    candidate_steps: list[tuple[int, Mapping[str, Any]]] = []
    for order, step in enumerate(steps):
        memory_prior = step.get("memory_prior", {})
        if not isinstance(memory_prior, Mapping):
            continue
        top_candidates = memory_prior.get("top_candidates", [])
        if not isinstance(top_candidates, list) or not top_candidates:
            continue
        candidate_steps.append((order, step))
    if safe_state_sampling == "top_score_desc":
        candidate_steps.sort(key=_candidate_state_top_score_sort_key)
    elif safe_state_sampling == "active_phase_path":
        candidate_steps.sort(key=_candidate_state_active_phase_path_sort_key)

    states: list[Mapping[str, Any]] = []
    category_counts: dict[str, int] = {}
    category_episode_counts: dict[tuple[str, int], int] = {}
    for _, step in candidate_steps:
        category = str(step.get("target_category", ""))
        if max_states_per_category is not None:
            category_count = category_counts.get(category, 0)
            if category_count >= max_states_per_category:
                continue
        category_episode = (category, _int(step.get("episode_index")))
        if max_states_per_category_episode is not None:
            category_episode_count = category_episode_counts.get(category_episode, 0)
            if category_episode_count >= max_states_per_category_episode:
                continue
        states.append(step)
        category_counts[category] = category_counts.get(category, 0) + 1
        category_episode_counts[category_episode] = (
            category_episode_counts.get(category_episode, 0) + 1
        )
        if max_states is not None and len(states) >= max_states:
            break
    return states


def _candidate_state_top_score_sort_key(
    candidate_step: tuple[int, Mapping[str, Any]],
) -> tuple[bool, float, int]:
    order, step = candidate_step
    memory_prior = _mapping(step.get("memory_prior"))
    top_score = _memory_top_score(_memory_top_candidates(memory_prior))
    if top_score is None:
        return (True, 0.0, order)
    return (False, -top_score, order)


def _candidate_state_active_phase_path_sort_key(
    candidate_step: tuple[int, Mapping[str, Any]],
) -> tuple[int, bool, float, bool, float, int]:
    order, step = candidate_step
    memory_prior = _mapping(step.get("memory_prior"))
    top_candidates = _memory_top_candidates(memory_prior)
    selected_candidate = _selected_memory_candidate(memory_prior, top_candidates)
    phase_rank = _active_phase_rank(
        phase=str(memory_prior.get("active_perception_phase", "")),
        decision=str(memory_prior.get("decision") or step.get("decision", "")),
    )
    path_distance = _first_optional_float(
        memory_prior.get("path_distance_m"),
        selected_candidate.get("path_distance_m"),
    )
    top_score = _first_optional_float(
        _memory_top_score(top_candidates),
        memory_prior.get("score"),
        selected_candidate.get("score"),
    )
    return (
        phase_rank,
        path_distance is None,
        path_distance if path_distance is not None else 0.0,
        top_score is None,
        -top_score if top_score is not None else 0.0,
        order,
    )


def _active_phase_state_features(
    *,
    step: Mapping[str, Any],
    memory_prior: Mapping[str, Any],
    selected_candidate: Mapping[str, Any],
) -> dict[str, Any]:
    phase = str(memory_prior.get("active_perception_phase", ""))
    decision = str(memory_prior.get("decision") or step.get("decision", ""))
    phase_rank = _active_phase_rank(phase=phase, decision=decision)
    path_distance = _first_optional_float(
        memory_prior.get("path_distance_m"),
        selected_candidate.get("path_distance_m"),
    )
    is_orient = phase_rank == 0
    is_scan = phase_rank == 1
    is_frontier = "active_perception_frontier" in decision
    is_at_viewpoint = bool(
        is_orient
        or is_scan
        or (path_distance is not None and path_distance <= 1.0e-9)
    )
    return {
        "memory_active_perception_phase_rank": phase_rank,
        "memory_active_perception_orient_anchor": is_orient,
        "memory_active_perception_scan_anchor": is_scan,
        "memory_active_perception_frontier": is_frontier,
        "memory_active_perception_at_viewpoint": is_at_viewpoint,
        "memory_active_perception_scan_steps_remaining": _optional_float(
            memory_prior.get("active_perception_scan_steps_remaining")
        ),
    }


def _active_phase_rank(*, phase: str, decision: str) -> int:
    normalized_phase = phase.strip()
    normalized_decision = decision.strip()
    if (
        normalized_phase == "orient_anchor"
        or normalized_decision == "orient_memory_anchor_from_active_viewpoint"
    ):
        return 0
    if (
        normalized_phase == "scan_anchor"
        or normalized_decision == "scan_memory_anchor_from_active_viewpoint"
    ):
        return 1
    if "active_perception_frontier" in normalized_decision:
        return 2
    if normalized_phase:
        return 2
    return 3


def _branch_specs(
    *,
    top_candidates: Sequence[Any],
    candidates_per_state: int,
    branch_actions: tuple[str, ...],
) -> list[dict[str, Any]]:
    if branch_actions:
        return [
            {
                "kind": "action",
                "action": action,
                "candidate": {},
                "rank": index,
                "count": len(branch_actions),
            }
            for index, action in enumerate(branch_actions)
        ]
    specs: list[dict[str, Any]] = []
    for candidate_rank, candidate in enumerate(top_candidates[:candidates_per_state]):
        if not isinstance(candidate, Mapping):
            continue
        specs.append(
            {
                "kind": "candidate",
                "action": None,
                "candidate": candidate,
                "rank": candidate_rank,
                "count": len(top_candidates),
            }
        )
    return specs


def _branch_actions(actions: Sequence[str] | None) -> tuple[str, ...]:
    if actions is None:
        return ()
    parsed = tuple(str(action).strip() for action in actions if str(action).strip())
    allowed = {"move_forward", "turn_left", "turn_right"}
    invalid = [action for action in parsed if action not in allowed]
    if invalid:
        raise ValueError(f"unsupported branch action(s): {', '.join(invalid)}")
    return parsed


def _branch_followup_policy(policy: str) -> str:
    parsed = str(policy or "left_scan").strip()
    if parsed not in BRANCH_FOLLOWUP_POLICIES:
        allowed = ", ".join(BRANCH_FOLLOWUP_POLICIES)
        raise ValueError(f"unsupported branch follow-up policy: {parsed}; allowed: {allowed}")
    return parsed


def _state_sampling_mode(mode: str) -> str:
    parsed = str(mode or "trace_order").strip()
    if parsed not in STATE_SAMPLING_MODES:
        allowed = ", ".join(STATE_SAMPLING_MODES)
        raise ValueError(f"unsupported state sampling mode: {parsed}; allowed: {allowed}")
    return parsed


def _action_matrix_state_key(
    dataset_index: int,
    rollout: Mapping[str, Any],
) -> tuple[Any, ...]:
    return (
        dataset_index,
        str(rollout.get("source_policy_trace", "")),
        _int(rollout.get("state_index")),
        _int(rollout.get("episode_index")),
        str(rollout.get("episode_id", "")),
        _int(rollout.get("step_index")),
    )


def _action_matrix_state_template(
    dataset_index: int,
    dataset: Mapping[str, Any],
    rollout: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "source_dataset": str(dataset.get("source_dataset_path", "")),
        "source_dataset_index": int(dataset_index),
        "source_policy_trace": str(rollout.get("source_policy_trace", "")),
        "state_index": _int(rollout.get("state_index")),
        "episode_index": _int(rollout.get("episode_index")),
        "episode_id": str(rollout.get("episode_id", "")),
        "scene_id": str(rollout.get("scene_id", "")),
        "target_category": str(rollout.get("target_category", "")),
        "step_index": _int(rollout.get("step_index")),
        "state_action": str(rollout.get("state_action", "")),
        "state_decision": str(rollout.get("state_decision", "")),
        "state_features": dict(_mapping(rollout.get("state_features"))),
        "actions": {},
    }


def _action_matrix_state_report(
    group: Mapping[str, Any],
    *,
    actions: Sequence[str],
) -> dict[str, Any]:
    action_payloads = group.get("actions", {})
    if not isinstance(action_payloads, Mapping):
        action_payloads = {}
    positive_actions = [
        action
        for action in actions
        if bool(_mapping(action_payloads.get(action)).get("success"))
    ]
    times = {
        action: _optional_int(
            _mapping(action_payloads.get(action)).get("time_to_visible_steps")
        )
        for action in positive_actions
    }
    finite_times = {
        action: value for action, value in times.items() if value is not None
    }
    if finite_times:
        best_time = min(finite_times.values())
        fastest_actions = [
            action for action in actions if finite_times.get(action) == best_time
        ]
    else:
        fastest_actions = []
    strict_fastest_action = fastest_actions[0] if len(fastest_actions) == 1 else None
    return {
        **{key: value for key, value in group.items() if key != "actions"},
        "positive_action_count": len(positive_actions),
        "positive_actions": positive_actions,
        "fastest_actions": fastest_actions,
        "strict_fastest_action": strict_fastest_action,
        "oracle_recovered": bool(positive_actions),
        "actions": {
            action: dict(_mapping(action_payloads.get(action))) for action in actions
        },
    }


def _action_matrix_aggregate(
    states: Sequence[Mapping[str, Any]],
    *,
    actions: Sequence[str],
) -> dict[str, Any]:
    action_counts = {
        action: {
            "rollout_count": 0,
            "success_count": 0,
            "fastest_count": 0,
            "strict_fastest_count": 0,
        }
        for action in actions
    }
    strict_fastest_counts: dict[str, int] = {}
    positive_action_count_counts: dict[str, int] = {}
    fastest_action_tie_count = 0
    oracle_recovered_count = 0
    for state in states:
        if bool(state.get("oracle_recovered")):
            oracle_recovered_count += 1
        positive_count = _int(state.get("positive_action_count"))
        positive_key = str(positive_count)
        positive_action_count_counts[positive_key] = (
            positive_action_count_counts.get(positive_key, 0) + 1
        )
        fastest_actions = state.get("fastest_actions", [])
        if not isinstance(fastest_actions, Sequence) or isinstance(
            fastest_actions, (str, bytes)
        ):
            fastest_actions = []
        if len(fastest_actions) > 1:
            fastest_action_tie_count += 1
        strict_fastest_action = state.get("strict_fastest_action")
        if strict_fastest_action:
            key = str(strict_fastest_action)
            strict_fastest_counts[key] = strict_fastest_counts.get(key, 0) + 1
        action_payloads = state.get("actions", {})
        if not isinstance(action_payloads, Mapping):
            action_payloads = {}
        for action in actions:
            payload = _mapping(action_payloads.get(action))
            if not payload:
                continue
            action_counts[action]["rollout_count"] += 1
            if bool(payload.get("success")):
                action_counts[action]["success_count"] += 1
            if action in fastest_actions:
                action_counts[action]["fastest_count"] += 1
            if strict_fastest_action == action:
                action_counts[action]["strict_fastest_count"] += 1
    return {
        "oracle_recovered_count": oracle_recovered_count,
        "strict_fastest_action_counts": strict_fastest_counts,
        "fastest_action_tie_count": fastest_action_tie_count,
        "positive_action_count_counts": positive_action_count_counts,
        "action_counts": action_counts,
    }


def _candidate_viewpoint_pose_from_cell(
    cell: Any,
    *,
    grid_size_cells: int = DEFAULT_VIEWPOINT_GRID_SIZE_CELLS,
    grid_cell_size_m: float = DEFAULT_VIEWPOINT_GRID_CELL_SIZE_M,
) -> dict[str, Any] | None:
    row, col = _optional_cell(cell)
    if row is None or col is None:
        return None
    safe_grid_size = _safe_viewpoint_grid_size(grid_size_cells)
    safe_cell_size = _safe_viewpoint_grid_cell_size(grid_cell_size_m)
    origin_row = safe_grid_size // 2
    origin_col = safe_grid_size // 2
    return {
        "grid_size_cells": safe_grid_size,
        "grid_cell_size_m": safe_cell_size,
        "grid_origin_row": origin_row,
        "grid_origin_col": origin_col,
        "candidate_x_m": _optional_float((col - origin_col) * safe_cell_size),
        "candidate_z_m": _optional_float((origin_row - row) * safe_cell_size),
    }


def _candidate_option_pose(
    candidate: Mapping[str, Any],
    *,
    grid_size_cells: int = DEFAULT_VIEWPOINT_GRID_SIZE_CELLS,
    grid_cell_size_m: float = DEFAULT_VIEWPOINT_GRID_CELL_SIZE_M,
) -> dict[str, Any] | None:
    candidate_x = _optional_float(candidate.get("candidate_x_m"))
    candidate_z = _optional_float(candidate.get("candidate_z_m"))
    if candidate_x is not None and candidate_z is not None:
        safe_grid_size = _safe_viewpoint_grid_size(grid_size_cells)
        safe_cell_size = _safe_viewpoint_grid_cell_size(grid_cell_size_m)
        origin = safe_grid_size // 2
        return {
            "grid_size_cells": safe_grid_size,
            "grid_cell_size_m": safe_cell_size,
            "grid_origin_row": origin,
            "grid_origin_col": origin,
            "candidate_x_m": candidate_x,
            "candidate_z_m": candidate_z,
        }
    return _candidate_viewpoint_pose_from_cell(
        candidate.get("viewpoint_cell") or candidate.get("frontier_cell"),
        grid_size_cells=grid_size_cells,
        grid_cell_size_m=grid_cell_size_m,
    )


def _viewpoint_scan_headings(count: int) -> tuple[float, ...]:
    safe_count = max(1, int(count))
    return tuple(float(2.0 * np.pi * index / safe_count) for index in range(safe_count))


def _restore_candidate_viewpoint_observation(
    env: Any,
    *,
    x_m: float,
    z_m: float,
    heading_rad: float,
) -> _ReplayResult:
    custom_restore = getattr(env, "restore_candidate_viewpoint", None)
    if callable(custom_restore):
        observation = custom_restore(x_m=x_m, z_m=z_m, heading_rad=heading_rad)
        if isinstance(observation, Mapping):
            return _ReplayResult(
                observation=_normalize_candidate_restore_observation(observation),
                replay_actions=(),
                valid=True,
            )
        return _ReplayResult(
            observation=None,
            replay_actions=(),
            valid=False,
            invalid_reason="candidate_restore_failed",
        )

    episode = getattr(env, "current_episode", None)
    sim = getattr(env, "sim", None) or getattr(env, "_sim", None)
    if episode is None or sim is None:
        return _ReplayResult(
            observation=None,
            replay_actions=(),
            valid=False,
            invalid_reason="candidate_restore_unsupported",
        )
    start_position = _tuple3(getattr(episode, "start_position", None))
    start_rotation = _tuple4(getattr(episode, "start_rotation", None))
    if start_position is None or start_rotation is None:
        return _ReplayResult(
            observation=None,
            replay_actions=(),
            valid=False,
            invalid_reason="missing_episode_start_pose",
        )
    position = _episode_relative_xz_to_world_position(
        start_position=start_position,
        start_rotation=start_rotation,
        x_m=x_m,
        z_m=z_m,
    )
    snapped_position, snap_valid = _snap_candidate_position(sim, position)
    if not snap_valid:
        return _ReplayResult(
            observation=None,
            replay_actions=(),
            valid=False,
            invalid_reason="candidate_pose_not_navigable",
        )
    rotation = _episode_heading_to_world_rotation(
        start_rotation=start_rotation,
        heading_rad=heading_rad,
    )
    try:
        agent = sim.initialize_agent(0)
        state = agent.get_state()
        state.position = np.asarray(snapped_position, dtype=float)
        state.rotation = list(rotation)
        agent.set_state(state)
        observation = sim.get_sensor_observations()
    except Exception as exc:  # pragma: no cover - depends on Habitat runtime
        return _ReplayResult(
            observation=None,
            replay_actions=(),
            valid=False,
            invalid_reason=f"candidate_restore_exception:{type(exc).__name__}",
        )
    if not isinstance(observation, Mapping):
        return _ReplayResult(
            observation=None,
            replay_actions=(),
            valid=False,
            invalid_reason="candidate_restore_returned_no_observation",
        )
    return _ReplayResult(
        observation=_normalize_candidate_restore_observation(observation),
        replay_actions=(),
        valid=True,
    )


def _normalize_candidate_restore_observation(
    observation: Mapping[str, Any],
) -> Mapping[str, Any]:
    normalized = dict(observation)
    if "rgb" not in normalized and "color_sensor" in normalized:
        normalized["rgb"] = normalized["color_sensor"]
    rgb = normalized.get("rgb")
    if rgb is not None:
        array = np.asarray(rgb)
        if array.ndim == 3 and array.shape[2] > 3:
            normalized["rgb"] = array[:, :, :3]
    return normalized


def _episode_relative_xz_to_world_position(
    *,
    start_position: tuple[float, float, float],
    start_rotation: tuple[float, float, float, float],
    x_m: float,
    z_m: float,
) -> tuple[float, float, float]:
    yaw = _yaw_from_quaternion_xyzw(start_rotation)
    right = np.asarray((np.cos(yaw), 0.0, -np.sin(yaw)), dtype=float)
    forward = np.asarray((-np.sin(yaw), 0.0, -np.cos(yaw)), dtype=float)
    start = np.asarray(start_position, dtype=float)
    position = start + float(x_m) * right + float(z_m) * forward
    return tuple(float(value) for value in position)


def _episode_heading_to_world_rotation(
    *,
    start_rotation: tuple[float, float, float, float],
    heading_rad: float,
) -> tuple[float, float, float, float]:
    half_yaw = -float(heading_rad) / 2.0
    heading_rotation = _normalize_quaternion_xyzw(
        (0.0, float(np.sin(half_yaw)), 0.0, float(np.cos(half_yaw)))
    )
    return _multiply_quaternion_xyzw(start_rotation, heading_rotation)


def _snap_candidate_position(
    sim: Any,
    position: tuple[float, float, float],
    *,
    max_snap_distance_m: float = 0.75,
) -> tuple[tuple[float, float, float], bool]:
    pathfinder = getattr(sim, "pathfinder", None)
    if pathfinder is None:
        return position, True
    raw_position = np.asarray(position, dtype=float)
    snapped = raw_position
    snap_point = getattr(pathfinder, "snap_point", None)
    if callable(snap_point):
        try:
            snapped = np.asarray(snap_point(raw_position), dtype=float)
        except Exception:
            snapped = raw_position
    is_navigable = getattr(pathfinder, "is_navigable", None)
    navigable = True
    if callable(is_navigable):
        try:
            navigable = bool(is_navigable(snapped))
        except Exception:
            navigable = True
    snap_distance = float(np.linalg.norm(snapped - raw_position))
    return (
        tuple(float(value) for value in snapped),
        bool(navigable and snap_distance <= max_snap_distance_m),
    )


def _multiply_quaternion_xyzw(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    x1, y1, z1, w1 = _normalize_quaternion_xyzw(first)
    x2, y2, z2, w2 = _normalize_quaternion_xyzw(second)
    return _normalize_quaternion_xyzw(
        (
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        )
    )


def _normalize_quaternion_xyzw(
    rotation: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    norm = float(np.sqrt(sum(float(value) * float(value) for value in rotation)))
    if norm == 0.0:
        return 0.0, 0.0, 0.0, 1.0
    return tuple(float(value) / norm for value in rotation)  # type: ignore[return-value]


def _yaw_from_quaternion_xyzw(
    rotation: tuple[float, float, float, float],
) -> float:
    x, y, z, w = _normalize_quaternion_xyzw(rotation)
    siny_cosp = 2.0 * (w * y + x * z)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return float(np.arctan2(siny_cosp, cosy_cosp))


def _tuple3(value: Any) -> tuple[float, float, float] | None:
    if value is None:
        return None
    try:
        values = tuple(float(part) for part in value)
    except (TypeError, ValueError):
        return None
    if len(values) != 3:
        return None
    return values


def _tuple4(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    try:
        values = tuple(float(part) for part in value)
    except (TypeError, ValueError):
        return None
    if len(values) != 4:
        return None
    return values


def _safe_viewpoint_grid_size(size_cells: int) -> int:
    size = int(size_cells)
    if size <= 2:
        raise ValueError("viewpoint grid size must be greater than 2")
    if size % 2 == 0:
        raise ValueError("viewpoint grid size must be odd")
    return size


def _safe_viewpoint_grid_cell_size(cell_size_m: float) -> float:
    cell_size = float(cell_size_m)
    if cell_size <= 0.0:
        raise ValueError("viewpoint grid cell size must be positive")
    return cell_size


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def _policy_steps(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_steps = payload.get("steps", [])
    if not isinstance(raw_steps, list):
        raise ValueError("policy trace steps must be a list")
    steps = [dict(step) for step in raw_steps if isinstance(step, Mapping)]
    return sorted(steps, key=lambda step: (_episode_key(step), _int(step.get("step_index"))))


def _max_step_index(steps: Sequence[Mapping[str, Any]]) -> int:
    return max((_int(step.get("step_index")) for step in steps), default=0)


def _episode_key(row: Mapping[str, Any]) -> tuple[int, str]:
    return _int(row.get("episode_index")), str(row.get("episode_id", ""))


def _optional_cell(value: Any) -> tuple[int | None, int | None]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None, None
    if len(value) < 2:
        return None, None
    return _optional_int(value[0]), _optional_int(value[1])


def _optional_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any, *, default: int = 0) -> int:
    maybe_value = _optional_int(value)
    return default if maybe_value is None else maybe_value


def _optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), 12)
    except (TypeError, ValueError):
        return None


def _first_optional_float(*values: Any) -> float | None:
    for value in values:
        parsed = _optional_float(value)
        if parsed is not None:
            return parsed
    return None


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return None


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, tuple)):
        return " ".join(str(item) for item in value)
    return value
