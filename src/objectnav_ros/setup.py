from glob import glob

from setuptools import find_packages, setup


package_name = "objectnav_ros"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["tests"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/config", glob("config/*.yaml")),
        (f"share/{package_name}/launch", glob("launch/*.py")),
        (f"share/{package_name}/rviz", glob("rviz/*.rviz")),
    ],
    install_requires=["setuptools"],
    extras_require={"test": ["pytest"]},
    zip_safe=True,
    maintainer="Dual Anchor ObjectNav Contributors",
    maintainer_email="research@example.invalid",
    description="ROS 2 adapter layer for the Dual-Anchor ObjectNav core.",
    license="UNLICENSED",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "objectnav_adapter = objectnav_ros.nodes.objectnav_node:main",
            "assumed_target_nav2_smoke = objectnav_ros.nodes.assumed_target_nav2_smoke:main",
            "objectnav_synthetic_replay = objectnav_ros.nodes.synthetic_replay_node:main",
        ]
    },
)
