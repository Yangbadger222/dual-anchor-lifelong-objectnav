from __future__ import annotations

import math
from pathlib import Path

from objectnav_core.evaluation.logger import TrialLogger
from objectnav_core.mapping.fixtures import build_corridor_grid
from objectnav_core.mapping.frontiers import extract_frontier_clusters
from objectnav_core.memory.sqlite_store import SQLiteMemoryStore
from objectnav_core.models import (
    MemoryState,
    ObjectObservation,
    Pose2D,
    SceneConfig,
    TrialMetrics,
    TrialResult,
    make_default_corridor_scene,
)
from objectnav_core.planning.frontier_policies import (
    FrontierPolicyCandidate,
    FrontierPolicyName,
    select_frontier_candidate,
)
from objectnav_core.planning.viewpoints import (
    plan_verification_viewpoint,
)
from objectnav_core.simulation.navigation import DiscreteStepNavigationClient
from objectnav_core.simulation.observations import ConfigTruthObjectSource


class Phase1ATrialRunner:
    def __init__(
        self,
        memory_path: str | Path,
        scene: SceneConfig | None = None,
        frontier_policy: FrontierPolicyName | str = FrontierPolicyName.FIRST_FRONTIER,
    ) -> None:
        self.scene = scene or make_default_corridor_scene()
        self.memory = SQLiteMemoryStore(memory_path)
        self.frontier_policy = FrontierPolicyName(frontier_policy)

    def run(self, trial_name: str) -> TrialResult:
        if trial_name == "discover_and_verify":
            return self._run_discover_and_verify()
        if trial_name == "reuse_same_start":
            return self._run_reuse("reuse_same_start", Pose2D(x=1.0, y=1.2, yaw=0.0))
        if trial_name == "reuse_different_start":
            return self._run_reuse("reuse_different_start", Pose2D(x=2.2, y=1.2, yaw=0.0))
        if trial_name == "missing_and_relocation":
            return self._run_missing_and_relocation()
        raise ValueError(f"unknown Phase 1A trial: {trial_name}")

    def _run_discover_and_verify(self) -> TrialResult:
        trial_id = "discover_and_verify"
        logger = TrialLogger(self.memory, trial_id)
        grid = build_corridor_grid(self.scene)
        full_grid = build_corridor_grid(self.scene, reveal_all=True)
        source = ConfigTruthObjectSource(self.scene)
        pose = Pose2D(x=1.0, y=1.2, yaw=0.0)
        path_length = 0.0
        elapsed = 0.0
        nav_goals = 0
        frontier_total = 0
        frontier_selected = 0
        observations: list[ObjectObservation] = []
        selected_frontier: FrontierPolicyCandidate | None = None

        for _ in range(8):
            grid.reveal_forward_sector(pose, self.scene.reveal_model)
            observations = source.observations_at(pose, grid)
            if observations:
                logger.record("object_observation", "target observed", {"pose": pose.model_dump()})
                break
            clusters = extract_frontier_clusters(grid)
            frontier_total += len(clusters)
            if not clusters:
                break
            try:
                selected_frontier = select_frontier_candidate(
                    grid=grid,
                    start_pose=pose,
                    frontiers=clusters,
                    policy=self.frontier_policy,
                )
            except ValueError:
                break
            goal = selected_frontier.viewpoint
            frontier_selected += 1
            nav_goals += 1
            pose, distance, ticks = self._navigate(pose, goal)
            path_length += distance
            elapsed += ticks
            logger.record(
                "frontier_selected",
                "selected frontier viewpoint",
                {
                    "goal": goal.model_dump(),
                    "policy": selected_frontier.policy.value,
                    "candidate_type": selected_frontier.candidate_type,
                    "information_gain": selected_frontier.information_gain,
                    "path_cost_m": selected_frontier.path_cost_m,
                    "revisit_penalty": selected_frontier.revisit_penalty,
                    "score": selected_frontier.score,
                },
            )

        if not observations:
            metrics = TrialMetrics(
                success=False,
                failure_reason="target_not_observed",
                final_state="failed",
                path_length_m=path_length,
                elapsed_time_s=elapsed,
                num_nav_goals=nav_goals,
                frontier_count_total=frontier_total,
                frontier_selected_count=frontier_selected,
                selected_candidate_types=(
                    [selected_frontier.candidate_type] if selected_frontier else []
                ),
                final_candidate_score=selected_frontier.score if selected_frontier else None,
            )
            return self._record_result(trial_id, metrics, logger)

        observation = observations[0]
        self.memory.upsert_object_from_observation(observation, MemoryState.OBSERVED)
        viewpoint = plan_verification_viewpoint(full_grid, self.scene.objects[0])
        nav_goals += 1
        pose, distance, ticks = self._navigate(pose, viewpoint)
        path_length += distance
        elapsed += ticks
        verification_observations = source.observations_at(viewpoint, full_grid)
        if verification_observations:
            self.memory.upsert_object_from_observation(
                verification_observations[0],
                MemoryState.REUSABLE,
                verification_viewpoint=viewpoint,
            )
            logger.record("verification", "target verified", {"viewpoint": viewpoint.model_dump()})
            success = True
            final_state = MemoryState.REUSABLE.value
            failure = None
        else:
            success = False
            final_state = "verification_failed"
            failure = "verification_failed"

        metrics = TrialMetrics(
            success=success,
            failure_reason=failure,
            final_state=final_state,
            path_length_m=path_length,
            elapsed_time_s=elapsed,
            num_nav_goals=nav_goals,
            frontier_count_total=frontier_total,
            frontier_selected_count=frontier_selected,
            time_to_first_observation_s=elapsed if observations else None,
            time_to_verify_s=elapsed if success else None,
            observation_count=len(observations) + len(verification_observations),
            verification_attempt_count=1,
            memory_reused=False,
            memory_query_count=1,
            memory_hit_count=0,
            memory_state_transition_count=2,
            selected_candidate_types=[
                selected_frontier.candidate_type if selected_frontier else "frontier",
                "object_verification",
            ],
            final_candidate_score=selected_frontier.score if selected_frontier else None,
        )
        return self._record_result(trial_id, metrics, logger)

    def _run_reuse(self, trial_id: str, start_pose: Pose2D) -> TrialResult:
        logger = TrialLogger(self.memory, trial_id)
        memories = self.memory.query_objects(
            class_name="water_dispenser",
            states=[MemoryState.REUSABLE],
            anchor_id=self.scene.anchor.anchor_id,
        )
        if not memories or memories[0].verification_viewpoint is None:
            metrics = TrialMetrics(
                success=False,
                failure_reason="no_reusable_memory",
                final_state="failed",
                memory_query_count=1,
            )
            return self._record_result(trial_id, metrics, logger)

        target = memories[0]
        pose, path_length, ticks = self._navigate(start_pose, target.verification_viewpoint)
        source = ConfigTruthObjectSource(self.scene)
        grid = build_corridor_grid(self.scene, reveal_all=True)
        observations = source.observations_at(pose, grid)
        if observations:
            self.memory.upsert_object_from_observation(
                observations[0],
                MemoryState.REUSABLE,
                verification_viewpoint=target.verification_viewpoint,
            )
            logger.record("memory_reuse", "reused verified target memory", {"object_id": target.object_id})
        metrics = TrialMetrics(
            success=bool(observations),
            failure_reason=None if observations else "verification_failed",
            final_state=MemoryState.REUSABLE.value if observations else "verification_failed",
            path_length_m=path_length,
            elapsed_time_s=ticks,
            num_nav_goals=1,
            observation_count=len(observations),
            verification_attempt_count=1,
            memory_reused=True,
            memory_query_count=1,
            memory_hit_count=1,
            selected_candidate_types=["memory"],
        )
        return self._record_result(trial_id, metrics, logger)

    def _run_missing_and_relocation(self) -> TrialResult:
        trial_id = "missing_and_relocation"
        logger = TrialLogger(self.memory, trial_id)
        memories = self.memory.query_objects(
            class_name="water_dispenser",
            states=[MemoryState.REUSABLE],
            anchor_id=self.scene.anchor.anchor_id,
        )
        if not memories or memories[0].verification_viewpoint is None:
            self._run_discover_and_verify()
            memories = self.memory.query_objects(
                class_name="water_dispenser",
                states=[MemoryState.REUSABLE],
                anchor_id=self.scene.anchor.anchor_id,
            )

        old_memory = memories[0]
        hidden_scene = self.scene.model_copy(deep=True)
        hidden_scene.objects[0].active = False
        hidden_source = ConfigTruthObjectSource(hidden_scene)
        grid = build_corridor_grid(hidden_scene, reveal_all=True)
        start = Pose2D(x=1.0, y=1.2, yaw=0.0)
        viewpoint = old_memory.verification_viewpoint
        assert viewpoint is not None
        pose, path_length, ticks = self._navigate(start, viewpoint)
        first_check = hidden_source.observations_at(pose, grid)
        memory_transitions = 0
        if not first_check:
            self.memory.update_object_state(old_memory.object_id, MemoryState.SUSPECT_MISSING)
            memory_transitions += 1
            logger.record("verification", "old target suspect missing", {"object_id": old_memory.object_id})

        yaw_scan_poses = [
            Pose2D(x=pose.x, y=pose.y, yaw=viewpoint.yaw - math.radians(25)),
            Pose2D(x=pose.x, y=pose.y, yaw=viewpoint.yaw + math.radians(25)),
        ]
        second_check = [
            observation
            for scan_pose in yaw_scan_poses
            for observation in hidden_source.observations_at(scan_pose, grid)
        ]
        missing_success = not first_check and not second_check
        if missing_success:
            self.memory.update_object_state(old_memory.object_id, MemoryState.MISSING)
            memory_transitions += 1
            logger.record("memory_mutation", "old target marked missing", {"object_id": old_memory.object_id})

        moved_scene = self.scene.model_copy(deep=True)
        moved_object = moved_scene.objects[0]
        moved_object.object_id = "water_dispenser_002"
        moved_object.pose_map = Pose2D(x=10.0, y=0.25, yaw=moved_object.pose_map.yaw)
        moved_source = ConfigTruthObjectSource(moved_scene)
        moved_grid = build_corridor_grid(moved_scene, reveal_all=True)
        moved_viewpoint = plan_verification_viewpoint(moved_grid, moved_object)
        moved_observations = moved_source.observations_at(moved_viewpoint, moved_grid)
        relocation_recorded = False
        if moved_observations:
            self.memory.upsert_object_from_observation(
                moved_observations[0],
                MemoryState.REUSABLE,
                verification_viewpoint=moved_viewpoint,
            )
            self.memory.add_relation(
                source_object_id=moved_object.object_id,
                target_object_id=old_memory.object_id,
                relation_type="possible_relocation_of",
            )
            relocation_recorded = True
            memory_transitions += 1
            logger.record("relocation", "new target linked to missing target", {})

        metrics = TrialMetrics(
            success=missing_success and relocation_recorded,
            failure_reason=None if missing_success and relocation_recorded else "relocation_failed",
            final_state=MemoryState.REUSABLE.value if relocation_recorded else "failed",
            path_length_m=path_length,
            elapsed_time_s=ticks,
            num_nav_goals=1,
            observation_count=len(moved_observations),
            verification_attempt_count=2,
            failed_viewpoint_count=1 if missing_success else 0,
            memory_reused=True,
            memory_query_count=1,
            memory_hit_count=1,
            memory_state_transition_count=memory_transitions,
            stale_recheck_count=1,
            missing_detection_success=missing_success,
            relocation_recorded=relocation_recorded,
            selected_candidate_types=["memory", "yaw_scan", "relocation"],
        )
        return self._record_result(trial_id, metrics, logger)

    def _navigate(self, start_pose: Pose2D, goal_pose: Pose2D) -> tuple[Pose2D, float, float]:
        navigator = DiscreteStepNavigationClient(start_pose=start_pose)
        navigator.send_goal(goal_pose)
        ticks = 0
        while ticks < 200 and navigator.status.value == "ACTIVE":
            navigator.tick(1.0)
            ticks += 1
        return navigator.current_pose, navigator.path_length_m, float(ticks)

    def _record_result(
        self,
        trial_id: str,
        metrics: TrialMetrics,
        logger: TrialLogger,
    ) -> TrialResult:
        self.memory.record_trial_metrics(trial_id, metrics)
        return TrialResult(trial_id=trial_id, metrics=metrics, events=logger.events)
