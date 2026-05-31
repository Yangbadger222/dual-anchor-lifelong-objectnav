from __future__ import annotations

import json

import pytest

from objectnav_core.cli.run_habitat_official_memory_discovery import (
    build_parser,
    main,
)


def test_official_memory_discovery_cli_parser_defaults() -> None:
    args = build_parser().parse_args(["--output", "runs/discovery"])

    assert args.output == "runs/discovery"
    assert args.detector == "grounding_dino"
    assert args.detector_weights is None
    assert args.detector_conf == 0.25
    assert args.detector_device == "auto"
    assert args.policy == "occupancy_frontier"
    assert "chair" in args.categories
    assert "tv_monitor" in args.categories
    assert args.positive_count_threshold == 1
    assert args.anchor_mode == "projected_detection"
    assert args.anchor_selection_policy == "confidence"
    assert args.anchor_commit_policy == "immediate"
    assert args.detector_approach_max_steps == 1


def test_official_memory_discovery_cli_defaults_to_grounding_dino_model(
    tmp_path,
) -> None:
    recorder = _Recorder()

    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--categories",
            "chair,plant",
            "--max-episodes",
            "1",
            "--max-steps",
            "1",
        ],
        detector_factory=recorder.detector_factory,
        runner=recorder.runner,
    )

    assert exit_code == 0
    assert recorder.detector_backend == "grounding_dino"
    assert recorder.detector_kwargs == {
        "model_id": "IDEA-Research/grounding-dino-tiny",
        "categories": ["chair", "plant"],
        "conf": 0.25,
        "text_threshold": 0.25,
        "max_image_side": None,
        "device": "auto",
    }
    assert recorder.runner_kwargs["detector_name"] == (
        "grounding_dino:IDEA-Research/grounding-dino-tiny"
    )


def test_official_memory_discovery_cli_forwards_yolo_detector_and_runner(
    tmp_path,
    capsys,
) -> None:
    recorder = _Recorder()

    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--detector",
            "yolo_world",
            "--detector-weights",
            "custom-yolo.pt",
            "--detector-conf",
            "0.31",
            "--detector-device",
            "cpu",
            "--categories",
            "chair,plant",
            "--policy",
            "frontier_only",
            "--max-episodes",
            "2",
            "--max-steps",
            "17",
            "--seed",
            "99",
            "--min-detection-confidence",
            "0.41",
            "--max-anchors-per-episode",
            "3",
            "--positive-count-threshold",
            "2",
            "--anchor-mode",
            "robot_viewpoint",
            "--anchor-selection-policy",
            "view_quality",
            "--anchor-commit-policy",
            "detector_approach",
            "--detector-approach-max-steps",
            "2",
            "--hfov-deg",
            "80",
            "--min-depth-m",
            "0.3",
            "--max-depth-m",
            "4.5",
        ],
        detector_factory=recorder.detector_factory,
        runner=recorder.runner,
    )

    printed = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert printed == {"task": "fake_discovery", "exported_anchor_count": 0}
    assert recorder.detector_backend == "yolo_world"
    assert recorder.detector_kwargs == {
        "weights": "custom-yolo.pt",
        "categories": ["chair", "plant"],
        "conf": 0.31,
        "device": "cpu",
    }
    assert recorder.runner_output_dir == tmp_path
    assert recorder.runner_kwargs["detector_adapter"] is recorder.detector
    assert recorder.runner_kwargs["detector_name"] == "yolo_world:custom-yolo.pt"
    assert recorder.runner_kwargs["policy"] == "frontier_only"
    assert recorder.runner_kwargs["max_episodes"] == 2
    assert recorder.runner_kwargs["max_steps"] == 17
    assert recorder.runner_kwargs["seed"] == 99
    assert recorder.runner_kwargs["min_detection_confidence"] == 0.41
    assert recorder.runner_kwargs["max_anchors_per_episode"] == 3
    assert recorder.runner_kwargs["positive_count_threshold"] == 2
    assert recorder.runner_kwargs["anchor_mode"] == "robot_viewpoint"
    assert recorder.runner_kwargs["anchor_selection_policy"] == "view_quality"
    assert recorder.runner_kwargs["anchor_commit_policy"] == "detector_approach"
    assert recorder.runner_kwargs["detector_approach_max_steps"] == 2
    assert recorder.runner_kwargs["hfov_deg"] == 80.0
    assert recorder.runner_kwargs["min_depth_m"] == 0.3
    assert recorder.runner_kwargs["max_depth_m"] == 4.5


def test_official_memory_discovery_cli_forwards_grounding_dino_options(
    tmp_path,
) -> None:
    recorder = _Recorder()

    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--detector",
            "grounding_dino",
            "--detector-weights",
            "IDEA-Research/grounding-dino-tiny",
            "--detector-conf",
            "0.22",
            "--grounding-dino-text-threshold",
            "0.19",
            "--grounding-dino-max-image-side",
            "512",
            "--categories",
            "chair,tv monitor",
            "--max-episodes",
            "1",
            "--max-steps",
            "1",
        ],
        detector_factory=recorder.detector_factory,
        runner=recorder.runner,
    )

    assert exit_code == 0
    assert recorder.detector_backend == "grounding_dino"
    assert recorder.detector_kwargs == {
        "model_id": "IDEA-Research/grounding-dino-tiny",
        "categories": ["chair", "tv monitor"],
        "conf": 0.22,
        "text_threshold": 0.19,
        "max_image_side": 512,
        "device": "auto",
    }
    assert recorder.runner_kwargs["detector_name"] == (
        "grounding_dino:IDEA-Research/grounding-dino-tiny"
    )


def test_official_memory_discovery_cli_forwards_confirmed_detector_approach(
    tmp_path,
) -> None:
    recorder = _Recorder()

    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--categories",
            "chair",
            "--anchor-mode",
            "robot_viewpoint",
            "--anchor-commit-policy",
            "confirmed_detector_approach",
            "--detector-approach-max-steps",
            "6",
        ],
        detector_factory=recorder.detector_factory,
        runner=recorder.runner,
    )

    assert exit_code == 0
    assert recorder.runner_kwargs["anchor_mode"] == "robot_viewpoint"
    assert recorder.runner_kwargs["anchor_commit_policy"] == (
        "confirmed_detector_approach"
    )
    assert recorder.runner_kwargs["detector_approach_max_steps"] == 6


def test_official_memory_discovery_cli_rejects_empty_categories(tmp_path) -> None:
    recorder = _Recorder()

    with pytest.raises(SystemExit):
        main(
            [
                "--output",
                str(tmp_path),
                "--categories",
                " , ",
            ],
            detector_factory=recorder.detector_factory,
            runner=recorder.runner,
        )


class _Recorder:
    def __init__(self) -> None:
        self.detector = object()
        self.detector_backend: str | None = None
        self.detector_kwargs: dict[str, object] | None = None
        self.runner_output_dir = None
        self.runner_kwargs: dict[str, object] = {}

    def detector_factory(self, backend: str, **kwargs: object) -> object:
        self.detector_backend = backend
        self.detector_kwargs = dict(kwargs)
        return self.detector

    def runner(self, output_dir: object, **kwargs: object) -> dict[str, object]:
        self.runner_output_dir = output_dir
        self.runner_kwargs = dict(kwargs)
        return {"task": "fake_discovery", "exported_anchor_count": 0}
