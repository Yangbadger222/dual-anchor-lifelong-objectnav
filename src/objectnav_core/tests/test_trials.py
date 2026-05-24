from pathlib import Path

from objectnav_core.memory.sqlite_store import SQLiteMemoryStore
from objectnav_core.models import (
    MemoryState,
    ObjectObservation,
    Pose2D,
    TrialMetrics,
    make_default_corridor_scene,
)
from objectnav_core.simulation.trials import Phase1ATrialRunner


def test_sqlite_store_queries_reusable_objects_and_records_relocation(tmp_path: Path) -> None:
    scene = make_default_corridor_scene()
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite")
    target = scene.objects[0]
    observation = ObjectObservation(
        object_id=target.object_id,
        class_name=target.class_name,
        confidence=1.0,
        pose=target.pose_map,
        anchor_id=scene.anchor.anchor_id,
        anchor_type=scene.anchor.anchor_type,
        frame_id=scene.anchor.frame_id,
        detector_name="test",
    )

    store.upsert_object_from_observation(
        observation,
        MemoryState.REUSABLE,
        verification_viewpoint=Pose2D(x=8.0, y=1.45, yaw=-1.5708),
    )
    reusable = store.query_objects(
        class_name="water_dispenser",
        states=[MemoryState.REUSABLE],
        anchor_id=scene.anchor.anchor_id,
    )

    assert len(reusable) == 1
    assert reusable[0].object_id == "water_dispenser_001"
    assert reusable[0].verification_viewpoint is not None

    store.update_object_state("water_dispenser_001", MemoryState.MISSING)
    store.add_relation(
        source_object_id="water_dispenser_002",
        target_object_id="water_dispenser_001",
        relation_type="possible_relocation_of",
    )

    assert store.get_object("water_dispenser_001").state is MemoryState.MISSING
    assert store.list_relations()[0].relation_type == "possible_relocation_of"
    assert "water_dispenser_001" in store.export_json()


def test_sqlite_store_persists_trial_metrics(tmp_path: Path) -> None:
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite")
    metrics = TrialMetrics(
        success=True,
        final_state="reusable",
        path_length_m=7.5,
        memory_reused=True,
        selected_candidate_types=["memory"],
    )

    store.record_trial_metrics("reuse_same_start", metrics)

    saved = store.get_trial_metrics("reuse_same_start")
    assert saved == metrics


def test_phase1a_runs_discovery_reuse_and_relocation(tmp_path: Path) -> None:
    runner = Phase1ATrialRunner(tmp_path / "memory.sqlite")

    discover = runner.run("discover_and_verify")
    reuse_same = runner.run("reuse_same_start")
    reuse_different = runner.run("reuse_different_start")
    relocation = runner.run("missing_and_relocation")

    assert discover.metrics.success
    assert discover.metrics.memory_reused is False
    assert discover.metrics.observation_count >= 1
    assert discover.metrics.time_to_verify_s is not None

    assert reuse_same.metrics.success
    assert reuse_same.metrics.memory_reused is True
    assert reuse_same.metrics.num_nav_goals == 1

    assert reuse_different.metrics.success
    assert reuse_different.metrics.memory_reused is True

    assert relocation.metrics.success
    assert relocation.metrics.missing_detection_success is True
    assert relocation.metrics.relocation_recorded is True
    assert runner.memory.get_object("water_dispenser_001").state is MemoryState.MISSING
    assert runner.memory.get_object("water_dispenser_002").state is MemoryState.REUSABLE

    saved_metrics = runner.memory.list_trial_metrics()
    assert {trial_id for trial_id, _ in saved_metrics} == {
        "discover_and_verify",
        "reuse_same_start",
        "reuse_different_start",
        "missing_and_relocation",
    }
    assert dict(saved_metrics)["missing_and_relocation"].relocation_recorded is True


def test_phase1a_runner_accepts_information_gain_frontier_policy(tmp_path: Path) -> None:
    runner = Phase1ATrialRunner(
        tmp_path / "memory.sqlite",
        frontier_policy="information_gain",
    )

    result = runner.run("discover_and_verify")

    assert result.metrics.success
    assert result.metrics.selected_candidate_types[0] == "information_gain_frontier"
    assert result.metrics.final_candidate_score is not None
