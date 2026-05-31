from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
    export_official_candidate_rollout_dataset,
    write_official_candidate_rollout_dataset_csv,
)
from objectnav_core.perception.yolo_world_adapter import Detection


def test_candidate_rollout_dataset_labels_candidates_from_same_replayed_state(
    tmp_path: Path,
) -> None:
    policy_trace_path = _write_policy_trace(tmp_path)
    envs: list[_BranchReplayEnv] = []
    configured_max_steps: list[int] = []

    def env_factory(_config: object) -> _BranchReplayEnv:
        configured_max_steps.append(int(getattr(_config, "max_steps")))
        env = _BranchReplayEnv()
        envs.append(env)
        return env

    dataset = export_official_candidate_rollout_dataset(
        policy_trace_path,
        output_dir=tmp_path / "rollouts",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        target_detector_adapter=_PixelDetector(),
        target_detector_min_confidence=0.5,
        max_states=1,
        candidates_per_state=2,
        rollout_horizon_steps=1,
        env_factory=env_factory,
    )

    assert dataset["task"] == "habitat_official_candidate_rollout_dataset"
    assert dataset["schema_version"] == "official-candidate-rollout-v1"
    assert dataset["state_count"] == 1
    assert dataset["rollout_count"] == 2
    assert dataset["positive_rollout_count"] == 1
    assert dataset["invalid_rollout_count"] == 0

    left_candidate, right_candidate = dataset["rollouts"]
    assert left_candidate["candidate_rank"] == 0
    assert left_candidate["rollout_actions"] == ["turn_left"]
    assert left_candidate["replay_actions"] == ["move_forward"]
    assert left_candidate["labels"] == {
        "current_target_visible": False,
        "target_visible_within_rollout": True,
        "hidden_to_visible_within_rollout": True,
        "label_available": True,
    }
    assert right_candidate["candidate_rank"] == 1
    assert right_candidate["rollout_actions"] == ["turn_right"]
    assert right_candidate["replay_actions"] == ["move_forward"]
    assert right_candidate["labels"]["hidden_to_visible_within_rollout"] is False

    assert [env.actions for env in envs] == [
        ["move_forward", "turn_left"],
        ["move_forward", "turn_right"],
    ]
    assert configured_max_steps == [3, 3]


def test_candidate_state_restore_dataset_labels_exact_replayed_state(
    tmp_path: Path,
) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        export_official_candidate_state_restore_dataset,
    )

    envs: list[_StateRestoreVisibleEnv] = []

    def env_factory(_config: object) -> _StateRestoreVisibleEnv:
        env = _StateRestoreVisibleEnv()
        envs.append(env)
        return env

    dataset = export_official_candidate_state_restore_dataset(
        _write_policy_trace(tmp_path),
        output_dir=tmp_path / "restore",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=_PixelDetector(),
        target_detector_min_confidence=0.5,
        max_states=1,
        env_factory=env_factory,
    )

    assert dataset["task"] == "habitat_official_candidate_state_restore_dataset"
    assert dataset["schema_version"] == "official-candidate-state-restore-v1"
    assert dataset["state_count"] == 1
    assert dataset["restore_count"] == 1
    assert dataset["target_visible_state_count"] == 1
    row = dataset["states"][0]
    assert row["replay_actions"] == ["move_forward"]
    assert row["valid_restore"] is True
    assert row["candidate_rank"] == 0
    assert row["candidate_count"] == 2
    assert row["labels"] == {
        "label_available": True,
        "target_visible_at_restore": True,
        "hidden_at_restore": False,
    }
    assert [env.actions for env in envs] == [["move_forward"]]


def test_candidate_state_restore_dataset_writes_csv(tmp_path: Path) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        export_official_candidate_state_restore_dataset,
        write_official_candidate_state_restore_dataset_csv,
    )

    dataset = export_official_candidate_state_restore_dataset(
        _write_policy_trace(tmp_path),
        output_dir=tmp_path / "restore",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=_PixelDetector(),
        max_states=1,
        env_factory=lambda _config: _StateRestoreVisibleEnv(),
    )
    csv_path = tmp_path / "restore.csv"

    write_official_candidate_state_restore_dataset_csv(dataset, csv_path)

    csv_text = csv_path.read_text(encoding="utf-8")
    assert "target_visible_at_restore" in csv_text
    assert "memory_active_perception_phase_rank" in csv_text
    assert "move_forward" in csv_text
    assert "true" in csv_text


def test_candidate_state_restore_dataset_cli_writes_json_and_csv(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.export_habitat_official_candidate_state_restore_dataset import (
        main,
    )

    output_path = tmp_path / "restore.json"
    csv_path = tmp_path / "restore.csv"

    def runner(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "task": "habitat_official_candidate_state_restore_dataset",
            "schema_version": "official-candidate-state-restore-v1",
            "state_count": 1,
            "restore_count": 1,
            "target_visible_state_count": 1,
            "invalid_restore_count": 0,
            "states": [
                {
                    "source_policy_trace": "trace.json",
                    "episode_index": 0,
                    "episode_id": "episode-0",
                    "scene_id": "scene.glb",
                    "target_category": "chair",
                    "step_index": 1,
                    "state_action": "turn_left",
                    "state_decision": (
                        "turn_toward_memory_active_perception_frontier"
                    ),
                    "candidate_rank": 0,
                    "candidate_count": 1,
                    "valid_restore": True,
                    "invalid_reason": None,
                    "replay_actions": ["move_forward"],
                    "state_features": {
                        "memory_active_perception_phase_rank": 2,
                    },
                    "labels": {
                        "label_available": True,
                        "target_visible_at_restore": True,
                        "hidden_at_restore": False,
                    },
                }
            ],
        }

    exit_code = main(
        [
            "trace.json",
            "--output",
            str(output_path),
            "--csv-output",
            str(csv_path),
        ],
        detector_factory=lambda *_args, **_kwargs: None,
        runner=runner,
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["task"] == "habitat_official_candidate_state_restore_dataset"
    assert "target_visible_at_restore" in csv_path.read_text(encoding="utf-8")


def test_candidate_state_restore_cli_resolves_grounding_dino_default_weights(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.export_habitat_official_candidate_state_restore_dataset import (
        main,
    )

    output_path = tmp_path / "restore.json"
    captured: dict[str, object] = {}

    def detector_factory(detector_name: str, **kwargs: object) -> object:
        captured["detector_name"] = detector_name
        captured["detector_kwargs"] = dict(kwargs)
        return {"detector": detector_name}

    def runner(*_args: object, **kwargs: object) -> dict[str, object]:
        captured["target_detector_adapter"] = kwargs["target_detector_adapter"]
        return {
            "task": "habitat_official_candidate_state_restore_dataset",
            "schema_version": "official-candidate-state-restore-v1",
            "state_count": 0,
            "restore_count": 0,
            "target_visible_state_count": 0,
            "invalid_restore_count": 0,
            "states": [],
        }

    exit_code = main(
        [
            "trace.json",
            "--output",
            str(output_path),
            "--detector",
            "grounding_dino",
            "--grounding-dino-max-image-side",
            "384",
            "--categories",
            "chair,plant",
        ],
        detector_factory=detector_factory,
        runner=runner,
    )

    assert exit_code == 0
    assert captured["detector_kwargs"] == {
        "model_id": "IDEA-Research/grounding-dino-tiny",
        "categories": ["chair", "plant"],
        "conf": 0.25,
        "text_threshold": 0.25,
        "max_image_side": 384,
        "device": "auto",
    }
    assert captured["target_detector_adapter"] == {"detector": "grounding_dino"}


def test_candidate_viewpoint_grid_cell_conversion_uses_episode_relative_xz() -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        _candidate_viewpoint_pose_from_cell,
    )

    origin_pose = _candidate_viewpoint_pose_from_cell([40, 40])
    right_pose = _candidate_viewpoint_pose_from_cell([40, 41])
    forward_pose = _candidate_viewpoint_pose_from_cell([39, 40])

    assert origin_pose["candidate_x_m"] == 0.0
    assert origin_pose["candidate_z_m"] == 0.0
    assert origin_pose["grid_origin_row"] == 40
    assert origin_pose["grid_origin_col"] == 40
    assert right_pose["candidate_x_m"] == 0.25
    assert right_pose["candidate_z_m"] == 0.0
    assert forward_pose["candidate_x_m"] == 0.0
    assert forward_pose["candidate_z_m"] == 0.25


def test_candidate_viewpoint_restore_dataset_labels_top_k_scan_viewpoints(
    tmp_path: Path,
) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        export_official_candidate_viewpoint_restore_dataset,
    )

    envs: list[_CandidateViewpointRestoreEnv] = []

    def env_factory(_config: object) -> _CandidateViewpointRestoreEnv:
        env = _CandidateViewpointRestoreEnv()
        envs.append(env)
        return env

    dataset = export_official_candidate_viewpoint_restore_dataset(
        _write_policy_trace(tmp_path),
        output_dir=tmp_path / "candidate_viewpoints",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=_PixelDetector(),
        target_detector_min_confidence=0.5,
        max_states=1,
        candidates_per_state=2,
        viewpoint_heading_count=4,
        env_factory=env_factory,
    )

    assert dataset["task"] == "habitat_official_candidate_viewpoint_restore_dataset"
    assert dataset["schema_version"] == "official-candidate-viewpoint-restore-v1"
    assert dataset["state_count"] == 1
    assert dataset["candidate_viewpoint_count"] == 2
    assert dataset["target_visible_candidate_viewpoint_count"] == 1
    assert dataset["hidden_to_visible_candidate_viewpoint_count"] == 1

    first, second = dataset["candidate_viewpoints"]
    assert first["candidate_rank"] == 0
    assert first["candidate_x_m"] == 0.0
    assert first["candidate_z_m"] == 0.25
    assert first["visible_heading_count"] == 0
    assert first["labels"] == {
        "label_available": True,
        "current_target_visible_at_restore": False,
        "target_visible_from_candidate_viewpoint": False,
        "hidden_to_visible_from_candidate_viewpoint": False,
    }
    assert second["candidate_rank"] == 1
    assert second["candidate_x_m"] == 0.25
    assert second["candidate_z_m"] == 0.25
    assert second["viewpoint_heading_count"] == 4
    assert second["visible_heading_count"] == 1
    assert second["best_detector_confidence"] == 0.91
    assert second["labels"] == {
        "label_available": True,
        "current_target_visible_at_restore": False,
        "target_visible_from_candidate_viewpoint": True,
        "hidden_to_visible_from_candidate_viewpoint": True,
    }
    assert [env.actions for env in envs] == [["move_forward"]]
    assert envs[0].candidate_restores == [
        (0.0, 0.25, 0.0),
        (0.0, 0.25, round(float(np.pi / 2.0), 6)),
        (0.0, 0.25, round(float(np.pi), 6)),
        (0.0, 0.25, round(float(3.0 * np.pi / 2.0), 6)),
        (0.25, 0.25, 0.0),
        (0.25, 0.25, round(float(np.pi / 2.0), 6)),
        (0.25, 0.25, round(float(np.pi), 6)),
        (0.25, 0.25, round(float(3.0 * np.pi / 2.0), 6)),
    ]


def test_candidate_viewpoint_restore_dataset_uses_frontier_cell_when_viewpoint_missing(
    tmp_path: Path,
) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        export_official_candidate_viewpoint_restore_dataset,
    )

    policy_trace_path = tmp_path / "frontier_only_candidates.json"
    policy_trace_path.write_text(
        json.dumps(
            {
                "task": "official_policy_step_trace",
                "steps": [
                    _policy_step(
                        step_index=1,
                        action="turn_left",
                        decision="turn_toward_memory_active_perception_frontier",
                        memory_prior={
                            "decision": (
                                "turn_toward_memory_active_perception_frontier"
                            ),
                            "top_candidates": [
                                {
                                    "frontier_cell": [40, 41],
                                    "score": 0.7,
                                    "travel_distance_m": 0.25,
                                }
                            ],
                        },
                    ),
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    env = _CandidateViewpointRestoreEnv()

    dataset = export_official_candidate_viewpoint_restore_dataset(
        policy_trace_path,
        output_dir=tmp_path / "candidate_viewpoints",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=_PixelDetector(),
        target_detector_min_confidence=0.5,
        max_states=1,
        candidates_per_state=1,
        viewpoint_heading_count=1,
        env_factory=lambda _config: env,
    )

    row = dataset["candidate_viewpoints"][0]
    assert row["viewpoint_row"] is None
    assert row["frontier_row"] == 40
    assert row["frontier_col"] == 41
    assert row["candidate_x_m"] == 0.25
    assert row["candidate_z_m"] == 0.0
    assert row["valid_candidate_restore"] is True
    assert row["invalid_reason"] is None
    assert env.candidate_restores == [(0.25, 0.0, 0.0)]


def test_candidate_viewpoint_restore_dataset_keeps_invalid_restore_auditable(
    tmp_path: Path,
) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        export_official_candidate_viewpoint_restore_dataset,
    )

    dataset = export_official_candidate_viewpoint_restore_dataset(
        _write_policy_trace(tmp_path),
        output_dir=tmp_path / "candidate_viewpoints",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=_PixelDetector(),
        target_detector_min_confidence=0.5,
        max_states=1,
        candidates_per_state=2,
        viewpoint_heading_count=1,
        env_factory=lambda _config: _CandidateViewpointRestoreEnv(
            invalid_candidate_x_m=0.25
        ),
    )

    invalid = dataset["candidate_viewpoints"][1]
    assert invalid["candidate_rank"] == 1
    assert invalid["valid_state_restore"] is True
    assert invalid["valid_candidate_restore"] is False
    assert invalid["invalid_reason"] == "candidate_restore_failed"
    assert invalid["labels"] == {
        "label_available": False,
        "current_target_visible_at_restore": False,
        "target_visible_from_candidate_viewpoint": False,
        "hidden_to_visible_from_candidate_viewpoint": False,
    }


def test_candidate_viewpoint_restore_fallback_uses_episode_start_pose() -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        _restore_candidate_viewpoint_observation,
    )

    sim = _CandidatePoseSim()
    env = SimpleNamespace(
        current_episode=SimpleNamespace(
            start_position=(10.0, 0.0, 20.0),
            start_rotation=(0.0, 0.0, 0.0, 1.0),
        ),
        sim=sim,
    )

    restore = _restore_candidate_viewpoint_observation(
        env,
        x_m=0.25,
        z_m=0.5,
        heading_rad=float(np.pi / 2.0),
    )

    assert restore.valid is True
    assert sim.agent.state.position.tolist() == [10.25, 0.0, 19.5]
    assert sim.agent.state.rotation == [
        0.0,
        -0.7071067811865475,
        0.0,
        0.7071067811865476,
    ]


def test_candidate_viewpoint_restore_fallback_strips_sim_rgba_alpha() -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        _restore_candidate_viewpoint_observation,
    )

    sim = _CandidatePoseSim(rgba=True)
    env = SimpleNamespace(
        current_episode=SimpleNamespace(
            start_position=(10.0, 0.0, 20.0),
            start_rotation=(0.0, 0.0, 0.0, 1.0),
        ),
        sim=sim,
    )

    restore = _restore_candidate_viewpoint_observation(
        env,
        x_m=0.0,
        z_m=0.0,
        heading_rad=0.0,
    )

    assert restore.valid is True
    assert np.asarray(restore.observation["rgb"]).shape == (2, 2, 3)


def test_candidate_viewpoint_restore_dataset_cli_writes_json_and_csv(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.export_habitat_official_candidate_viewpoint_restore_dataset import (
        main,
    )

    output_path = tmp_path / "candidate_viewpoints.json"
    csv_path = tmp_path / "candidate_viewpoints.csv"
    runner_kwargs: dict[str, Any] = {}

    def runner(*_args: object, **kwargs: object) -> dict[str, object]:
        runner_kwargs.update(kwargs)
        return {
            "task": "habitat_official_candidate_viewpoint_restore_dataset",
            "schema_version": "official-candidate-viewpoint-restore-v1",
            "state_count": 1,
            "candidate_viewpoint_count": 1,
            "target_visible_candidate_viewpoint_count": 1,
            "hidden_to_visible_candidate_viewpoint_count": 1,
            "invalid_candidate_restore_count": 0,
            "candidate_viewpoints": [
                {
                    "source_policy_trace": "trace.json",
                    "episode_index": 0,
                    "episode_id": "episode-0",
                    "scene_id": "scene.glb",
                    "target_category": "chair",
                    "step_index": 1,
                    "state_action": "turn_left",
                    "state_decision": (
                        "turn_toward_memory_active_perception_frontier"
                    ),
                    "candidate_rank": 0,
                    "candidate_count": 1,
                    "candidate_x_m": 0.0,
                    "candidate_z_m": 0.25,
                    "viewpoint_heading_count": 4,
                    "visible_heading_count": 1,
                    "valid_state_restore": True,
                    "valid_candidate_restore": True,
                    "invalid_reason": None,
                    "replay_actions": ["move_forward"],
                    "state_features": {
                        "memory_active_perception_phase_rank": 2,
                    },
                    "labels": {
                        "label_available": True,
                        "current_target_visible_at_restore": False,
                        "target_visible_from_candidate_viewpoint": True,
                        "hidden_to_visible_from_candidate_viewpoint": True,
                    },
                }
            ],
        }

    exit_code = main(
        [
            "trace.json",
            "--output",
            str(output_path),
            "--csv-output",
            str(csv_path),
            "--candidates-per-state",
            "3",
            "--viewpoint-heading-count",
            "4",
            "--max-states-per-category",
            "2",
            "--max-states-per-category-episode",
            "1",
            "--state-sampling",
            "active_phase_path",
        ],
        detector_factory=lambda *_args, **_kwargs: None,
        runner=runner,
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["task"] == "habitat_official_candidate_viewpoint_restore_dataset"
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "target_visible_from_candidate_viewpoint" in csv_text
    assert "candidate_x_m" in csv_text
    assert runner_kwargs["candidates_per_state"] == 3
    assert runner_kwargs["viewpoint_heading_count"] == 4
    assert runner_kwargs["max_states_per_category"] == 2
    assert runner_kwargs["max_states_per_category_episode"] == 1
    assert runner_kwargs["state_sampling"] == "active_phase_path"


def test_candidate_viewpoint_restore_cli_resolves_grounding_dino_default_weights(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.export_habitat_official_candidate_viewpoint_restore_dataset import (
        main,
    )

    output_path = tmp_path / "candidate_viewpoints.json"
    captured: dict[str, object] = {}

    def detector_factory(detector_name: str, **kwargs: object) -> object:
        captured["detector_name"] = detector_name
        captured["detector_kwargs"] = dict(kwargs)
        return {"detector": detector_name}

    def runner(*_args: object, **kwargs: object) -> dict[str, object]:
        captured["target_detector_adapter"] = kwargs["target_detector_adapter"]
        return {
            "task": "habitat_official_candidate_viewpoint_restore_dataset",
            "schema_version": "official-candidate-viewpoint-restore-v1",
            "state_count": 0,
            "candidate_viewpoint_count": 0,
            "target_visible_candidate_viewpoint_count": 0,
            "hidden_to_visible_candidate_viewpoint_count": 0,
            "invalid_candidate_restore_count": 0,
            "candidate_viewpoints": [],
        }

    exit_code = main(
        [
            "trace.json",
            "--output",
            str(output_path),
            "--detector",
            "grounding_dino",
            "--grounding-dino-max-image-side",
            "384",
            "--categories",
            "chair,plant",
        ],
        detector_factory=detector_factory,
        runner=runner,
    )

    assert exit_code == 0
    assert captured["detector_name"] == "grounding_dino"
    assert captured["detector_kwargs"] == {
        "model_id": "IDEA-Research/grounding-dino-tiny",
        "categories": ["chair", "plant"],
        "conf": 0.25,
        "text_threshold": 0.25,
        "max_image_side": 384,
        "device": "auto",
    }
    assert captured["target_detector_adapter"] == {"detector": "grounding_dino"}


def test_candidate_option_value_dataset_labels_hidden_to_visible_option_rollouts(
    tmp_path: Path,
) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        export_official_candidate_option_value_dataset,
    )

    envs: list[_CandidateOptionValueEnv] = []

    def env_factory(_config: object) -> "_CandidateOptionValueEnv":
        env = _CandidateOptionValueEnv()
        envs.append(env)
        return env

    dataset = export_official_candidate_option_value_dataset(
        _write_policy_trace(tmp_path),
        output_dir=tmp_path / "candidate_option_values",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=_PixelDetector(),
        target_detector_min_confidence=0.5,
        max_states=1,
        candidates_per_state=2,
        option_horizon_steps=1,
        option_scan_steps=1,
        env_factory=env_factory,
    )

    assert dataset["task"] == "habitat_official_candidate_option_value_dataset"
    assert dataset["schema_version"] == "official-candidate-option-value-v1"
    assert dataset["state_count"] == 1
    assert dataset["candidate_option_count"] == 2
    assert dataset["positive_option_count"] == 1

    first, second = dataset["candidate_viewpoints"]
    assert first["candidate_rank"] == 0
    assert first["option_rollout_actions"] == ["turn_left"]
    assert first["option_scan_step_count"] == 1
    assert first["labels"]["label_available"] is True
    assert first["labels"]["current_target_visible_at_restore"] is False
    assert first["labels"]["target_visible_within_option_rollout"] is True
    assert first["labels"]["hidden_to_visible_within_option_rollout"] is True
    assert second["candidate_rank"] == 1
    assert second["labels"]["hidden_to_visible_within_option_rollout"] is False
    assert [env.actions for env in envs] == [
        ["move_forward", "turn_left", "stop"],
        ["move_forward", "turn_right", "stop"],
    ]


def test_candidate_option_value_records_detector_confidence_gain(
    tmp_path: Path,
) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        export_official_candidate_option_value_dataset,
    )

    dataset = export_official_candidate_option_value_dataset(
        _write_policy_trace(tmp_path),
        output_dir=tmp_path / "candidate_option_values",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=_PixelDetector(),
        target_detector_min_confidence=0.5,
        max_states=1,
        candidates_per_state=1,
        option_horizon_steps=1,
        option_scan_steps=1,
        env_factory=lambda _config: _CandidateOptionValueEnv(),
    )

    row = dataset["candidate_viewpoints"][0]
    assert row["initial_detector_confidence"] is None
    assert row["best_detector_confidence"] == 0.91
    assert row["detector_confidence_gain"] == 0.91
    assert row["labels"]["detector_confidence_gain_within_option_rollout"] is True


def test_candidate_option_value_rollout_turns_then_moves_using_live_pose(
    tmp_path: Path,
) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        export_official_candidate_option_value_dataset,
    )

    policy_trace_path = tmp_path / "option_pose_trace.json"
    policy_trace_path.write_text(
        json.dumps(
            {
                "task": "official_policy_step_trace",
                "steps": [
                    _policy_step(
                        step_index=0,
                        action="turn_right",
                        decision="turn_toward_memory_active_perception_frontier",
                        memory_prior={
                            "decision": (
                                "turn_toward_memory_active_perception_frontier"
                            ),
                            "top_candidates": [
                                _candidate(
                                    rank=0,
                                    bearing_error_rad=0.75,
                                    viewpoint_cell=[39, 41],
                                    frontier_cell=[38, 41],
                                )
                            ],
                        },
                    )
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    env = _CandidateOptionPoseEnv()

    dataset = export_official_candidate_option_value_dataset(
        policy_trace_path,
        output_dir=tmp_path / "candidate_option_values",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=_PixelDetector(),
        target_detector_min_confidence=0.5,
        max_states=1,
        candidates_per_state=1,
        option_horizon_steps=2,
        option_scan_steps=1,
        env_factory=lambda _config: env,
    )

    row = dataset["candidate_viewpoints"][0]
    assert row["candidate_x_m"] == 0.25
    assert row["candidate_z_m"] == 0.25
    assert row["option_rollout_actions"] == ["turn_right", "move_forward"]
    assert env.actions == ["turn_right", "move_forward", "stop"]


def test_candidate_option_value_rollout_scans_when_candidate_corridor_blocked(
    tmp_path: Path,
) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        export_official_candidate_option_value_dataset,
    )

    policy_trace_path = tmp_path / "option_blocked_trace.json"
    policy_trace_path.write_text(
        json.dumps(
            {
                "task": "official_policy_step_trace",
                "steps": [
                    _policy_step(
                        step_index=0,
                        action="move_forward",
                        decision="move_toward_memory_active_perception_frontier",
                        memory_prior={
                            "decision": (
                                "move_toward_memory_active_perception_frontier"
                            ),
                            "top_candidates": [
                                _candidate(
                                    rank=0,
                                    bearing_error_rad=0.0,
                                    viewpoint_cell=[38, 40],
                                    frontier_cell=[37, 40],
                                )
                            ],
                        },
                    )
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    env = _BlockedCandidateOptionEnv()

    dataset = export_official_candidate_option_value_dataset(
        policy_trace_path,
        output_dir=tmp_path / "candidate_option_values",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=_PixelDetector(),
        target_detector_min_confidence=0.5,
        max_states=1,
        candidates_per_state=1,
        option_horizon_steps=2,
        option_scan_steps=2,
        env_factory=lambda _config: env,
    )

    row = dataset["candidate_viewpoints"][0]
    assert row["option_rollout_actions"] == ["turn_left", "turn_left"]
    assert row["option_scan_step_count"] == 2
    assert row["option_blocked_scan_step_count"] == 1
    assert row["labels"]["hidden_to_visible_within_option_rollout"] is True


def test_candidate_option_value_records_official_progress_and_stop_probe(
    tmp_path: Path,
) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        export_official_candidate_option_value_dataset,
    )

    env = _ProgressCandidateOptionEnv()

    dataset = export_official_candidate_option_value_dataset(
        _write_policy_trace(tmp_path),
        output_dir=tmp_path / "candidate_option_values",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=_PixelDetector(),
        target_detector_min_confidence=0.5,
        max_states=1,
        candidates_per_state=1,
        option_horizon_steps=1,
        option_scan_steps=1,
        env_factory=lambda _config: env,
    )

    row = dataset["candidate_viewpoints"][0]
    assert row["initial_distance_to_goal_m"] == 2.0
    assert row["final_distance_to_goal_m"] == 1.7
    assert row["min_distance_to_goal_m"] == 1.7
    assert row["distance_to_goal_delta_m"] == 0.3
    assert row["best_distance_to_goal_delta_m"] == 0.3
    assert row["stop_probe_success"] == 1.0
    assert row["stop_probe_spl"] == 0.5
    assert row["stop_probe_softspl"] == 0.75
    assert row["stop_probe_distance_to_goal_m"] == 1.7
    assert row["option_rollout_actions"] == ["turn_left"]
    assert "stop" not in row["option_rollout_actions"]
    assert row["labels"]["official_progress_within_option_rollout"] is True
    assert row["labels"]["official_stop_success_after_option_rollout"] is True
    assert env.actions == ["move_forward", "turn_left", "stop"]


def test_candidate_option_value_dataset_writes_csv(tmp_path: Path) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        export_official_candidate_option_value_dataset,
        write_official_candidate_option_value_dataset_csv,
    )

    dataset = export_official_candidate_option_value_dataset(
        _write_policy_trace(tmp_path),
        output_dir=tmp_path / "candidate_option_values",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=_PixelDetector(),
        target_detector_min_confidence=0.5,
        max_states=1,
        candidates_per_state=1,
        option_horizon_steps=1,
        option_scan_steps=1,
        env_factory=lambda _config: _CandidateOptionValueEnv(),
    )
    csv_path = tmp_path / "candidate_option_values.csv"

    write_official_candidate_option_value_dataset_csv(dataset, csv_path)

    csv_text = csv_path.read_text(encoding="utf-8")
    assert "hidden_to_visible_within_option_rollout" in csv_text
    assert "option_rollout_actions" in csv_text
    assert "candidate_x_m" in csv_text
    assert "turn_left" in csv_text


def test_candidate_option_value_dataset_cli_writes_json_and_csv(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.export_habitat_official_candidate_option_value_dataset import (
        main,
    )

    output_path = tmp_path / "candidate_option_values.json"
    csv_path = tmp_path / "candidate_option_values.csv"
    runner_kwargs: dict[str, Any] = {}

    def runner(*_args: object, **kwargs: object) -> dict[str, object]:
        runner_kwargs.update(kwargs)
        return {
            "task": "habitat_official_candidate_option_value_dataset",
            "schema_version": "official-candidate-option-value-v1",
            "state_count": 1,
            "candidate_option_count": 1,
            "positive_option_count": 1,
            "invalid_option_count": 0,
            "candidate_viewpoints": [
                {
                    "source_policy_trace": "trace.json",
                    "episode_index": 0,
                    "episode_id": "episode-0",
                    "scene_id": "scene.glb",
                    "target_category": "chair",
                    "step_index": 1,
                    "state_action": "turn_left",
                    "state_decision": (
                        "turn_toward_memory_active_perception_frontier"
                    ),
                    "candidate_rank": 0,
                    "candidate_count": 1,
                    "candidate_x_m": 0.0,
                    "candidate_z_m": 0.25,
                    "valid_option_rollout": True,
                    "invalid_reason": None,
                    "replay_actions": ["move_forward"],
                    "option_rollout_actions": ["turn_left"],
                    "state_features": {
                        "memory_active_perception_phase_rank": 2,
                    },
                    "labels": {
                        "label_available": True,
                        "current_target_visible_at_restore": False,
                        "target_visible_within_option_rollout": True,
                        "hidden_to_visible_within_option_rollout": True,
                    },
                }
            ],
        }

    exit_code = main(
        [
            "trace.json",
            "--output",
            str(output_path),
            "--csv-output",
            str(csv_path),
            "--candidates-per-state",
            "3",
            "--option-horizon-steps",
            "7",
            "--option-scan-steps",
            "2",
            "--option-progress-threshold-m",
            "0.2",
            "--max-states-per-category",
            "2",
            "--max-states-per-category-episode",
            "1",
            "--state-sampling",
            "active_phase_path",
        ],
        detector_factory=lambda *_args, **_kwargs: None,
        runner=runner,
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["task"] == "habitat_official_candidate_option_value_dataset"
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "target_visible_within_option_rollout" in csv_text
    assert runner_kwargs["candidates_per_state"] == 3
    assert runner_kwargs["option_horizon_steps"] == 7
    assert runner_kwargs["option_scan_steps"] == 2
    assert runner_kwargs["option_progress_threshold_m"] == 0.2
    assert runner_kwargs["max_states_per_category"] == 2
    assert runner_kwargs["max_states_per_category_episode"] == 1
    assert runner_kwargs["state_sampling"] == "active_phase_path"


def test_candidate_option_value_cli_resolves_grounding_dino_default_weights(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.export_habitat_official_candidate_option_value_dataset import (
        main,
    )

    output_path = tmp_path / "candidate_option_values.json"
    captured: dict[str, object] = {}

    def detector_factory(detector_name: str, **kwargs: object) -> object:
        captured["detector_name"] = detector_name
        captured["detector_kwargs"] = dict(kwargs)
        return {"detector": detector_name}

    def runner(*_args: object, **kwargs: object) -> dict[str, object]:
        captured["target_detector_adapter"] = kwargs["target_detector_adapter"]
        return {
            "task": "habitat_official_candidate_option_value_dataset",
            "schema_version": "official-candidate-option-value-v1",
            "state_count": 0,
            "candidate_option_count": 0,
            "positive_option_count": 0,
            "invalid_option_count": 0,
            "candidate_viewpoints": [],
        }

    exit_code = main(
        [
            "trace.json",
            "--output",
            str(output_path),
            "--detector",
            "grounding_dino",
            "--grounding-dino-max-image-side",
            "384",
            "--categories",
            "chair,plant",
        ],
        detector_factory=detector_factory,
        runner=runner,
    )

    assert exit_code == 0
    assert captured["detector_kwargs"] == {
        "model_id": "IDEA-Research/grounding-dino-tiny",
        "categories": ["chair", "plant"],
        "conf": 0.25,
        "text_threshold": 0.25,
        "max_image_side": 384,
        "device": "auto",
    }
    assert captured["target_detector_adapter"] == {"detector": "grounding_dino"}


def test_candidate_rollout_dataset_writes_stable_csv(tmp_path: Path) -> None:
    dataset = export_official_candidate_rollout_dataset(
        _write_policy_trace(tmp_path),
        output_dir=tmp_path / "rollouts",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=_PixelDetector(),
        max_states=1,
        candidates_per_state=2,
        rollout_horizon_steps=1,
        env_factory=lambda _config: _BranchReplayEnv(),
    )
    csv_path = tmp_path / "rollouts.csv"

    write_official_candidate_rollout_dataset_csv(dataset, csv_path)

    rows = csv_path.read_text(encoding="utf-8").splitlines()
    header = rows[0].split(",")
    assert "candidate_rank" in header
    assert "hidden_to_visible_within_rollout" in header
    assert "rollout_actions" in header
    assert "turn_left" in rows[1]
    assert rows[1].endswith("true")
    assert rows[2].endswith("false")


def test_candidate_rollout_dataset_can_branch_explicit_first_actions(
    tmp_path: Path,
) -> None:
    dataset = export_official_candidate_rollout_dataset(
        _write_policy_trace(tmp_path),
        output_dir=tmp_path / "rollouts",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=_PixelDetector(),
        max_states=1,
        rollout_horizon_steps=1,
        branch_actions=("turn_left", "turn_right"),
        env_factory=lambda _config: _BranchReplayEnv(),
    )

    assert dataset["branch_mode"] == "action_matrix"
    assert dataset["rollout_count"] == 2
    assert dataset["positive_rollout_count"] == 1
    left_action, right_action = dataset["rollouts"]
    assert left_action["branch_kind"] == "action"
    assert left_action["branch_action"] == "turn_left"
    assert left_action["rollout_actions"] == ["turn_left"]
    assert left_action["labels"]["hidden_to_visible_within_rollout"] is True
    assert right_action["branch_kind"] == "action"
    assert right_action["branch_action"] == "turn_right"
    assert right_action["rollout_actions"] == ["turn_right"]
    assert right_action["labels"]["hidden_to_visible_within_rollout"] is False


def test_candidate_rollout_dataset_can_repeat_explicit_first_actions(
    tmp_path: Path,
) -> None:
    envs: list[_BranchReplayEnv] = []

    def env_factory(_config: object) -> _BranchReplayEnv:
        env = _BranchReplayEnv()
        envs.append(env)
        return env

    dataset = export_official_candidate_rollout_dataset(
        _write_policy_trace(tmp_path),
        output_dir=tmp_path / "rollouts",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=None,
        max_states=1,
        rollout_horizon_steps=3,
        branch_actions=("turn_left", "turn_right", "move_forward"),
        branch_followup_policy="repeat_first_action",
        env_factory=env_factory,
    )

    assert dataset["branch_followup_policy"] == "repeat_first_action"
    assert [
        rollout["rollout_actions"] for rollout in dataset["rollouts"]
    ] == [
        ["turn_left", "turn_left", "turn_left"],
        ["turn_right", "turn_right", "turn_right"],
        ["move_forward", "move_forward", "move_forward"],
    ]
    assert [env.actions for env in envs] == [
        ["move_forward", "turn_left", "turn_left", "turn_left"],
        ["move_forward", "turn_right", "turn_right", "turn_right"],
        ["move_forward", "move_forward", "move_forward", "move_forward"],
    ]
    assert dataset["positive_rollout_count"] == 0


def test_candidate_rollout_dataset_can_limit_states_per_target_category(
    tmp_path: Path,
) -> None:
    dataset = export_official_candidate_rollout_dataset(
        _write_policy_trace_with_categories(
            tmp_path,
            ["chair", "chair", "chair", "bed", "bed", "sofa"],
        ),
        output_dir=tmp_path / "rollouts",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=None,
        rollout_horizon_steps=1,
        branch_actions=("turn_left",),
        max_states_per_category=2,
        env_factory=lambda _config: _BranchReplayEnv(),
    )

    assert dataset["candidate_state_limit_per_category"] == 2
    assert dataset["state_count"] == 5
    assert [rollout["target_category"] for rollout in dataset["rollouts"]] == [
        "chair",
        "chair",
        "bed",
        "bed",
        "sofa",
    ]
    assert [rollout["step_index"] for rollout in dataset["rollouts"]] == [
        0,
        1,
        3,
        4,
        5,
    ]


def test_candidate_rollout_dataset_can_sample_states_by_top_candidate_score(
    tmp_path: Path,
) -> None:
    dataset = export_official_candidate_rollout_dataset(
        _write_policy_trace_with_category_scores(
            tmp_path,
            [
                ("chair", 0.10),
                ("chair", 0.90),
                ("chair", 0.70),
                ("bed", 0.20),
                ("bed", 0.80),
                ("bed", 0.60),
            ],
        ),
        output_dir=tmp_path / "rollouts",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=None,
        rollout_horizon_steps=1,
        branch_actions=("turn_left",),
        max_states_per_category=2,
        state_sampling="top_score_desc",
        env_factory=lambda _config: _BranchReplayEnv(),
    )

    assert dataset["candidate_state_sampling"] == "top_score_desc"
    assert dataset["state_count"] == 4
    assert [rollout["target_category"] for rollout in dataset["rollouts"]] == [
        "chair",
        "bed",
        "chair",
        "bed",
    ]
    assert [rollout["step_index"] for rollout in dataset["rollouts"]] == [
        1,
        4,
        2,
        5,
    ]


def test_candidate_rollout_dataset_can_sample_active_viewpoint_phases_across_episodes(
    tmp_path: Path,
) -> None:
    dataset = export_official_candidate_rollout_dataset(
        _write_policy_trace_for_phase_sampling(tmp_path),
        output_dir=tmp_path / "rollouts",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=None,
        rollout_horizon_steps=1,
        branch_actions=("turn_left",),
        max_states_per_category=4,
        max_states_per_category_episode=1,
        state_sampling="active_phase_path",
        env_factory=lambda _config: _BranchReplayEnv(),
    )

    assert dataset["candidate_state_sampling"] == "active_phase_path"
    assert dataset["candidate_state_limit_per_category_episode"] == 1
    assert dataset["state_count"] == 3
    assert [
        (
            rollout["episode_index"],
            rollout["step_index"],
            rollout["state_decision"],
        )
        for rollout in dataset["rollouts"]
    ] == [
        (0, 1, "orient_memory_anchor_from_active_viewpoint"),
        (1, 0, "orient_memory_anchor_from_active_viewpoint"),
        (2, 0, "turn_toward_memory_active_perception_frontier"),
    ]
    orient_features = dataset["rollouts"][0]["state_features"]
    assert orient_features["memory_active_perception_phase_rank"] == 0
    assert orient_features["memory_active_perception_orient_anchor"] is True
    assert orient_features["memory_active_perception_scan_anchor"] is False
    assert orient_features["memory_active_perception_frontier"] is False
    assert orient_features["memory_active_perception_at_viewpoint"] is True
    assert orient_features["memory_active_perception_scan_steps_remaining"] is None


def test_candidate_rollout_dataset_records_predecision_state_features(
    tmp_path: Path,
) -> None:
    dataset = export_official_candidate_rollout_dataset(
        _write_policy_trace(tmp_path),
        output_dir=tmp_path / "rollouts",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_detector_adapter=None,
        max_states=1,
        rollout_horizon_steps=1,
        branch_actions=("turn_left",),
        env_factory=lambda _config: _BranchReplayEnv(),
    )

    features = dataset["rollouts"][0]["state_features"]
    assert features["agent_x_m"] == 1.0
    assert features["agent_z_m"] == 0.0
    assert features["agent_heading_rad"] == 0.0
    assert features["memory_bearing_error_rad"] == -0.7
    assert features["memory_anchor_bearing_error_rad"] == -0.25
    assert features["memory_distance_to_anchor_m"] == 1.5
    assert features["memory_expected_evidence"] == 0.6
    assert features["memory_active_perception_candidate_count"] == 7
    assert features["memory_top_candidate_count"] == 2
    assert features["memory_top_score"] == 0.4
    assert features["memory_score_gap"] == 0.1
    assert features["memory_active_perception_phase_rank"] == 2
    assert features["memory_active_perception_orient_anchor"] is False
    assert features["memory_active_perception_scan_anchor"] is False
    assert features["memory_active_perception_frontier"] is True
    assert features["memory_active_perception_at_viewpoint"] is False
    assert features["memory_active_perception_scan_steps_remaining"] is None
    assert features["local_center_depth_clear"] is True
    assert features["local_center_depth_median"] == 1.0
    assert features["recent_target_visible_count"] == 2
    assert features["steps_since_last_target_visible"] == 3
    assert features["previous_target_visible"] is True
    assert "hidden_to_visible_within_rollout" not in features

    csv_path = tmp_path / "rollouts.csv"
    write_official_candidate_rollout_dataset_csv(dataset, csv_path)
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "memory_anchor_bearing_error_rad" in csv_text
    assert "memory_active_perception_phase_rank" in csv_text
    assert "local_center_depth_clear" in csv_text


def test_candidate_rollout_dataset_cli_writes_json_and_csv(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.export_habitat_official_candidate_rollout_dataset import (
        main,
    )

    policy_trace_path = _write_policy_trace(tmp_path)
    output_path = tmp_path / "dataset.json"
    csv_path = tmp_path / "dataset.csv"
    runner_kwargs: dict[str, Any] = {}

    def runner(*args: Any, **kwargs: Any) -> dict[str, Any]:
        runner_kwargs.update(kwargs)
        return {
            "task": "habitat_official_candidate_rollout_dataset",
            "schema_version": "official-candidate-rollout-v1",
            "state_count": 0,
            "rollout_count": 0,
            "positive_rollout_count": 0,
            "invalid_rollout_count": 0,
            "rollouts": [],
        }

    exit_code = main(
        [
            str(policy_trace_path),
            "--output",
            str(output_path),
            "--csv-output",
            str(csv_path),
            "--config-path",
            "official.yaml",
            "--dataset-data-path",
            "val_mini.json.gz",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--split",
            "val_mini",
            "--detector",
            "none",
            "--max-states",
            "3",
            "--candidates-per-state",
            "4",
            "--rollout-horizon-steps",
            "2",
            "--max-states-per-category",
            "2",
            "--max-states-per-category-episode",
            "1",
            "--state-sampling",
            "active_phase_path",
            "--branch-actions",
            "turn_left,turn_right",
            "--branch-followup-policy",
            "repeat_first_action",
        ],
        runner=runner,
    )

    assert exit_code == 0
    dataset = json.loads(output_path.read_text(encoding="utf-8"))
    assert dataset["task"] == "habitat_official_candidate_rollout_dataset"
    assert "hidden_to_visible_within_rollout" in csv_path.read_text(encoding="utf-8")
    assert runner_kwargs["config_path"] == "official.yaml"
    assert runner_kwargs["max_states"] == 3
    assert runner_kwargs["max_states_per_category"] == 2
    assert runner_kwargs["max_states_per_category_episode"] == 1
    assert runner_kwargs["state_sampling"] == "active_phase_path"
    assert runner_kwargs["candidates_per_state"] == 4
    assert runner_kwargs["rollout_horizon_steps"] == 2
    assert runner_kwargs["branch_actions"] == ("turn_left", "turn_right")
    assert runner_kwargs["branch_followup_policy"] == "repeat_first_action"
    assert runner_kwargs["target_detector_adapter"] is None


def test_candidate_rollout_cli_resolves_grounding_dino_default_weights(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.export_habitat_official_candidate_rollout_dataset import (
        main,
    )

    output_path = tmp_path / "dataset.json"
    captured: dict[str, object] = {}

    def detector_factory(detector_name: str, **kwargs: object) -> object:
        captured["detector_name"] = detector_name
        captured["detector_kwargs"] = dict(kwargs)
        return {"detector": detector_name}

    def runner(*_args: object, **kwargs: object) -> dict[str, object]:
        captured["target_detector_adapter"] = kwargs["target_detector_adapter"]
        return {
            "task": "habitat_official_candidate_rollout_dataset",
            "schema_version": "official-candidate-rollout-v1",
            "state_count": 0,
            "rollout_count": 0,
            "positive_rollout_count": 0,
            "invalid_rollout_count": 0,
            "rollouts": [],
        }

    exit_code = main(
        [
            "trace.json",
            "--output",
            str(output_path),
            "--detector",
            "grounding_dino",
            "--grounding-dino-max-image-side",
            "384",
            "--categories",
            "chair,plant",
        ],
        detector_factory=detector_factory,
        runner=runner,
    )

    assert exit_code == 0
    assert captured["detector_kwargs"] == {
        "model_id": "IDEA-Research/grounding-dino-tiny",
        "categories": ["chair", "plant"],
        "conf": 0.25,
        "text_threshold": 0.25,
        "max_image_side": 384,
        "device": "auto",
    }
    assert captured["target_detector_adapter"] == {"detector": "grounding_dino"}


def test_candidate_rollout_dataset_cli_module_has_main_guard() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "objectnav_core.cli.export_habitat_official_candidate_rollout_dataset",
            "--help",
        ],
        check=False,
        capture_output=True,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
    )

    assert completed.returncode == 0
    assert "candidate rollout labels" in completed.stdout


def test_candidate_rollout_action_matrix_report_scores_fastest_actions(
    tmp_path: Path,
) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        build_official_candidate_rollout_action_matrix_report,
        write_official_candidate_rollout_action_matrix_report_csv,
    )

    dataset = {
        "task": "habitat_official_candidate_rollout_dataset",
        "rollouts": [
            _action_rollout(0, "turn_left", success=True, action_count=3),
            _action_rollout(0, "turn_right", success=True, action_count=1),
            _action_rollout(0, "move_forward", success=False, action_count=5),
            _action_rollout(1, "turn_left", success=True, action_count=2),
            _action_rollout(1, "turn_right", success=False, action_count=5),
            _action_rollout(1, "move_forward", success=True, action_count=2),
            _action_rollout(2, "turn_left", current_visible=True, action_count=0),
            _action_rollout(2, "turn_right", current_visible=True, action_count=0),
            _action_rollout(2, "move_forward", current_visible=True, action_count=0),
        ],
    }

    report = build_official_candidate_rollout_action_matrix_report(
        [dataset],
        current_hidden_only=True,
    )

    assert report["task"] == "habitat_official_candidate_rollout_action_matrix_report"
    assert report["state_count"] == 2
    assert report["rollout_count"] == 6
    assert report["aggregate"]["strict_fastest_action_counts"] == {"turn_right": 1}
    assert report["aggregate"]["fastest_action_tie_count"] == 1
    assert report["aggregate"]["action_counts"]["turn_right"] == {
        "rollout_count": 2,
        "success_count": 1,
        "fastest_count": 1,
        "strict_fastest_count": 1,
    }

    first_state, second_state = report["states"]
    assert first_state["strict_fastest_action"] == "turn_right"
    assert first_state["fastest_actions"] == ["turn_right"]
    assert second_state["strict_fastest_action"] is None
    assert second_state["fastest_actions"] == ["move_forward", "turn_left"]

    csv_path = tmp_path / "report.csv"
    write_official_candidate_rollout_action_matrix_report_csv(
        report,
        csv_path,
    )
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "strict_fastest_action" in csv_text
    assert "turn_right" in csv_text


def test_candidate_rollout_action_matrix_report_preserves_state_features(
    tmp_path: Path,
) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
        build_official_candidate_rollout_action_matrix_report,
        write_official_candidate_rollout_action_matrix_report_csv,
    )

    features = {
        "memory_anchor_bearing_error_rad": -0.42,
        "local_center_depth_clear": True,
        "recent_target_visible_count": 1,
    }
    dataset = {
        "task": "habitat_official_candidate_rollout_dataset",
        "rollouts": [
            _action_rollout(
                0,
                "turn_left",
                success=True,
                action_count=2,
                state_features=features,
            ),
            _action_rollout(
                0,
                "turn_right",
                success=False,
                action_count=5,
                state_features=features,
            ),
            _action_rollout(
                0,
                "move_forward",
                success=False,
                action_count=5,
                state_features=features,
            ),
        ],
    }

    report = build_official_candidate_rollout_action_matrix_report([dataset])

    assert report["states"][0]["state_features"] == features
    csv_path = tmp_path / "report.csv"
    write_official_candidate_rollout_action_matrix_report_csv(report, csv_path)
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "memory_anchor_bearing_error_rad" in csv_text
    assert "-0.42" in csv_text


def test_candidate_rollout_action_matrix_report_cli_writes_json_and_csv(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix import (
        main,
    )

    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        json.dumps(
            {
                "task": "habitat_official_candidate_rollout_dataset",
                "rollouts": [
                    _action_rollout(0, "turn_left", success=True, action_count=2),
                    _action_rollout(0, "turn_right", success=False, action_count=5),
                    _action_rollout(0, "move_forward", success=True, action_count=1),
                ],
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "report.json"
    csv_path = tmp_path / "report.csv"

    exit_code = main(
        [
            str(dataset_path),
            "--output",
            str(output_path),
            "--csv-output",
            str(csv_path),
        ]
    )

    assert exit_code == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["aggregate"]["strict_fastest_action_counts"] == {
        "move_forward": 1
    }
    assert "candidate_score_move_forward" not in csv_path.read_text(encoding="utf-8")


def _write_policy_trace(tmp_path: Path) -> Path:
    policy_trace_path = tmp_path / "policy_trace.json"
    policy_trace_path.write_text(
        json.dumps(
            {
                "task": "official_policy_step_trace",
                "steps": [
                    _policy_step(
                        step_index=0,
                        action="move_forward",
                        decision="move_toward_memory_active_perception_frontier",
                    ),
                    _policy_step(
                        step_index=1,
                        action="turn_left",
                        decision="turn_toward_memory_active_perception_frontier",
                        memory_prior={
                            "decision": (
                                "turn_toward_memory_active_perception_frontier"
                            ),
                            "active_perception_candidate_count": 7,
                            "anchor_bearing_error_rad": -0.25,
                            "current_bbox_area_fraction": 0.01,
                            "current_detector_confidence": 0.42,
                            "current_depth_median": 0.8,
                            "selected_viewpoint_cell": [39, 40],
                            "selected_frontier_cell": [38, 40],
                            "previous_target_visible": True,
                            "recent_target_visible_count": 2,
                            "steps_since_last_target_visible": 3,
                            "top_candidates": [
                                _candidate(
                                    rank=0,
                                    bearing_error_rad=-0.7,
                                    viewpoint_cell=[39, 40],
                                    frontier_cell=[38, 40],
                                ),
                                _candidate(
                                    rank=1,
                                    bearing_error_rad=0.7,
                                    viewpoint_cell=[39, 41],
                                    frontier_cell=[38, 41],
                                ),
                            ],
                        },
                    ),
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return policy_trace_path


def _write_policy_trace_with_categories(
    tmp_path: Path,
    categories: list[str],
) -> Path:
    policy_trace_path = tmp_path / "policy_trace_categories.json"
    policy_trace_path.write_text(
        json.dumps(
            {
                "task": "official_policy_step_trace",
                "steps": [
                    _policy_step(
                        step_index=index,
                        action="move_forward",
                        decision="move_toward_memory_active_perception_frontier",
                        target_category=category,
                        memory_prior={
                            "decision": (
                                "move_toward_memory_active_perception_frontier"
                            ),
                            "top_candidates": [
                                _candidate(
                                    rank=0,
                                    bearing_error_rad=-0.1,
                                    viewpoint_cell=[39, 40],
                                    frontier_cell=[38, 40],
                                ),
                            ],
                        },
                    )
                    for index, category in enumerate(categories)
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return policy_trace_path


def _write_policy_trace_with_category_scores(
    tmp_path: Path,
    category_scores: list[tuple[str, float]],
) -> Path:
    policy_trace_path = tmp_path / "policy_trace_category_scores.json"
    policy_trace_path.write_text(
        json.dumps(
            {
                "task": "official_policy_step_trace",
                "steps": [
                    _policy_step(
                        step_index=index,
                        action="move_forward",
                        decision="move_toward_memory_active_perception_frontier",
                        target_category=category,
                        memory_prior={
                            "decision": (
                                "move_toward_memory_active_perception_frontier"
                            ),
                            "top_candidates": [
                                _candidate(
                                    rank=0,
                                    bearing_error_rad=-0.1,
                                    viewpoint_cell=[39, 40],
                                    frontier_cell=[38, 40],
                                    score=score,
                                ),
                            ],
                        },
                    )
                    for index, (category, score) in enumerate(category_scores)
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return policy_trace_path


def _write_policy_trace_for_phase_sampling(tmp_path: Path) -> Path:
    policy_trace_path = tmp_path / "policy_trace_phase_sampling.json"
    policy_trace_path.write_text(
        json.dumps(
            {
                "task": "official_policy_step_trace",
                "steps": [
                    _phase_policy_step(
                        episode_index=0,
                        step_index=0,
                        decision="move_toward_memory_active_perception_frontier",
                        phase="",
                        path_distance_m=2.0,
                        score=0.90,
                    ),
                    _phase_policy_step(
                        episode_index=0,
                        step_index=1,
                        decision="orient_memory_anchor_from_active_viewpoint",
                        phase="orient_anchor",
                        path_distance_m=0.0,
                        score=0.10,
                    ),
                    _phase_policy_step(
                        episode_index=0,
                        step_index=2,
                        decision="orient_memory_anchor_from_active_viewpoint",
                        phase="orient_anchor",
                        path_distance_m=0.0,
                        score=0.08,
                    ),
                    _phase_policy_step(
                        episode_index=1,
                        step_index=0,
                        decision="orient_memory_anchor_from_active_viewpoint",
                        phase="orient_anchor",
                        path_distance_m=0.0,
                        score=0.05,
                    ),
                    _phase_policy_step(
                        episode_index=1,
                        step_index=1,
                        decision="scan_memory_anchor_from_active_viewpoint",
                        phase="scan_anchor",
                        path_distance_m=0.0,
                        score=0.04,
                    ),
                    _phase_policy_step(
                        episode_index=2,
                        step_index=0,
                        decision="turn_toward_memory_active_perception_frontier",
                        phase="",
                        path_distance_m=1.0,
                        score=0.50,
                    ),
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return policy_trace_path


def _phase_policy_step(
    *,
    episode_index: int,
    step_index: int,
    decision: str,
    phase: str,
    path_distance_m: float,
    score: float,
) -> dict[str, object]:
    return _policy_step(
        episode_index=episode_index,
        step_index=step_index,
        action="turn_left" if "turn" in decision or "orient" in decision else "move_forward",
        decision=decision,
        target_category="bed",
        memory_prior={
            "active_perception_phase": phase,
            "decision": decision,
            "path_distance_m": path_distance_m,
            "score": score,
            "selected_viewpoint_cell": [39, 40],
            "selected_frontier_cell": [38, 40],
            "top_candidates": [
                _candidate(
                    rank=0,
                    bearing_error_rad=-0.1,
                    viewpoint_cell=[39, 40],
                    frontier_cell=[38, 40],
                    score=score,
                    path_distance_m=path_distance_m,
                ),
            ],
        },
    )


def _policy_step(
    *,
    step_index: int,
    action: str,
    decision: str,
    episode_index: int = 0,
    target_category: str = "chair",
    memory_prior: dict[str, object] | None = None,
) -> dict[str, object]:
    step: dict[str, object] = {
        "action": action,
        "decision": decision,
        "episode_id": "episode-0",
        "episode_index": episode_index,
        "heading_rad": 0.0,
        "policy": "memory_active_perception_frontier",
        "policy_kind": "memory_active_perception_frontier_active_search",
        "scene_id": "scene.glb",
        "step_index": step_index,
        "target_category": target_category,
        "x_m": float(step_index),
        "z_m": 0.0,
    }
    if memory_prior is not None:
        step["memory_prior"] = memory_prior
    return step


def _candidate(
    *,
    rank: int,
    bearing_error_rad: float,
    viewpoint_cell: list[int],
    frontier_cell: list[int],
    score: float | None = None,
    path_distance_m: float | None = None,
) -> dict[str, object]:
    safe_path_distance_m = path_distance_m if path_distance_m is not None else 0.5 + rank
    return {
        "bearing_error_rad": bearing_error_rad,
        "bearing_rad": bearing_error_rad,
        "belief_mass": 0.8 - 0.1 * rank,
        "distance_to_anchor_m": 1.5 + rank,
        "expected_evidence": 0.6 - 0.1 * rank,
        "frontier_cell": frontier_cell,
        "path_distance_m": safe_path_distance_m,
        "score": score if score is not None else 0.4 - 0.1 * rank,
        "travel_distance_m": safe_path_distance_m,
        "view_bearing_quality": 1.0,
        "view_distance_quality": 0.9,
        "view_quality": 0.9,
        "viewpoint_cell": viewpoint_cell,
    }


class _BranchReplayEnv:
    def __init__(self) -> None:
        self.actions: list[str] = []
        self.episode_over = False
        self.current_episode = SimpleNamespace(
            episode_id="episode-0",
            scene_id="scene.glb",
            object_category="chair",
        )

    def reset(self) -> dict[str, object]:
        self.actions = []
        self.episode_over = False
        return _observation(visible=False)

    def step(self, action: str) -> dict[str, object]:
        self.actions.append(action)
        if action == "stop":
            self.episode_over = True
        return _observation(visible=len(self.actions) >= 2 and action == "turn_left")

    def get_metrics(self) -> dict[str, float]:
        return {
            "success": 0.0,
            "spl": 0.0,
            "soft_spl": 0.0,
            "distance_to_goal": 1.0,
        }


class _StateRestoreVisibleEnv(_BranchReplayEnv):
    def step(self, action: str) -> dict[str, object]:
        self.actions.append(action)
        return _observation(visible=action == "move_forward")


class _CandidateViewpointRestoreEnv(_BranchReplayEnv):
    def __init__(self, invalid_candidate_x_m: float | None = None) -> None:
        super().__init__()
        self.invalid_candidate_x_m = invalid_candidate_x_m
        self.candidate_restores: list[tuple[float, float, float]] = []

    def restore_candidate_viewpoint(
        self,
        *,
        x_m: float,
        z_m: float,
        heading_rad: float,
    ) -> dict[str, object] | None:
        rounded = (
            round(float(x_m), 6),
            round(float(z_m), 6),
            round(float(heading_rad), 6),
        )
        self.candidate_restores.append(rounded)
        if (
            self.invalid_candidate_x_m is not None
            and round(float(x_m), 6) == round(self.invalid_candidate_x_m, 6)
        ):
            return None
        visible = x_m > 0.0 and abs(float(heading_rad) - float(np.pi / 2.0)) < 1e-6
        return _observation(visible=visible)


class _CandidateOptionValueEnv(_BranchReplayEnv):
    def step(self, action: str) -> dict[str, object]:
        self.actions.append(action)
        visible = self.actions == ["move_forward", "turn_left"]
        return _observation(visible=visible)


class _CandidateOptionPoseEnv(_BranchReplayEnv):
    def reset(self) -> dict[str, object]:
        self.actions = []
        self.episode_over = False
        return _observation(visible=False)

    def step(self, action: str) -> dict[str, object]:
        self.actions.append(action)
        if action == "turn_right":
            observation = _observation(visible=False)
            observation["compass"] = np.array([np.pi / 4.0], dtype=float)
            return observation
        if action == "move_forward":
            observation = _observation(visible=False)
            observation["gps"] = np.array([0.2, 0.2], dtype=float)
            observation["compass"] = np.array([np.pi / 4.0], dtype=float)
            return observation
        return _observation(visible=False)


class _BlockedCandidateOptionEnv(_BranchReplayEnv):
    def reset(self) -> dict[str, object]:
        self.actions = []
        self.episode_over = False
        return _blocked_observation(visible=False)

    def step(self, action: str) -> dict[str, object]:
        self.actions.append(action)
        return _blocked_observation(visible=len(self.actions) >= 2)


class _ProgressCandidateOptionEnv(_CandidateOptionValueEnv):
    def get_metrics(self) -> dict[str, float]:
        if self.actions and self.actions[-1] == "stop":
            return {
                "success": 1.0,
                "spl": 0.5,
                "soft_spl": 0.75,
                "distance_to_goal": 1.7,
            }
        distance = 1.7 if len(self.actions) >= 2 else 2.0
        return {
            "success": 0.0,
            "spl": 0.0,
            "soft_spl": 0.0,
            "distance_to_goal": distance,
        }


class _CandidatePoseSim:
    def __init__(self, *, rgba: bool = False) -> None:
        self.agent = _CandidatePoseAgent()
        self.rgba = rgba

    def initialize_agent(self, _agent_id: int) -> "_CandidatePoseAgent":
        return self.agent

    def get_sensor_observations(self) -> dict[str, object]:
        observation = _observation(visible=True)
        if self.rgba:
            rgb = np.asarray(observation["rgb"], dtype=np.uint8)
            alpha = np.full((*rgb.shape[:2], 1), 255, dtype=np.uint8)
            observation["rgb"] = np.concatenate([rgb, alpha], axis=2)
        return observation


class _CandidatePoseAgent:
    def __init__(self) -> None:
        self.state = SimpleNamespace(
            position=np.zeros(3, dtype=float),
            rotation=[0.0, 0.0, 0.0, 1.0],
        )

    def get_state(self) -> SimpleNamespace:
        return self.state

    def set_state(self, state: SimpleNamespace) -> None:
        self.state = state


class _PixelDetector:
    def detect(self, rgb: np.ndarray) -> list[Detection]:
        if int(rgb[0, 0, 0]) != 255:
            return []
        return [
            Detection(
                category="chair",
                bbox=(0, 0, 1, 1),
                confidence=0.91,
                mask=np.ones((2, 2), dtype=bool),
            )
        ]


def _observation(*, visible: bool) -> dict[str, object]:
    rgb = np.zeros((2, 2, 3), dtype=np.uint8)
    if visible:
        rgb[0, 0, 0] = 255
    return {
        "rgb": rgb,
        "depth": np.ones((3, 3), dtype=float),
        "gps": np.array([0.0, 0.0], dtype=float),
        "compass": np.array([0.0], dtype=float),
        "objectgoal": 0,
    }


def _blocked_observation(*, visible: bool) -> dict[str, object]:
    observation = _observation(visible=visible)
    observation["depth"] = np.zeros((3, 3), dtype=float)
    return observation


def _action_rollout(
    state_index: int,
    branch_action: str,
    *,
    success: bool = False,
    current_visible: bool = False,
    action_count: int,
    state_features: dict[str, object] | None = None,
) -> dict[str, object]:
    rollout_actions = [branch_action for _ in range(action_count)]
    return {
        "source_policy_trace": "trace.json",
        "state_index": state_index,
        "episode_index": 0,
        "episode_id": "episode-0",
        "scene_id": "scene.glb",
        "target_category": "chair",
        "step_index": state_index,
        "state_action": "turn_left",
        "state_decision": "turn_toward_memory_active_perception_frontier",
        "branch_kind": "action",
        "branch_action": branch_action,
        "valid_rollout": True,
        "rollout_actions": rollout_actions,
        "state_features": state_features or {},
        "labels": {
            "current_target_visible": current_visible,
            "target_visible_within_rollout": current_visible or success,
            "hidden_to_visible_within_rollout": success,
            "label_available": True,
        },
    }
