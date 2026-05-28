import json
import sys
from pathlib import Path

import numpy as np

from objectnav_core.evaluation import habitat_objectnav_rgb_noise_stress as stress
from objectnav_core.memory.usability import EvidenceType
from objectnav_core.memory.usability import DecisionType
from objectnav_core.perception.yolo_world_adapter import Detection


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


def test_preflight_accepts_naive_count_memory_baseline(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean",),
        detector="oracle_bbox",
        detector_weights="unused",
        detector_conf=0.25,
        memory_ablation=("naive_count",),
        seed=313,
    )

    assert "naive_count" in stress.SUPPORTED_MEMORY_ABLATIONS
    assert summary["memory_ablation"] == ["naive_count"]


def test_preflight_records_gate_rejection_debug_export_config(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean",),
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        memory_ablation=("on", "naive_count"),
        seed=313,
        debug_export_gate_rejections=True,
        debug_export_categories=("plant", "tv_monitor"),
        debug_export_limit_per_category=12,
    )

    assert summary["debug_export_gate_rejections"] is True
    assert summary["debug_export_categories"] == ["plant", "tv_monitor"]
    assert summary["debug_export_limit_per_category"] == 12


def test_gate_rejection_debug_export_condition_is_category_scoped() -> None:
    categories = {"plant", "tv_monitor"}

    assert stress._should_export_gate_rejection_debug(
        object_category="tv_monitor",
        decision=DecisionType.TRUST,
        gated_decision=DecisionType.VERIFY,
        debug_categories=categories,
    )
    assert not stress._should_export_gate_rejection_debug(
        object_category="toilet",
        decision=DecisionType.TRUST,
        gated_decision=DecisionType.VERIFY,
        debug_categories=categories,
    )
    assert not stress._should_export_gate_rejection_debug(
        object_category="plant",
        decision=DecisionType.VERIFY,
        gated_decision=DecisionType.VERIFY,
        debug_categories=categories,
    )


def test_write_gate_rejection_debug_png_creates_visual_artifact(tmp_path: Path) -> None:
    rgb = np.zeros((24, 32, 3), dtype=np.uint8)
    rgb[:, :, 1] = 120
    noisy_rgb = rgb.copy()
    oracle_mask = np.zeros((24, 32), dtype=bool)
    oracle_mask[6:16, 4:14] = True
    detector_mask = np.zeros((24, 32), dtype=bool)
    detector_mask[5:18, 12:28] = True
    detection = Detection(
        category="plant",
        bbox=(12, 5, 28, 18),
        confidence=0.77,
        mask=detector_mask,
    )

    png_path = stress._write_gate_rejection_debug_png(
        output_dir=tmp_path,
        rgb=rgb,
        noisy_rgb=noisy_rgb,
        oracle_mask=oracle_mask,
        detector_mask=detector_mask,
        detections=[detection],
        metadata={
            "object_category": "plant",
            "memory_mode": "on",
            "noise_level": "clean",
            "episode_index": 3,
            "episode_id": "episode-3",
            "step_index": 4,
            "action": "turn_left",
            "decision_gate_reason": "target_not_currently_visible",
            "raw_decision": "trust",
            "decision": "verify",
            "target_visible": False,
            "evidence_type": "unknown",
            "oracle_target_pixels": 100,
            "detector_target_pixels": 208,
            "detector_precision": 0.1,
            "oracle_recall": 0.2,
            "oracle_bbox": "4,6,14,16",
            "detection_conf_max": 0.77,
        },
        sequence_id=0,
    )

    assert png_path.exists()
    assert png_path.suffix == ".png"
    assert png_path.stat().st_size > 0


def test_detector_mask_filters_over_broad_detector_boxes() -> None:
    large_mask = np.ones((20, 30), dtype=bool)
    small_mask = np.zeros((20, 30), dtype=bool)
    small_mask[3:9, 4:12] = True
    detections = [
        Detection("tv monitor", (0, 0, 30, 20), 0.42, large_mask),
        Detection("tv monitor", (4, 3, 12, 9), 0.61, small_mask),
    ]
    adapter = _StaticDetector(detections)

    mask, kept, filtered_count = stress._detector_mask(
        detector="grounding_dino",
        detector_adapter=adapter,
        noisy_rgb=np.zeros((20, 30, 3), dtype=np.uint8),
        oracle_mask=np.zeros((20, 30), dtype=bool),
        target_category="tv_monitor",
        accepted_detection_labels={"tv monitor"},
        max_detection_area_ratio=0.7,
    )

    assert kept == [detections[1]]
    assert filtered_count == 1
    assert np.array_equal(mask, small_mask)


def test_detector_mask_keeps_over_broad_boxes_when_filter_disabled() -> None:
    large_mask = np.ones((20, 30), dtype=bool)
    detection = Detection("tv monitor", (0, 0, 30, 20), 0.42, large_mask)
    adapter = _StaticDetector([detection])

    mask, kept, filtered_count = stress._detector_mask(
        detector="grounding_dino",
        detector_adapter=adapter,
        noisy_rgb=np.zeros((20, 30, 3), dtype=np.uint8),
        oracle_mask=np.zeros((20, 30), dtype=bool),
        target_category="tv_monitor",
        accepted_detection_labels={"tv monitor"},
        max_detection_area_ratio=None,
    )

    assert kept == [detection]
    assert filtered_count == 0
    assert np.array_equal(mask, large_mask)


def test_detector_mask_drops_frame_when_union_area_is_over_broad() -> None:
    upper_mask = np.zeros((20, 30), dtype=bool)
    upper_mask[:12, :] = True
    lower_mask = np.zeros((20, 30), dtype=bool)
    lower_mask[8:, :] = True
    detections = [
        Detection("tv monitor", (0, 0, 30, 12), 0.42, upper_mask),
        Detection("tv monitor", (0, 8, 30, 20), 0.39, lower_mask),
    ]
    adapter = _StaticDetector(detections)

    mask, kept, filtered_count = stress._detector_mask(
        detector="grounding_dino",
        detector_adapter=adapter,
        noisy_rgb=np.zeros((20, 30, 3), dtype=np.uint8),
        oracle_mask=np.zeros((20, 30), dtype=bool),
        target_category="tv_monitor",
        accepted_detection_labels={"tv monitor"},
        max_detection_area_ratio=0.7,
    )

    assert kept == []
    assert filtered_count == 2
    assert not mask.any()


def test_naive_count_baseline_only_accumulates_positive_evidence() -> None:
    state = stress.NaiveCountState()

    state, belief = stress._naive_count_belief(state, EvidenceType.POSITIVE)
    assert state.positive_count == 1
    assert belief.p_valid < stress.NAIVE_COUNT_TRUST_P_VALID
    first_positive_p_valid = belief.p_valid

    state, belief = stress._naive_count_belief(state, EvidenceType.UNKNOWN)
    assert state.positive_count == 1
    assert belief.p_valid == first_positive_p_valid

    state, belief = stress._naive_count_belief(state, EvidenceType.NON_CONFIRMATION)
    assert state.positive_count == 1
    assert belief.p_valid == first_positive_p_valid

    state, belief = stress._naive_count_belief(state, EvidenceType.POSITIVE)
    assert state.positive_count == 2
    assert belief.p_valid >= stress.NAIVE_COUNT_TRUST_P_VALID
    assert belief.p_valid >= first_positive_p_valid


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
        grounding_dino_max_image_side=640,
    )

    assert "grounding_dino" in stress.SUPPORTED_DETECTORS
    assert summary["detector"] == "grounding_dino"
    assert summary["detector_weights"] == "IDEA-Research/grounding-dino-tiny"
    assert summary["grounding_dino_text_threshold"] == 0.2
    assert summary["grounding_dino_max_image_side"] == 640


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
        grounding_dino_max_image_side=640,
        target_category="tv_monitor",
        yolo_prompt_mode="target",
        detector_factory=lambda **kwargs: kwargs,
    )

    assert adapter == {
        "model_id": "IDEA-Research/grounding-dino-tiny",
        "categories": ["tv monitor"],
        "conf": 0.25,
        "text_threshold": 0.2,
        "max_image_side": 640,
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
            decision=DecisionType.TRUST,
            target_visible=True,
            stop_on_trust=False,
        )
        is False
    )


def test_shared_decision_gate_requires_current_positive_confirmation() -> None:
    assert (
        stress._gated_decision(
            decision=DecisionType.TRUST,
            target_visible=True,
            evidence_type=EvidenceType.POSITIVE,
        )
        is DecisionType.TRUST
    )
    assert (
        stress._gated_decision(
            decision=DecisionType.TRUST,
            target_visible=True,
            evidence_type=EvidenceType.UNKNOWN,
        )
        is DecisionType.VERIFY
    )
    assert (
        stress._gated_decision(
            decision=DecisionType.TRUST,
            target_visible=False,
            evidence_type=EvidenceType.POSITIVE,
        )
        is DecisionType.VERIFY
    )
    assert (
        stress._should_stop_episode(
            decision=DecisionType.TRUST,
            gated_decision=DecisionType.VERIFY,
            target_visible=True,
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


def test_run_summary_reports_raw_and_gated_decision_counts(tmp_path: Path) -> None:
    summary = stress._summarize_rgb_noise_run(
        output_path=tmp_path,
        config_summary={"detector": "oracle_bbox"},
        dataset_dir=Path("dataset"),
        scene_root=Path("scenes"),
        scene_dataset_config=Path("scene_config.json"),
        start_source="goal_viewpoint",
        sensor_height=720,
        sensor_width=1280,
        max_episodes=None,
        rows=[
            {
                "evidence_type": "positive",
                "decision": "trust",
                "raw_decision": "trust",
                "decision_gate_reason": "current_positive_confirmation",
                "oracle_stop_success": True,
                "detector_precision": 1.0,
                "oracle_recall": 1.0,
            },
            {
                "evidence_type": "positive",
                "decision": "verify",
                "raw_decision": "trust",
                "decision_gate_reason": "target_not_currently_visible",
                "oracle_stop_success": False,
                "detector_precision": 0.0,
                "oracle_recall": 0.0,
            },
        ],
        episode_summaries=[
            {
                "object_category": "tv_monitor",
                "final_p_valid": 0.95,
                "oracle_stop_success_rows": 1,
            }
        ],
    )

    assert summary["decision_counts"]["trust"] == 1
    assert summary["decision_counts"]["verify"] == 1
    assert summary["raw_decision_counts"] == {"trust": 2}
    assert summary["decision_gate_reason_counts"] == {
        "current_positive_confirmation": 1,
        "target_not_currently_visible": 1,
    }


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


class _StaticDetector:
    def __init__(self, detections: list[Detection]) -> None:
        self._detections = detections

    def detect(self, rgb: object) -> list[Detection]:
        return self._detections
