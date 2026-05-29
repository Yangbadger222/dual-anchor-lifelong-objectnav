from pathlib import Path

from objectnav_core.evaluation.lifelong_objectnav_benchmark import (
    run_lifelong_objectnav_benchmark,
)
from objectnav_core.mapping.fixtures import build_multiroom_grid
from objectnav_core.models import Pose2D, make_default_multiroom_lifelong_scene
from objectnav_core.planning.memory_guided import (
    MemoryMatchEvidence,
    select_memory_guided_candidate,
)


def test_multiroom_lifelong_grid_has_reachable_target_room() -> None:
    scene = make_default_multiroom_lifelong_scene()
    grid = build_multiroom_grid(scene, reveal_all=True)
    target = scene.objects[0]

    assert grid.is_free_world(1.4, 5.0)
    assert grid.is_free_world(target.pose_map.x, target.pose_map.y)
    assert grid.has_line_of_sight(
        Pose2D(x=12.0, y=7.0, yaw=1.5708),
        target.pose_map,
    )


def test_lifelong_objectnav_benchmark_memory_reduces_repeated_exploration(
    tmp_path: Path,
) -> None:
    summary = run_lifelong_objectnav_benchmark(tmp_path)

    memory = summary["policy_summaries"]["memory_guided"]["aggregate"]
    frontier = summary["policy_summaries"]["frontier_only"]["aggregate"]

    assert memory["success_episodes"] == 3
    assert memory["success_episodes"] > frontier["success_episodes"]
    assert memory["memory_reuse_episodes"] >= 2
    assert memory["relocation_recorded"] is True
    assert memory["total_path_length_m"] < frontier["total_path_length_m"]
    assert memory["frontier_selected_count"] < frontier["frontier_selected_count"]
    assert summary["comparison"]["memory_guided_path_reduction_ratio"] > 0.2
    assert summary["comparison"]["memory_guided_success_delta"] > 0


def test_memory_guided_candidate_prefers_reusable_memory_over_frontier() -> None:
    scene = make_default_multiroom_lifelong_scene()
    grid = build_multiroom_grid(scene, reveal_all=True)
    target = scene.objects[0]

    from objectnav_core.models import (
        AnchorType,
        MemoryObject,
        MemoryState,
    )

    memory = MemoryObject(
        object_id=target.object_id,
        class_name=target.class_name,
        state=MemoryState.REUSABLE,
        pose=target.pose_map,
        anchor_id=scene.anchor.anchor_id,
        anchor_type=AnchorType.INDOOR_MAP,
        frame_id=scene.anchor.frame_id,
        confidence=0.95,
        detector_name="test",
        verification_viewpoint=Pose2D(x=12.0, y=7.0, yaw=1.5708),
    )

    candidate = select_memory_guided_candidate(
        grid=grid,
        start_pose=Pose2D(x=2.0, y=5.0, yaw=0.0),
        target_class=target.class_name,
        memories=[memory],
        frontiers=[],
    )

    assert candidate.candidate_type == "memory"
    assert candidate.object_id == target.object_id


def test_memory_guided_candidate_defers_ambiguous_dual_anchor_memory_to_frontier() -> None:
    scene = make_default_multiroom_lifelong_scene()
    grid = build_multiroom_grid(scene, reveal_all=True)
    target = scene.objects[0]

    from objectnav_core.mapping.frontiers import FrontierCluster
    from objectnav_core.models import (
        AnchorType,
        MemoryObject,
        MemoryState,
    )

    memory = MemoryObject(
        object_id=target.object_id,
        class_name=target.class_name,
        state=MemoryState.REUSABLE,
        pose=target.pose_map,
        anchor_id=scene.anchor.anchor_id,
        anchor_type=AnchorType.INDOOR_MAP,
        frame_id=scene.anchor.frame_id,
        confidence=0.95,
        detector_name="test",
        verification_viewpoint=Pose2D(x=12.0, y=7.0, yaw=1.5708),
    )
    frontier = FrontierCluster(
        cells=((4, 4), (4, 5), (4, 6), (5, 4), (5, 5), (5, 6)),
        centroid=Pose2D(x=4.5, y=5.0),
    )

    candidate = select_memory_guided_candidate(
        grid=grid,
        start_pose=Pose2D(x=2.0, y=5.0, yaw=0.0),
        target_class=target.class_name,
        memories=[memory],
        frontiers=[frontier],
        memory_match_evidence={
            target.object_id: MemoryMatchEvidence(
                accepted=False,
                reason="ambiguous",
                mahalanobis_distance=0.1,
            )
        },
    )

    assert candidate.candidate_type == "frontier"
