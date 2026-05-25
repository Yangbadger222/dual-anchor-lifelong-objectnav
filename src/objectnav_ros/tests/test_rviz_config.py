from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_replay_rviz_config_contains_expected_topics() -> None:
    config_path = PACKAGE_ROOT / "rviz" / "synthetic_replay.rviz"

    text = config_path.read_text(encoding="utf-8")

    assert "Fixed Frame: map" in text
    assert "/global_costmap/costmap" in text
    assert "/objectnav/selected_goal" in text
    assert "/objectnav/frontier_markers" in text
    assert "/objectnav/memory_markers" in text
    assert "/objectnav/debug_markers" in text
    assert "Durability Policy: Transient Local" in text
    assert "rviz_default_plugins/Map" in text
    assert "rviz_default_plugins/MarkerArray" in text


def test_package_installs_rviz_config_and_launch_file() -> None:
    setup_text = (PACKAGE_ROOT / "setup.py").read_text(encoding="utf-8")
    launch_path = PACKAGE_ROOT / "launch" / "synthetic_replay_rviz.launch.py"

    assert '(f"share/{package_name}/rviz", glob("rviz/*.rviz"))' in setup_text
    assert launch_path.exists()
    assert "synthetic_replay.rviz" in launch_path.read_text(encoding="utf-8")
