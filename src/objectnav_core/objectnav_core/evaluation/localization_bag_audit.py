from __future__ import annotations

import bisect
import csv
import html
import json
import math
import sqlite3
import statistics
import struct
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


EARTH_RADIUS_M = 6378137.0
REQUIRED_TOPIC_NAMES = {
    "/fix",
    "/fastlio2/lio_odom",
    "/gps_corridor/enu_to_map",
    "/gps_corridor/pgo_enu_to_map",
    "/gps_corridor/alignment_debug",
    "/gps_corridor/alignment_status",
}


@dataclass(frozen=True)
class NavSatFixRecord:
    header_stamp_ns: int
    header_frame_id: str
    status: int
    service: int
    latitude: float
    longitude: float
    altitude: float
    position_covariance: tuple[float, ...]
    position_covariance_type: int


@dataclass(frozen=True)
class OdometryRecord:
    header_stamp_ns: int
    header_frame_id: str
    child_frame_id: str
    x: float
    y: float
    z: float
    qx: float
    qy: float
    qz: float
    qw: float
    vx: float
    vy: float
    vz: float
    wx: float
    wy: float
    wz: float

    @property
    def yaw(self) -> float:
        siny_cosp = 2.0 * (self.qw * self.qz + self.qx * self.qy)
        cosy_cosp = 1.0 - 2.0 * (self.qy * self.qy + self.qz * self.qz)
        return math.atan2(siny_cosp, cosy_cosp)


@dataclass(frozen=True)
class FixSample:
    session_id: str
    bag_timestamp_ns: int
    header_stamp_ns: int
    frame_id: str
    status: int
    service: int
    latitude: float
    longitude: float
    altitude: float
    covariance_x: float
    covariance_y: float
    covariance_z: float
    covariance_type: int
    valid: bool
    enu_east_m: float | None
    enu_north_m: float | None


@dataclass(frozen=True)
class LioSample:
    session_id: str
    bag_timestamp_ns: int
    header_stamp_ns: int
    frame_id: str
    child_frame_id: str
    x: float
    y: float
    z: float
    yaw: float
    speed_mps: float | None
    yaw_rate_radps: float | None


class CdrReader:
    def __init__(self, data: bytes) -> None:
        if len(data) < 4:
            raise ValueError("CDR payload is shorter than the 4-byte encapsulation header")
        if data[1] != 1:
            raise ValueError("Only little-endian CDR payloads are supported")
        self._data = data
        self._offset = 4

    def _align(self, size: int) -> None:
        while (self._offset - 4) % size:
            self._offset += 1

    def _read(self, fmt: str, size: int, alignment: int) -> Any:
        self._align(alignment)
        end = self._offset + size
        if end > len(self._data):
            raise ValueError("CDR payload ended while reading a field")
        value = struct.unpack_from(fmt, self._data, self._offset)[0]
        self._offset = end
        return value

    def i8(self) -> int:
        return self._read("<b", 1, 1)

    def u8(self) -> int:
        return self._read("<B", 1, 1)

    def i32(self) -> int:
        return self._read("<i", 4, 4)

    def u16(self) -> int:
        return self._read("<H", 2, 2)

    def u32(self) -> int:
        return self._read("<I", 4, 4)

    def f64(self) -> float:
        return self._read("<d", 8, 8)

    def string(self) -> str:
        length = self.u32()
        end = self._offset + length
        if end > len(self._data):
            raise ValueError("CDR payload ended while reading a string")
        raw = self._data[self._offset:end]
        self._offset = end
        self._align(4)
        if raw.endswith(b"\x00"):
            raw = raw[:-1]
        return raw.decode("utf-8", errors="replace")


def _read_header(reader: CdrReader) -> tuple[int, str]:
    sec = reader.i32()
    nanosec = reader.u32()
    frame_id = reader.string()
    return sec * 1_000_000_000 + nanosec, frame_id


def decode_navsat_fix(data: bytes) -> NavSatFixRecord:
    reader = CdrReader(data)
    stamp_ns, frame_id = _read_header(reader)
    status = reader.i8()
    service = reader.u16()
    latitude = reader.f64()
    longitude = reader.f64()
    altitude = reader.f64()
    covariance = tuple(reader.f64() for _ in range(9))
    covariance_type = reader.u8()
    return NavSatFixRecord(
        header_stamp_ns=stamp_ns,
        header_frame_id=frame_id,
        status=status,
        service=service,
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
        position_covariance=covariance,
        position_covariance_type=covariance_type,
    )


def decode_odometry(data: bytes) -> OdometryRecord:
    reader = CdrReader(data)
    stamp_ns, frame_id = _read_header(reader)
    child_frame_id = reader.string()
    x = reader.f64()
    y = reader.f64()
    z = reader.f64()
    qx = reader.f64()
    qy = reader.f64()
    qz = reader.f64()
    qw = reader.f64()
    for _ in range(36):
        reader.f64()
    vx = reader.f64()
    vy = reader.f64()
    vz = reader.f64()
    wx = reader.f64()
    wy = reader.f64()
    wz = reader.f64()
    for _ in range(36):
        reader.f64()
    return OdometryRecord(
        header_stamp_ns=stamp_ns,
        header_frame_id=frame_id,
        child_frame_id=child_frame_id,
        x=x,
        y=y,
        z=z,
        qx=qx,
        qy=qy,
        qz=qz,
        qw=qw,
        vx=vx,
        vy=vy,
        vz=vz,
        wx=wx,
        wy=wy,
        wz=wz,
    )


def decode_float64_multi_array(data: bytes) -> list[float]:
    reader = CdrReader(data)
    dim_count = reader.u32()
    for _ in range(dim_count):
        reader.string()
        reader.u32()
        reader.u32()
    reader.u32()
    value_count = reader.u32()
    return [reader.f64() for _ in range(value_count)]


def decode_string(data: bytes) -> str:
    return CdrReader(data).string()


def discover_bag_paths(data_root: str | Path, limit: int | None = None) -> list[Path]:
    root = Path(data_root)
    bags = sorted(path.parent for path in root.glob("**/metadata.yaml") if path.parent.name == "bag")
    if limit is not None:
        return bags[:limit]
    return bags


def run_localization_bag_audit(
    output_dir: str | Path,
    bag_paths: Iterable[str | Path] | None = None,
    data_root: str | Path | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    resolved_bags = [Path(path) for path in bag_paths or []]
    if data_root is not None:
        resolved_bags.extend(discover_bag_paths(data_root, limit=limit))
    if limit is not None and bag_paths:
        resolved_bags = resolved_bags[:limit]
    if not resolved_bags:
        raise ValueError("No bag paths were provided or discovered")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    sessions: list[dict[str, Any]] = []
    all_topic_rows: list[dict[str, Any]] = []
    all_fix_samples: list[FixSample] = []
    all_lio_samples: list[LioSample] = []

    for bag_path in resolved_bags:
        session, topic_rows, fix_samples, lio_samples = audit_bag(bag_path)
        sessions.append(session)
        all_topic_rows.extend(topic_rows)
        all_fix_samples.extend(fix_samples)
        all_lio_samples.extend(lio_samples)

    summary = {
        "bag_count": len(sessions),
        "health_counts": dict(Counter(session["anchor_health"] for session in sessions)),
        "sessions": sessions,
    }

    _write_json(output / "summary.json", summary)
    _write_session_metrics(output / "session_metrics.csv", sessions)
    _write_dict_rows(output / "topic_counts.csv", all_topic_rows)
    _write_fix_samples(output / "fix_samples.csv", all_fix_samples)
    _write_lio_samples(output / "lio_samples.csv", all_lio_samples)
    _write_report(output / "audit_report.html", summary)
    return summary


def audit_bag(bag_path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[FixSample], list[LioSample]]:
    bag = Path(bag_path)
    metadata = _read_metadata(bag)
    session_id = _session_id_from_bag_path(bag)
    db_path = _resolve_db_path(bag, metadata)

    topic_rows: list[dict[str, Any]] = []
    fix_records: list[tuple[int, NavSatFixRecord]] = []
    odom_records: list[tuple[int, OdometryRecord]] = []
    status_counts: Counter[str] = Counter()
    array_topic_values: dict[str, list[list[float]]] = defaultdict(list)
    decode_errors: Counter[str] = Counter()

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        topics = _read_topics(conn)
        metadata_counts = _topic_counts_from_metadata(metadata)
        for topic_id, topic in topics.items():
            topic_rows.append(
                {
                    "session_id": session_id,
                    "topic_id": topic_id,
                    "name": topic["name"],
                    "type": topic["type"],
                    "message_count": metadata_counts.get(topic["name"], 0),
                }
            )

        wanted_ids = [topic_id for topic_id, topic in topics.items() if topic["name"] in REQUIRED_TOPIC_NAMES]
        if wanted_ids:
            placeholders = ",".join("?" for _ in wanted_ids)
            cursor = conn.execute(
                f"""
                SELECT messages.timestamp, topics.name, messages.data
                FROM messages
                JOIN topics ON topics.id = messages.topic_id
                WHERE messages.topic_id IN ({placeholders})
                ORDER BY messages.timestamp ASC
                """,
                wanted_ids,
            )
            for timestamp_ns, topic_name, data in cursor:
                try:
                    if topic_name == "/fix":
                        fix_records.append((int(timestamp_ns), decode_navsat_fix(data)))
                    elif topic_name == "/fastlio2/lio_odom":
                        odom_records.append((int(timestamp_ns), decode_odometry(data)))
                    elif topic_name == "/gps_corridor/alignment_status":
                        status_counts[decode_string(data)] += 1
                    elif topic_name in {
                        "/gps_corridor/enu_to_map",
                        "/gps_corridor/pgo_enu_to_map",
                        "/gps_corridor/alignment_debug",
                    }:
                        array_topic_values[topic_name].append(decode_float64_multi_array(data))
                except Exception:
                    decode_errors[topic_name] += 1

    fix_samples = _make_fix_samples(session_id, fix_records)
    lio_samples = _make_lio_samples(session_id, odom_records)
    lio_metrics = _summarize_lio(lio_samples)
    fix_metrics = _summarize_fix(fix_samples)
    alignment = _summarize_gps_lio_alignment(fix_samples, lio_samples)
    array_metrics = {topic: _summarize_array_values(values) for topic, values in array_topic_values.items()}
    anchor_health, warnings = _classify_anchor_health(lio_metrics, fix_metrics, alignment)
    warnings.extend(_decode_warnings(decode_errors))

    session = {
        "session_id": session_id,
        "bag_path": str(bag),
        "db_path": str(db_path),
        "duration_s": _metadata_duration_s(metadata),
        "message_count": _metadata_message_count(metadata),
        "topic_count": len(topic_rows),
        "anchor_health": anchor_health,
        "warnings": warnings,
        "required_topic_presence": {name: any(row["name"] == name for row in topic_rows) for name in sorted(REQUIRED_TOPIC_NAMES)},
        "lio": lio_metrics,
        "fix": fix_metrics,
        "gps_lio_alignment": alignment,
        "alignment_status_counts": dict(status_counts),
        "array_topic_metrics": array_metrics,
        "decode_errors": dict(decode_errors),
    }
    return session, topic_rows, fix_samples, lio_samples


def _read_metadata(bag: Path) -> dict[str, Any]:
    metadata_path = bag / "metadata.yaml"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Bag metadata not found: {metadata_path}")
    return yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}


def _resolve_db_path(bag: Path, metadata: dict[str, Any]) -> Path:
    info = metadata.get("rosbag2_bagfile_information", {})
    for relative in info.get("relative_file_paths", []) or []:
        candidate = bag / relative
        if candidate.exists():
            return candidate
    candidates = sorted(bag.glob("*.db3"))
    if candidates:
        return candidates[0]
    raise FileNotFoundError(f"No SQLite .db3 file found in {bag}")


def _session_id_from_bag_path(bag: Path) -> str:
    return bag.parent.name if bag.name == "bag" else bag.name


def _metadata_duration_s(metadata: dict[str, Any]) -> float:
    info = metadata.get("rosbag2_bagfile_information", {})
    return float((info.get("duration") or {}).get("nanoseconds", 0)) / 1e9


def _metadata_message_count(metadata: dict[str, Any]) -> int:
    return int((metadata.get("rosbag2_bagfile_information", {}) or {}).get("message_count", 0))


def _topic_counts_from_metadata(metadata: dict[str, Any]) -> dict[str, int]:
    info = metadata.get("rosbag2_bagfile_information", {})
    counts: dict[str, int] = {}
    for item in info.get("topics_with_message_count", []) or []:
        topic = item.get("topic_metadata", {}).get("name")
        if topic:
            counts[topic] = int(item.get("message_count", 0))
    return counts


def _read_topics(conn: sqlite3.Connection) -> dict[int, dict[str, str]]:
    rows = conn.execute("SELECT id, name, type FROM topics ORDER BY id").fetchall()
    return {int(topic_id): {"name": str(name), "type": str(type_name)} for topic_id, name, type_name in rows}


def _make_fix_samples(session_id: str, records: list[tuple[int, NavSatFixRecord]]) -> list[FixSample]:
    valid_origin = next((record for _, record in records if _is_valid_fix(record)), None)
    origin = (valid_origin.latitude, valid_origin.longitude) if valid_origin else None
    samples: list[FixSample] = []
    for bag_timestamp_ns, record in records:
        valid = _is_valid_fix(record)
        enu: tuple[float | None, float | None] = (None, None)
        if valid and origin is not None:
            enu = _latlon_to_enu(record.latitude, record.longitude, origin[0], origin[1])
        covariance = list(record.position_covariance) + [math.nan] * 9
        samples.append(
            FixSample(
                session_id=session_id,
                bag_timestamp_ns=bag_timestamp_ns,
                header_stamp_ns=record.header_stamp_ns,
                frame_id=record.header_frame_id,
                status=record.status,
                service=record.service,
                latitude=record.latitude,
                longitude=record.longitude,
                altitude=record.altitude,
                covariance_x=covariance[0],
                covariance_y=covariance[4],
                covariance_z=covariance[8],
                covariance_type=record.position_covariance_type,
                valid=valid,
                enu_east_m=enu[0],
                enu_north_m=enu[1],
            )
        )
    return samples


def _make_lio_samples(session_id: str, records: list[tuple[int, OdometryRecord]]) -> list[LioSample]:
    samples: list[LioSample] = []
    previous: tuple[int, OdometryRecord] | None = None
    for bag_timestamp_ns, record in records:
        speed: float | None = None
        yaw_rate: float | None = None
        if previous is not None:
            previous_ts, previous_record = previous
            dt = (bag_timestamp_ns - previous_ts) / 1e9
            if dt > 0:
                distance = math.hypot(record.x - previous_record.x, record.y - previous_record.y)
                speed = distance / dt
                yaw_rate = abs(_angle_diff(record.yaw, previous_record.yaw)) / dt
        samples.append(
            LioSample(
                session_id=session_id,
                bag_timestamp_ns=bag_timestamp_ns,
                header_stamp_ns=record.header_stamp_ns,
                frame_id=record.header_frame_id,
                child_frame_id=record.child_frame_id,
                x=record.x,
                y=record.y,
                z=record.z,
                yaw=record.yaw,
                speed_mps=speed,
                yaw_rate_radps=yaw_rate,
            )
        )
        previous = (bag_timestamp_ns, record)
    return samples


def _is_valid_fix(record: NavSatFixRecord) -> bool:
    if record.status < 0:
        return False
    if not math.isfinite(record.latitude) or not math.isfinite(record.longitude):
        return False
    if abs(record.latitude) < 1e-9 and abs(record.longitude) < 1e-9:
        return False
    return -90.0 <= record.latitude <= 90.0 and -180.0 <= record.longitude <= 180.0


def _latlon_to_enu(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    north = math.radians(lat - lat0) * EARTH_RADIUS_M
    east = math.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(math.radians(lat0))
    return east, north


def _summarize_lio(samples: list[LioSample]) -> dict[str, Any]:
    timestamps = [sample.bag_timestamp_ns for sample in samples]
    speeds = [sample.speed_mps for sample in samples if sample.speed_mps is not None and math.isfinite(sample.speed_mps)]
    yaw_rates = [sample.yaw_rate_radps for sample in samples if sample.yaw_rate_radps is not None and math.isfinite(sample.yaw_rate_radps)]
    steps = [
        math.hypot(samples[index].x - samples[index - 1].x, samples[index].y - samples[index - 1].y)
        for index in range(1, len(samples))
    ]
    return {
        "sample_count": len(samples),
        "duration_s": _duration_s(timestamps),
        "mean_rate_hz": _mean_rate_hz(timestamps),
        "max_gap_s": _max_gap_s(timestamps),
        "path_length_m": sum(steps),
        "max_step_m": max(steps, default=0.0),
        "mean_speed_mps": _mean(speeds),
        "p95_speed_mps": _percentile(speeds, 95),
        "max_speed_mps": max(speeds, default=0.0),
        "p95_yaw_rate_radps": _percentile(yaw_rates, 95),
        "max_yaw_rate_radps": max(yaw_rates, default=0.0),
        "start_xy": [samples[0].x, samples[0].y] if samples else None,
        "end_xy": [samples[-1].x, samples[-1].y] if samples else None,
    }


def _summarize_fix(samples: list[FixSample]) -> dict[str, Any]:
    valid_samples = [sample for sample in samples if sample.valid and sample.enu_east_m is not None and sample.enu_north_m is not None]
    timestamps = [sample.bag_timestamp_ns for sample in samples]
    valid_timestamps = [sample.bag_timestamp_ns for sample in valid_samples]
    jumps = [
        math.hypot(
            valid_samples[index].enu_east_m - valid_samples[index - 1].enu_east_m,
            valid_samples[index].enu_north_m - valid_samples[index - 1].enu_north_m,
        )
        for index in range(1, len(valid_samples))
        if valid_samples[index].enu_east_m is not None
        and valid_samples[index - 1].enu_east_m is not None
        and valid_samples[index].enu_north_m is not None
        and valid_samples[index - 1].enu_north_m is not None
    ]
    speeds: list[float] = []
    for index in range(1, len(valid_samples)):
        dt = (valid_samples[index].bag_timestamp_ns - valid_samples[index - 1].bag_timestamp_ns) / 1e9
        if dt > 0 and index - 1 < len(jumps):
            speeds.append(jumps[index - 1] / dt)
    cov_x = [sample.covariance_x for sample in samples if math.isfinite(sample.covariance_x)]
    cov_y = [sample.covariance_y for sample in samples if math.isfinite(sample.covariance_y)]
    return {
        "sample_count": len(samples),
        "valid_count": len(valid_samples),
        "invalid_count": len(samples) - len(valid_samples),
        "valid_ratio": (len(valid_samples) / len(samples)) if samples else 0.0,
        "duration_s": _duration_s(timestamps),
        "mean_rate_hz": _mean_rate_hz(timestamps),
        "max_gap_s": _max_gap_s(timestamps),
        "valid_duration_s": _duration_s(valid_timestamps),
        "valid_max_gap_s": _max_gap_s(valid_timestamps),
        "max_jump_m": max(jumps, default=0.0),
        "p95_jump_m": _percentile(jumps, 95),
        "max_speed_mps": max(speeds, default=0.0),
        "p95_speed_mps": _percentile(speeds, 95),
        "mean_covariance_x_m2": _mean(cov_x),
        "mean_covariance_y_m2": _mean(cov_y),
    }


def _summarize_gps_lio_alignment(fix_samples: list[FixSample], lio_samples: list[LioSample]) -> dict[str, Any]:
    pairs = _pair_fix_to_lio(fix_samples, lio_samples)
    if len(pairs) < 2:
        return {
            "pair_count": len(pairs),
            "status": "insufficient_pairs",
            "rms_residual_m": None,
            "p95_residual_m": None,
            "max_residual_m": None,
            "source_path_length_m": 0.0,
            "max_time_delta_s": max((pair[4] for pair in pairs), default=None),
        }

    src = [(pair[0], pair[1]) for pair in pairs]
    dst = [(pair[2], pair[3]) for pair in pairs]
    transform = _fit_similarity_2d(src, dst)
    source_path_length = sum(math.hypot(src[index][0] - src[index - 1][0], src[index][1] - src[index - 1][1]) for index in range(1, len(src)))
    if transform is None:
        return {
            "pair_count": len(pairs),
            "status": "insufficient_spread",
            "rms_residual_m": None,
            "p95_residual_m": None,
            "max_residual_m": None,
            "source_path_length_m": source_path_length,
            "max_time_delta_s": max(pair[4] for pair in pairs),
        }

    residuals = []
    for point, target in zip(src, dst, strict=True):
        mapped = _apply_similarity_2d(transform, point)
        residuals.append(math.hypot(mapped[0] - target[0], mapped[1] - target[1]))

    return {
        "pair_count": len(pairs),
        "status": "aligned",
        "rms_residual_m": math.sqrt(sum(residual * residual for residual in residuals) / len(residuals)),
        "p95_residual_m": _percentile(residuals, 95),
        "max_residual_m": max(residuals, default=0.0),
        "source_path_length_m": source_path_length,
        "max_time_delta_s": max(pair[4] for pair in pairs),
        "scale": transform["scale"],
        "yaw_rad": transform["yaw_rad"],
        "tx_m": transform["tx_m"],
        "ty_m": transform["ty_m"],
    }


def _pair_fix_to_lio(fix_samples: list[FixSample], lio_samples: list[LioSample], max_time_delta_s: float = 0.5) -> list[tuple[float, float, float, float, float]]:
    valid_fixes = [sample for sample in fix_samples if sample.valid and sample.enu_east_m is not None and sample.enu_north_m is not None]
    if not valid_fixes or not lio_samples:
        return []
    lio_times = [sample.bag_timestamp_ns for sample in lio_samples]
    pairs: list[tuple[float, float, float, float, float]] = []
    for fix in valid_fixes:
        insert_at = bisect.bisect_left(lio_times, fix.bag_timestamp_ns)
        candidates = []
        if insert_at < len(lio_samples):
            candidates.append(lio_samples[insert_at])
        if insert_at > 0:
            candidates.append(lio_samples[insert_at - 1])
        if not candidates:
            continue
        best = min(candidates, key=lambda sample: abs(sample.bag_timestamp_ns - fix.bag_timestamp_ns))
        delta_s = abs(best.bag_timestamp_ns - fix.bag_timestamp_ns) / 1e9
        if delta_s <= max_time_delta_s:
            pairs.append((float(fix.enu_east_m), float(fix.enu_north_m), best.x, best.y, delta_s))
    return pairs


def _fit_similarity_2d(src: list[tuple[float, float]], dst: list[tuple[float, float]]) -> dict[str, float] | None:
    src_mean = (sum(point[0] for point in src) / len(src), sum(point[1] for point in src) / len(src))
    dst_mean = (sum(point[0] for point in dst) / len(dst), sum(point[1] for point in dst) / len(dst))
    a = 0.0
    b = 0.0
    denom = 0.0
    for source, target in zip(src, dst, strict=True):
        sx = source[0] - src_mean[0]
        sy = source[1] - src_mean[1]
        tx = target[0] - dst_mean[0]
        ty = target[1] - dst_mean[1]
        a += sx * tx + sy * ty
        b += sx * ty - sy * tx
        denom += sx * sx + sy * sy
    if denom < 1e-9:
        return None
    scale = math.hypot(a, b) / denom
    yaw = math.atan2(b, a)
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)
    tx = dst_mean[0] - scale * (cos_yaw * src_mean[0] - sin_yaw * src_mean[1])
    ty = dst_mean[1] - scale * (sin_yaw * src_mean[0] + cos_yaw * src_mean[1])
    return {"scale": scale, "yaw_rad": yaw, "tx_m": tx, "ty_m": ty}


def _apply_similarity_2d(transform: dict[str, float], point: tuple[float, float]) -> tuple[float, float]:
    cos_yaw = math.cos(transform["yaw_rad"])
    sin_yaw = math.sin(transform["yaw_rad"])
    x = transform["scale"] * (cos_yaw * point[0] - sin_yaw * point[1]) + transform["tx_m"]
    y = transform["scale"] * (sin_yaw * point[0] + cos_yaw * point[1]) + transform["ty_m"]
    return x, y


def _summarize_array_values(values: list[list[float]]) -> dict[str, Any]:
    lengths = Counter(len(value) for value in values)
    finite_values = [component for value in values for component in value if math.isfinite(component)]
    per_index: list[dict[str, float | int]] = []
    max_len = max(lengths, default=0)
    for index in range(max_len):
        components = [value[index] for value in values if index < len(value) and math.isfinite(value[index])]
        if components:
            per_index.append(
                {
                    "index": index,
                    "mean": _mean(components),
                    "stdev": statistics.pstdev(components) if len(components) > 1 else 0.0,
                    "min": min(components),
                    "max": max(components),
                }
            )
    return {
        "sample_count": len(values),
        "length_counts": {str(key): count for key, count in sorted(lengths.items())},
        "finite_component_count": len(finite_values),
        "last": values[-1] if values else [],
        "per_index": per_index,
    }


def _classify_anchor_health(
    lio_metrics: dict[str, Any],
    fix_metrics: dict[str, Any],
    alignment: dict[str, Any],
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if lio_metrics["sample_count"] < 2:
        return "insufficient_lio", ["fewer than two FAST-LIO odometry samples"]
    if lio_metrics["max_gap_s"] > 2.0:
        warnings.append("FAST-LIO has timestamp gaps above 2 s")
    if lio_metrics["max_speed_mps"] > 5.0:
        warnings.append("FAST-LIO has step-derived speed above 5 m/s")

    if fix_metrics["sample_count"] == 0:
        return "lio_only", warnings + ["no /fix samples were recorded"]
    if fix_metrics["valid_count"] < 3 or fix_metrics["valid_ratio"] < 0.2:
        return "lio_only", warnings + ["GNSS valid-fix ratio is too low for anchor alignment"]
    if fix_metrics["max_jump_m"] > 20.0 or fix_metrics["p95_speed_mps"] > 8.0:
        return "gnss_rejected", warnings + ["GNSS jumps are too large for trusted anchoring"]

    if alignment["status"] != "aligned":
        return "weak_alignment", warnings + [f"GPS-LIO alignment status is {alignment['status']}"]
    if alignment["source_path_length_m"] < 5.0:
        return "weak_alignment", warnings + ["valid GNSS motion spread is below the 5 m anchor-audit floor"]

    rms = alignment["rms_residual_m"]
    p95 = alignment["p95_residual_m"]
    if rms is not None and p95 is not None:
        if rms > 5.0 or p95 > 8.0:
            return "gnss_rejected", warnings + ["GPS-LIO alignment residual is too large"]
        if rms > 2.0 or p95 > 3.0:
            return "weak_alignment", warnings + ["GPS-LIO alignment residual is marginal"]
    return "usable", warnings


def _decode_warnings(decode_errors: Counter[str]) -> list[str]:
    return [f"failed to decode {count} messages from {topic}" for topic, count in sorted(decode_errors.items())]


def _duration_s(timestamps_ns: list[int]) -> float:
    if len(timestamps_ns) < 2:
        return 0.0
    return max(0.0, (timestamps_ns[-1] - timestamps_ns[0]) / 1e9)


def _mean_rate_hz(timestamps_ns: list[int]) -> float:
    duration = _duration_s(timestamps_ns)
    if duration <= 0.0 or len(timestamps_ns) < 2:
        return 0.0
    return (len(timestamps_ns) - 1) / duration


def _max_gap_s(timestamps_ns: list[int]) -> float:
    if len(timestamps_ns) < 2:
        return 0.0
    return max((timestamps_ns[index] - timestamps_ns[index - 1]) / 1e9 for index in range(1, len(timestamps_ns)))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile / 100.0
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _angle_diff(a: float, b: float) -> float:
    diff = a - b
    while diff > math.pi:
        diff -= 2.0 * math.pi
    while diff < -math.pi:
        diff += 2.0 * math.pi
    return diff


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_dict_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_session_metrics(path: Path, sessions: list[dict[str, Any]]) -> None:
    rows = []
    for session in sessions:
        rows.append(
            {
                "session_id": session["session_id"],
                "bag_path": session["bag_path"],
                "anchor_health": session["anchor_health"],
                "duration_s": session["duration_s"],
                "message_count": session["message_count"],
                "topic_count": session["topic_count"],
                "lio_samples": session["lio"]["sample_count"],
                "lio_path_length_m": session["lio"]["path_length_m"],
                "lio_max_gap_s": session["lio"]["max_gap_s"],
                "lio_max_speed_mps": session["lio"]["max_speed_mps"],
                "fix_samples": session["fix"]["sample_count"],
                "fix_valid_ratio": session["fix"]["valid_ratio"],
                "fix_max_jump_m": session["fix"]["max_jump_m"],
                "alignment_pair_count": session["gps_lio_alignment"]["pair_count"],
                "alignment_rms_residual_m": session["gps_lio_alignment"]["rms_residual_m"],
                "alignment_p95_residual_m": session["gps_lio_alignment"]["p95_residual_m"],
                "warning_count": len(session["warnings"]),
            }
        )
    _write_dict_rows(path, rows)


def _write_fix_samples(path: Path, samples: list[FixSample]) -> None:
    rows = [
        {
            "session_id": sample.session_id,
            "bag_timestamp_ns": sample.bag_timestamp_ns,
            "header_stamp_ns": sample.header_stamp_ns,
            "frame_id": sample.frame_id,
            "status": sample.status,
            "service": sample.service,
            "latitude": sample.latitude,
            "longitude": sample.longitude,
            "altitude": sample.altitude,
            "covariance_x": sample.covariance_x,
            "covariance_y": sample.covariance_y,
            "covariance_z": sample.covariance_z,
            "covariance_type": sample.covariance_type,
            "valid": sample.valid,
            "enu_east_m": sample.enu_east_m,
            "enu_north_m": sample.enu_north_m,
        }
        for sample in samples
    ]
    _write_dict_rows(path, rows)


def _write_lio_samples(path: Path, samples: list[LioSample]) -> None:
    rows = [
        {
            "session_id": sample.session_id,
            "bag_timestamp_ns": sample.bag_timestamp_ns,
            "header_stamp_ns": sample.header_stamp_ns,
            "frame_id": sample.frame_id,
            "child_frame_id": sample.child_frame_id,
            "x": sample.x,
            "y": sample.y,
            "z": sample.z,
            "yaw": sample.yaw,
            "speed_mps": sample.speed_mps,
            "yaw_rate_radps": sample.yaw_rate_radps,
        }
        for sample in samples
    ]
    _write_dict_rows(path, rows)


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    rows = []
    for session in summary["sessions"]:
        warnings = "<br>".join(html.escape(warning) for warning in session["warnings"]) or "None"
        rows.append(
            "<tr>"
            f"<td>{html.escape(session['session_id'])}</td>"
            f"<td>{html.escape(session['anchor_health'])}</td>"
            f"<td>{session['duration_s']:.1f}</td>"
            f"<td>{session['lio']['sample_count']}</td>"
            f"<td>{session['lio']['path_length_m']:.2f}</td>"
            f"<td>{session['fix']['sample_count']}</td>"
            f"<td>{session['fix']['valid_ratio']:.3f}</td>"
            f"<td>{_fmt_optional(session['gps_lio_alignment']['rms_residual_m'])}</td>"
            f"<td>{warnings}</td>"
            "</tr>"
        )

    health_items = "".join(
        f"<li><code>{html.escape(health)}</code>: {count}</li>"
        for health, count in sorted(summary["health_counts"].items())
    )
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Localization-Only Bag Audit</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #18212f; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border: 1px solid #d8dee9; padding: 8px 10px; vertical-align: top; }}
    th {{ background: #eef3f8; text-align: left; }}
    code {{ background: #eef3f8; padding: 1px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Localization-Only Bag Audit</h1>
  <p>Scope: FAST-LIO, NavSatFix, and GPS corridor alignment health. This report does not evaluate ObjectNav perception or memory.</p>
  <h2>Health Counts</h2>
  <ul>{health_items}</ul>
  <h2>Sessions</h2>
  <table>
    <thead>
      <tr>
        <th>Session</th>
        <th>Anchor Health</th>
        <th>Duration (s)</th>
        <th>LIO Samples</th>
        <th>LIO Path (m)</th>
        <th>Fix Samples</th>
        <th>Fix Valid Ratio</th>
        <th>GPS-LIO RMS (m)</th>
        <th>Warnings</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _fmt_optional(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return html.escape(str(value))
