from __future__ import annotations

import json
from pathlib import Path

import pytest

from objectnav_core.cli.export_lifecycle_memory_prior import main
from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    load_official_memory_prior,
)
from objectnav_core.evaluation.lifecycle_memory_prior_export import (
    LifecycleMemoryPriorExportConfig,
    export_lifecycle_memory_prior,
)
from objectnav_core.evaluation.lifelong_memory_harness import LifelongMemoryHarness
from objectnav_core.memory.usability import MemoryBelief


def test_export_lifecycle_memory_prior_writes_official_anchor_json(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lifecycle_memory.sqlite"
    output_path = tmp_path / "official_memory_prior.json"
    memory = LifelongMemoryHarness(db_path)
    memory.save_belief(
        scene_id="scene-a",
        episode_dataset_version="objectnav_hm3d_v1/val_mini",
        category="chair",
        instance_id="goal_object:7",
        belief=MemoryBelief(
            p_existence=0.9,
            p_location_valid=0.8,
            p_usable=0.5,
        ),
    )
    memory.save_object_instance_anchor(
        scene_id="scene-a",
        episode_dataset_version="objectnav_hm3d_v1/val_mini",
        category="chair",
        instance_id="goal_object:7",
        anchor_x=1.25,
        anchor_z=-2.5,
    )
    memory.connection.close()

    summary = export_lifecycle_memory_prior(
        LifecycleMemoryPriorExportConfig(
            memory_db_path=db_path,
            output_path=output_path,
            source_tag="lifecycle_detector_positive",
        )
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    anchors = load_official_memory_prior(output_path)

    assert summary["exported_anchor_count"] == 1
    assert payload["anchors"][0]["object_category"] == "chair"
    assert payload["anchors"][0]["scene_id"] == "scene-a"
    assert payload["anchors"][0]["x_m"] == 1.25
    assert payload["anchors"][0]["z_m"] == -2.5
    assert payload["anchors"][0]["confidence"] == pytest.approx(0.36)
    assert payload["anchors"][0]["coordinate_frame"] == "habitat_world"
    assert payload["anchors"][0]["source"] == (
        "lifecycle_detector_positive:goal_object:7"
    )
    assert anchors[0].coordinate_frame == "habitat_world"
    assert anchors[0].source == "lifecycle_detector_positive:goal_object:7"


def test_export_lifecycle_memory_prior_filters_by_confidence_and_defaults_missing_belief(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lifecycle_memory.sqlite"
    output_path = tmp_path / "official_memory_prior.json"
    memory = LifelongMemoryHarness(db_path)
    memory.save_belief(
        scene_id="scene-a",
        episode_dataset_version="objectnav_hm3d_v1/val_mini",
        category="chair",
        instance_id="weak",
        belief=MemoryBelief(
            p_existence=0.2,
            p_location_valid=0.2,
            p_usable=0.2,
        ),
    )
    memory.save_object_instance_anchor(
        scene_id="scene-a",
        episode_dataset_version="objectnav_hm3d_v1/val_mini",
        category="chair",
        instance_id="weak",
        anchor_x=1.0,
        anchor_z=1.0,
    )
    memory.save_object_instance_anchor(
        scene_id="scene-a",
        episode_dataset_version="objectnav_hm3d_v1/val_mini",
        category="chair",
        instance_id="missing-belief",
        anchor_x=2.0,
        anchor_z=2.0,
    )
    memory.connection.close()

    summary = export_lifecycle_memory_prior(
        LifecycleMemoryPriorExportConfig(
            memory_db_path=db_path,
            output_path=output_path,
            min_confidence=0.5,
        )
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["filtered_anchor_count"] == 1
    assert summary["exported_anchor_count"] == 1
    assert payload["anchors"][0]["source"] == "lifecycle_memory:missing-belief"
    assert payload["anchors"][0]["confidence"] == 1.0


def test_export_lifecycle_memory_prior_cli_writes_json(tmp_path: Path) -> None:
    db_path = tmp_path / "lifecycle_memory.sqlite"
    output_path = tmp_path / "official_memory_prior.json"
    memory = LifelongMemoryHarness(db_path)
    memory.save_object_instance_anchor(
        scene_id="scene-a",
        episode_dataset_version="objectnav_hm3d_v1/val_mini",
        category="plant",
        instance_id="goal_object:3",
        anchor_x=-1.0,
        anchor_z=3.0,
    )
    memory.connection.close()

    exit_code = main(
        [
            "--memory-db",
            str(db_path),
            "--output",
            str(output_path),
            "--source-tag",
            "lifecycle_cli",
            "--min-confidence",
            "0.5",
        ]
    )

    anchors = load_official_memory_prior(output_path)

    assert exit_code == 0
    assert anchors[0].object_category == "plant"
    assert anchors[0].source == "lifecycle_cli:goal_object:3"
