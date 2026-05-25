from pathlib import Path
from xml.etree import ElementTree

import objectnav_ros.adapters.costmap_adapter
import objectnav_ros.nodes.objectnav_node


SRC_ROOT = Path(__file__).resolve().parents[2]
CORE_PACKAGE = SRC_ROOT / "objectnav_core" / "objectnav_core"
ROS_PACKAGE = SRC_ROOT / "objectnav_ros"


def test_objectnav_core_stays_ros_free() -> None:
    forbidden_terms = (
        "rclpy",
        "nav2_msgs",
        "nav_msgs",
        "geometry_msgs",
        "sensor_msgs",
        "tf2_ros",
        "visualization_msgs",
    )
    matches: list[str] = []
    for path in CORE_PACKAGE.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            if term in text:
                matches.append(f"{path.relative_to(SRC_ROOT)}:{term}")
    assert matches == []


def test_objectnav_ros_is_ament_python_package() -> None:
    package_xml = ROS_PACKAGE / "package.xml"
    setup_py = ROS_PACKAGE / "setup.py"
    resource_file = ROS_PACKAGE / "resource" / "objectnav_ros"

    assert package_xml.exists()
    assert setup_py.exists()
    assert resource_file.exists()

    root = ElementTree.parse(package_xml).getroot()
    assert root.findtext("name") == "objectnav_ros"
    assert root.findtext("export/build_type") == "ament_python"
    assert root.findtext("buildtool_depend") == "ament_python"
    assert root.findtext("exec_depend[.='objectnav_core']") == "objectnav_core"
    assert root.findtext("exec_depend[.='rclpy']") == "rclpy"
    assert objectnav_ros.adapters.costmap_adapter is not None
    assert objectnav_ros.nodes.objectnav_node is not None
