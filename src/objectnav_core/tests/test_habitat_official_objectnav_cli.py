from __future__ import annotations

import json

from objectnav_core.cli.run_habitat_official_objectnav_eval import main


def test_official_objectnav_cli_preflight_writes_protocol_summary(tmp_path) -> None:
    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--config-path",
            "third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml",
            "--dataset-data-path",
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--split",
            "val_mini",
            "--policy",
            "noop",
            "--max-episodes",
            "1",
            "--preflight-only",
        ]
    )

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (tmp_path / "protocol_manifest.json").read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert summary["task"] == "habitat_official_objectnav_preflight"
    assert summary["policy"] == "noop"
    assert manifest["metric_source"] == "habitat.Env.get_metrics"
    assert manifest["split"] == "val_mini"


def test_official_objectnav_cli_preflight_accepts_frontier_only(tmp_path) -> None:
    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--config-path",
            "third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml",
            "--dataset-data-path",
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--split",
            "val_mini",
            "--policy",
            "frontier_only",
            "--max-episodes",
            "3",
            "--preflight-only",
        ]
    )

    manifest = json.loads(
        (tmp_path / "protocol_manifest.json").read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert manifest["policy"] == "frontier_only"
    assert manifest["policy_kind"] == "target_agnostic_depth_frontier_baseline"


def test_official_objectnav_cli_preflight_accepts_occupancy_frontier(tmp_path) -> None:
    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--config-path",
            "third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml",
            "--dataset-data-path",
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--split",
            "val_mini",
            "--policy",
            "occupancy_frontier",
            "--max-episodes",
            "3",
            "--preflight-only",
        ]
    )

    manifest = json.loads(
        (tmp_path / "protocol_manifest.json").read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert manifest["policy"] == "occupancy_frontier"
    assert manifest["policy_kind"] == "target_agnostic_occupancy_frontier_baseline"


def test_official_objectnav_cli_preflight_accepts_memory_guided_frontier(
    tmp_path,
) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")

    exit_code = main(
        [
            "--output",
            str(tmp_path / "out"),
            "--config-path",
            "third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml",
            "--dataset-data-path",
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--split",
            "val_mini",
            "--policy",
            "memory_guided_frontier",
            "--memory-prior-path",
            str(memory_path),
            "--memory-stop-radius-m",
            "0.35",
            "--memory-bearing-tolerance-deg",
            "20",
            "--memory-min-confidence",
            "0.5",
            "--max-episodes",
            "3",
            "--preflight-only",
        ]
    )

    manifest = json.loads(
        (tmp_path / "out" / "protocol_manifest.json").read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert manifest["policy"] == "memory_guided_frontier"
    assert manifest["policy_kind"] == "memory_guided_occupancy_frontier"
    assert manifest["memory_prior"]["path"] == str(memory_path)
    assert manifest["memory_prior"]["min_confidence"] == 0.5


def test_official_objectnav_cli_preflight_accepts_memory_evidence_frontier(
    tmp_path,
) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")

    exit_code = main(
        [
            "--output",
            str(tmp_path / "out"),
            "--config-path",
            "third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml",
            "--dataset-data-path",
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--split",
            "val_mini",
            "--policy",
            "memory_evidence_frontier",
            "--memory-prior-path",
            str(memory_path),
            "--max-episodes",
            "3",
            "--preflight-only",
        ]
    )

    manifest = json.loads(
        (tmp_path / "out" / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (tmp_path / "out" / "summary.json").read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert manifest["policy"] == "memory_evidence_frontier"
    assert manifest["policy_kind"] == "memory_evidence_frontier_active_search"
    assert summary["policy"] == "memory_evidence_frontier"


def test_official_objectnav_cli_preflight_accepts_memory_learned_local_frontier(
    tmp_path,
) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")
    model_path = tmp_path / "local_model.json"
    model_path.write_text(
        json.dumps(
            {
                "task": "habitat_official_local_action_logistic_model",
                "label_name": "next_target_visible",
                "feature_names": ["action_turn_left"],
                "weights": [1.0],
                "bias": 0.0,
                "preprocessing": {
                    "feature_means": {"action_turn_left": 0.0},
                    "feature_scales": {"action_turn_left": 1.0},
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--output",
            str(tmp_path / "out"),
            "--config-path",
            "third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml",
            "--dataset-data-path",
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--split",
            "val_mini",
            "--policy",
            "memory_learned_local_frontier",
            "--memory-prior-path",
            str(memory_path),
            "--local-action-model-path",
            str(model_path),
            "--max-episodes",
            "3",
            "--preflight-only",
        ]
    )

    manifest = json.loads(
        (tmp_path / "out" / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (tmp_path / "out" / "summary.json").read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert manifest["policy"] == "memory_learned_local_frontier"
    assert manifest["policy_kind"] == "memory_learned_local_frontier_active_search"
    assert manifest["local_action_model"]["path"] == str(model_path)
    assert summary["config"]["local_action_model_path"] == str(model_path)


def test_official_objectnav_cli_passes_candidate_viewpoint_ranker_model_path(
    tmp_path,
) -> None:
    captured: dict[str, object] = {}

    def runner(output_dir, **kwargs):
        captured["output_dir"] = output_dir
        captured["runner_kwargs"] = dict(kwargs)
        return {
            "task": "habitat_official_objectnav_eval",
            "policy": kwargs["policy"],
        }

    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")
    model_path = tmp_path / "candidate_ranker.json"
    model_path.write_text(
        json.dumps(
            {
                "task": "habitat_official_candidate_viewpoint_ranker_model",
                "feature_names": ["candidate_rank"],
                "weights": [1.0],
                "bias": 0.0,
                "preprocessing": {
                    "feature_means": {"candidate_rank": 0.0},
                    "feature_scales": {"candidate_rank": 1.0},
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--output",
            str(tmp_path / "out"),
            "--policy",
            "memory_active_perception_frontier",
            "--memory-prior-path",
            str(memory_path),
            "--candidate-viewpoint-ranker-model-path",
            str(model_path),
        ],
        runner=runner,
    )

    runner_kwargs = captured["runner_kwargs"]
    assert exit_code == 0
    assert runner_kwargs["candidate_viewpoint_ranker_model_path"] == str(model_path)


def test_official_objectnav_cli_passes_pathfinder_suffix_goal_radius(
    tmp_path,
) -> None:
    captured: dict[str, object] = {}

    def runner(output_dir, **kwargs):
        captured["output_dir"] = output_dir
        captured["runner_kwargs"] = dict(kwargs)
        return {
            "task": "habitat_official_objectnav_eval",
            "policy": kwargs["policy"],
        }

    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")

    exit_code = main(
        [
            "--output",
            str(tmp_path / "out"),
            "--policy",
            "memory_active_perception_frontier_pathfinder_suffix",
            "--memory-prior-path",
            str(memory_path),
            "--pathfinder-suffix-goal-radius-m",
            "1.0",
        ],
        runner=runner,
    )

    runner_kwargs = captured["runner_kwargs"]
    assert exit_code == 0
    assert runner_kwargs["pathfinder_suffix_goal_radius_m"] == 1.0


def test_official_objectnav_cli_passes_targetnav_ddppo_options(
    tmp_path,
) -> None:
    captured: dict[str, object] = {}

    def runner(output_dir, **kwargs):
        captured["output_dir"] = output_dir
        captured["runner_kwargs"] = dict(kwargs)
        return {
            "task": "habitat_official_objectnav_eval",
            "policy": kwargs["policy"],
        }

    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")
    checkpoint_path = tmp_path / "ckpt.60.pth"
    checkpoint_path.write_bytes(b"placeholder")

    exit_code = main(
        [
            "--output",
            str(tmp_path / "out"),
            "--policy",
            "memory_active_perception_frontier_targetnav_ddppo",
            "--memory-prior-path",
            str(memory_path),
            "--targetnav-ddppo-checkpoint-path",
            str(checkpoint_path),
            "--targetnav-ddppo-device",
            "cuda",
        ],
        runner=runner,
    )

    runner_kwargs = captured["runner_kwargs"]
    assert exit_code == 0
    assert runner_kwargs["targetnav_ddppo_checkpoint_path"] == str(checkpoint_path)
    assert runner_kwargs["targetnav_ddppo_device"] == "cuda"


def test_official_objectnav_cli_passes_targetnav_backend_option(
    tmp_path,
) -> None:
    captured: dict[str, object] = {}

    def runner(output_dir, **kwargs):
        captured["output_dir"] = output_dir
        captured["runner_kwargs"] = dict(kwargs)
        return {
            "task": "habitat_official_objectnav_eval",
            "policy": kwargs["policy"],
        }

    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")

    exit_code = main(
        [
            "--output",
            str(tmp_path / "out"),
            "--policy",
            "memory_active_perception_frontier_targetnav",
            "--memory-prior-path",
            str(memory_path),
            "--targetnav-backend",
            "oracle_follower",
        ],
        runner=runner,
    )

    runner_kwargs = captured["runner_kwargs"]
    assert exit_code == 0
    assert runner_kwargs["targetnav_backend"] == "oracle_follower"


def test_official_objectnav_cli_records_detector_center_direction_sign(
    tmp_path,
) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")

    exit_code = main(
        [
            "--output",
            str(tmp_path / "out"),
            "--config-path",
            "third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml",
            "--dataset-data-path",
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--split",
            "val_mini",
            "--policy",
            "memory_belief_frontier",
            "--memory-prior-path",
            str(memory_path),
            "--detector-center-direction-sign",
            "-1",
            "--max-episodes",
            "3",
            "--preflight-only",
        ]
    )

    manifest = json.loads(
        (tmp_path / "out" / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (tmp_path / "out" / "summary.json").read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert manifest["detector_control"]["center_direction_sign"] == -1
    assert summary["config"]["detector_center_direction_sign"] == -1


def test_official_objectnav_cli_injects_query_detector_adapter(tmp_path) -> None:
    captured: dict[str, object] = {}

    def detector_factory(detector_name: str, **kwargs: object) -> object:
        captured["detector_name"] = detector_name
        captured["detector_kwargs"] = dict(kwargs)
        return {"detector": detector_name}

    def runner(output_dir, **kwargs):
        captured["output_dir"] = output_dir
        captured["runner_kwargs"] = dict(kwargs)
        return {
            "task": "habitat_official_objectnav_eval",
            "policy": kwargs["policy"],
            "detector_trace": {"call_count": 0},
        }

    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")
    model_path = tmp_path / "local_model.json"
    model_path.write_text(
        json.dumps(
            {
                "task": "habitat_official_local_action_logistic_model",
                "feature_names": ["action_move_forward"],
                "weights": [0.0],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--output",
            str(tmp_path / "out"),
            "--policy",
            "memory_learned_local_frontier",
            "--memory-prior-path",
            str(memory_path),
            "--local-action-model-path",
            str(model_path),
            "--detector",
            "yolo_world",
            "--detector-weights",
            "yolov8s-worldv2.pt",
            "--detector-conf",
            "0.31",
            "--target-detector-min-confidence",
            "0.29",
            "--detector-device",
            "cpu",
            "--categories",
            "chair,tv_monitor",
        ],
        detector_factory=detector_factory,
        runner=runner,
    )

    runner_kwargs = captured["runner_kwargs"]
    assert exit_code == 0
    assert captured["detector_name"] == "yolo_world"
    assert captured["detector_kwargs"] == {
        "weights": "yolov8s-worldv2.pt",
        "categories": ["chair", "tv_monitor"],
        "conf": 0.31,
        "device": "cpu",
    }
    assert runner_kwargs["target_detector_adapter"] == {"detector": "yolo_world"}
    assert runner_kwargs["target_detector_min_confidence"] == 0.29


def test_official_objectnav_cli_resolves_grounding_dino_default_weights(
    tmp_path,
) -> None:
    captured: dict[str, object] = {}

    def detector_factory(detector_name: str, **kwargs: object) -> object:
        captured["detector_name"] = detector_name
        captured["detector_kwargs"] = dict(kwargs)
        return {"detector": detector_name}

    def runner(output_dir, **kwargs):
        captured["output_dir"] = output_dir
        captured["runner_kwargs"] = dict(kwargs)
        return {
            "task": "habitat_official_objectnav_eval",
            "policy": kwargs["policy"],
        }

    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")

    exit_code = main(
        [
            "--output",
            str(tmp_path / "out"),
            "--policy",
            "memory_guided_frontier",
            "--memory-prior-path",
            str(memory_path),
            "--detector",
            "grounding_dino",
            "--grounding-dino-max-image-side",
            "384",
            "--categories",
            "chair,plant",
        ],
        detector_factory=detector_factory,
        runner=runner,
    )

    assert exit_code == 0
    assert captured["detector_name"] == "grounding_dino"
    assert captured["detector_kwargs"] == {
        "model_id": "IDEA-Research/grounding-dino-tiny",
        "categories": ["chair", "plant"],
        "conf": 0.25,
        "text_threshold": 0.25,
        "max_image_side": 384,
        "device": "auto",
    }
