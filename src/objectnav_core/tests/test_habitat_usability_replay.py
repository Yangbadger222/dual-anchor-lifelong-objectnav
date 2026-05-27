import sys

from objectnav_core.evaluation import habitat_usability_replay as replay
from objectnav_core.memory.usability import EvidenceType


def test_importing_replay_module_does_not_import_habitat() -> None:
    assert "habitat" not in sys.modules
    assert "habitat_sim" not in sys.modules


def test_classify_evidence_from_habitat_trace_row() -> None:
    base_row = {
        "action": "move_forward",
        "distance_to_synthetic_target": "1.0",
        "depth_valid_ratio": "1.0",
        "previous_step_collided": "False",
    }

    assert replay._classify_evidence(
        base_row,
        previous_distance=1.5,
        positive_radius=1.25,
        free_radius=2.5,
    )[0] is EvidenceType.POSITIVE

    free_row = {**base_row, "distance_to_synthetic_target": "2.0"}
    assert replay._classify_evidence(
        free_row,
        previous_distance=2.4,
        positive_radius=1.25,
        free_radius=2.5,
    )[0] is EvidenceType.FREE

    blocked_row = {**base_row, "previous_step_collided": "True"}
    assert replay._classify_evidence(
        blocked_row,
        previous_distance=1.5,
        positive_radius=1.25,
        free_radius=2.5,
    )[0] is EvidenceType.ACCESS_BLOCKED


def test_replay_algorithm_writes_decision_rows_from_trace_rows() -> None:
    trace_rows = [
        {
            "episode_id": "synthetic-0",
            "step_index": "0",
            "action": "reset",
            "distance_to_synthetic_target": "2.0",
            "depth_valid_ratio": "1.0",
            "previous_step_collided": "False",
        },
        {
            "episode_id": "synthetic-0",
            "step_index": "1",
            "action": "move_forward",
            "distance_to_synthetic_target": "1.0",
            "depth_valid_ratio": "1.0",
            "previous_step_collided": "False",
        },
        {
            "episode_id": "synthetic-0",
            "step_index": "2",
            "action": "stop",
            "distance_to_synthetic_target": "1.0",
            "depth_valid_ratio": "1.0",
            "previous_step_collided": "False",
        },
    ]

    rows, summary = replay._replay_algorithm(
        trace_rows,
        episode_index=0,
        scenario=replay.ReplayScenario("near_anchor", 1.0),
        scene_path="/tmp/simple_room.glb",
        smoke_summary={"episode_over": True, "navmesh_loaded": True},
        positive_radius=1.25,
        free_radius=2.5,
    )

    assert [row["evidence_type"] for row in rows] == [
        "unknown",
        "positive",
        "positive",
    ]
    assert summary["episode_over"] is True
    assert summary["final_p_valid"] > 0.65
