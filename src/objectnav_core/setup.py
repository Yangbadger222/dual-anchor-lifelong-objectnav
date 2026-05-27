from setuptools import find_packages, setup


package_name = "objectnav_core"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["tests"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools", "numpy", "pydantic>=2", "PyYAML"],
    extras_require={"test": ["pytest"]},
    zip_safe=True,
    maintainer="Dual Anchor ObjectNav Contributors",
    maintainer_email="research@example.invalid",
    description="ROS-free core library for Dual-Anchor Lifelong Semantic ObjectNav.",
    license="UNLICENSED",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "objectnav_phase1a = objectnav_core.cli.run_phase1a:main",
            "objectnav_phase1a_report = objectnav_core.cli.generate_phase1a_report:main",
            "objectnav_usability_stress = objectnav_core.cli.run_usability_stress:main",
            "objectnav_grid_trace_experiment = objectnav_core.cli.run_grid_trace_experiment:main",
            "objectnav_localization_bag_audit = objectnav_core.cli.run_localization_bag_audit:main",
            "objectnav_habitat_objectnav_smoke = objectnav_core.cli.run_habitat_objectnav_smoke:main",
            "objectnav_habitat_usability_replay = objectnav_core.cli.run_habitat_usability_replay:main",
            "objectnav_habitat_semantic_yolo_stress = objectnav_core.cli.run_habitat_semantic_yolo_stress:main",
            "objectnav_habitat_objectnav_valmini_semantic_stress = objectnav_core.cli.run_habitat_objectnav_valmini_semantic_stress:main",
            "objectnav_habitat_objectnav_rgb_noise_stress = objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress:main",
        ]
    },
)
