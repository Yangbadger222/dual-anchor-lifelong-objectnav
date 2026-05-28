from pathlib import Path

from objectnav_core.evaluation.lifelong_memory_harness import LifelongMemoryHarness
from objectnav_core.memory.usability import MemoryBelief


def test_lifelong_harness_persists_belief_by_scene_dataset_and_category(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "memory.sqlite"
    first = LifelongMemoryHarness(db_path)
    belief = MemoryBelief(p_existence=0.8, p_location_valid=0.7, p_usable=0.6)

    first.save_belief(
        scene_id="scene-a",
        episode_dataset_version="objectnav_hm3d_v1/val_mini",
        category="chair",
        belief=belief,
    )

    second = LifelongMemoryHarness(db_path)
    loaded = second.load_belief(
        scene_id="scene-a",
        episode_dataset_version="objectnav_hm3d_v1/val_mini",
        category="chair",
        default=MemoryBelief(0.1, 0.1, 0.1),
    )

    assert loaded == belief
    assert second.load_belief(
        scene_id="scene-b",
        episode_dataset_version="objectnav_hm3d_v1/val_mini",
        category="chair",
        default=MemoryBelief(0.1, 0.1, 0.1),
    ) == MemoryBelief(0.1, 0.1, 0.1)


def test_lifelong_harness_persists_geometry_anchor_by_object_instance(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "memory.sqlite"
    first = LifelongMemoryHarness(db_path)

    first.save_object_instance_anchor(
        scene_id="scene-a",
        episode_dataset_version="objectnav_hm3d_v1/val_mini",
        category="bed",
        instance_id="goal_object:16",
        anchor_x=1.25,
        anchor_z=-2.5,
    )

    second = LifelongMemoryHarness(db_path)

    assert second.load_object_instance_anchor(
        scene_id="scene-a",
        episode_dataset_version="objectnav_hm3d_v1/val_mini",
        category="bed",
        instance_id="goal_object:16",
    ) == (1.25, -2.5)
    assert second.load_object_instance_anchor(
        scene_id="scene-a",
        episode_dataset_version="objectnav_hm3d_v1/val_mini",
        category="bed",
        instance_id="goal_object:999",
    ) is None
