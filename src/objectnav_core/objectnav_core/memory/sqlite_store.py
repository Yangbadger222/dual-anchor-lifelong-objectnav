from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Iterable

from objectnav_core.models import (
    AnchorType,
    MemoryObject,
    MemoryState,
    ObjectObservation,
    ObjectRelation,
    Pose2D,
    TrialMetrics,
)


class SQLiteMemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS objects (
              object_id TEXT PRIMARY KEY,
              class_name TEXT NOT NULL,
              state TEXT NOT NULL,
              x REAL NOT NULL,
              y REAL NOT NULL,
              yaw REAL NOT NULL,
              anchor_id TEXT NOT NULL,
              anchor_type TEXT NOT NULL,
              frame_id TEXT NOT NULL,
              confidence REAL NOT NULL,
              detector_name TEXT NOT NULL,
              verification_x REAL,
              verification_y REAL,
              verification_yaw REAL,
              updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS object_observations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              object_id TEXT NOT NULL,
              class_name TEXT NOT NULL,
              x REAL NOT NULL,
              y REAL NOT NULL,
              yaw REAL NOT NULL,
              anchor_id TEXT NOT NULL,
              timestamp REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS object_relations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_object_id TEXT NOT NULL,
              target_object_id TEXT NOT NULL,
              relation_type TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trial_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              trial_id TEXT NOT NULL,
              timestamp REAL NOT NULL,
              event_type TEXT NOT NULL,
              message TEXT NOT NULL,
              payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trial_metrics (
              trial_id TEXT PRIMARY KEY,
              metrics_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_objects_class_state_anchor
            ON objects(class_name, state, anchor_id);

            CREATE INDEX IF NOT EXISTS idx_objects_anchor_xy
            ON objects(anchor_id, x, y);

            CREATE INDEX IF NOT EXISTS idx_observations_object_time
            ON object_observations(object_id, timestamp);

            CREATE INDEX IF NOT EXISTS idx_trial_events_trial_time
            ON trial_events(trial_id, timestamp);
            """
        )
        self.connection.commit()

    def upsert_object_from_observation(
        self,
        observation: ObjectObservation,
        state: MemoryState,
        verification_viewpoint: Pose2D | None = None,
    ) -> None:
        updated_at = time.time()
        self.connection.execute(
            """
            INSERT INTO objects (
              object_id, class_name, state, x, y, yaw, anchor_id, anchor_type,
              frame_id, confidence, detector_name, verification_x,
              verification_y, verification_yaw, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(object_id) DO UPDATE SET
              class_name=excluded.class_name,
              state=excluded.state,
              x=excluded.x,
              y=excluded.y,
              yaw=excluded.yaw,
              anchor_id=excluded.anchor_id,
              anchor_type=excluded.anchor_type,
              frame_id=excluded.frame_id,
              confidence=excluded.confidence,
              detector_name=excluded.detector_name,
              verification_x=excluded.verification_x,
              verification_y=excluded.verification_y,
              verification_yaw=excluded.verification_yaw,
              updated_at=excluded.updated_at
            """,
            (
                observation.object_id,
                observation.class_name,
                state.value,
                observation.pose.x,
                observation.pose.y,
                observation.pose.yaw,
                observation.anchor_id,
                observation.anchor_type.value,
                observation.frame_id,
                observation.confidence,
                observation.detector_name,
                verification_viewpoint.x if verification_viewpoint else None,
                verification_viewpoint.y if verification_viewpoint else None,
                verification_viewpoint.yaw if verification_viewpoint else None,
                updated_at,
            ),
        )
        self.connection.execute(
            """
            INSERT INTO object_observations (
              object_id, class_name, x, y, yaw, anchor_id, timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation.object_id,
                observation.class_name,
                observation.pose.x,
                observation.pose.y,
                observation.pose.yaw,
                observation.anchor_id,
                updated_at,
            ),
        )
        self.connection.commit()

    def query_objects(
        self,
        class_name: str,
        states: Iterable[MemoryState],
        anchor_id: str,
    ) -> list[MemoryObject]:
        state_values = [state.value for state in states]
        if not state_values:
            return []
        placeholders = ",".join("?" for _ in state_values)
        rows = self.connection.execute(
            f"""
            SELECT * FROM objects
            WHERE class_name = ?
              AND anchor_id = ?
              AND state IN ({placeholders})
            ORDER BY updated_at DESC
            """,
            (class_name, anchor_id, *state_values),
        ).fetchall()
        return [self._row_to_object(row) for row in rows]

    def get_object(self, object_id: str) -> MemoryObject:
        row = self.connection.execute(
            "SELECT * FROM objects WHERE object_id = ?",
            (object_id,),
        ).fetchone()
        if row is None:
            raise KeyError(object_id)
        return self._row_to_object(row)

    def update_object_state(self, object_id: str, state: MemoryState) -> None:
        self.connection.execute(
            "UPDATE objects SET state = ?, updated_at = ? WHERE object_id = ?",
            (state.value, time.time(), object_id),
        )
        self.connection.commit()

    def add_relation(
        self,
        source_object_id: str,
        target_object_id: str,
        relation_type: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO object_relations (
              source_object_id, target_object_id, relation_type
            )
            VALUES (?, ?, ?)
            """,
            (source_object_id, target_object_id, relation_type),
        )
        self.connection.commit()

    def list_relations(self) -> list[ObjectRelation]:
        rows = self.connection.execute(
            """
            SELECT source_object_id, target_object_id, relation_type
            FROM object_relations
            ORDER BY id
            """
        ).fetchall()
        return [ObjectRelation(**dict(row)) for row in rows]

    def record_trial_event(
        self,
        trial_id: str,
        event_type: str,
        message: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO trial_events (
              trial_id, timestamp, event_type, message, payload_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (trial_id, time.time(), event_type, message, json.dumps(payload or {}, sort_keys=True)),
        )
        self.connection.commit()

    def record_trial_metrics(self, trial_id: str, metrics: TrialMetrics) -> None:
        self.connection.execute(
            """
            INSERT INTO trial_metrics (trial_id, metrics_json)
            VALUES (?, ?)
            ON CONFLICT(trial_id) DO UPDATE SET
              metrics_json=excluded.metrics_json
            """,
            (trial_id, metrics.model_dump_json()),
        )
        self.connection.commit()

    def get_trial_metrics(self, trial_id: str) -> TrialMetrics:
        row = self.connection.execute(
            "SELECT metrics_json FROM trial_metrics WHERE trial_id = ?",
            (trial_id,),
        ).fetchone()
        if row is None:
            raise KeyError(trial_id)
        return TrialMetrics.model_validate_json(row["metrics_json"])

    def list_trial_metrics(self) -> list[tuple[str, TrialMetrics]]:
        rows = self.connection.execute(
            """
            SELECT trial_id, metrics_json
            FROM trial_metrics
            ORDER BY trial_id
            """
        ).fetchall()
        return [
            (row["trial_id"], TrialMetrics.model_validate_json(row["metrics_json"]))
            for row in rows
        ]

    def export_json(self) -> str:
        objects = [
            self._row_to_object(row).model_dump(mode="json")
            for row in self.connection.execute("SELECT * FROM objects ORDER BY object_id")
        ]
        relations = [relation.model_dump(mode="json") for relation in self.list_relations()]
        return json.dumps({"objects": objects, "relations": relations}, sort_keys=True)

    def _row_to_object(self, row: sqlite3.Row) -> MemoryObject:
        verification_viewpoint = None
        if row["verification_x"] is not None:
            verification_viewpoint = Pose2D(
                x=row["verification_x"],
                y=row["verification_y"],
                yaw=row["verification_yaw"],
            )
        return MemoryObject(
            object_id=row["object_id"],
            class_name=row["class_name"],
            state=MemoryState(row["state"]),
            pose=Pose2D(x=row["x"], y=row["y"], yaw=row["yaw"]),
            anchor_id=row["anchor_id"],
            anchor_type=AnchorType(row["anchor_type"]),
            frame_id=row["frame_id"],
            confidence=row["confidence"],
            detector_name=row["detector_name"],
            verification_viewpoint=verification_viewpoint,
        )
