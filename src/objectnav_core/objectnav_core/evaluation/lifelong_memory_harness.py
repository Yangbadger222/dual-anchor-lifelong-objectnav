from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from objectnav_core.memory.usability import MemoryBelief


class LifelongMemoryHarness:
    """Persist compact usability beliefs across Habitat episodes.

    The full object memory store tracks object poses and trial events. The
    RGB-noise validation harness also needs a small, explicit belief table so
    the memory-on/off ablation can prove whether state survives reset.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS usability_beliefs (
              scene_id TEXT NOT NULL,
              episode_dataset_version TEXT NOT NULL,
              category TEXT NOT NULL,
              p_existence REAL NOT NULL,
              p_location_valid REAL NOT NULL,
              p_usable REAL NOT NULL,
              updated_at REAL NOT NULL,
              PRIMARY KEY (scene_id, episode_dataset_version, category)
            )
            """
        )
        self.connection.commit()

    def load_belief(
        self,
        *,
        scene_id: str,
        episode_dataset_version: str,
        category: str,
        default: MemoryBelief,
    ) -> MemoryBelief:
        row = self.connection.execute(
            """
            SELECT p_existence, p_location_valid, p_usable
            FROM usability_beliefs
            WHERE scene_id = ?
              AND episode_dataset_version = ?
              AND category = ?
            """,
            (scene_id, episode_dataset_version, category),
        ).fetchone()
        if row is None:
            return default
        return MemoryBelief(
            p_existence=float(row["p_existence"]),
            p_location_valid=float(row["p_location_valid"]),
            p_usable=float(row["p_usable"]),
        )

    def save_belief(
        self,
        *,
        scene_id: str,
        episode_dataset_version: str,
        category: str,
        belief: MemoryBelief,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO usability_beliefs (
              scene_id, episode_dataset_version, category, p_existence,
              p_location_valid, p_usable, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(scene_id, episode_dataset_version, category)
            DO UPDATE SET
              p_existence = excluded.p_existence,
              p_location_valid = excluded.p_location_valid,
              p_usable = excluded.p_usable,
              updated_at = excluded.updated_at
            """,
            (
                scene_id,
                episode_dataset_version,
                category,
                belief.p_existence,
                belief.p_location_valid,
                belief.p_usable,
                time.time(),
            ),
        )
        self.connection.commit()
