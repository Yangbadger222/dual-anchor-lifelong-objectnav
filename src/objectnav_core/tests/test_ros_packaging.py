from pathlib import Path
from xml.etree import ElementTree


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_objectnav_core_is_ament_python_package_without_ros_runtime_imports() -> None:
    package_xml = PACKAGE_ROOT / "package.xml"
    setup_py = PACKAGE_ROOT / "setup.py"
    resource_file = PACKAGE_ROOT / "resource" / "objectnav_core"

    assert package_xml.exists()
    assert setup_py.exists()
    assert resource_file.exists()

    root = ElementTree.parse(package_xml).getroot()
    assert root.findtext("name") == "objectnav_core"
    assert root.findtext("export/build_type") == "ament_python"
    assert root.findtext("buildtool_depend") == "ament_python"

    setup_text = setup_py.read_text(encoding="utf-8")
    assert "objectnav_core" in setup_text
    assert "rclpy" not in setup_text
    assert "objectnav_phase1a" in setup_text
    assert "objectnav_core.cli.run_phase1a:main" in setup_text
    assert "objectnav_phase1a_report" in setup_text
    assert "objectnav_core.cli.generate_phase1a_report:main" in setup_text
