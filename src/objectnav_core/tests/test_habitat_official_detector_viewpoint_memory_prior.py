from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    load_official_memory_prior,
)


def test_detector_viewpoint_memory_prior_exports_positive_viewpoint_anchor(
    tmp_path: Path,
) -> None:
    module = _detector_viewpoint_module()
    output_path = tmp_path / "detector_viewpoint_memory_prior.json"
    env = _FakeDetectorViewpointEnv(
        [
            _episode(
                episode_id="episode-1",
                scene_id="scene-a",
                object_category="chair",
                start_position=(10.0, 0.0, 20.0),
                start_rotation=(0.0, 0.0, 0.0, 1.0),
                viewpoint_position=(12.0, 0.25, 17.0),
            )
        ],
        rgb_by_viewpoint=[np.full((4, 4, 3), 7, dtype=np.uint8)],
    )

    summary = module.export_habitat_official_detector_viewpoint_memory_prior(
        output_path,
        detector_adapter=_FakeDetector("chair", 0.82),
        detector_name="fake_dino",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="hm3d",
        max_episodes=1,
        max_viewpoints_per_episode=4,
        min_detection_confidence=0.25,
        env_factory=lambda _config: env,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    anchors = load_official_memory_prior(output_path)

    assert summary["exported_anchor_count"] == 1
    assert summary["detector_positive_viewpoint_count"] == 1
    assert payload["metadata"]["source"] == (
        "habitat_official_detector_positive_viewpoint_memory_prior"
    )
    assert payload["metadata"]["source_validity"] == (
        "privileged_viewpoint_detector_diagnostic"
    )
    assert anchors[0].object_category == "chair"
    assert anchors[0].episode_id == "episode-1"
    assert anchors[0].x_m == pytest.approx(2.0)
    assert anchors[0].y_m == pytest.approx(0.25)
    assert anchors[0].z_m == pytest.approx(3.0)
    assert anchors[0].confidence == pytest.approx(0.82)
    assert anchors[0].source == (
        "fake_dino:episode=episode-1:viewpoint=0:detection=0"
    )


def test_detector_viewpoint_memory_prior_skips_when_detector_never_confirms(
    tmp_path: Path,
) -> None:
    module = _detector_viewpoint_module()
    output_path = tmp_path / "detector_viewpoint_memory_prior.json"
    env = _FakeDetectorViewpointEnv(
        [
            _episode(
                episode_id="episode-2",
                scene_id="scene-a",
                object_category="toilet",
                start_position=(0.0, 0.0, 0.0),
                start_rotation=(0.0, 0.0, 0.0, 1.0),
                viewpoint_position=(0.0, 0.0, -2.0),
            )
        ],
        rgb_by_viewpoint=[np.zeros((4, 4, 3), dtype=np.uint8)],
    )

    summary = module.export_habitat_official_detector_viewpoint_memory_prior(
        output_path,
        detector_adapter=_FakeDetector("chair", 0.9),
        detector_name="fake_dino",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="hm3d",
        max_episodes=1,
        env_factory=lambda _config: env,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["exported_anchor_count"] == 0
    assert summary["skipped_episode_count"] == 1
    assert summary["skipped_episodes"][0]["reason"] == (
        "no_detector_positive_viewpoint"
    )
    assert payload["anchors"] == []


def test_detector_viewpoint_memory_prior_writes_per_viewpoint_trace(
    tmp_path: Path,
) -> None:
    module = _detector_viewpoint_module()
    output_path = tmp_path / "detector_viewpoint_memory_prior.json"
    trace_path = tmp_path / "viewpoint_trace.json"
    env = _FakeDetectorViewpointEnv(
        [
            _episode(
                episode_id="episode-3",
                scene_id="scene-a",
                object_category="tv_monitor",
                start_position=(0.0, 0.0, 0.0),
                start_rotation=(0.0, 0.0, 0.0, 1.0),
                viewpoint_positions=((0.0, 0.0, -1.0), (1.0, 0.0, -2.0)),
            )
        ],
        rgb_by_viewpoint=[
            np.full((4, 4, 3), 10, dtype=np.uint8),
            np.full((4, 4, 3), 20, dtype=np.uint8),
        ],
    )

    summary = module.export_habitat_official_detector_viewpoint_memory_prior(
        output_path,
        detector_adapter=_SequenceDetector(
            [
                [SimpleNamespace(category="chair", confidence=0.91, bbox=(0, 0, 1, 1))],
                [
                    SimpleNamespace(
                        category="tv_monitor",
                        confidence=0.77,
                        bbox=(1, 1, 3, 3),
                    )
                ],
            ]
        ),
        detector_name="fake_dino",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="hm3d",
        max_episodes=1,
        viewpoint_trace_path=trace_path,
        env_factory=lambda _config: env,
    )

    trace = json.loads(trace_path.read_text(encoding="utf-8"))

    assert summary["artifact_files"]["viewpoint_trace"] == "viewpoint_trace.json"
    assert trace["task"] == "habitat_official_detector_viewpoint_memory_prior_trace"
    assert trace["viewpoint_count"] == 2
    assert trace["target_match_viewpoint_count"] == 1
    assert trace["selected_anchor_count"] == 1
    assert trace["viewpoints"][0]["viewpoint_index"] == 0
    assert trace["viewpoints"][0]["selected_anchor"] is False
    assert trace["viewpoints"][0]["target_match_count"] == 0
    assert trace["viewpoints"][0]["detections"][0]["category"] == "chair"
    assert trace["viewpoints"][0]["detections"][0]["matches_target"] is False
    assert trace["viewpoints"][1]["viewpoint_index"] == 1
    assert trace["viewpoints"][1]["selected_anchor"] is True
    assert trace["viewpoints"][1]["anchor_source"] == (
        "fake_dino:episode=episode-3:viewpoint=1:detection=0"
    )
    assert trace["viewpoints"][1]["detections"][0]["bbox"] == [1, 1, 3, 3]
    assert trace["viewpoints"][1]["detections"][0]["matches_target"] is True


def test_detector_viewpoint_memory_prior_writes_debug_images(
    tmp_path: Path,
) -> None:
    module = _detector_viewpoint_module()
    output_path = tmp_path / "detector_viewpoint_memory_prior.json"
    trace_path = tmp_path / "viewpoint_trace.json"
    image_dir = tmp_path / "viewpoint_images"
    env = _FakeDetectorViewpointEnv(
        [
            _episode(
                episode_id="episode-image",
                scene_id="scene-a",
                object_category="bed",
                start_position=(0.0, 0.0, 0.0),
                start_rotation=(0.0, 0.0, 0.0, 1.0),
                viewpoint_position=(0.0, 0.0, -1.0),
            )
        ],
        rgb_by_viewpoint=[np.full((8, 8, 3), 80, dtype=np.uint8)],
    )

    summary = module.export_habitat_official_detector_viewpoint_memory_prior(
        output_path,
        detector_adapter=_FakeDetector("bed", 0.8),
        detector_name="fake_dino",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="hm3d",
        max_episodes=1,
        viewpoint_trace_path=trace_path,
        viewpoint_image_dir=image_dir,
        env_factory=lambda _config: env,
    )

    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    image_path = Path(trace["viewpoints"][0]["image_path"])

    assert summary["artifact_files"]["viewpoint_images"] == "viewpoint_images"
    assert image_path.exists()
    assert image_path.suffix == ".png"


def test_detector_viewpoint_memory_prior_cli_defaults_to_grounding_dino(
    tmp_path: Path,
) -> None:
    cli_module = _detector_viewpoint_cli_module()
    calls: list[dict[str, object]] = []

    def detector_factory(detector_name: str, **kwargs: object) -> object:
        calls.append({"detector_name": detector_name, "detector_kwargs": dict(kwargs)})
        return object()

    def exporter(output_path: str | Path, **kwargs: object) -> dict[str, object]:
        calls.append({"output_path": str(output_path), **kwargs})
        Path(output_path).write_text(
            json.dumps({"anchors": [], "metadata": {}}),
            encoding="utf-8",
        )
        return {"task": "habitat_official_detector_viewpoint_memory_prior_export"}

    output_path = tmp_path / "prior.json"

    exit_code = cli_module.main(
        [
            "--output",
            str(output_path),
            "--config-path",
            "official.yaml",
            "--dataset-data-path",
            "val_mini.json.gz",
            "--scene-root",
            "hm3d",
            "--max-episodes",
            "2",
            "--max-viewpoints-per-episode",
            "3",
            "--grounding-dino-max-image-side",
            "384",
            "--viewpoint-trace-output",
            str(tmp_path / "trace.json"),
            "--viewpoint-image-dir",
            str(tmp_path / "images"),
        ],
        detector_factory=detector_factory,
        exporter=exporter,
    )

    assert exit_code == 0
    assert calls[0] == {
        "detector_name": "grounding_dino",
        "detector_kwargs": {
            "model_id": "IDEA-Research/grounding-dino-tiny",
            "categories": ["bed", "chair", "plant", "sofa", "toilet", "tv_monitor"],
            "conf": 0.25,
            "text_threshold": 0.25,
            "max_image_side": 384,
            "device": "auto",
        },
    }
    assert calls[1]["detector_adapter"] is not None
    assert calls[1]["detector_name"] == "grounding_dino:IDEA-Research/grounding-dino-tiny"
    assert calls[1]["max_episodes"] == 2
    assert calls[1]["max_viewpoints_per_episode"] == 3
    assert calls[1]["viewpoint_trace_path"] == tmp_path / "trace.json"
    assert calls[1]["viewpoint_image_dir"] == tmp_path / "images"


def _detector_viewpoint_module() -> object:
    try:
        return importlib.import_module(
            "objectnav_core.evaluation.habitat_official_detector_viewpoint_memory_prior"
        )
    except ModuleNotFoundError as exc:
        pytest.fail(f"detector viewpoint memory prior module missing: {exc}")


def _detector_viewpoint_cli_module() -> object:
    try:
        return importlib.import_module(
            "objectnav_core.cli.export_habitat_official_detector_viewpoint_memory_prior"
        )
    except ModuleNotFoundError as exc:
        pytest.fail(f"detector viewpoint memory prior CLI missing: {exc}")


def _episode(
    *,
    episode_id: str,
    scene_id: str,
    object_category: str,
    start_position: tuple[float, float, float],
    start_rotation: tuple[float, float, float, float],
    viewpoint_position: tuple[float, float, float] | None = None,
    viewpoint_positions: tuple[tuple[float, float, float], ...] | None = None,
) -> SimpleNamespace:
    positions = viewpoint_positions or (viewpoint_position,)
    if any(position is None for position in positions):
        raise ValueError("viewpoint_position or viewpoint_positions is required")
    return SimpleNamespace(
        episode_id=episode_id,
        scene_id=scene_id,
        object_category=object_category,
        start_position=start_position,
        start_rotation=start_rotation,
        goals=[
            SimpleNamespace(
                view_points=[
                    SimpleNamespace(
                        agent_state=SimpleNamespace(
                            position=position,
                            rotation=(0.0, 0.0, 0.0, 1.0),
                        )
                    )
                    for position in positions
                ]
            )
        ],
    )


class _FakeDetectorViewpointEnv:
    def __init__(
        self,
        episodes: list[SimpleNamespace],
        *,
        rgb_by_viewpoint: list[np.ndarray],
    ) -> None:
        self.episodes = episodes
        self._rgb_by_viewpoint = rgb_by_viewpoint
        self._episode_index = -1
        self._viewpoint_index = 0
        self.current_episode: SimpleNamespace | None = None
        self.closed = False

    def reset(self) -> dict[str, object]:
        self._episode_index += 1
        self._viewpoint_index = 0
        self.current_episode = self.episodes[self._episode_index]
        return {}

    def restore_viewpoint_observation(
        self,
        *,
        position: tuple[float, float, float],
        rotation: tuple[float, float, float, float],
    ) -> dict[str, object]:
        del position, rotation
        rgb = self._rgb_by_viewpoint[self._viewpoint_index]
        self._viewpoint_index += 1
        return {"rgb": rgb}

    def close(self) -> None:
        self.closed = True


class _FakeDetector:
    def __init__(self, category: str, confidence: float) -> None:
        self.category = category
        self.confidence = confidence

    def detect(self, rgb: np.ndarray) -> list[SimpleNamespace]:
        if not int(np.asarray(rgb).sum()):
            return []
        return [
            SimpleNamespace(
                category=self.category,
                confidence=self.confidence,
                bbox=(0, 0, 1, 1),
            )
        ]


class _SequenceDetector:
    def __init__(self, detections_by_call: list[list[SimpleNamespace]]) -> None:
        self._detections_by_call = detections_by_call
        self._index = 0

    def detect(self, rgb: np.ndarray) -> list[SimpleNamespace]:
        del rgb
        detections = self._detections_by_call[self._index]
        self._index += 1
        return detections
