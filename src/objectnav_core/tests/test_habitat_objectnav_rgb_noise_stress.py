import json
import sys
from pathlib import Path

from objectnav_core.evaluation import habitat_objectnav_rgb_noise_stress as stress
from objectnav_core.memory.usability import DecisionType


def test_importing_rgb_noise_stress_does_not_import_habitat_or_ultralytics() -> None:
    assert "habitat" not in sys.modules
    assert "habitat_sim" not in sys.modules
    assert "ultralytics" not in sys.modules
    assert "transformers" not in sys.modules


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
    assert summary["stop_on_trust"] is True
    assert summary["sensor_width"] == 640
    assert summary["sensor_height"] == 480
    assert summary["sensor_resolution"] == "640x480"
    assert summary["episodes_per_category"] is None
    assert summary["category_filter"] == [
        "bed",
        "chair",
        "plant",
        "sofa",
        "toilet",
        "tv_monitor",
    ]
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


def test_preflight_accepts_grounding_dino_detector(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean",),
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        memory_ablation=("on",),
        seed=313,
        grounding_dino_text_threshold=0.2,
    )

    assert "grounding_dino" in stress.SUPPORTED_DETECTORS
    assert summary["detector"] == "grounding_dino"
    assert summary["detector_weights"] == "IDEA-Research/grounding-dino-tiny"
    assert summary["grounding_dino_text_threshold"] == 0.2


def test_default_yolo_prompting_is_target_conditioned() -> None:
    assert stress.DEFAULT_SENSOR_WIDTH == 640
    assert stress.DEFAULT_SENSOR_HEIGHT == 480
    assert stress.DEFAULT_YOLO_PROMPT_MODE == "target"
    assert stress.DEFAULT_STOP_ON_TRUST is True
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


def test_detector_adapter_cache_supports_grounding_dino() -> None:
    cache: dict[tuple[str, tuple[str, ...]], object] = {}

    adapter = stress._detector_for_target(
        detector_cache=cache,
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        grounding_dino_text_threshold=0.2,
        target_category="tv_monitor",
        yolo_prompt_mode="target",
        detector_factory=lambda **kwargs: kwargs,
    )

    assert adapter == {
        "model_id": "IDEA-Research/grounding-dino-tiny",
        "categories": ["tv monitor"],
        "conf": 0.25,
        "text_threshold": 0.2,
        "device": "auto",
    }
    assert list(cache) == [("grounding_dino", ("tv monitor",))]


def test_sensor_resolution_prefers_explicit_rectangular_dimensions() -> None:
    assert stress._resolve_sensor_resolution(
        sensor_size=None,
        sensor_width=1280,
        sensor_height=720,
    ) == (720, 1280)
    assert stress._resolve_sensor_resolution(
        sensor_size=320,
        sensor_width=1280,
        sensor_height=720,
    ) == (320, 320)


def test_select_episodes_balances_by_category() -> None:
    episodes = [
        _Episode("p1", "plant"),
        _Episode("t1", "toilet"),
        _Episode("p2", "plant"),
        _Episode("c1", "chair"),
        _Episode("t2", "toilet"),
        _Episode("c2", "chair"),
    ]

    selected = stress._select_episodes(
        episodes,
        target_categories=("toilet", "plant"),
        episodes_per_category=1,
        max_episodes=None,
    )

    assert [episode.episode_id for episode in selected] == ["p1", "t1"]
    assert stress._category_counts(selected) == {"plant": 1, "toilet": 1}


def test_target_view_metrics_marks_edge_clipped_views() -> None:
    centered = stress._target_view_metrics(_mask_with_box((10, 12, 30, 36), (48, 48)))
    clipped = stress._target_view_metrics(_mask_with_box((31, 40, 48, 48), (48, 48)))
    floor_clipped = stress._target_view_metrics(_mask_with_box((10, 20, 30, 48), (48, 48)))

    assert centered["oracle_bbox"] == "10,12,30,36"
    assert centered["oracle_touches_edge"] is False
    assert centered["oracle_edge_sides"] == ""
    assert centered["oracle_touches_side_edge"] is False
    assert centered["oracle_bbox_fill_ratio"] == 1.0
    assert clipped["oracle_touches_edge"] is True
    assert clipped["oracle_edge_sides"] == "right|bottom"
    assert clipped["oracle_touches_side_edge"] is True
    assert clipped["oracle_edge_clearance_ratio"] == 0.0
    assert floor_clipped["oracle_edge_sides"] == "bottom"
    assert floor_clipped["oracle_touches_side_edge"] is False


def test_stop_on_trust_uses_objectnav_stop_semantics() -> None:
    assert (
        stress._should_stop_episode(
            decision=DecisionType.TRUST,
            target_visible=True,
            stop_on_trust=True,
        )
        is True
    )
    assert (
        stress._should_stop_episode(
            decision=DecisionType.TRUST,
            target_visible=False,
            stop_on_trust=True,
        )
        is False
    )
    assert (
        stress._should_stop_episode(
            decision=DecisionType.VERIFY,
            target_visible=True,
            stop_on_trust=True,
        )
        is False
    )
    assert (
        stress._should_stop_episode(
            decision=DecisionType.TRUST,
            target_visible=True,
            stop_on_trust=False,
        )
        is False
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


def test_preflight_rejects_bad_grounding_dino_text_threshold(tmp_path: Path) -> None:
    try:
        stress.run_rgb_noise_stress_preflight(
            output_dir=tmp_path,
            rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
            depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
            noise_levels=("clean",),
            detector="grounding_dino",
            detector_weights="IDEA-Research/grounding-dino-tiny",
            detector_conf=0.25,
            grounding_dino_text_threshold=1.1,
            memory_ablation=("on",),
            seed=313,
        )
    except ValueError as exc:
        assert "grounding_dino_text_threshold" in str(exc)
    else:
        raise AssertionError("bad Grounding-DINO text thresholds should fail preflight")


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


def _mask_with_box(
    bbox: tuple[int, int, int, int],
    shape: tuple[int, int],
) -> object:
    import numpy as np

    mask = np.zeros(shape, dtype=bool)
    x1, y1, x2, y2 = bbox
    mask[y1:y2, x1:x2] = True
    return mask


class _Episode:
    def __init__(self, episode_id: str, object_category: str) -> None:
        self.episode_id = episode_id
        self.object_category = object_category
