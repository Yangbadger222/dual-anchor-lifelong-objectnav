from __future__ import annotations

import json
from pathlib import Path

from objectnav_core.evaluation.habitat_official_local_action_dataset import (
    export_official_local_action_dataset,
    write_official_local_action_dataset_csv,
)


def test_official_local_action_dataset_labels_action_effect_transitions(
    tmp_path: Path,
) -> None:
    policy_trace_path, detector_trace_path = _write_trace_pair(tmp_path)

    report = export_official_local_action_dataset(
        policy_trace_path,
        detector_trace_path=detector_trace_path,
        source_run_id="synthetic-run",
    )

    assert report["task"] == "habitat_official_local_action_dataset"
    assert report["source_run_id"] == "synthetic-run"
    assert report["step_count"] == 4
    assert report["example_count"] == 3
    assert report["transition_counts"] == {
        "acquired": 1,
        "lost": 1,
        "remained_absent": 0,
        "retained": 1,
    }
    assert report["visible_before_count"] == 2
    assert report["visible_after_count"] == 2

    retained, lost, acquired = report["examples"]
    assert retained["action"] == "move_forward"
    assert retained["features"]["current_target_visible"] is True
    assert retained["features"]["current_detector_confidence"] == 0.5
    assert retained["features"]["current_bbox_area_fraction"] == 0.02
    assert retained["features"]["current_abs_center_offset_fraction"] == 0.4
    assert retained["features"]["suppressed_detector_center_action"] == ""
    assert retained["labels"]["next_target_visible"] is True
    assert retained["labels"]["target_retained"] is True
    assert retained["labels"]["target_lost"] is False
    assert retained["labels"]["target_acquired"] is False
    assert retained["labels"]["detector_confidence_delta"] == 0.2
    assert retained["labels"]["bbox_area_fraction_delta"] == 0.01
    assert retained["labels"]["abs_center_offset_fraction_delta"] == -0.2
    assert retained["labels"]["translation_delta_m"] == 0.25

    assert lost["decision"] == "center_detector_target"
    assert lost["labels"]["target_retained"] is False
    assert lost["labels"]["target_lost"] is True
    assert lost["labels"]["target_acquired"] is False
    assert lost["labels"]["next_target_visible"] is False

    assert acquired["features"]["current_target_visible"] is False
    assert acquired["features"]["current_detector_confidence"] is None
    assert acquired["features"]["suppressed_detector_center_action"] == "turn_right"
    assert acquired["labels"]["target_acquired"] is True
    assert acquired["labels"]["next_detector_confidence"] == 0.8


def test_official_local_action_dataset_writes_stable_csv(tmp_path: Path) -> None:
    policy_trace_path, detector_trace_path = _write_trace_pair(tmp_path)
    report = export_official_local_action_dataset(
        policy_trace_path,
        detector_trace_path=detector_trace_path,
        source_run_id="synthetic-run",
    )
    csv_path = tmp_path / "examples.csv"

    write_official_local_action_dataset_csv(report, csv_path)

    rows = csv_path.read_text(encoding="utf-8").splitlines()
    header = rows[0].split(",")
    assert header[:8] == [
        "source_policy_trace",
        "source_detector_trace",
        "source_run_id",
        "episode_index",
        "episode_id",
        "scene_id",
        "target_category",
        "policy",
    ]
    assert "current_target_visible" in header
    assert "next_target_visible" in header
    assert "bbox_area_fraction_delta" in header
    assert "synthetic-run" in rows[1]
    assert "move_forward" in rows[1]


def test_official_local_action_dataset_uses_policy_debug_detector_evidence(
    tmp_path: Path,
) -> None:
    policy_trace_path = tmp_path / "policy_trace.json"
    detector_trace_path = tmp_path / "detector_trace.json"
    policy_trace_path.write_text(
        json.dumps(
            {
                "task": "official_policy_step_trace",
                "steps": [
                    _policy_step(
                        step_index=0,
                        action="move_forward",
                        decision="approach_detector_target_after_center_loss",
                        x_m=0.0,
                        z_m=0.0,
                        heading_rad=-2.094,
                        memory_prior={
                            "decision": "approach_detector_target_after_center_loss",
                            "detector_confidence": 0.744381,
                            "detector_bbox": [579, 50, 640, 166],
                            "detector_center_offset_fraction": 0.45234375,
                            "detector_bbox_area_fraction": 0.023033854166666666,
                            "suppressed_detector_center_action": "turn_right",
                        },
                    ),
                    _policy_step(
                        step_index=1,
                        action="move_forward",
                        decision="approach_detector_target_after_center_loss",
                        x_m=-0.217,
                        z_m=-0.125,
                        heading_rad=-2.094,
                        memory_prior={
                            "decision": "approach_detector_target_after_center_loss",
                            "detector_confidence": 0.80616,
                            "detector_bbox": [613, 30, 640, 157],
                            "detector_center_offset_fraction": 0.47890625,
                            "detector_bbox_area_fraction": 0.011162109375,
                            "suppressed_detector_center_action": "turn_right",
                        },
                    ),
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    detector_trace_path.write_text(
        json.dumps(
            {
                "task": "official_query_detector_trace",
                "calls": [
                    _official_detector_call(step_index=0, confidence=0.744381),
                    _official_detector_call(step_index=1, confidence=0.80616),
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    report = export_official_local_action_dataset(
        policy_trace_path,
        detector_trace_path=detector_trace_path,
    )

    example = report["examples"][0]
    assert example["features"]["current_detector_confidence"] == 0.744381
    assert example["features"]["current_bbox_area_fraction"] == 0.023033854166666666
    assert example["features"]["current_center_offset_fraction"] == 0.45234375
    assert example["features"]["suppressed_detector_center_action"] == "turn_right"
    assert example["labels"]["next_detector_confidence"] == 0.80616
    assert example["labels"]["bbox_area_fraction_delta"] == -0.011871744792
    assert example["labels"]["abs_center_offset_fraction_delta"] == 0.0265625


def test_official_local_action_dataset_exports_temporal_features_and_horizon_labels(
    tmp_path: Path,
) -> None:
    policy_trace_path = tmp_path / "policy_trace.json"
    detector_trace_path = tmp_path / "detector_trace.json"
    policy_trace_path.write_text(
        json.dumps(
            {
                "task": "official_policy_step_trace",
                "steps": [
                    _policy_step(
                        step_index=0,
                        action="move_forward",
                        decision="approach_detector_target_after_center_loss",
                        x_m=0.0,
                        z_m=0.0,
                        heading_rad=-2.094,
                        memory_prior=_target_memory_prior(
                            confidence=0.80,
                            area_fraction=0.04,
                            center_offset=0.25,
                            depth_median=0.50,
                        ),
                    ),
                    _policy_step(
                        step_index=1,
                        action="move_forward",
                        decision="approach_detector_target_after_center_loss",
                        x_m=-0.2,
                        z_m=-0.1,
                        heading_rad=-2.094,
                        memory_prior=_target_memory_prior(
                            confidence=0.75,
                            area_fraction=0.03,
                            center_offset=0.35,
                            depth_median=0.40,
                            suppressed_actions=["turn_right"],
                        ),
                    ),
                    _policy_step(
                        step_index=2,
                        action="move_forward",
                        decision="approach_detector_target_after_center_loss",
                        x_m=-0.4,
                        z_m=-0.2,
                        heading_rad=-2.094,
                        memory_prior=_target_memory_prior(
                            confidence=0.70,
                            area_fraction=0.02,
                            center_offset=0.45,
                            depth_median=0.30,
                            suppressed_actions=["turn_left", "turn_right"],
                        ),
                    ),
                    _policy_step(
                        step_index=3,
                        action="turn_right",
                        decision="turn_toward_memory_belief_frontier",
                        x_m=-0.4,
                        z_m=-0.2,
                        heading_rad=-2.094,
                    ),
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    detector_trace_path.write_text(
        json.dumps({"task": "official_query_detector_trace", "calls": []}),
        encoding="utf-8",
    )

    report = export_official_local_action_dataset(
        policy_trace_path,
        detector_trace_path=detector_trace_path,
        history_steps=2,
        horizon_steps=2,
    )

    example = report["examples"][2]
    features = example["features"]
    labels = example["labels"]
    assert report["schema_version"] == "official-local-action-effect-v2"
    assert report["history_steps"] == 2
    assert report["horizon_steps"] == 2
    assert features["history_observed_step_count"] == 2
    assert features["previous_target_visible"] is True
    assert features["recent_target_visible_count"] == 3
    assert features["steps_since_last_target_visible"] == 0
    assert features["previous_action"] == "move_forward"
    assert features["previous_decision"] == "approach_detector_target_after_center_loss"
    assert features["recent_move_forward_count"] == 2
    assert features["recent_reacquire_count"] == 0
    assert features["current_depth_median"] == 0.30
    assert features["current_confidence_minus_previous"] == -0.05
    assert features["current_bbox_area_minus_previous"] == -0.01
    assert features["current_depth_minus_previous"] == -0.10
    assert features["current_abs_center_offset_minus_previous"] == 0.10
    assert features["suppressed_turn_left"] is True
    assert features["suppressed_turn_right"] is True
    assert labels["horizon_observed_step_count"] == 1
    assert labels["target_visible_within_horizon"] is False
    assert labels["target_visible_at_horizon"] is False
    assert labels["target_lost_within_horizon"] is True
    assert labels["first_target_loss_step_delta"] == 1
    assert labels["best_future_bbox_area_fraction"] is None
    assert labels["best_future_depth_delta"] is None


def test_official_local_action_dataset_cli_writes_json_and_csv(
    tmp_path: Path,
    capsys,
) -> None:
    from objectnav_core.cli.export_habitat_official_local_action_dataset import main

    policy_trace_path, detector_trace_path = _write_trace_pair(tmp_path)
    output_path = tmp_path / "dataset.json"
    csv_path = tmp_path / "examples.csv"

    exit_code = main(
        [
            str(policy_trace_path),
            "--detector-trace",
            str(detector_trace_path),
            "--output",
            str(output_path),
            "--csv-output",
            str(csv_path),
            "--source-run-id",
            "synthetic-run",
            "--history-steps",
            "2",
            "--horizon-steps",
            "2",
        ]
    )

    assert exit_code == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["source_policy_trace"] == str(policy_trace_path)
    assert report["source_detector_trace"] == str(detector_trace_path)
    assert report["source_run_id"] == "synthetic-run"
    assert report["history_steps"] == 2
    assert report["horizon_steps"] == 2
    assert report["example_count"] == 3
    assert csv_path.exists()
    stdout = capsys.readouterr().out
    assert "example_count" in stdout
    assert '"examples"' not in stdout


def _write_trace_pair(tmp_path: Path) -> tuple[Path, Path]:
    policy_trace_path = tmp_path / "policy_trace.json"
    detector_trace_path = tmp_path / "detector_trace.json"
    policy_trace_path.write_text(
        json.dumps(
            {
                "task": "official_policy_step_trace",
                "steps": [
                    _policy_step(
                        step_index=0,
                        action="move_forward",
                        decision="approach_detector_target",
                        x_m=0.0,
                        z_m=0.0,
                        heading_rad=0.0,
                    ),
                    _policy_step(
                        step_index=1,
                        action="turn_right",
                        decision="center_detector_target",
                        x_m=0.25,
                        z_m=0.0,
                        heading_rad=0.0,
                    ),
                    _policy_step(
                        step_index=2,
                        action="turn_left",
                        decision="reacquire_detector_target",
                        x_m=0.25,
                        z_m=0.0,
                        heading_rad=0.523599,
                        memory_prior={
                            "decision": "reacquire_detector_target",
                            "suppressed_detector_center_action": "turn_right",
                        },
                    ),
                    _policy_step(
                        step_index=3,
                        action="move_forward",
                        decision="approach_detector_target_after_center_loss",
                        x_m=0.25,
                        z_m=0.0,
                        heading_rad=0.0,
                    ),
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    detector_trace_path.write_text(
        json.dumps(
            {
                "task": "official_query_detector_trace",
                "calls": [
                    _detector_call(
                        step_index=0,
                        confidence=0.5,
                        bbox=(380, 80, 540, 176),
                        center_offset=0.4,
                        area_fraction=0.02,
                    ),
                    _detector_call(
                        step_index=1,
                        confidence=0.7,
                        bbox=(300, 80, 460, 224),
                        center_offset=0.2,
                        area_fraction=0.03,
                    ),
                    _detector_call(step_index=2, confidence=None),
                    _detector_call(
                        step_index=3,
                        confidence=0.8,
                        bbox=(320, 72, 480, 240),
                        center_offset=0.0,
                        area_fraction=0.035,
                    ),
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return policy_trace_path, detector_trace_path


def _policy_step(
    *,
    step_index: int,
    action: str,
    decision: str,
    x_m: float,
    z_m: float,
    heading_rad: float,
    memory_prior: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "episode_index": 0,
        "episode_id": "episode-0",
        "scene_id": "hm3d/test.scene.glb",
        "target_category": "tv_monitor",
        "policy": "memory_evidence_frontier",
        "policy_kind": "memory_evidence_frontier_active_search",
        "step_index": step_index,
        "action": action,
        "decision": decision,
        "x_m": x_m,
        "z_m": z_m,
        "heading_rad": heading_rad,
        "memory_prior": memory_prior or {"decision": decision},
    }


def _detector_call(
    *,
    step_index: int,
    confidence: float | None,
    bbox: tuple[int, int, int, int] | None = None,
    center_offset: float | None = None,
    area_fraction: float | None = None,
) -> dict[str, object]:
    if confidence is None:
        return {
            "episode_index": 0,
            "episode_id": "episode-0",
            "scene_id": "hm3d/test.scene.glb",
            "target_category": "tv_monitor",
            "step_index": step_index,
            "missing_rgb": False,
            "detection_count": 0,
            "target_match_count": 0,
            "detections": [],
        }
    return {
        "episode_index": 0,
        "episode_id": "episode-0",
        "scene_id": "hm3d/test.scene.glb",
        "target_category": "tv_monitor",
        "step_index": step_index,
        "missing_rgb": False,
        "detection_count": 1,
        "target_match_count": 1,
        "detections": [
            {
                "category": "tv_monitor",
                "confidence": confidence,
                "bbox": list(bbox or (0, 0, 1, 1)),
                "matches_target": True,
            }
        ],
        "primary_target_evidence": {
            "detector_confidence": confidence,
            "detector_bbox": list(bbox or (0, 0, 1, 1)),
            "detector_center_offset_fraction": center_offset,
            "detector_bbox_area_fraction": area_fraction,
        },
    }


def _official_detector_call(*, step_index: int, confidence: float) -> dict[str, object]:
    return {
        "episode_index": 0,
        "episode_id": "episode-0",
        "scene_id": "hm3d/test.scene.glb",
        "target_category": "tv_monitor",
        "step_index": step_index,
        "missing_rgb": False,
        "detection_count": 1,
        "target_match_count": 1,
        "detections": [
            {
                "category": "tv_monitor",
                "confidence": confidence,
                "bbox": [0, 0, 1, 1],
                "matches_target": True,
            }
        ],
    }


def _target_memory_prior(
    *,
    confidence: float,
    area_fraction: float,
    center_offset: float,
    depth_median: float,
    suppressed_actions: list[str] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "decision": "approach_detector_target_after_center_loss",
        "detector_confidence": confidence,
        "detector_bbox": [0, 0, 1, 1],
        "detector_center_offset_fraction": center_offset,
        "detector_bbox_area_fraction": area_fraction,
        "detector_depth_median": depth_median,
    }
    if suppressed_actions:
        payload["suppressed_detector_center_action"] = suppressed_actions[0]
        payload["suppressed_detector_center_actions"] = suppressed_actions
    return payload
