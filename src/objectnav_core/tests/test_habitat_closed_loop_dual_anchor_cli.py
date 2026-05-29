from __future__ import annotations

import json

from objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav import main


def test_habitat_closed_loop_dual_anchor_cli_preflight(tmp_path) -> None:
    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--dataset-dir",
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--target-categories",
            "plant,toilet",
            "--max-groups",
            "2",
            "--challenge",
            "ambiguous",
            "--query-repeats",
            "2",
            "--memory-valid-prior",
            "0.25",
            "--preflight-only",
        ]
    )

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert summary["task"] == "habitat_closed_loop_dual_anchor_objectnav_preflight"
    assert summary["target_categories"] == ["plant", "toilet"]
    assert summary["challenge"] == "ambiguous"
    assert summary["query_repeats"] == 2
    assert summary["memory_valid_prior"] == 0.25


def test_habitat_closed_loop_cli_preflight_accepts_grounding_dino_config(
    tmp_path,
) -> None:
    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--dataset-dir",
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--target-categories",
            "plant,toilet",
            "--max-groups",
            "2",
            "--detector",
            "grounding_dino",
            "--detector-weights",
            "IDEA-Research/grounding-dino-tiny",
            "--detector-conf",
            "0.25",
            "--grounding-dino-text-threshold",
            "0.2",
            "--grounding-dino-max-image-side",
            "384",
            "--rgb-noise-profile",
            "configs/noise/rgb_published_v1.yaml",
            "--depth-noise-profile",
            "configs/noise/depth_realsense_d435_v1.yaml",
            "--noise-level",
            "mild",
            "--min-target-pixels",
            "24",
            "--min-detector-pixels",
            "20",
            "--max-detection-area-ratio",
            "0.7",
            "--detector-prompt-mode",
            "target",
            "--preflight-only",
        ]
    )

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert summary["detector"] == "grounding_dino"
    assert summary["detector_weights"] == "IDEA-Research/grounding-dino-tiny"
    assert summary["detector_conf"] == 0.25
    assert summary["grounding_dino_text_threshold"] == 0.2
    assert summary["grounding_dino_max_image_side"] == 384
    assert summary["noise_level"] == "mild"
    assert summary["min_detector_pixels"] == 20


def test_habitat_closed_loop_cli_preflight_accepts_navmesh_frontier_config(
    tmp_path,
) -> None:
    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--dataset-dir",
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--target-categories",
            "plant,toilet",
            "--max-groups",
            "2",
            "--frontier-mode",
            "navmesh_frontier",
            "--frontier-probe-count",
            "5",
            "--frontier-probe-heading-count",
            "8",
            "--preflight-only",
        ]
    )

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert summary["frontier_mode"] == "navmesh_frontier"
    assert summary["frontier_probe_count"] == 5
    assert summary["frontier_probe_heading_count"] == 8


def test_habitat_closed_loop_cli_preflight_accepts_memory_reliability_mode(
    tmp_path,
) -> None:
    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--dataset-dir",
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--memory-reliability-mode",
            "evidence",
            "--preflight-only",
        ]
    )

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert summary["memory_reliability_mode"] == "evidence"


def test_habitat_closed_loop_cli_preflight_accepts_route_observation_mode(
    tmp_path,
) -> None:
    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--dataset-dir",
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--route-observation-mode",
            "per_action",
            "--preflight-only",
        ]
    )

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert summary["route_observation_mode"] == "per_action"


def test_habitat_closed_loop_cli_preflight_accepts_detector_confirmation_config(
    tmp_path,
) -> None:
    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--dataset-dir",
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--detector-confirmation-mode",
            "multiview",
            "--detector-confirmation-frames",
            "2",
            "--detector-confirmation-min-translation",
            "0.05",
            "--detector-confirmation-min-rotation-deg",
            "5.0",
            "--detector-confirmation-min-mask-iou",
            "0.05",
            "--preflight-only",
        ]
    )

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert summary["detector_confirmation_mode"] == "multiview"
    assert summary["detector_confirmation"] == {
        "frames": 2,
        "min_translation_m": 0.05,
        "min_rotation_deg": 5.0,
        "min_mask_iou": 0.05,
    }
