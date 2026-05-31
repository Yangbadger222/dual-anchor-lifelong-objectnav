from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from objectnav_core.evaluation.habitat_official_targetnav_local_policy_dataset import (
    export_official_targetnav_local_policy_dataset,
    write_official_targetnav_local_policy_dataset_csv,
)


def test_targetnav_local_policy_dataset_exports_oracle_teacher_examples() -> None:
    envs: list[_OracleTargetNavEnv] = []
    followers: list[_FakeFollower] = []

    def env_factory(_config: object) -> _OracleTargetNavEnv:
        env = _OracleTargetNavEnv()
        envs.append(env)
        return env

    def follower_factory(env: object, *, goal_radius_m: float) -> _FakeFollower:
        assert goal_radius_m == pytest.approx(0.35)
        follower = _FakeFollower(actions=[1, 2, 0])
        followers.append(follower)
        return follower

    dataset = export_official_targetnav_local_policy_dataset(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        max_episodes=1,
        max_steps=3,
        seed=7,
        goal_radius_m=0.35,
        env_factory=env_factory,
        follower_factory=follower_factory,
    )

    assert dataset["task"] == "habitat_official_targetnav_local_policy_dataset"
    assert dataset["schema_version"] == "official-targetnav-local-policy-v1"
    assert dataset["source_validity"] == "oracle_teacher_only"
    assert dataset["config"]["config_path"] == "official.yaml"
    assert dataset["episode_count"] == 1
    assert dataset["example_count"] == 3
    assert dataset["skipped_no_goal_episode_count"] == 0
    assert dataset["skipped_teacher_unavailable_episode_count"] == 0
    assert dataset["action_distribution"] == {
        "move_forward": 1,
        "stop": 1,
        "turn_left": 1,
    }

    first = dataset["examples"][0]
    assert first["episode_id"] == "episode-0"
    assert first["scene_id"] == "scene.glb"
    assert first["target_category"] == "chair"
    assert first["step_index"] == 0
    assert first["goal_position"] == [0.0, 0.0, -2.0]
    assert first["target_goal"] == {
        "x_m": 0.0,
        "z_m": 2.0,
        "coordinate_frame": "episode_start_relative",
        "conversion": "episode_start_pose",
    }
    assert first["pointgoal_with_gps_compass"] == pytest.approx([2.0, 0.0])
    assert first["teacher_action"] == "move_forward"
    assert first["teacher_action_raw"] == 1
    assert first["depth_stats"] == {
        "height": 2,
        "width": 2,
        "finite_count": 4,
        "min": 1.0,
        "max": 4.0,
        "mean": 2.5,
        "median": 2.5,
    }
    assert first["gps"] == [0.0, 0.0]
    assert first["compass"] == [0.0]
    assert first["habitat_official"]["distance_to_goal"] == 2.0
    assert first["provenance"]["source_validity"] == "oracle_teacher_only"
    assert first["provenance"]["teacher"] == "habitat_shortest_path_follower"

    assert [env.actions for env in envs] == [["move_forward", "turn_left", "stop"]]
    assert [call.tolist() for call in followers[0].goal_calls] == [
        [0.0, 0.0, -2.0],
        [0.0, 0.0, -2.0],
        [0.0, 0.0, -2.0],
    ]


def test_targetnav_local_policy_dataset_counts_missing_goal_and_teacher() -> None:
    no_goal = export_official_targetnav_local_policy_dataset(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        max_episodes=1,
        max_steps=2,
        env_factory=lambda _config: _OracleTargetNavEnv(with_goal=False),
        follower_factory=lambda _env, *, goal_radius_m: _FakeFollower(actions=[1]),
    )
    no_teacher = export_official_targetnav_local_policy_dataset(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        max_episodes=1,
        max_steps=2,
        env_factory=lambda _config: _OracleTargetNavEnv(),
        follower_factory=lambda _env, *, goal_radius_m: None,
    )

    assert no_goal["example_count"] == 0
    assert no_goal["skipped_no_goal_episode_count"] == 1
    assert no_goal["skipped_teacher_unavailable_episode_count"] == 0
    assert no_teacher["example_count"] == 0
    assert no_teacher["skipped_no_goal_episode_count"] == 0
    assert no_teacher["skipped_teacher_unavailable_episode_count"] == 1


def test_targetnav_local_policy_dataset_writes_flat_csv(tmp_path: Path) -> None:
    dataset = export_official_targetnav_local_policy_dataset(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        max_episodes=1,
        max_steps=1,
        env_factory=lambda _config: _OracleTargetNavEnv(),
        follower_factory=lambda _env, *, goal_radius_m: _FakeFollower(actions=[1]),
    )
    csv_path = tmp_path / "targetnav_local_policy.csv"

    write_official_targetnav_local_policy_dataset_csv(dataset, csv_path)

    csv_text = csv_path.read_text(encoding="utf-8")
    assert "pointgoal_distance" in csv_text
    assert "pointgoal_heading" in csv_text
    assert "teacher_action" in csv_text
    assert "move_forward" in csv_text
    assert "depth_median" in csv_text
    assert "oracle_teacher_only" in csv_text


def test_targetnav_local_policy_dataset_cli_writes_json_and_csv(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.export_habitat_official_targetnav_local_policy_dataset import (
        main,
    )

    output_path = tmp_path / "dataset.json"
    csv_path = tmp_path / "dataset.csv"
    runner_kwargs: dict[str, Any] = {}

    def runner(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        runner_kwargs.update(kwargs)
        return {
            "task": "habitat_official_targetnav_local_policy_dataset",
            "schema_version": "official-targetnav-local-policy-v1",
            "source_validity": "oracle_teacher_only",
            "episode_count": 1,
            "example_count": 1,
            "skipped_no_goal_episode_count": 0,
            "skipped_teacher_unavailable_episode_count": 0,
            "invalid_teacher_action_count": 0,
            "action_distribution": {"move_forward": 1},
            "examples": [
                {
                    "source_validity": "oracle_teacher_only",
                    "episode_index": 0,
                    "episode_id": "episode-0",
                    "scene_id": "scene.glb",
                    "target_category": "chair",
                    "step_index": 0,
                    "goal_position": [0.0, 0.0, -2.0],
                    "target_goal": {"x_m": 0.0, "z_m": 2.0},
                    "pointgoal_with_gps_compass": [2.0, 0.0],
                    "teacher_action": "move_forward",
                    "teacher_action_raw": 1,
                    "depth_stats": {"median": 2.5},
                    "gps": [0.0, 0.0],
                    "compass": [0.0],
                    "habitat_official": {"distance_to_goal": 2.0},
                    "provenance": {"source_validity": "oracle_teacher_only"},
                }
            ],
        }

    exit_code = main(
        [
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
            "--max-episodes",
            "2",
            "--max-steps",
            "5",
            "--seed",
            "11",
            "--goal-radius",
            "0.4",
        ],
        runner=runner,
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["task"] == "habitat_official_targetnav_local_policy_dataset"
    assert "move_forward" in csv_path.read_text(encoding="utf-8")
    assert runner_kwargs["config_path"] == "official.yaml"
    assert runner_kwargs["max_episodes"] == 2
    assert runner_kwargs["max_steps"] == 5
    assert runner_kwargs["seed"] == 11
    assert runner_kwargs["goal_radius_m"] == 0.4


def test_targetnav_local_policy_dataset_cli_module_has_main_guard() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "objectnav_core.cli.export_habitat_official_targetnav_local_policy_dataset",
            "--help",
        ],
        check=False,
        capture_output=True,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
    )

    assert completed.returncode == 0
    assert "TargetNav local policy" in completed.stdout


class _OracleTargetNavEnv:
    def __init__(self, *, with_goal: bool = True) -> None:
        self.actions: list[str] = []
        self.episode_over = False
        self.sim = _FakeSim()
        self.current_episode = SimpleNamespace(
            episode_id="episode-0",
            scene_id="scene.glb",
            object_category="chair",
            start_position=[0.0, 0.0, 0.0],
            start_rotation=[0.0, 0.0, 0.0, 1.0],
            goals=[_goal()] if with_goal else [],
        )

    def reset(self) -> dict[str, object]:
        self.actions = []
        self.episode_over = False
        self.sim.position = np.array([0.0, 0.0, 0.0], dtype=float)
        return _observation(gps=[0.0, 0.0], compass=[0.0])

    def step(self, action: str) -> dict[str, object]:
        self.actions.append(action)
        if action == "move_forward":
            self.sim.position = np.array([0.0, 0.0, -1.0], dtype=float)
            return _observation(gps=[1.0, 0.0], compass=[0.0])
        if action == "turn_left":
            return _observation(gps=[1.0, 0.0], compass=[np.pi / 2.0])
        if action == "stop":
            self.episode_over = True
        return _observation(gps=[1.0, 0.0], compass=[np.pi / 2.0])

    def get_metrics(self) -> dict[str, float]:
        return {
            "success": 0.0,
            "spl": 0.0,
            "soft_spl": 0.0,
            "distance_to_goal": max(0.0, 2.0 - len(self.actions)),
        }

    def close(self) -> None:
        pass


class _FakeSim:
    def __init__(self) -> None:
        self.position = np.array([0.0, 0.0, 0.0], dtype=float)

    def get_agent_state(self) -> SimpleNamespace:
        return SimpleNamespace(position=self.position)


class _FakeFollower:
    def __init__(self, *, actions: list[int | str | None]) -> None:
        self.actions = list(actions)
        self.goal_calls: list[np.ndarray] = []

    def get_next_action(self, goal_position: object) -> int | str | None:
        self.goal_calls.append(np.asarray(goal_position, dtype=float))
        if not self.actions:
            return None
        return self.actions.pop(0)


def _goal() -> SimpleNamespace:
    return SimpleNamespace(
        position=[0.0, 0.0, -2.0],
        view_points=[
            SimpleNamespace(
                agent_state=SimpleNamespace(position=[0.0, 0.0, -2.0])
            )
        ],
    )


def _observation(
    *,
    gps: list[float],
    compass: list[float],
) -> dict[str, object]:
    return {
        "depth": np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float),
        "gps": np.array(gps, dtype=float),
        "compass": np.array(compass, dtype=float),
    }
