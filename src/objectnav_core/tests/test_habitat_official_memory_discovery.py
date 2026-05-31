from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    load_official_memory_prior,
    run_official_objectnav_episode_loop,
)
from objectnav_core.evaluation.habitat_official_memory_discovery import (
    run_habitat_official_memory_discovery,
)
from objectnav_core.perception.yolo_world_adapter import Detection


def test_official_memory_discovery_writes_detector_memory_prior(
    tmp_path: Path,
) -> None:
    detector_mask = np.zeros((4, 4), dtype=bool)
    detector_mask[1:3, 1:3] = True
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.82,
                mask=detector_mask,
            )
        ]
    )
    env = _FakeDiscoveryEnv(
        [
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            }
        ],
        object_category="chair",
    )

    summary = run_habitat_official_memory_discovery(
        tmp_path,
        env_factory=lambda _config: env,
        detector_adapter=detector,
        policy="noop",
        max_episodes=1,
        max_steps=1,
    )

    anchors = load_official_memory_prior(tmp_path / "memory_prior.json")
    rows = list(csv.DictReader((tmp_path / "detections.csv").open()))
    saved_summary = json.loads((tmp_path / "summary.json").read_text())

    assert summary == saved_summary
    assert summary["exported_anchor_count"] == 1
    assert summary["detection_count"] == 1
    assert summary["label_filtered_count"] == 0
    assert summary["projection_failed_count"] == 0
    assert len(anchors) == 1
    assert anchors[0].object_category == "chair"
    assert anchors[0].scene_id == "scene-a"
    assert anchors[0].episode_id == "episode-a"
    assert anchors[0].x_m == 0.0
    assert anchors[0].z_m == 2.0
    assert anchors[0].confidence == 0.82
    assert anchors[0].coordinate_frame == "episode_start_relative"
    assert rows[0]["detection_category"] == "chair"
    assert rows[0]["anchor_z_m"] == "2.0"


def test_official_memory_discovery_filters_wrong_category(tmp_path: Path) -> None:
    detector_mask = np.zeros((4, 4), dtype=bool)
    detector_mask[1:3, 1:3] = True
    detector = _StaticDetector(
        [
            Detection(
                category="sofa",
                bbox=(1, 1, 3, 3),
                confidence=0.82,
                mask=detector_mask,
            )
        ]
    )
    env = _FakeDiscoveryEnv(
        [
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            }
        ],
        object_category="chair",
    )

    summary = run_habitat_official_memory_discovery(
        tmp_path,
        env_factory=lambda _config: env,
        detector_adapter=detector,
        policy="noop",
        max_episodes=1,
        max_steps=1,
    )

    anchors = load_official_memory_prior(tmp_path / "memory_prior.json")

    assert summary["exported_anchor_count"] == 0
    assert summary["detection_count"] == 1
    assert summary["label_filtered_count"] == 1
    assert anchors == ()


def test_official_memory_discovery_counts_projection_failures(tmp_path: Path) -> None:
    detector_mask = np.zeros((4, 4), dtype=bool)
    detector_mask[1:3, 1:3] = True
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.82,
                mask=detector_mask,
            )
        ]
    )
    env = _FakeDiscoveryEnv(
        [
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.zeros((4, 4), dtype=np.float32),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            }
        ],
        object_category="chair",
    )

    summary = run_habitat_official_memory_discovery(
        tmp_path,
        env_factory=lambda _config: env,
        detector_adapter=detector,
        policy="noop",
        max_episodes=1,
        max_steps=1,
    )

    anchors = load_official_memory_prior(tmp_path / "memory_prior.json")

    assert summary["exported_anchor_count"] == 0
    assert summary["detection_count"] == 1
    assert summary["label_filtered_count"] == 0
    assert summary["projection_failed_count"] == 1
    assert anchors == ()


def test_official_memory_discovery_robot_viewpoint_anchor_uses_current_pose(
    tmp_path: Path,
) -> None:
    detector_mask = np.zeros((4, 4), dtype=bool)
    detector_mask[1:3, 1:3] = True
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.82,
                mask=detector_mask,
            )
        ]
    )
    env = _FakeDiscoveryEnv(
        [
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.zeros((4, 4), dtype=np.float32),
                "gps": [2.0, -1.0],
                "compass": [0.0],
            }
        ],
        object_category="chair",
    )

    summary = run_habitat_official_memory_discovery(
        tmp_path,
        env_factory=lambda _config: env,
        detector_adapter=detector,
        policy="noop",
        max_episodes=1,
        max_steps=1,
        anchor_mode="robot_viewpoint",
    )

    prior = json.loads((tmp_path / "memory_prior.json").read_text(encoding="utf-8"))
    anchors = load_official_memory_prior(tmp_path / "memory_prior.json")
    rows = list(csv.DictReader((tmp_path / "detections.csv").open()))

    assert summary["exported_anchor_count"] == 1
    assert summary["projection_failed_count"] == 0
    assert summary["config"]["anchor_mode"] == "robot_viewpoint"
    assert prior["metadata"]["anchor_mode"] == "robot_viewpoint"
    assert len(anchors) == 1
    assert anchors[0].episode_id == "episode-a"
    assert anchors[0].x_m == -1.0
    assert anchors[0].z_m == 2.0
    assert rows[0]["anchor_mode"] == "robot_viewpoint"


def test_official_memory_discovery_detector_approach_commits_after_local_action(
    tmp_path: Path,
) -> None:
    detector_mask = np.zeros((4, 4), dtype=bool)
    detector_mask[1:3, 1:3] = True
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.82,
                mask=detector_mask,
            )
        ]
    )
    env = _FakeDiscoveryEnv(
        [
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 1.2, dtype=np.float32),
                "gps": [1.0, 0.0],
                "compass": [0.0],
            },
        ],
        object_category="chair",
    )

    summary = run_habitat_official_memory_discovery(
        tmp_path,
        env_factory=lambda _config: env,
        detector_adapter=detector,
        policy="noop",
        max_episodes=1,
        max_steps=2,
        anchor_mode="robot_viewpoint",
        anchor_commit_policy="detector_approach",
        detector_approach_max_steps=1,
    )

    prior = json.loads((tmp_path / "memory_prior.json").read_text(encoding="utf-8"))
    anchors = load_official_memory_prior(tmp_path / "memory_prior.json")
    rows = list(csv.DictReader((tmp_path / "detections.csv").open()))

    assert env.actions[0] == "move_forward"
    assert summary["exported_anchor_count"] == 1
    assert summary["detector_approach_deferred_count"] == 1
    assert summary["config"]["anchor_commit_policy"] == "detector_approach"
    assert prior["metadata"]["anchor_commit_policy"] == "detector_approach"
    assert len(anchors) == 1
    assert anchors[0].source.endswith("step=1:detection=0")
    assert anchors[0].x_m == 0.0
    assert anchors[0].z_m == 1.0
    assert rows[0]["anchor_commit_policy"] == "detector_approach"
    assert rows[0]["detector_approach_deferred_steps"] == "1"


def test_official_memory_discovery_confirmed_detector_approach_commits_after_range_confirmation(
    tmp_path: Path,
) -> None:
    detector_mask = np.zeros((4, 4), dtype=bool)
    detector_mask[1:3, 1:3] = True
    detector = _SequenceDetector(
        [
            [
                Detection(
                    category="chair",
                    bbox=(2, 1, 4, 3),
                    confidence=0.70,
                    mask=detector_mask,
                )
            ],
            [
                Detection(
                    category="chair",
                    bbox=(1, 1, 3, 3),
                    confidence=0.80,
                    mask=detector_mask,
                )
            ],
            [
                Detection(
                    category="chair",
                    bbox=(1, 1, 3, 3),
                    confidence=0.90,
                    mask=detector_mask,
                )
            ],
            [],
        ]
    )
    confirmed_depth = np.full((4, 4), 2.0, dtype=np.float32)
    confirmed_depth[1:3, 1:3] = 0.8
    env = _FakeDiscoveryEnv(
        [
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [1.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": confirmed_depth,
                "gps": [2.0, 1.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": confirmed_depth,
                "gps": [3.0, 1.0],
                "compass": [0.0],
            },
        ],
        object_category="chair",
    )

    summary = run_habitat_official_memory_discovery(
        tmp_path,
        env_factory=lambda _config: env,
        detector_adapter=detector,
        policy="frontier_only",
        max_episodes=1,
        max_steps=4,
        anchor_mode="robot_viewpoint",
        anchor_commit_policy="confirmed_detector_approach",
        detector_approach_max_steps=5,
    )

    prior = json.loads((tmp_path / "memory_prior.json").read_text(encoding="utf-8"))
    anchors = load_official_memory_prior(tmp_path / "memory_prior.json")
    rows = list(csv.DictReader((tmp_path / "detections.csv").open()))

    assert env.actions[:2] == ["turn_right", "move_forward"]
    assert summary["exported_anchor_count"] == 1
    assert summary["detector_approach_deferred_count"] == 2
    assert summary["detector_approach_confirmed_count"] == 1
    assert summary["detector_approach_unconfirmed_count"] == 0
    assert summary["config"]["anchor_commit_policy"] == "confirmed_detector_approach"
    assert prior["metadata"]["anchor_commit_policy"] == "confirmed_detector_approach"
    assert len(anchors) == 1
    assert anchors[0].source.endswith("step=2:detection=0")
    assert anchors[0].confidence == 0.90
    assert anchors[0].x_m == 1.0
    assert anchors[0].z_m == 2.0
    assert rows[0]["anchor_commit_policy"] == "confirmed_detector_approach"
    assert rows[0]["detector_approach_deferred_steps"] == "2"


def test_official_memory_discovery_confirmed_detector_approach_drops_unconfirmed_glimpse(
    tmp_path: Path,
) -> None:
    detector_mask = np.zeros((4, 4), dtype=bool)
    detector_mask[1:3, 1:3] = True
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.82,
                mask=detector_mask,
            )
        ]
    )
    env = _FakeDiscoveryEnv(
        [
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [1.0, 0.0],
                "compass": [0.0],
            },
        ],
        object_category="chair",
    )

    summary = run_habitat_official_memory_discovery(
        tmp_path,
        env_factory=lambda _config: env,
        detector_adapter=detector,
        policy="frontier_only",
        max_episodes=1,
        max_steps=2,
        anchor_mode="robot_viewpoint",
        anchor_commit_policy="confirmed_detector_approach",
        detector_approach_max_steps=1,
    )

    anchors = load_official_memory_prior(tmp_path / "memory_prior.json")
    rows = list(csv.DictReader((tmp_path / "detections.csv").open()))

    assert env.actions == ["move_forward", "stop"]
    assert summary["exported_anchor_count"] == 0
    assert summary["detector_approach_deferred_count"] == 1
    assert summary["detector_approach_confirmed_count"] == 0
    assert summary["detector_approach_unconfirmed_count"] == 1
    assert anchors == ()
    assert rows == []


def test_official_memory_discovery_anchor_cap_keeps_highest_confidence(
    tmp_path: Path,
) -> None:
    detector_mask = np.zeros((4, 4), dtype=bool)
    detector_mask[1:3, 1:3] = True
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(0, 1, 2, 3),
                confidence=0.2,
                mask=detector_mask,
            ),
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.9,
                mask=detector_mask,
            ),
        ]
    )
    env = _FakeDiscoveryEnv(
        [
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            }
        ],
        object_category="chair",
    )

    summary = run_habitat_official_memory_discovery(
        tmp_path,
        env_factory=lambda _config: env,
        detector_adapter=detector,
        policy="noop",
        max_episodes=1,
        max_steps=1,
        max_anchors_per_episode=1,
    )

    anchors = load_official_memory_prior(tmp_path / "memory_prior.json")
    rows = list(csv.DictReader((tmp_path / "detections.csv").open()))

    assert summary["exported_anchor_count"] == 1
    assert summary["anchor_cap_filtered_count"] == 1
    assert len(anchors) == 1
    assert anchors[0].confidence == 0.9
    assert rows[0]["detection_confidence"] == "0.9"


def test_official_memory_discovery_view_quality_prefers_centered_large_viewpoint(
    tmp_path: Path,
) -> None:
    detector_mask = np.zeros((4, 4), dtype=bool)
    detector_mask[1:3, 1:3] = True
    detector = _SequenceDetector(
        [
            [
                Detection(
                    category="chair",
                    bbox=(0, 1, 1, 3),
                    confidence=0.95,
                    mask=detector_mask,
                )
            ],
            [
                Detection(
                    category="chair",
                    bbox=(1, 1, 3, 3),
                    confidence=0.70,
                    mask=detector_mask,
                )
            ],
        ]
    )
    env = _FakeDiscoveryEnv(
        [
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 1.0, dtype=np.float32),
                "gps": [4.0, 2.0],
                "compass": [0.0],
            },
        ],
        object_category="chair",
    )

    summary = run_habitat_official_memory_discovery(
        tmp_path,
        env_factory=lambda _config: env,
        detector_adapter=detector,
        policy="frontier_only",
        max_episodes=1,
        max_steps=2,
        max_anchors_per_episode=1,
        anchor_mode="robot_viewpoint",
        anchor_selection_policy="view_quality",
    )

    prior = json.loads((tmp_path / "memory_prior.json").read_text(encoding="utf-8"))
    anchors = load_official_memory_prior(tmp_path / "memory_prior.json")
    rows = list(csv.DictReader((tmp_path / "detections.csv").open()))

    assert summary["exported_anchor_count"] == 1
    assert summary["config"]["anchor_selection_policy"] == "view_quality"
    assert prior["metadata"]["anchor_selection_policy"] == "view_quality"
    assert len(anchors) == 1
    assert anchors[0].source.endswith("step=1:detection=0")
    assert anchors[0].confidence == 0.70
    assert anchors[0].x_m == 2.0
    assert anchors[0].z_m == 4.0
    assert rows[0]["anchor_selection_policy"] == "view_quality"
    assert rows[0]["detector_bbox_area_fraction"] == "0.25"
    assert rows[0]["detector_center_offset_fraction"] == "0.0"


def test_official_memory_discovery_confidence_selection_remains_default(
    tmp_path: Path,
) -> None:
    detector_mask = np.zeros((4, 4), dtype=bool)
    detector_mask[1:3, 1:3] = True
    detector = _SequenceDetector(
        [
            [
                Detection(
                    category="chair",
                    bbox=(0, 1, 1, 3),
                    confidence=0.95,
                    mask=detector_mask,
                )
            ],
            [
                Detection(
                    category="chair",
                    bbox=(1, 1, 3, 3),
                    confidence=0.70,
                    mask=detector_mask,
                )
            ],
        ]
    )
    env = _FakeDiscoveryEnv(
        [
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 1.0, dtype=np.float32),
                "gps": [4.0, 2.0],
                "compass": [0.0],
            },
        ],
        object_category="chair",
    )

    summary = run_habitat_official_memory_discovery(
        tmp_path,
        env_factory=lambda _config: env,
        detector_adapter=detector,
        policy="frontier_only",
        max_episodes=1,
        max_steps=2,
        max_anchors_per_episode=1,
        anchor_mode="robot_viewpoint",
    )

    prior = json.loads((tmp_path / "memory_prior.json").read_text(encoding="utf-8"))
    anchors = load_official_memory_prior(tmp_path / "memory_prior.json")

    assert summary["config"]["anchor_selection_policy"] == "confidence"
    assert prior["metadata"]["anchor_selection_policy"] == "confidence"
    assert len(anchors) == 1
    assert anchors[0].source.endswith("step=0:detection=0")
    assert anchors[0].confidence == 0.95


def test_official_memory_discovery_positive_count_threshold_filters_singletons(
    tmp_path: Path,
) -> None:
    detector_mask = np.zeros((4, 4), dtype=bool)
    detector_mask[1:3, 1:3] = True
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.82,
                mask=detector_mask,
            )
        ]
    )
    env = _FakeDiscoveryEnv(
        [
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            }
        ],
        object_category="chair",
    )

    summary = run_habitat_official_memory_discovery(
        tmp_path,
        env_factory=lambda _config: env,
        detector_adapter=detector,
        policy="noop",
        max_episodes=1,
        max_steps=1,
        positive_count_threshold=2,
    )

    prior = json.loads((tmp_path / "memory_prior.json").read_text(encoding="utf-8"))
    anchors = load_official_memory_prior(tmp_path / "memory_prior.json")

    assert summary["exported_anchor_count"] == 0
    assert summary["positive_count_threshold_filtered_count"] == 1
    assert summary["config"]["positive_count_threshold"] == 2
    assert prior["metadata"]["memory_source_policy"] == "naive_count_positive_only"
    assert prior["metadata"]["positive_count_threshold"] == 2
    assert anchors == ()


def test_official_memory_discovery_positive_count_threshold_keeps_repeated_positive(
    tmp_path: Path,
) -> None:
    detector_mask = np.zeros((4, 4), dtype=bool)
    detector_mask[1:3, 1:3] = True
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(0, 1, 2, 3),
                confidence=0.4,
                mask=detector_mask,
            ),
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.9,
                mask=detector_mask,
            ),
        ]
    )
    env = _FakeDiscoveryEnv(
        [
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            }
        ],
        object_category="chair",
    )

    summary = run_habitat_official_memory_discovery(
        tmp_path,
        env_factory=lambda _config: env,
        detector_adapter=detector,
        policy="noop",
        max_episodes=1,
        max_steps=1,
        positive_count_threshold=2,
    )

    anchors = load_official_memory_prior(tmp_path / "memory_prior.json")

    assert summary["exported_anchor_count"] == 2
    assert summary["positive_count_threshold_filtered_count"] == 0
    assert len(anchors) == 2
    assert anchors[0].source.startswith("injected_detector:episode=episode-a")


def test_official_memory_discovery_prior_feeds_memory_guided_frontier(
    tmp_path: Path,
) -> None:
    detector_mask = np.zeros((4, 4), dtype=bool)
    detector_mask[1:3, 1:3] = True
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.82,
                mask=detector_mask,
            )
        ]
    )
    discovery_env = _FakeDiscoveryEnv(
        [
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            }
        ],
        object_category="chair",
    )

    run_habitat_official_memory_discovery(
        tmp_path,
        env_factory=lambda _config: discovery_env,
        detector_adapter=detector,
        policy="noop",
        max_episodes=1,
        max_steps=1,
    )

    anchors = load_official_memory_prior(tmp_path / "memory_prior.json")
    query_env = _FakeDiscoveryEnv(
        [
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=np.float32),
                "gps": [1.9, 0.0],
                "compass": [0.0],
            },
        ],
        object_category="chair",
    )

    rows = run_official_objectnav_episode_loop(
        query_env,
        policy="memory_guided_frontier",
        max_episodes=1,
        max_steps=3,
        memory_anchors=anchors,
    )

    assert anchors[0].coordinate_frame == "episode_start_relative"
    assert query_env.actions == ["move_forward", "stop"]
    assert rows[0]["policy_debug"]["memory_prior"]["decision"] == "stop_at_memory"
    assert rows[0]["policy_debug"]["memory_prior"]["selected_source"].startswith(
        "injected_detector:episode=episode-a"
    )
    assert "fallback_reason" not in rows[0]["policy_debug"]["memory_prior"]


class _StaticDetector:
    def __init__(self, detections: list[Detection]) -> None:
        self.detections = detections

    def detect(self, rgb: np.ndarray) -> list[Detection]:
        assert rgb.dtype == np.uint8
        return list(self.detections)


class _SequenceDetector:
    def __init__(self, detections_by_call: list[list[Detection]]) -> None:
        self.detections_by_call = detections_by_call
        self.call_index = 0

    def detect(self, rgb: np.ndarray) -> list[Detection]:
        assert rgb.dtype == np.uint8
        index = min(self.call_index, len(self.detections_by_call) - 1)
        self.call_index += 1
        return list(self.detections_by_call[index])


class _FakeDiscoveryEnv:
    def __init__(
        self,
        observations: list[dict[str, object]],
        *,
        object_category: str,
    ) -> None:
        self.observations = observations
        self.episode_over = False
        self.current_episode = SimpleNamespace(
            episode_id="episode-a",
            scene_id="scene-a",
            object_category=object_category,
        )
        self.actions: list[str] = []
        self.step_index = 0

    def reset(self) -> dict[str, object]:
        self.episode_over = False
        self.actions = []
        self.step_index = 0
        return self.observations[0]

    def step(self, action: str) -> dict[str, object]:
        self.actions.append(action)
        if action == "stop":
            self.episode_over = True
        self.step_index += 1
        return self.observations[min(self.step_index, len(self.observations) - 1)]

    def get_metrics(self) -> dict[str, float]:
        return {
            "success": 0.0,
            "spl": 0.0,
            "soft_spl": 0.0,
            "distance_to_goal": 1.0,
        }
