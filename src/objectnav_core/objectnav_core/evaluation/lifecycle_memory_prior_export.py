from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    load_official_memory_prior,
)


@dataclass(frozen=True)
class LifecycleMemoryPriorExportConfig:
    memory_db_path: str | Path
    output_path: str | Path
    source_tag: str = "lifecycle_memory"
    min_confidence: float = 0.0
    coordinate_frame: str = "habitat_world"
    dataset_version: str | None = None
    scene_id: str | None = None
    categories: tuple[str, ...] = ()


def export_lifecycle_memory_prior(
    config: LifecycleMemoryPriorExportConfig,
) -> dict[str, Any]:
    db_path = Path(config.memory_db_path)
    output_path = Path(config.output_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Lifecycle memory DB not found: {db_path}")
    if config.min_confidence < 0.0:
        raise ValueError("min_confidence must be non-negative")

    rows = _read_lifecycle_anchor_rows(config)
    anchors: list[dict[str, Any]] = []
    filtered_count = 0
    for row in rows:
        confidence = _row_confidence(row)
        if confidence < config.min_confidence:
            filtered_count += 1
            continue
        anchors.append(
            {
                "object_category": str(row["category"]),
                "scene_id": str(row["scene_id"]),
                "x_m": float(row["anchor_x"]),
                "z_m": float(row["anchor_z"]),
                "confidence": round(confidence, 6),
                "source": f"{config.source_tag}:{row['instance_id']}",
                "coordinate_frame": config.coordinate_frame,
            }
        )

    payload = {
        "anchors": anchors,
        "metadata": {
            "source": "lifecycle_memory_prior_export",
            "memory_db_path": str(db_path),
            "source_tag": config.source_tag,
            "min_confidence": config.min_confidence,
            "coordinate_frame": config.coordinate_frame,
            "dataset_version": config.dataset_version,
            "scene_id": config.scene_id,
            "categories": list(config.categories),
            "input_anchor_count": len(rows),
            "filtered_anchor_count": filtered_count,
            "exported_anchor_count": len(anchors),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    load_official_memory_prior(output_path)
    return dict(payload["metadata"])


def _read_lifecycle_anchor_rows(
    config: LifecycleMemoryPriorExportConfig,
) -> list[sqlite3.Row]:
    db_path = Path(config.memory_db_path)
    uri = f"file:{db_path}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        _require_tables(connection, ("object_instance_anchors", "usability_beliefs"))
        where: list[str] = []
        params: list[Any] = []
        if config.dataset_version:
            where.append("a.episode_dataset_version = ?")
            params.append(config.dataset_version)
        if config.scene_id:
            where.append("a.scene_id = ?")
            params.append(config.scene_id)
        if config.categories:
            placeholders = ",".join("?" for _ in config.categories)
            where.append(f"a.category IN ({placeholders})")
            params.extend(config.categories)
        where_sql = "WHERE " + " AND ".join(where) if where else ""
        return list(
            connection.execute(
                f"""
                SELECT
                  a.scene_id,
                  a.episode_dataset_version,
                  a.category,
                  a.instance_id,
                  a.anchor_x,
                  a.anchor_z,
                  b.p_existence,
                  b.p_location_valid,
                  b.p_usable
                FROM object_instance_anchors a
                LEFT JOIN usability_beliefs b
                  ON b.scene_id = a.scene_id
                 AND b.episode_dataset_version = a.episode_dataset_version
                 AND b.category = a.category
                 AND b.instance_id = a.instance_id
                {where_sql}
                ORDER BY
                  a.scene_id,
                  a.category,
                  a.instance_id
                """,
                params,
            )
        )


def _require_tables(
    connection: sqlite3.Connection,
    table_names: Sequence[str],
) -> None:
    existing = {
        str(row["name"])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    missing = [table for table in table_names if table not in existing]
    if missing:
        raise ValueError(
            "Lifecycle memory DB missing expected table(s): " + ", ".join(missing)
        )


def _row_confidence(row: sqlite3.Row) -> float:
    if (
        row["p_existence"] is None
        or row["p_location_valid"] is None
        or row["p_usable"] is None
    ):
        return 1.0
    return (
        float(row["p_existence"])
        * float(row["p_location_valid"])
        * float(row["p_usable"])
    )
