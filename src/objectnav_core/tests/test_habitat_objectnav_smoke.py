import csv
import json
import sys
from pathlib import Path

import numpy as np

from objectnav_core.evaluation import habitat_objectnav_smoke as smoke


def test_importing_smoke_module_does_not_import_habitat() -> None:
    assert "habitat" not in sys.modules
    assert "habitat_sim" not in sys.modules


def test_synthetic_objectnav_dataset_document_has_required_fields() -> None:
    spec = smoke.SyntheticObjectNavSpec(
        scene_path="/tmp/simple_room.glb",
        object_category="mug",
        target_position=(1.0, 0.0, -1.0),
    )

    document = smoke._synthetic_objectnav_dataset_document(spec)

    assert document["category_to_task_category_id"] == {"mug": 0}
    assert document["category_to_scene_annotation_category_id"] == {"mug": 0}
    assert document["episodes"][0]["scene_id"] == "/tmp/simple_room.glb"
    assert document["episodes"][0]["object_category"] == "mug"
    assert document["episodes"][0]["goals"][0]["position"] == [1.0, 0.0, -1.0]


def test_depth_and_rgb_stats_are_stable() -> None:
    depth = np.array([[0.0, 1.0], [2.0, np.nan]], dtype=np.float32)
    rgb = np.array([[[0, 10, 20], [30, 40, 50]]], dtype=np.uint8)

    assert smoke._depth_stats(depth) == {
        "depth_shape": "2x2",
        "depth_min": 1.0,
        "depth_max": 2.0,
        "depth_mean": 1.5,
        "depth_valid_ratio": 0.5,
    }
    assert smoke._rgb_stats(rgb) == {
        "rgb_shape": "1x2x3",
        "rgb_mean": 25.0,
        "rgb_nonzero_ratio": 0.833333,
    }


def test_write_artifacts_from_synthetic_rows(tmp_path: Path) -> None:
    rows = [
        {
            "episode_id": "synthetic-0",
            "step_index": 0,
            "action": "reset",
            "depth_mean": 1.0,
            "depth_valid_ratio": 0.5,
            "previous_step_collided": False,
        },
        {
            "episode_id": "synthetic-0",
            "step_index": 1,
            "action": "stop",
            "depth_mean": 2.0,
            "depth_valid_ratio": 0.75,
            "previous_step_collided": True,
        },
    ]

    trace_path = tmp_path / "habitat_trace.csv"
    smoke._write_csv(trace_path, rows)
    summary = smoke._summarize_rows(
        rows,
        scene_path="/tmp/simple_room.glb",
        seed=23,
        sensor_size=64,
        actions=["stop"],
        observation_keys=["depth", "objectgoal", "rgb"],
        episode_over=True,
        habitat_version="0.3.3",
        habitat_sim_version="0.3.3",
    )
    smoke._write_json(tmp_path / "summary.json", summary)
    smoke._write_report(tmp_path / "report.html", summary)

    with trace_path.open(encoding="utf-8", newline="") as handle:
        assert list(csv.DictReader(handle))[1]["action"] == "stop"
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))[
        "collision_steps"
    ] == 1
    assert "Habitat ObjectNav Smoke" in (tmp_path / "report.html").read_text(
        encoding="utf-8"
    )
