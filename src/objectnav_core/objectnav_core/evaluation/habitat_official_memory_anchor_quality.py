from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    OfficialMemoryAnchor,
    load_official_memory_prior,
    write_json,
)


ANCHOR_QUALITY_TASK = "habitat_official_memory_anchor_quality"

_CSV_FIELDS: tuple[str, ...] = (
    "episode_id",
    "scene_id",
    "object_category",
    "reference_source",
    "reference_x_m",
    "reference_y_m",
    "reference_z_m",
    "candidate_count",
    "episode_exact_candidate_count",
    "episode_wildcard_candidate_count",
    "selected_source",
    "selected_confidence",
    "selected_x_m",
    "selected_y_m",
    "selected_z_m",
    "selected_error_m",
    "selected_y_error_m",
    "selected_is_good",
    "nearest_source",
    "nearest_confidence",
    "nearest_x_m",
    "nearest_y_m",
    "nearest_z_m",
    "nearest_error_m",
    "nearest_y_error_m",
    "nearest_confidence_rank",
    "nearest_is_good",
    "selected_to_nearest_error_gap_m",
)


def report_habitat_official_memory_anchor_quality(
    output_dir: str | Path,
    *,
    candidate_prior_path: str | Path,
    reference_prior_path: str | Path,
    max_good_error_m: float = 1.0,
) -> dict[str, Any]:
    if max_good_error_m < 0.0:
        raise ValueError("max_good_error_m must be non-negative")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    candidate_prior = Path(candidate_prior_path)
    reference_prior = Path(reference_prior_path)
    candidate_anchors = list(load_official_memory_prior(candidate_prior))
    reference_anchors = list(load_official_memory_prior(reference_prior))

    reference_groups = _group_by_episode_and_category(reference_anchors)
    rows = [
        _quality_row(
            reference_anchor=references[0],
            duplicate_reference_count=max(0, len(references) - 1),
            candidates=_matching_candidates(candidate_anchors, references[0]),
            max_good_error_m=max_good_error_m,
        )
        for _key, references in sorted(reference_groups.items(), key=_sort_group_item)
    ]
    selected_errors = _finite_row_values(rows, "selected_error_m")
    nearest_errors = _finite_row_values(rows, "nearest_error_m")
    report = {
        "task": ANCHOR_QUALITY_TASK,
        "candidate_prior_path": str(candidate_prior),
        "reference_prior_path": str(reference_prior),
        "max_good_error_m": max_good_error_m,
        "reference_anchor_count": len(reference_anchors),
        "reference_key_count": len(reference_groups),
        "duplicate_reference_key_count": sum(
            max(0, len(references) - 1) for references in reference_groups.values()
        ),
        "candidate_anchor_count": len(candidate_anchors),
        "candidate_covered_reference_count": sum(
            1 for row in rows if int(row["candidate_count"]) > 0
        ),
        "missing_candidate_count": sum(
            1 for row in rows if int(row["candidate_count"]) == 0
        ),
        "reference_rows_with_episode_exact_candidate_count": sum(
            1 for row in rows if int(row["episode_exact_candidate_count"]) > 0
        ),
        "reference_rows_with_episode_wildcard_candidate_count": sum(
            1 for row in rows if int(row["episode_wildcard_candidate_count"]) > 0
        ),
        "total_episode_exact_candidate_matches": sum(
            int(row["episode_exact_candidate_count"]) for row in rows
        ),
        "total_episode_wildcard_candidate_matches": sum(
            int(row["episode_wildcard_candidate_count"]) for row in rows
        ),
        "selected_good_count": sum(1 for row in rows if row["selected_is_good"]),
        "nearest_good_count": sum(1 for row in rows if row["nearest_is_good"]),
        "selected_mean_error_m": _round_metric(mean(selected_errors))
        if selected_errors
        else None,
        "nearest_mean_error_m": _round_metric(mean(nearest_errors))
        if nearest_errors
        else None,
        "rows": rows,
        "artifact_files": {
            "json": "anchor_quality.json",
            "csv": "anchor_quality.csv",
            "markdown": "anchor_quality.md",
        },
        "notes": [
            "This is an offline prior-quality diagnostic, not a benchmark metric.",
            "selected_* follows confidence ranking; nearest_* reports best spatial candidate.",
        ],
    }
    write_json(output_path / "anchor_quality.json", report)
    _write_csv(output_path / "anchor_quality.csv", rows)
    _write_markdown(output_path / "anchor_quality.md", report)
    return {
        key: value
        for key, value in report.items()
        if key not in {"rows"}
    }


def _quality_row(
    *,
    reference_anchor: OfficialMemoryAnchor,
    duplicate_reference_count: int,
    candidates: Sequence[OfficialMemoryAnchor],
    max_good_error_m: float,
) -> dict[str, Any]:
    sorted_candidates = sorted(
        candidates,
        key=lambda anchor: (
            _episode_exact_match(anchor.episode_id, reference_anchor.episode_id),
            anchor.confidence,
            anchor.source,
        ),
        reverse=True,
    )
    selected = sorted_candidates[0] if sorted_candidates else None
    nearest = _nearest_anchor(reference_anchor, sorted_candidates)
    selected_error = _anchor_xz_error_m(reference_anchor, selected)
    nearest_error = _anchor_xz_error_m(reference_anchor, nearest)
    nearest_rank = (
        sorted_candidates.index(nearest) + 1
        if nearest is not None and nearest in sorted_candidates
        else None
    )
    return {
        "episode_id": reference_anchor.episode_id,
        "scene_id": reference_anchor.scene_id,
        "object_category": reference_anchor.object_category,
        "reference_source": reference_anchor.source,
        "reference_x_m": reference_anchor.x_m,
        "reference_y_m": reference_anchor.y_m,
        "reference_z_m": reference_anchor.z_m,
        "duplicate_reference_count": duplicate_reference_count,
        "candidate_count": len(sorted_candidates),
        "episode_exact_candidate_count": sum(
            1
            for candidate in sorted_candidates
            if _episode_exact_match(candidate.episode_id, reference_anchor.episode_id)
        ),
        "episode_wildcard_candidate_count": sum(
            1
            for candidate in sorted_candidates
            if candidate.episode_id is None or not candidate.episode_id
        ),
        "selected_source": selected.source if selected is not None else None,
        "selected_confidence": selected.confidence if selected is not None else None,
        "selected_x_m": selected.x_m if selected is not None else None,
        "selected_y_m": selected.y_m if selected is not None else None,
        "selected_z_m": selected.z_m if selected is not None else None,
        "selected_error_m": selected_error,
        "selected_y_error_m": _anchor_y_error_m(reference_anchor, selected),
        "selected_is_good": (
            selected_error is not None and selected_error <= max_good_error_m
        ),
        "nearest_source": nearest.source if nearest is not None else None,
        "nearest_confidence": nearest.confidence if nearest is not None else None,
        "nearest_x_m": nearest.x_m if nearest is not None else None,
        "nearest_y_m": nearest.y_m if nearest is not None else None,
        "nearest_z_m": nearest.z_m if nearest is not None else None,
        "nearest_error_m": nearest_error,
        "nearest_y_error_m": _anchor_y_error_m(reference_anchor, nearest),
        "nearest_confidence_rank": nearest_rank,
        "nearest_is_good": nearest_error is not None
        and nearest_error <= max_good_error_m,
        "selected_to_nearest_error_gap_m": (
            _round_metric(selected_error - nearest_error)
            if selected_error is not None and nearest_error is not None
            else None
        ),
    }


def _matching_candidates(
    anchors: Sequence[OfficialMemoryAnchor],
    reference_anchor: OfficialMemoryAnchor,
) -> list[OfficialMemoryAnchor]:
    return [
        anchor
        for anchor in anchors
        if anchor.object_category == reference_anchor.object_category
        and _scene_matches(anchor.scene_id, reference_anchor.scene_id)
        and _episode_matches(anchor.episode_id, reference_anchor.episode_id)
    ]


def _group_by_episode_and_category(
    anchors: Iterable[OfficialMemoryAnchor],
) -> dict[tuple[str | None, str], list[OfficialMemoryAnchor]]:
    groups: dict[tuple[str | None, str], list[OfficialMemoryAnchor]] = {}
    for anchor in anchors:
        groups.setdefault((anchor.episode_id, anchor.object_category), []).append(
            anchor
        )
    return groups


def _scene_matches(anchor_scene_id: str | None, scene_id: str | None) -> bool:
    if anchor_scene_id is None or not anchor_scene_id:
        return True
    if scene_id is None or not scene_id:
        return False
    return (
        scene_id == anchor_scene_id
        or scene_id.endswith(anchor_scene_id)
        or anchor_scene_id in scene_id
    )


def _episode_matches(
    anchor_episode_id: str | None,
    episode_id: str | None,
) -> bool:
    if anchor_episode_id is None or not anchor_episode_id:
        return True
    if episode_id is None or not episode_id:
        return False
    return str(anchor_episode_id) == str(episode_id)


def _episode_exact_match(
    anchor_episode_id: str | None,
    episode_id: str | None,
) -> bool:
    return bool(
        anchor_episode_id
        and episode_id
        and str(anchor_episode_id) == str(episode_id)
    )


def _nearest_anchor(
    reference_anchor: OfficialMemoryAnchor,
    candidates: Sequence[OfficialMemoryAnchor],
) -> OfficialMemoryAnchor | None:
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda anchor: (
            _anchor_xz_error_m(reference_anchor, anchor),
            -float(anchor.confidence),
            anchor.source,
        ),
    )


def _anchor_xz_error_m(
    reference_anchor: OfficialMemoryAnchor,
    candidate_anchor: OfficialMemoryAnchor | None,
) -> float | None:
    if candidate_anchor is None:
        return None
    return _round_metric(
        float(
            np.hypot(
                float(candidate_anchor.x_m) - float(reference_anchor.x_m),
                float(candidate_anchor.z_m) - float(reference_anchor.z_m),
            )
        )
    )


def _anchor_y_error_m(
    reference_anchor: OfficialMemoryAnchor,
    candidate_anchor: OfficialMemoryAnchor | None,
) -> float | None:
    if candidate_anchor is None:
        return None
    if reference_anchor.y_m is None or candidate_anchor.y_m is None:
        return None
    return _round_metric(abs(float(candidate_anchor.y_m) - float(reference_anchor.y_m)))


def _finite_row_values(rows: Sequence[Mapping[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, (float, int)) and np.isfinite(float(value)):
            values.append(float(value))
    return values


def _sort_group_item(
    item: tuple[tuple[str | None, str], Sequence[OfficialMemoryAnchor]],
) -> tuple[str, str]:
    (episode_id, object_category), _anchors = item
    return str(episode_id or ""), object_category


def _round_metric(value: float) -> float:
    return round(float(value), 6)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in _CSV_FIELDS})


def _write_markdown(path: Path, report: Mapping[str, Any]) -> None:
    rows = report.get("rows", [])
    if not isinstance(rows, list):
        rows = []
    lines = [
        "# Official Memory Anchor Quality",
        "",
        f"- Candidate prior: `{report['candidate_prior_path']}`",
        f"- Reference prior: `{report['reference_prior_path']}`",
        f"- Candidate coverage: {report['candidate_covered_reference_count']}/"
        f"{report['reference_key_count']}",
        f"- Selected good anchors: {report['selected_good_count']}/"
        f"{report['reference_key_count']}",
        f"- Nearest good anchors: {report['nearest_good_count']}/"
        f"{report['reference_key_count']}",
        f"- Selected mean error: `{report['selected_mean_error_m']}` m",
        f"- Nearest mean error: `{report['nearest_mean_error_m']}` m",
        "",
        "| Episode | Category | Candidates | Selected Error (m) | Nearest Error (m) | Nearest Rank |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {episode} | {category} | {count} | {selected} | {nearest} | {rank} |".format(
                episode=row.get("episode_id") or "",
                category=row.get("object_category") or "",
                count=row.get("candidate_count"),
                selected=_markdown_value(row.get("selected_error_m")),
                nearest=_markdown_value(row.get("nearest_error_m")),
                rank=_markdown_value(row.get("nearest_confidence_rank")),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _markdown_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
