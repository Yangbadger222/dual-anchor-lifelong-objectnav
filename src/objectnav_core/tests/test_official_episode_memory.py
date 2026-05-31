from __future__ import annotations

import numpy as np
import pytest

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    OfficialMemoryAnchor,
    load_official_memory_prior_from_payload,
)
from objectnav_core.evaluation.official_episode_memory import (
    estimate_episode_detection_anchor,
    make_official_memory_prior_payload,
)


def test_episode_detection_anchor_projects_center_bbox_forward() -> None:
    anchor = estimate_episode_detection_anchor(
        {
            "depth": np.full((4, 4), 2.0, dtype=np.float32),
            "gps": [1.0, 0.0],
            "compass": [0.0],
        },
        bbox_xyxy=(1, 1, 3, 3),
        object_category="chair",
        confidence=0.82,
        source="detector:frame-1",
    )

    assert anchor is not None
    assert anchor.object_category == "chair"
    assert anchor.x_m == pytest.approx(0.0)
    assert anchor.z_m == pytest.approx(3.0)
    assert anchor.confidence == 0.82
    assert anchor.source == "detector:frame-1"
    assert anchor.coordinate_frame == "episode_start_relative"


def test_episode_detection_anchor_uses_habitat_compass_sign() -> None:
    anchor = estimate_episode_detection_anchor(
        {
            "depth": np.full((4, 4), 2.0, dtype=np.float32),
            "gps": [0.0, 0.0],
            "compass": [-1.57079632679],
        },
        bbox_xyxy=(1, 1, 3, 3),
        object_category="chair",
    )

    assert anchor is not None
    assert anchor.x_m == pytest.approx(2.0)
    assert anchor.z_m == pytest.approx(0.0, abs=1e-6)


def test_episode_detection_anchor_converts_normalized_depth_to_meters() -> None:
    anchor = estimate_episode_detection_anchor(
        {
            "depth": np.full((4, 4), 1.0 / 3.0, dtype=np.float32),
            "gps": [0.0, 0.0],
            "compass": [0.0],
        },
        bbox_xyxy=(1, 1, 3, 3),
        object_category="chair",
        min_depth_m=0.5,
        max_depth_m=5.0,
    )

    assert anchor is not None
    assert anchor.x_m == pytest.approx(0.0)
    assert anchor.z_m == pytest.approx(2.0)


def test_episode_detection_anchor_returns_none_for_unusable_depth() -> None:
    anchor = estimate_episode_detection_anchor(
        {
            "depth": np.zeros((4, 4), dtype=np.float32),
            "gps": [0.0, 0.0],
            "compass": [0.0],
        },
        bbox_xyxy=(1, 1, 3, 3),
        object_category="chair",
    )

    assert anchor is None


def test_episode_detection_anchor_returns_none_for_empty_bbox() -> None:
    anchor = estimate_episode_detection_anchor(
        {
            "depth": np.full((4, 4), 2.0, dtype=np.float32),
            "gps": [0.0, 0.0],
            "compass": [0.0],
        },
        bbox_xyxy=(2, 2, 2, 3),
        object_category="chair",
    )

    assert anchor is None


def test_official_memory_prior_payload_round_trips_parser() -> None:
    anchor = estimate_episode_detection_anchor(
        {
            "depth": np.full((4, 4), 2.0, dtype=np.float32),
            "gps": [0.0, 0.0],
            "compass": [0.0],
        },
        bbox_xyxy=(1, 1, 3, 3),
        object_category="chair",
        scene_id="scene-a",
        confidence=0.75,
        source="detector:frame-1",
    )
    assert anchor is not None

    payload = make_official_memory_prior_payload(
        [anchor],
        metadata={"source": "unit-test"},
    )
    anchors = load_official_memory_prior_from_payload(payload)

    assert payload["metadata"]["source"] == "unit-test"
    assert len(anchors) == 1
    assert anchors[0].object_category == "chair"
    assert anchors[0].scene_id == "scene-a"
    assert anchors[0].x_m == pytest.approx(0.0)
    assert anchors[0].z_m == pytest.approx(2.0)
    assert anchors[0].coordinate_frame == "episode_start_relative"


def test_official_memory_prior_payload_round_trips_episode_id() -> None:
    payload = make_official_memory_prior_payload(
        [
            OfficialMemoryAnchor(
                object_category="chair",
                x_m=1.25,
                z_m=-0.5,
                scene_id="scene-a",
                episode_id="episode-7",
                confidence=1.0,
                source="oracle:episode-7",
            )
        ]
    )
    anchors = load_official_memory_prior_from_payload(payload)

    assert payload["anchors"][0]["episode_id"] == "episode-7"
    assert len(anchors) == 1
    assert anchors[0].episode_id == "episode-7"


def test_official_memory_prior_payload_round_trips_vertical_offset() -> None:
    payload = make_official_memory_prior_payload(
        [
            OfficialMemoryAnchor(
                object_category="chair",
                x_m=1.25,
                y_m=-2.25,
                z_m=-0.5,
                scene_id="scene-a",
                episode_id="episode-7",
                confidence=1.0,
                source="oracle:episode-7",
            )
        ]
    )
    anchors = load_official_memory_prior_from_payload(payload)

    assert payload["anchors"][0]["y_m"] == -2.25
    assert len(anchors) == 1
    assert anchors[0].y_m == pytest.approx(-2.25)
