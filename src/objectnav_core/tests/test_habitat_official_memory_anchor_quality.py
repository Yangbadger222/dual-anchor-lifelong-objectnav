from __future__ import annotations

import importlib
import json
from pathlib import Path

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    OfficialMemoryAnchor,
)
from objectnav_core.evaluation.official_episode_memory import (
    make_official_memory_prior_payload,
)


def test_memory_anchor_quality_reports_selected_vs_nearest_anchor(
    tmp_path: Path,
) -> None:
    module = _quality_module()
    reference_path = tmp_path / "reference_prior.json"
    candidate_path = tmp_path / "candidate_prior.json"
    output_dir = tmp_path / "quality"
    _write_prior(
        reference_path,
        [
            OfficialMemoryAnchor(
                object_category="chair",
                x_m=0.0,
                y_m=0.25,
                z_m=0.0,
                episode_id="episode-1",
                scene_id="scene-a",
                source="oracle:episode-1",
            ),
            OfficialMemoryAnchor(
                object_category="bed",
                x_m=10.0,
                y_m=0.0,
                z_m=10.0,
                episode_id="episode-2",
                scene_id="scene-a",
                source="oracle:episode-2",
            ),
        ],
    )
    _write_prior(
        candidate_path,
        [
            OfficialMemoryAnchor(
                object_category="chair",
                x_m=3.0,
                z_m=4.0,
                episode_id="episode-1",
                scene_id="scene-a",
                confidence=0.9,
                source="candidate:bad-high-confidence",
            ),
            OfficialMemoryAnchor(
                object_category="chair",
                x_m=0.3,
                z_m=0.4,
                episode_id="episode-1",
                scene_id="scene-a",
                confidence=0.4,
                source="candidate:good-low-confidence",
            ),
            OfficialMemoryAnchor(
                object_category="chair",
                x_m=10.0,
                z_m=10.0,
                episode_id="other-episode",
                scene_id="scene-a",
                confidence=1.0,
                source="candidate:wrong-episode",
            ),
        ],
    )

    summary = module.report_habitat_official_memory_anchor_quality(
        output_dir,
        candidate_prior_path=candidate_path,
        reference_prior_path=reference_path,
        max_good_error_m=1.0,
    )

    report = json.loads((output_dir / "anchor_quality.json").read_text())

    assert summary["task"] == "habitat_official_memory_anchor_quality"
    assert summary["reference_anchor_count"] == 2
    assert summary["candidate_anchor_count"] == 3
    assert summary["candidate_covered_reference_count"] == 1
    assert summary["missing_candidate_count"] == 1
    assert summary["selected_good_count"] == 0
    assert summary["nearest_good_count"] == 1
    assert summary["selected_mean_error_m"] == 5.0
    assert summary["nearest_mean_error_m"] == 0.5
    assert summary["artifact_files"] == {
        "json": "anchor_quality.json",
        "csv": "anchor_quality.csv",
        "markdown": "anchor_quality.md",
    }
    assert len(report["rows"]) == 2
    assert report["rows"][0]["episode_id"] == "episode-1"
    assert report["rows"][0]["object_category"] == "chair"
    assert report["rows"][0]["candidate_count"] == 2
    assert report["rows"][0]["selected_source"] == "candidate:bad-high-confidence"
    assert report["rows"][0]["selected_error_m"] == 5.0
    assert report["rows"][0]["selected_is_good"] is False
    assert report["rows"][0]["nearest_source"] == "candidate:good-low-confidence"
    assert report["rows"][0]["nearest_error_m"] == 0.5
    assert report["rows"][0]["nearest_confidence_rank"] == 2
    assert report["rows"][0]["nearest_is_good"] is True
    assert report["rows"][0]["selected_to_nearest_error_gap_m"] == 4.5
    assert report["rows"][0]["selected_y_error_m"] is None
    assert report["rows"][1]["episode_id"] == "episode-2"
    assert report["rows"][1]["candidate_count"] == 0
    assert report["rows"][1]["selected_error_m"] is None
    assert (output_dir / "anchor_quality.csv").exists()
    assert (output_dir / "anchor_quality.md").read_text().startswith(
        "# Official Memory Anchor Quality"
    )


def test_memory_anchor_quality_cli_forwards_arguments(tmp_path: Path) -> None:
    cli_module = _quality_cli_module()
    calls: list[dict[str, object]] = []

    def reporter(output_dir: str | Path, **kwargs: object) -> dict[str, object]:
        calls.append({"output_dir": str(output_dir), **kwargs})
        return {"task": "habitat_official_memory_anchor_quality"}

    exit_code = cli_module.main(
        [
            "--candidate-prior",
            "candidate.json",
            "--reference-prior",
            "reference.json",
            "--output-dir",
            str(tmp_path / "report"),
            "--max-good-error-m",
            "0.75",
        ],
        reporter=reporter,
    )

    assert exit_code == 0
    assert calls == [
        {
            "output_dir": str(tmp_path / "report"),
            "candidate_prior_path": "candidate.json",
            "reference_prior_path": "reference.json",
            "max_good_error_m": 0.75,
        }
    ]


def test_memory_anchor_quality_counts_episode_wildcard_candidates(
    tmp_path: Path,
) -> None:
    module = _quality_module()
    reference_path = tmp_path / "reference_prior.json"
    candidate_path = tmp_path / "candidate_prior.json"
    output_dir = tmp_path / "quality"
    _write_prior(
        reference_path,
        [
            OfficialMemoryAnchor(
                object_category="toilet",
                x_m=0.0,
                z_m=0.0,
                episode_id="episode-6",
                scene_id="scene-a",
                source="oracle:episode-6",
            )
        ],
    )
    _write_prior(
        candidate_path,
        [
            OfficialMemoryAnchor(
                object_category="toilet",
                x_m=0.6,
                z_m=0.8,
                episode_id=None,
                scene_id="scene-a",
                confidence=0.7,
                source="candidate:generic-same-scene",
            ),
            OfficialMemoryAnchor(
                object_category="toilet",
                x_m=0.0,
                z_m=0.0,
                episode_id=None,
                scene_id="scene-b",
                confidence=1.0,
                source="candidate:generic-wrong-scene",
            ),
        ],
    )

    summary = module.report_habitat_official_memory_anchor_quality(
        output_dir,
        candidate_prior_path=candidate_path,
        reference_prior_path=reference_path,
        max_good_error_m=1.0,
    )
    report = json.loads((output_dir / "anchor_quality.json").read_text())

    assert summary["candidate_covered_reference_count"] == 1
    assert report["rows"][0]["candidate_count"] == 1
    assert report["rows"][0]["episode_exact_candidate_count"] == 0
    assert report["rows"][0]["episode_wildcard_candidate_count"] == 1
    assert report["rows"][0]["selected_source"] == "candidate:generic-same-scene"
    assert report["rows"][0]["selected_error_m"] == 1.0
    assert report["rows"][0]["selected_is_good"] is True


def _quality_module() -> object:
    return importlib.import_module(
        "objectnav_core.evaluation.habitat_official_memory_anchor_quality"
    )


def _quality_cli_module() -> object:
    return importlib.import_module(
        "objectnav_core.cli.report_habitat_official_memory_anchor_quality"
    )


def _write_prior(path: Path, anchors: list[OfficialMemoryAnchor]) -> None:
    path.write_text(
        json.dumps(
            make_official_memory_prior_payload(
                anchors,
                metadata={
                    "source": "test_prior",
                    "coordinate_frame": "episode_start_relative",
                },
            )
        ),
        encoding="utf-8",
    )
