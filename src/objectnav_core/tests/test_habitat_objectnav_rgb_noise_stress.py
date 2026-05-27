import json
import sys
from pathlib import Path

from objectnav_core.evaluation import habitat_objectnav_rgb_noise_stress as stress


def test_importing_rgb_noise_stress_does_not_import_habitat_or_ultralytics() -> None:
    assert "habitat" not in sys.modules
    assert "habitat_sim" not in sys.modules
    assert "ultralytics" not in sys.modules


def test_preflight_writes_summary_for_rgb_noise_stress(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean", "mild"),
        detector="yolo_world",
        detector_weights="yolov8s-worldv2.pt",
        detector_conf=0.25,
        memory_ablation=("on", "off"),
        seed=313,
    )

    assert summary["task"] == "habitat_objectnav_rgb_noise_stress_preflight"
    assert summary["detector"] == "yolo_world"
    assert summary["yolo_prompt_mode"] == "target"
    assert summary["target_categories"] == [
        "bed",
        "chair",
        "plant",
        "sofa",
        "toilet",
        "tv_monitor",
    ]
    assert summary["noise_levels"] == ["clean", "mild"]
    assert summary["memory_ablation"] == ["on", "off"]
    assert summary["out_and_back_action_count"] > 6
    assert (tmp_path / "summary.json").exists()
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8")) == summary


def test_default_yolo_prompting_is_target_conditioned() -> None:
    assert stress.DEFAULT_SENSOR_SIZE == 320
    assert stress.DEFAULT_YOLO_PROMPT_MODE == "target"
    assert stress._yolo_prompt_categories("toilet", "target") == ("toilet",)
    assert stress._yolo_prompt_categories("tv_monitor", "target") == ("tv monitor",)
    assert stress._yolo_prompt_categories("toilet", "all_categories") == (
        "bed",
        "chair",
        "plant",
        "sofa",
        "toilet",
        "tv monitor",
    )
    assert "white toilet" in stress._accepted_yolo_detection_labels(
        "toilet",
        "target_aliases",
    )


def test_preflight_rejects_unknown_yolo_prompt_mode(tmp_path: Path) -> None:
    try:
        stress.run_rgb_noise_stress_preflight(
            output_dir=tmp_path,
            rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
            depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
            noise_levels=("clean",),
            detector="yolo_world",
            detector_weights="yolov8s-worldv2.pt",
            detector_conf=0.25,
            memory_ablation=("on",),
            seed=313,
            yolo_prompt_mode="everything",
        )
    except ValueError as exc:
        assert "yolo_prompt_mode" in str(exc)
    else:
        raise AssertionError("unknown yolo prompt modes should fail preflight")


def test_preflight_rejects_noise_level_missing_from_profile(tmp_path: Path) -> None:
    try:
        stress.run_rgb_noise_stress_preflight(
            output_dir=tmp_path,
            rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
            depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
            noise_levels=("clean", "extreme"),
            detector="yolo_world",
            detector_weights="yolov8s-worldv2.pt",
            detector_conf=0.25,
            memory_ablation=("on",),
            seed=313,
        )
    except ValueError as exc:
        assert "extreme" in str(exc)
    else:
        raise AssertionError("unknown noise levels should fail preflight")
