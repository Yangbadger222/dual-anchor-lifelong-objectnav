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
    assert "objectnav_usability_stress" in setup_text
    assert "objectnav_core.cli.run_usability_stress:main" in setup_text
    assert "objectnav_grid_trace_experiment" in setup_text
    assert "objectnav_core.cli.run_grid_trace_experiment:main" in setup_text
    assert "objectnav_localization_bag_audit" in setup_text
    assert "objectnav_core.cli.run_localization_bag_audit:main" in setup_text
    assert "objectnav_habitat_objectnav_smoke" in setup_text
    assert "objectnav_core.cli.run_habitat_objectnav_smoke:main" in setup_text
    assert "objectnav_habitat_usability_replay" in setup_text
    assert "objectnav_core.cli.run_habitat_usability_replay:main" in setup_text
    assert "objectnav_habitat_semantic_yolo_stress" in setup_text
    assert "objectnav_core.cli.run_habitat_semantic_yolo_stress:main" in setup_text
    assert "objectnav_habitat_objectnav_valmini_semantic_stress" in setup_text
    assert (
        "objectnav_core.cli.run_habitat_objectnav_valmini_semantic_stress:main"
        in setup_text
    )
    assert "objectnav_habitat_objectnav_rgb_noise_stress" in setup_text
    assert "objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress:main" in setup_text
    assert "objectnav_habitat_official_memory_discovery" in setup_text
    assert (
        "objectnav_core.cli.run_habitat_official_memory_discovery:main"
        in setup_text
    )
    assert "objectnav_habitat_official_memory_comparison" in setup_text
    assert (
        "objectnav_core.cli.run_habitat_official_memory_comparison:main"
        in setup_text
    )
    assert "objectnav_habitat_official_detector_viewpoint_memory_prior" in setup_text
    assert (
        "objectnav_core.cli.export_habitat_official_detector_viewpoint_memory_prior:main"
        in setup_text
    )
    assert "objectnav_habitat_official_local_action_dataset" in setup_text
    assert (
        "objectnav_core.cli.export_habitat_official_local_action_dataset:main"
        in setup_text
    )
    assert "objectnav_habitat_official_targetnav_local_policy_dataset" in setup_text
    assert (
        "objectnav_core.cli.export_habitat_official_targetnav_local_policy_dataset:main"
        in setup_text
    )
    assert "objectnav_habitat_official_view_recall_dataset" in setup_text
    assert (
        "objectnav_core.cli.export_habitat_official_view_recall_dataset:main"
        in setup_text
    )
    assert "objectnav_habitat_official_view_candidate_dataset" in setup_text
    assert (
        "objectnav_core.cli.export_habitat_official_view_candidate_dataset:main"
        in setup_text
    )
    assert "objectnav_habitat_official_candidate_rollout_dataset" in setup_text
    assert (
        "objectnav_core.cli.export_habitat_official_candidate_rollout_dataset:main"
        in setup_text
    )
    assert "objectnav_habitat_official_candidate_state_restore_dataset" in setup_text
    assert (
        "objectnav_core.cli.export_habitat_official_candidate_state_restore_dataset:main"
        in setup_text
    )
    assert "objectnav_habitat_official_candidate_viewpoint_restore_dataset" in setup_text
    assert (
        "objectnav_core.cli.export_habitat_official_candidate_viewpoint_restore_dataset:main"
        in setup_text
    )
    assert "objectnav_habitat_official_candidate_rollout_action_matrix_report" in setup_text
    assert (
        "objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix:main"
        in setup_text
    )
    assert "objectnav_habitat_official_candidate_rollout_hard_states" in setup_text
    assert (
        "objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states:main"
        in setup_text
    )
    assert "objectnav_habitat_official_candidate_rollout_action_utility_model" in setup_text
    assert (
        "objectnav_core.cli.train_habitat_official_candidate_rollout_action_utility_model:main"
        in setup_text
    )
    assert "objectnav_habitat_official_local_action_model" in setup_text
    assert (
        "objectnav_core.cli.train_habitat_official_local_action_model:main"
        in setup_text
    )
    assert "objectnav_habitat_official_local_action_score" in setup_text
    assert (
        "objectnav_core.cli.score_habitat_official_local_action_model:main"
        in setup_text
    )
    assert "objectnav_habitat_official_view_recall_model" in setup_text
    assert (
        "objectnav_core.cli.train_habitat_official_view_recall_model:main"
        in setup_text
    )
    assert "objectnav_habitat_official_view_recall_score" in setup_text
    assert (
        "objectnav_core.cli.score_habitat_official_view_recall_model:main"
        in setup_text
    )
    assert "objectnav_habitat_official_candidate_viewpoint_ranker" in setup_text
    assert (
        "objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker:main"
        in setup_text
    )
    assert "objectnav_habitat_official_memory_anchor_quality" in setup_text
    assert (
        "objectnav_core.cli.report_habitat_official_memory_anchor_quality:main"
        in setup_text
    )
