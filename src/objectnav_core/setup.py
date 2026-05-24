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
        ]
    },
)
