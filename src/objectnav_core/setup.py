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
    install_requires=[
        "setuptools",
        "numpy",
        "pydantic>=2",
        "PyYAML",
        "eval_type_backport; python_version < '3.10'",
    ],
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
            "objectnav_habitat_memory_lifecycle_objectnav = objectnav_core.cli.run_habitat_memory_lifecycle_objectnav:main",
            "objectnav_habitat_official_objectnav_eval = objectnav_core.cli.run_habitat_official_objectnav_eval:main",
            "objectnav_habitat_official_memory_discovery = objectnav_core.cli.run_habitat_official_memory_discovery:main",
            "objectnav_habitat_official_memory_comparison = objectnav_core.cli.run_habitat_official_memory_comparison:main",
            "objectnav_habitat_official_oracle_memory_prior = objectnav_core.cli.export_habitat_official_oracle_memory_prior:main",
            "objectnav_habitat_official_detector_viewpoint_memory_prior = objectnav_core.cli.export_habitat_official_detector_viewpoint_memory_prior:main",
            "objectnav_export_lifecycle_memory_prior = objectnav_core.cli.export_lifecycle_memory_prior:main",
            "objectnav_habitat_official_local_action_dataset = objectnav_core.cli.export_habitat_official_local_action_dataset:main",
            "objectnav_habitat_official_targetnav_local_policy_dataset = objectnav_core.cli.export_habitat_official_targetnav_local_policy_dataset:main",
            "objectnav_habitat_official_view_recall_dataset = objectnav_core.cli.export_habitat_official_view_recall_dataset:main",
            "objectnav_habitat_official_view_candidate_dataset = objectnav_core.cli.export_habitat_official_view_candidate_dataset:main",
            "objectnav_habitat_official_candidate_rollout_dataset = objectnav_core.cli.export_habitat_official_candidate_rollout_dataset:main",
            "objectnav_habitat_official_candidate_state_restore_dataset = objectnav_core.cli.export_habitat_official_candidate_state_restore_dataset:main",
            "objectnav_habitat_official_candidate_viewpoint_restore_dataset = objectnav_core.cli.export_habitat_official_candidate_viewpoint_restore_dataset:main",
            "objectnav_habitat_official_candidate_option_value_dataset = objectnav_core.cli.export_habitat_official_candidate_option_value_dataset:main",
            "objectnav_habitat_official_candidate_rollout_action_matrix_report = objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix:main",
            "objectnav_habitat_official_candidate_rollout_hard_states = objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states:main",
            "objectnav_habitat_official_candidate_rollout_action_utility_model = objectnav_core.cli.train_habitat_official_candidate_rollout_action_utility_model:main",
            "objectnav_habitat_official_candidate_viewpoint_ranker = objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker:main",
            "objectnav_habitat_official_local_action_model = objectnav_core.cli.train_habitat_official_local_action_model:main",
            "objectnav_habitat_official_local_action_score = objectnav_core.cli.score_habitat_official_local_action_model:main",
            "objectnav_habitat_official_view_recall_model = objectnav_core.cli.train_habitat_official_view_recall_model:main",
            "objectnav_habitat_official_view_recall_score = objectnav_core.cli.score_habitat_official_view_recall_model:main",
            "objectnav_habitat_official_memory_anchor_quality = objectnav_core.cli.report_habitat_official_memory_anchor_quality:main",
            "objectnav_lifelong_objectnav_benchmark = objectnav_core.cli.run_lifelong_objectnav_benchmark:main",
        ]
    },
)
