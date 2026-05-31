from __future__ import annotations

import json
from pathlib import Path

import pytest

from objectnav_core.evaluation.habitat_official_objectnav_eval import METRIC_SOURCE
from objectnav_core.evaluation.habitat_official_memory_comparison import (
    DEFAULT_COMPARISON_SPECS,
    compare_official_memory_summaries,
    run_habitat_official_memory_comparison,
)
from objectnav_core.cli.run_habitat_official_memory_comparison import main


def test_official_memory_comparison_aggregates_only_habitat_metrics(
    tmp_path: Path,
) -> None:
    summaries = {
        "memory_guided": _write_summary(
            tmp_path,
            "memory_guided",
            policy="memory_active_perception_frontier_targetnav",
            success_rate=0.5,
            spl=0.25,
            soft_spl=0.45,
            distance_to_goal=1.25,
            caveat="memory_prior_source_not_benchmark_validated",
        ),
        "no_memory": _write_summary(
            tmp_path,
            "no_memory",
            policy="no_memory_targetnav",
            success_rate=0.25,
            spl=0.1,
            soft_spl=0.2,
            distance_to_goal=2.0,
        ),
        "naive_count": _write_summary(
            tmp_path,
            "naive_count",
            policy="naive_count_targetnav",
            success_rate=0.25,
            spl=0.05,
            soft_spl=0.15,
            distance_to_goal=2.5,
            caveat="naive_count_prior_source_not_validated",
        ),
    }

    report = compare_official_memory_summaries(tmp_path / "comparison", summaries)

    rows = {row["label"]: row for row in report["rows"]}
    assert report["task"] == "habitat_official_memory_baseline_comparison"
    assert report["metric_source"] == METRIC_SOURCE
    assert report["labels"] == ["memory_guided", "no_memory", "naive_count"]
    assert rows["memory_guided"]["success_rate"] == 0.5
    assert rows["no_memory"]["spl"] == 0.1
    assert rows["naive_count"]["distance_to_goal"] == 2.5
    assert report["comparison"]["memory_guided_vs_no_memory_success_rate_delta"] == 0.25
    assert report["comparison"]["memory_guided_vs_naive_count_spl_delta"] == 0.2

    csv_text = (tmp_path / "comparison" / "comparison.csv").read_text(
        encoding="utf-8"
    )
    markdown_text = (tmp_path / "comparison" / "comparison.md").read_text(
        encoding="utf-8"
    )
    assert "label,policy,episodes,success_rate,spl,soft_spl,distance_to_goal" in csv_text
    assert "memory_guided" in csv_text
    assert "| Method | Policy | Episodes | SR | SPL | SoftSPL | DistanceToGoal | Caveat |" in markdown_text
    assert "memory_active_perception_frontier_targetnav" in markdown_text


def test_official_memory_comparison_rejects_non_official_metric_source(
    tmp_path: Path,
) -> None:
    bad_summary = _write_summary(
        tmp_path,
        "memory_guided",
        policy="memory_guided_frontier",
        success_rate=1.0,
        spl=1.0,
        soft_spl=1.0,
        distance_to_goal=0.0,
        measure_source="local_recomputed_metrics",
    )

    with pytest.raises(ValueError, match="Habitat official metrics"):
        compare_official_memory_summaries(
            tmp_path / "comparison",
            {
                "memory_guided": bad_summary,
                "no_memory": _write_summary(tmp_path, "no_memory"),
                "naive_count": _write_summary(tmp_path, "naive_count"),
            },
        )


def test_official_memory_comparison_run_mode_uses_expected_policy_mapping(
    tmp_path: Path,
) -> None:
    memory_prior = tmp_path / "memory_prior.json"
    naive_prior = tmp_path / "naive_prior.json"
    memory_prior.write_text(json.dumps({"anchors": []}), encoding="utf-8")
    naive_prior.write_text(json.dumps({"anchors": []}), encoding="utf-8")
    calls: list[tuple[Path, dict[str, object]]] = []

    def fake_runner(output_dir, **kwargs):
        output_path = Path(output_dir)
        calls.append((output_path, dict(kwargs)))
        return _summary_payload(
            policy=str(kwargs["policy"]),
            success_rate=0.0,
            spl=0.0,
            soft_spl=0.1,
            distance_to_goal=3.0,
        )

    report = run_habitat_official_memory_comparison(
        tmp_path / "comparison",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="hm3d",
        memory_guided_prior_path=memory_prior,
        naive_count_prior_path=naive_prior,
        max_episodes=4,
        max_steps=100,
        targetnav_backend="oracle_follower",
        runner=fake_runner,
    )

    assert report["labels"] == ["memory_guided", "no_memory", "naive_count"]
    assert [call[1]["policy"] for call in calls] == [
        DEFAULT_COMPARISON_SPECS["memory_guided"].policy,
        DEFAULT_COMPARISON_SPECS["no_memory"].policy,
        DEFAULT_COMPARISON_SPECS["naive_count"].policy,
    ]
    assert calls[0][1]["memory_prior_path"] == str(memory_prior)
    assert calls[1][1]["memory_prior_path"] is None
    assert calls[2][1]["memory_prior_path"] == str(naive_prior)
    assert [call[1]["targetnav_backend"] for call in calls] == [
        "oracle_follower",
        "oracle_follower",
        "oracle_follower",
    ]
    assert (tmp_path / "comparison" / "comparison.json").exists()


def test_official_memory_comparison_cli_writes_aggregate_report(
    tmp_path: Path,
) -> None:
    exit_code = main(
        [
            "--output",
            str(tmp_path / "comparison"),
            "--from-summary",
            f"memory_guided={_write_summary(tmp_path, 'memory_guided')}",
            "--from-summary",
            f"no_memory={_write_summary(tmp_path, 'no_memory')}",
            "--from-summary",
            f"naive_count={_write_summary(tmp_path, 'naive_count')}",
        ]
    )

    report = json.loads(
        (tmp_path / "comparison" / "comparison.json").read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert report["labels"] == ["memory_guided", "no_memory", "naive_count"]
    assert (tmp_path / "comparison" / "comparison.csv").exists()
    assert (tmp_path / "comparison" / "comparison.md").exists()


def test_official_memory_comparison_cli_resolves_grounding_dino_default_weights(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    memory_prior = tmp_path / "memory_prior.json"
    naive_prior = tmp_path / "naive_prior.json"
    memory_prior.write_text(json.dumps({"anchors": []}), encoding="utf-8")
    naive_prior.write_text(json.dumps({"anchors": []}), encoding="utf-8")

    def detector_factory(detector_name: str, **kwargs: object) -> object:
        captured["detector_name"] = detector_name
        captured["detector_kwargs"] = dict(kwargs)
        return {"detector": detector_name}

    def fake_runner(output_dir, **kwargs):
        captured["targetnav_backend"] = kwargs["targetnav_backend"]
        return _summary_payload(
            policy=str(kwargs["policy"]),
            success_rate=0.0,
            spl=0.0,
            soft_spl=0.0,
            distance_to_goal=1.0,
        )

    exit_code = main(
        [
            "--output",
            str(tmp_path / "comparison"),
            "--memory-guided-prior-path",
            str(memory_prior),
            "--naive-count-prior-path",
            str(naive_prior),
            "--detector",
            "grounding_dino",
            "--targetnav-backend",
            "oracle_follower",
            "--grounding-dino-max-image-side",
            "384",
            "--max-episodes",
            "1",
            "--max-steps",
            "1",
        ],
        detector_factory=detector_factory,
        runner=fake_runner,
    )

    assert exit_code == 0
    assert captured["targetnav_backend"] == "oracle_follower"
    assert captured["detector_name"] == "grounding_dino"
    assert captured["detector_kwargs"] == {
        "model_id": "IDEA-Research/grounding-dino-tiny",
        "categories": ["bed", "chair", "plant", "sofa", "toilet", "tv_monitor"],
        "conf": 0.25,
        "text_threshold": 0.25,
        "max_image_side": 384,
        "device": "auto",
    }


def _write_summary(
    tmp_path: Path,
    label: str,
    *,
    policy: str = "occupancy_frontier",
    success_rate: float = 0.0,
    spl: float = 0.0,
    soft_spl: float = 0.0,
    distance_to_goal: float = 1.0,
    caveat: str | None = None,
    measure_source: str = METRIC_SOURCE,
) -> Path:
    run_dir = tmp_path / f"{label}_run"
    run_dir.mkdir()
    summary_path = run_dir / "summary.json"
    payload = _summary_payload(
        policy=policy,
        success_rate=success_rate,
        spl=spl,
        soft_spl=soft_spl,
        distance_to_goal=distance_to_goal,
        caveat=caveat,
        measure_source=measure_source,
    )
    summary_path.write_text(json.dumps(payload), encoding="utf-8")
    return summary_path


def _summary_payload(
    *,
    policy: str,
    success_rate: float,
    spl: float,
    soft_spl: float,
    distance_to_goal: float,
    caveat: str | None = None,
    measure_source: str = METRIC_SOURCE,
) -> dict[str, object]:
    return {
        "task": "habitat_official_objectnav_eval",
        "full_habitat_run": True,
        "policy": policy,
        "config": {
            "split": "val_mini",
            "max_episodes": 4,
            "max_steps": 100,
            "seed": 313,
        },
        "protocol_manifest": {
            "policy": policy,
            "policy_kind": f"{policy}_kind",
            "invalid_for_benchmark_claim_reason": caveat,
        },
        "official_metrics": {
            "episodes": 4,
            "measure_source": measure_source,
            "success_rate": success_rate,
            "spl": spl,
            "soft_spl": soft_spl,
            "distance_to_goal": distance_to_goal,
            "required_measures_present": True,
            "required_measures": [
                "success",
                "spl",
                "soft_spl",
                "distance_to_goal",
            ],
        },
    }
