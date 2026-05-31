from __future__ import annotations

import math
import sqlite3
import struct
from pathlib import Path

import yaml

from objectnav_core.evaluation.localization_bag_audit import (
    decode_float64_multi_array,
    decode_navsat_fix,
    decode_odometry,
    decode_string,
    run_localization_bag_audit,
)


EARTH_RADIUS_M = 6378137.0


def _align(buf: bytearray, size: int) -> None:
    while (len(buf) - 4) % size:
        buf.append(0)


def _i8(buf: bytearray, value: int) -> None:
    buf.extend(struct.pack("<b", value))


def _u8(buf: bytearray, value: int) -> None:
    buf.extend(struct.pack("<B", value))


def _u16(buf: bytearray, value: int) -> None:
    _align(buf, 2)
    buf.extend(struct.pack("<H", value))


def _i32(buf: bytearray, value: int) -> None:
    _align(buf, 4)
    buf.extend(struct.pack("<i", value))


def _u32(buf: bytearray, value: int) -> None:
    _align(buf, 4)
    buf.extend(struct.pack("<I", value))


def _f64(buf: bytearray, value: float) -> None:
    _align(buf, 8)
    buf.extend(struct.pack("<d", value))


def _string(buf: bytearray, value: str) -> None:
    encoded = value.encode("utf-8") + b"\x00"
    _u32(buf, len(encoded))
    buf.extend(encoded)
    _align(buf, 4)


def _blob() -> bytearray:
    return bytearray(b"\x00\x01\x00\x00")


def _header(buf: bytearray, stamp_ns: int, frame_id: str) -> None:
    _i32(buf, stamp_ns // 1_000_000_000)
    _u32(buf, stamp_ns % 1_000_000_000)
    _string(buf, frame_id)


def _navsat_fix_blob(stamp_ns: int, lat: float, lon: float, status: int = 0) -> bytes:
    buf = _blob()
    _header(buf, stamp_ns, "gps")
    _i8(buf, status)
    _u16(buf, 1)
    _f64(buf, lat)
    _f64(buf, lon)
    _f64(buf, 10.0)
    for index in range(9):
        _f64(buf, 4.0 if index in {0, 4, 8} else 0.0)
    _u8(buf, 2)
    return bytes(buf)


def _odom_blob(stamp_ns: int, x: float, y: float, yaw: float) -> bytes:
    buf = _blob()
    _header(buf, stamp_ns, "odom")
    _string(buf, "base_link")
    _f64(buf, x)
    _f64(buf, y)
    _f64(buf, 0.0)
    _f64(buf, 0.0)
    _f64(buf, 0.0)
    _f64(buf, math.sin(yaw / 2.0))
    _f64(buf, math.cos(yaw / 2.0))
    for _ in range(36):
        _f64(buf, 0.0)
    _f64(buf, 0.1)
    _f64(buf, 0.0)
    _f64(buf, 0.0)
    _f64(buf, 0.0)
    _f64(buf, 0.0)
    _f64(buf, 0.01)
    for _ in range(36):
        _f64(buf, 0.0)
    return bytes(buf)


def _float64_multi_array_blob(values: list[float]) -> bytes:
    buf = _blob()
    _u32(buf, 0)
    _u32(buf, 0)
    _u32(buf, len(values))
    for value in values:
        _f64(buf, value)
    return bytes(buf)


def _string_blob(value: str) -> bytes:
    buf = _blob()
    _string(buf, value)
    return bytes(buf)


def _gps_from_local(lat0: float, lon0: float, east_m: float, north_m: float) -> tuple[float, float]:
    lat = lat0 + math.degrees(north_m / EARTH_RADIUS_M)
    lon = lon0 + math.degrees(east_m / (EARTH_RADIUS_M * math.cos(math.radians(lat0))))
    return lat, lon


def _create_synthetic_bag(bag_dir: Path, east_values: list[float] | None = None) -> Path:
    bag_dir.mkdir(parents=True)
    db_path = bag_dir / "bag_0.db3"
    metadata_path = bag_dir / "metadata.yaml"

    topics = [
        (1, "/fix", "sensor_msgs/msg/NavSatFix"),
        (2, "/fastlio2/lio_odom", "nav_msgs/msg/Odometry"),
        (3, "/gps_corridor/alignment_status", "std_msgs/msg/String"),
        (4, "/gps_corridor/alignment_debug", "std_msgs/msg/Float64MultiArray"),
    ]

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE schema(schema_version INTEGER PRIMARY KEY, ros_distro TEXT NOT NULL);
        CREATE TABLE metadata(id INTEGER PRIMARY KEY, metadata_version INTEGER NOT NULL, metadata TEXT NOT NULL);
        CREATE TABLE topics(
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            serialization_format TEXT NOT NULL,
            offered_qos_profiles TEXT NOT NULL
        );
        CREATE TABLE messages(id INTEGER PRIMARY KEY, topic_id INTEGER NOT NULL, timestamp INTEGER NOT NULL, data BLOB NOT NULL);
        CREATE INDEX timestamp_idx ON messages (timestamp ASC);
        """
    )
    conn.execute("INSERT INTO schema VALUES (4, 'humble')")
    for topic in topics:
        conn.execute("INSERT INTO topics VALUES (?, ?, ?, 'cdr', '')", topic)

    lat0 = 31.0
    lon0 = 120.0
    messages = []
    for index, east in enumerate(east_values or [0.0, 5.0, 10.0]):
        stamp_ns = 1_000_000_000 + index * 1_000_000_000
        lat, lon = _gps_from_local(lat0, lon0, east, 0.0)
        messages.append((1, stamp_ns, _navsat_fix_blob(stamp_ns, lat, lon)))
        messages.append((2, stamp_ns + 20_000_000, _odom_blob(stamp_ns, 10.0 + east, 20.0, 0.05 * index)))
    messages.append((3, 1_500_000_000, _string_blob("ALIGNER_USABLE")))
    messages.append((4, 1_500_000_000, _float64_multi_array_blob([0.1, 0.2, 0.3])))

    for message_id, (topic_id, stamp_ns, data) in enumerate(messages, start=1):
        conn.execute("INSERT INTO messages VALUES (?, ?, ?, ?)", (message_id, topic_id, stamp_ns, data))
    conn.commit()
    conn.close()

    metadata = {
        "rosbag2_bagfile_information": {
            "version": 5,
            "storage_identifier": "sqlite3",
            "duration": {"nanoseconds": 2_020_000_000},
            "starting_time": {"nanoseconds_since_epoch": 1_000_000_000},
            "message_count": len(messages),
            "topics_with_message_count": [
                {
                    "topic_metadata": {
                        "name": name,
                        "type": type_name,
                        "serialization_format": "cdr",
                        "offered_qos_profiles": "",
                    },
                    "message_count": sum(1 for topic_id, _, _ in messages if topic_id == id_),
                }
                for id_, name, type_name in topics
            ],
            "relative_file_paths": ["bag_0.db3"],
            "files": [
                {
                    "path": "bag_0.db3",
                    "duration": {"nanoseconds": 2_020_000_000},
                    "message_count": len(messages),
                }
            ],
        }
    }
    metadata_path.write_text(yaml.safe_dump(metadata), encoding="utf-8")
    return bag_dir


def test_minimal_cdr_decoders_parse_required_message_types() -> None:
    fix = decode_navsat_fix(_navsat_fix_blob(1_200_000_000, 31.1, 120.2))
    odom = decode_odometry(_odom_blob(1_200_000_000, 3.0, 4.0, 0.3))
    array = decode_float64_multi_array(_float64_multi_array_blob([1.0, 2.0, 3.0]))
    text = decode_string(_string_blob("ALIGNER_USABLE"))

    assert fix.header_frame_id == "gps"
    assert fix.status == 0
    assert fix.latitude == 31.1
    assert fix.longitude == 120.2
    assert fix.position_covariance_type == 2
    assert odom.header_frame_id == "odom"
    assert odom.child_frame_id == "base_link"
    assert odom.x == 3.0
    assert odom.y == 4.0
    assert 0.29 < odom.yaw < 0.31
    assert array == [1.0, 2.0, 3.0]
    assert text == "ALIGNER_USABLE"


def test_localization_bag_audit_writes_metrics_and_report(tmp_path: Path) -> None:
    bag_dir = _create_synthetic_bag(tmp_path / "session" / "bag")
    output_dir = tmp_path / "audit"

    summary = run_localization_bag_audit(output_dir=output_dir, bag_paths=[bag_dir])

    session = summary["sessions"][0]
    assert session["session_id"] == "session"
    assert session["anchor_health"] == "usable"
    assert session["fix"]["valid_ratio"] == 1.0
    assert session["lio"]["sample_count"] == 3
    assert session["lio"]["path_length_m"] > 1.9
    assert session["gps_lio_alignment"]["pair_count"] == 3
    assert session["gps_lio_alignment"]["rms_residual_m"] < 0.05
    assert session["alignment_status_counts"]["ALIGNER_USABLE"] == 1

    assert (output_dir / "summary.json").exists()
    assert (output_dir / "session_metrics.csv").read_text(encoding="utf-8").count("\n") == 2
    assert (output_dir / "topic_counts.csv").exists()
    assert (output_dir / "fix_samples.csv").exists()
    assert (output_dir / "lio_samples.csv").exists()
    assert "Localization-Only Bag Audit" in (output_dir / "audit_report.html").read_text(encoding="utf-8")


def test_localization_bag_audit_marks_small_motion_alignment_as_weak(tmp_path: Path) -> None:
    bag_dir = _create_synthetic_bag(tmp_path / "session" / "bag", east_values=[0.0, 2.0, 4.0])
    summary = run_localization_bag_audit(output_dir=tmp_path / "audit", bag_paths=[bag_dir])

    session = summary["sessions"][0]
    assert session["gps_lio_alignment"]["source_path_length_m"] < 5.0
    assert session["anchor_health"] == "weak_alignment"


def test_localization_bag_audit_cli_runs_on_explicit_bag(tmp_path: Path) -> None:
    from objectnav_core.cli.run_localization_bag_audit import main

    bag_dir = _create_synthetic_bag(tmp_path / "session" / "bag")
    output_dir = tmp_path / "audit_cli"

    exit_code = main(["--output", str(output_dir), "--bag", str(bag_dir)])

    assert exit_code == 0
    assert (output_dir / "summary.json").exists()
