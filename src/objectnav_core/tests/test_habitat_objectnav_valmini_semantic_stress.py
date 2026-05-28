import gzip
import json
import sys
from pathlib import Path

import numpy as np

from objectnav_core.evaluation import habitat_objectnav_valmini_semantic_stress as stress
from objectnav_core.memory.usability import EvidenceType


def test_importing_valmini_stress_module_does_not_import_habitat() -> None:
    assert "habitat" not in sys.modules
    assert "habitat_sim" not in sys.modules


def test_resolve_hm3d_val_scene_to_local_habitat_layout(tmp_path: Path) -> None:
    scene = tmp_path / "habitat" / "00800-TEEsavR23oF" / "TEEsavR23oF.basis.glb"
    scene.parent.mkdir(parents=True)
    scene.write_text("fake glb", encoding="utf-8")

    resolved = stress._resolve_hm3d_scene_path(
        "hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb",
        scene_root=tmp_path,
    )

    assert resolved == scene.resolve()


def test_write_scene_dataset_config_uses_absolute_scene_paths(tmp_path: Path) -> None:
    scene = tmp_path / "habitat" / "00800-TEEsavR23oF" / "TEEsavR23oF.basis.glb"
    scene.parent.mkdir(parents=True)
    scene.write_text("fake glb", encoding="utf-8")
    config_path = tmp_path / "hm3d_valmini_annotated_basis.scene_dataset_config.json"

    stress._write_scene_dataset_config(config_path, [scene])

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["stages"]["paths"][".glb"] == [str(scene.resolve())]
    assert (
        payload["stages"]["default_attributes"]["semantic_asset"]
        == "%%CONFIG_NAME_AS_ASSET_FILENAME%%.semantic.glb"
    )
    assert payload["stages"]["default_attributes"]["has_semantic_textures"] is True


def test_load_valmini_episode_content_maps_goal_viewpoints(tmp_path: Path) -> None:
    scene = tmp_path / "scenes" / "habitat" / "00800-TEEsavR23oF" / "TEEsavR23oF.basis.glb"
    scene.parent.mkdir(parents=True)
    scene.write_text("fake glb", encoding="utf-8")
    content_dir = tmp_path / "dataset" / "content"
    content_dir.mkdir(parents=True)
    content_file = content_dir / "TEEsavR23oF.json.gz"
    payload = {
        "goals_by_category": {
            "TEEsavR23oF.basis.glb_chair": [
                {
                    "view_points": [
                        {
                            "agent_state": {
                                "position": [1, 2, 3],
                                "rotation": [0, 0, 0, 1],
                            },
                            "iou": 1.0,
                        }
                    ]
                }
            ]
        },
        "episodes": [
            {
                "episode_id": "7",
                "scene_id": "hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb",
                "start_position": [4, 5, 6],
                "start_rotation": [0, 1, 0, 0],
                "object_category": "chair",
                "info": {"geodesic_distance": 9.5, "euclidean_distance": 3.25},
            }
        ],
    }
    with gzip.open(content_file, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)

    episodes = stress._load_valmini_episodes(
        tmp_path / "dataset",
        scene_root=tmp_path / "scenes",
    )

    assert len(episodes) == 1
    assert episodes[0].episode_id == "7"
    assert episodes[0].resolved_scene_path == scene.resolve()
    assert episodes[0].goal_viewpoints[0]["iou"] == 1.0
    assert episodes[0].geodesic_distance == 9.5
    assert episodes[0].info == {"geodesic_distance": 9.5, "euclidean_distance": 3.25}


def test_load_valmini_episode_content_prefers_closest_goal_object_viewpoints(
    tmp_path: Path,
) -> None:
    scene = tmp_path / "scenes" / "habitat" / "00800-TEEsavR23oF" / "TEEsavR23oF.basis.glb"
    scene.parent.mkdir(parents=True)
    scene.write_text("fake glb", encoding="utf-8")
    content_dir = tmp_path / "dataset" / "content"
    content_dir.mkdir(parents=True)
    content_file = content_dir / "TEEsavR23oF.json.gz"
    payload = {
        "goals_by_category": {
            "TEEsavR23oF.basis.glb_bed": [
                {
                    "object_id": 16,
                    "view_points": [
                        {
                            "agent_state": {
                                "position": [1, 0, 0],
                                "rotation": [0, 0, 0, 1],
                            },
                            "iou": 1.0,
                        }
                    ],
                },
                {
                    "object_id": 17,
                    "view_points": [
                        {
                            "agent_state": {
                                "position": [2, 0, 0],
                                "rotation": [0, 0, 0, 1],
                            },
                            "iou": 2.0,
                        }
                    ],
                },
            ]
        },
        "episodes": [
            {
                "episode_id": "8",
                "scene_id": "hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb",
                "start_position": [4, 5, 6],
                "start_rotation": [0, 1, 0, 0],
                "object_category": "bed",
                "info": {
                    "geodesic_distance": 9.5,
                    "euclidean_distance": 3.25,
                    "closest_goal_object_id": 17,
                },
            }
        ],
    }
    with gzip.open(content_file, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)

    episodes = stress._load_valmini_episodes(
        tmp_path / "dataset",
        scene_root=tmp_path / "scenes",
    )

    assert len(episodes[0].goal_viewpoints) == 1
    assert episodes[0].goal_viewpoints[0]["iou"] == 2.0


def test_goal_viewpoint_start_falls_back_to_episode_start_when_missing(tmp_path: Path) -> None:
    episode = stress.ObjectNavValMiniEpisode(
        episode_id="1",
        content_file="content.json.gz",
        original_scene_id="hm3d/val/scene/scene.basis.glb",
        resolved_scene_path=tmp_path / "scene.basis.glb",
        object_category="chair",
        start_position=(1.0, 2.0, 3.0),
        start_rotation=(0.0, 0.0, 0.0, 1.0),
        goal_viewpoints=(),
        geodesic_distance=None,
        euclidean_distance=None,
    )

    start = stress._select_episode_start(episode, start_source="goal_viewpoint")

    assert start.source_used == "episode_start"
    assert start.position == (1.0, 2.0, 3.0)


def test_goal_viewpoint_start_uses_first_goal_viewpoint(tmp_path: Path) -> None:
    episode = stress.ObjectNavValMiniEpisode(
        episode_id="1",
        content_file="content.json.gz",
        original_scene_id="hm3d/val/scene/scene.basis.glb",
        resolved_scene_path=tmp_path / "scene.basis.glb",
        object_category="chair",
        start_position=(1.0, 2.0, 3.0),
        start_rotation=(0.0, 0.0, 0.0, 1.0),
        goal_viewpoints=(
            {
                "agent_state": {
                    "position": [4.0, 5.0, 6.0],
                    "rotation": [0.0, 1.0, 0.0, 0.0],
                }
            },
        ),
        geodesic_distance=None,
        euclidean_distance=None,
    )

    start = stress._select_episode_start(episode, start_source="goal_viewpoint")

    assert start.source_used == "goal_viewpoint"
    assert start.position == (4.0, 5.0, 6.0)
    assert start.rotation == (0.0, 1.0, 0.0, 0.0)


def test_semantic_ids_for_target_category_handles_objectnav_aliases() -> None:
    mapping = {
        10: "tv",
        11: "television",
        12: "couch",
        13: "sofa",
        14: "chair",
        15: "monitor stand",
    }

    assert stress._semantic_ids_for_target_category(mapping, "tv_monitor") == (10, 11)
    assert stress._semantic_ids_for_target_category(mapping, "sofa") == (12, 13)
    assert stress._semantic_ids_for_target_category(mapping, "chair") == (14,)


def test_positive_confirmation_suppresses_single_frame_positive() -> None:
    state = stress.PositiveConfirmationState()
    mask = np.ones((4, 4), dtype=bool)

    result = stress._apply_positive_confirmation(
        evidence_type=EvidenceType.POSITIVE,
        evidence_strength=1.2,
        quarantined=False,
        evidence_reason="detector_positive_mask",
        state=state,
        pose=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
        detector_mask=mask,
        config=stress.PositiveConfirmationConfig(
            frames=2,
            min_translation=0.05,
            min_rotation_deg=5.0,
            min_mask_iou=0.05,
        ),
    )

    assert result["evidence_type"] is EvidenceType.UNKNOWN
    assert result["quarantined"] is True
    assert result["evidence_reason"] == "pending_positive_confirmation"
    assert result["pending_count"] == 1
    assert result["confirmed"] is False


def test_positive_confirmation_accepts_repeated_positive_after_view_change() -> None:
    state = stress.PositiveConfirmationState()
    mask = np.zeros((4, 4), dtype=bool)
    mask[1:3, 1:3] = True
    config = stress.PositiveConfirmationConfig(
        frames=2,
        min_translation=0.05,
        min_rotation_deg=5.0,
        min_mask_iou=0.05,
    )

    stress._apply_positive_confirmation(
        evidence_type=EvidenceType.POSITIVE,
        evidence_strength=1.2,
        quarantined=False,
        evidence_reason="detector_positive_mask",
        state=state,
        pose=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
        detector_mask=mask,
        config=config,
    )
    result = stress._apply_positive_confirmation(
        evidence_type=EvidenceType.POSITIVE,
        evidence_strength=1.2,
        quarantined=False,
        evidence_reason="detector_positive_mask",
        state=state,
        pose=((0.1, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
        detector_mask=mask,
        config=config,
    )

    assert result["evidence_type"] is EvidenceType.POSITIVE
    assert result["evidence_reason"] == "confirmed_detector_positive_mask"
    assert result["pending_count"] == 2
    assert result["translation"] == 0.1
    assert result["confirmed"] is True


def test_positive_confirmation_waits_for_view_change() -> None:
    state = stress.PositiveConfirmationState()
    mask = np.ones((4, 4), dtype=bool)
    config = stress.PositiveConfirmationConfig(
        frames=2,
        min_translation=0.05,
        min_rotation_deg=5.0,
        min_mask_iou=0.05,
    )

    stress._apply_positive_confirmation(
        evidence_type=EvidenceType.POSITIVE,
        evidence_strength=1.2,
        quarantined=False,
        evidence_reason="detector_positive_mask",
        state=state,
        pose=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
        detector_mask=mask,
        config=config,
    )
    result = stress._apply_positive_confirmation(
        evidence_type=EvidenceType.POSITIVE,
        evidence_strength=1.2,
        quarantined=False,
        evidence_reason="detector_positive_mask",
        state=state,
        pose=((0.01, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
        detector_mask=mask,
        config=config,
    )

    assert result["evidence_type"] is EvidenceType.UNKNOWN
    assert result["evidence_reason"] == "waiting_for_multiview_positive_confirmation"
    assert result["pending_count"] == 2
    assert result["confirmed"] is False


def test_positive_confirmation_waits_for_mask_consistency() -> None:
    state = stress.PositiveConfirmationState()
    first_mask = np.zeros((6, 6), dtype=bool)
    first_mask[0:2, 0:2] = True
    second_mask = np.zeros((6, 6), dtype=bool)
    second_mask[4:6, 4:6] = True
    config = stress.PositiveConfirmationConfig(
        frames=2,
        min_translation=0.05,
        min_rotation_deg=5.0,
        min_mask_iou=0.05,
    )

    stress._apply_positive_confirmation(
        evidence_type=EvidenceType.POSITIVE,
        evidence_strength=1.2,
        quarantined=False,
        evidence_reason="detector_positive_mask",
        state=state,
        pose=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
        detector_mask=first_mask,
        config=config,
    )
    result = stress._apply_positive_confirmation(
        evidence_type=EvidenceType.POSITIVE,
        evidence_strength=1.2,
        quarantined=False,
        evidence_reason="detector_positive_mask",
        state=state,
        pose=((0.1, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
        detector_mask=second_mask,
        config=config,
    )

    assert result["evidence_type"] is EvidenceType.UNKNOWN
    assert result["evidence_reason"] == "waiting_for_mask_consistency_confirmation"
    assert result["mask_iou"] == 0.0
    assert result["confirmed"] is False
