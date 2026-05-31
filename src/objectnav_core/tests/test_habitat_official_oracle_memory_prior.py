from __future__ import annotations

import json
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    load_official_memory_prior,
)


def test_world_position_to_episode_relative_xz_inverts_start_pose() -> None:
    module = _oracle_memory_module()

    x_m, z_m = module._world_position_to_episode_relative_xz(
        goal_position=(12.0, 0.0, 17.0),
        start_position=(10.0, 0.0, 20.0),
        start_rotation=(0.0, 0.0, 0.0, 1.0),
    )

    assert x_m == pytest.approx(2.0)
    assert z_m == pytest.approx(3.0)


def test_make_official_oracle_memory_anchor_uses_episode_goal_position() -> None:
    module = _oracle_memory_module()
    episode = _episode(
        episode_id="episode-7",
        scene_id="scene-a",
        object_category="chair",
        start_position=(10.0, 0.0, 20.0),
        start_rotation=(0.0, 0.0, 0.0, 1.0),
        goal_position=(12.0, 0.0, 17.0),
    )

    anchor = module.make_official_oracle_memory_anchor(
        episode,
        goal_position=(12.0, 0.0, 17.0),
    )

    assert anchor is not None
    assert anchor.object_category == "chair"
    assert anchor.scene_id == "scene-a"
    assert anchor.episode_id == "episode-7"
    assert anchor.x_m == pytest.approx(2.0)
    assert anchor.z_m == pytest.approx(3.0)
    assert anchor.confidence == 1.0
    assert anchor.source == "habitat_oracle_goal:episode-7"
    assert anchor.coordinate_frame == "episode_start_relative"


def test_make_official_oracle_memory_anchor_preserves_vertical_offset() -> None:
    module = _oracle_memory_module()
    episode = _episode(
        episode_id="episode-7",
        scene_id="scene-a",
        object_category="chair",
        start_position=(10.0, 2.5, 20.0),
        start_rotation=(0.0, 0.0, 0.0, 1.0),
        goal_position=(12.0, 0.25, 17.0),
    )

    anchor = module.make_official_oracle_memory_anchor(
        episode,
        goal_position=(12.0, 0.25, 17.0),
    )

    assert anchor is not None
    assert anchor.x_m == pytest.approx(2.0)
    assert anchor.y_m == pytest.approx(-2.25)
    assert anchor.z_m == pytest.approx(3.0)


def test_export_habitat_official_oracle_memory_prior_writes_diagnostic_json(
    tmp_path: Path,
) -> None:
    module = _oracle_memory_module()
    output_path = tmp_path / "oracle_memory_prior.json"
    env = _FakeOracleMemoryEnv(
        [
            _episode(
                episode_id="episode-1",
                scene_id="scene-a",
                object_category="chair",
                start_position=(10.0, 0.0, 20.0),
                start_rotation=(0.0, 0.0, 0.0, 1.0),
                goal_position=(12.0, 0.0, 17.0),
            ),
            _episode(
                episode_id="episode-2",
                scene_id="scene-a",
                object_category="chair",
                start_position=None,
                start_rotation=(0.0, 0.0, 0.0, 1.0),
                goal_position=(9.0, 0.0, 18.0),
            ),
        ]
    )

    summary = module.export_habitat_official_oracle_memory_prior(
        output_path,
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        max_episodes=2,
        validate_habitat=False,
        env_factory=lambda _config: env,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    anchors = load_official_memory_prior(output_path)

    assert summary["exported_anchor_count"] == 1
    assert summary["skipped_episode_count"] == 1
    assert payload["metadata"]["source"] == "habitat_official_oracle_memory_prior"
    assert payload["metadata"]["source_validity"] == "oracle_diagnostic_only"
    assert payload["metadata"]["coordinate_frame"] == "episode_start_relative"
    assert anchors[0].episode_id == "episode-1"
    assert anchors[0].x_m == pytest.approx(2.0)
    assert anchors[0].z_m == pytest.approx(3.0)


def test_oracle_memory_prior_cli_passes_export_arguments(tmp_path: Path) -> None:
    cli_module = _oracle_memory_cli_module()
    calls: list[dict[str, object]] = []

    def exporter(output_path: str | Path, **kwargs: object) -> dict[str, object]:
        calls.append({"output_path": str(output_path), **kwargs})
        Path(output_path).write_text(
            json.dumps({"anchors": [], "metadata": {}}),
            encoding="utf-8",
        )
        return {"task": "habitat_official_oracle_memory_prior_export"}

    output_path = tmp_path / "oracle_memory_prior.json"

    exit_code = cli_module.main(
        [
            "--output",
            str(output_path),
            "--config-path",
            "official.yaml",
            "--dataset-data-path",
            "val_mini.json.gz",
            "--scene-root",
            "hm3d",
            "--split",
            "val_mini",
            "--max-episodes",
            "4",
            "--seed",
            "123",
        ],
        exporter=exporter,
    )

    assert exit_code == 0
    assert calls == [
        {
            "output_path": str(output_path),
            "config_path": "official.yaml",
            "dataset_data_path": "val_mini.json.gz",
            "scene_root": "hm3d",
            "split": "val_mini",
            "max_episodes": 4,
            "seed": 123,
            "validate_habitat": False,
        }
    ]


def _oracle_memory_module() -> object:
    try:
        return importlib.import_module(
            "objectnav_core.evaluation.habitat_official_oracle_memory_prior"
        )
    except ModuleNotFoundError as exc:
        pytest.fail(f"oracle memory prior module missing: {exc}")


def _oracle_memory_cli_module() -> object:
    try:
        return importlib.import_module(
            "objectnav_core.cli.export_habitat_official_oracle_memory_prior"
        )
    except ModuleNotFoundError as exc:
        pytest.fail(f"oracle memory prior CLI missing: {exc}")


def _episode(
    *,
    episode_id: str,
    scene_id: str,
    object_category: str,
    start_position: tuple[float, float, float] | None,
    start_rotation: tuple[float, float, float, float] | None,
    goal_position: tuple[float, float, float],
) -> SimpleNamespace:
    return SimpleNamespace(
        episode_id=episode_id,
        scene_id=scene_id,
        object_category=object_category,
        start_position=start_position,
        start_rotation=start_rotation,
        goals=[
            SimpleNamespace(
                position=goal_position,
                view_points=[
                    SimpleNamespace(
                        agent_state=SimpleNamespace(position=goal_position)
                    )
                ],
            )
        ],
    )


class _FakeOracleMemoryEnv:
    def __init__(self, episodes: list[SimpleNamespace]) -> None:
        self.episodes = episodes
        self.current_episode: SimpleNamespace | None = None
        self.episode_index = -1
        self.closed = False

    @property
    def number_of_episodes(self) -> int:
        return len(self.episodes)

    def reset(self) -> dict[str, object]:
        self.episode_index += 1
        self.current_episode = self.episodes[self.episode_index]
        return {"objectgoal": 0}

    def close(self) -> None:
        self.closed = True
