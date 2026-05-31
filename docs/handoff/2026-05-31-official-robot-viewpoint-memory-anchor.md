# Handoff: Official Robot Viewpoint Memory Anchor

Date: 2026-05-31
Owner: Codex
Status: Needs Next Method Step

## Current State

Implemented an offline anchor-quality diagnostic and a new official discovery
`anchor_mode=robot_viewpoint`.

The diagnostic confirmed:

- fixed projected DINO anchors now carry exact episode ids;
- projected anchors remain meters from detector-positive viewpoint references;
- raw robot-pose-at-first-detection anchors are also meters away and still
  produce `0/4` with the oracle TargetNav backend;
- the next method should store robot/viewpoint poses only after a detector
  approach or confirmation phase, not at the first raw detection.

## Files Touched

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_memory_anchor_quality.py`
- `src/objectnav_core/objectnav_core/cli/report_habitat_official_memory_anchor_quality.py`
- `src/objectnav_core/objectnav_core/evaluation/official_episode_memory.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_official_memory_discovery.py`
- `src/objectnav_core/objectnav_core/cli/run_habitat_official_memory_discovery.py`
- `src/objectnav_core/tests/test_habitat_official_memory_anchor_quality.py`
- `src/objectnav_core/tests/test_official_episode_memory.py`
- `src/objectnav_core/tests/test_habitat_official_memory_discovery.py`
- `src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py`
- `src/objectnav_core/tests/test_ros_packaging.py`
- `src/objectnav_core/setup.py`
- `docs/design/2026-05-31-official-memory-anchor-quality-diagnostic.md`
- `docs/design/2026-05-31-official-robot-viewpoint-memory-anchor.md`
- `docs/experiments/2026-05-31-official-memory-anchor-quality-diagnostic.md`
- `docs/devlog/2026-05.md`

## Commands Run

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_official_episode_memory.py src/objectnav_core/tests/test_habitat_official_memory_discovery.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_memory_anchor_quality.py src/objectnav_core/tests/test_habitat_official_detector_viewpoint_memory_prior.py src/objectnav_core/tests/test_grounding_dino_adapter.py src/objectnav_core/tests/test_ros_packaging.py -q

python3 -m compileall -q src/objectnav_core/objectnav_core/evaluation/official_episode_memory.py src/objectnav_core/objectnav_core/evaluation/habitat_official_memory_discovery.py src/objectnav_core/objectnav_core/evaluation/habitat_official_memory_anchor_quality.py src/objectnav_core/objectnav_core/cli/run_habitat_official_memory_discovery.py src/objectnav_core/objectnav_core/cli/report_habitat_official_memory_anchor_quality.py

git diff --check

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m pytest src/objectnav_core/tests/test_official_episode_memory.py src/objectnav_core/tests/test_habitat_official_memory_discovery.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_memory_anchor_quality.py src/objectnav_core/tests/test_ros_packaging.py -q'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m objectnav_core.cli.run_habitat_official_memory_discovery --output runs/habitat_official_objectnav/grounding_dino_discovery_prior_alias_episode_ids_4ep_100steps_20260531_v1 --max-episodes 4 --max-steps 100 --detector grounding_dino --grounding-dino-max-image-side 384 --min-detection-confidence 0.25'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m objectnav_core.cli.run_habitat_official_memory_discovery --output runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_prior_4ep_100steps_20260531_v1 --max-episodes 4 --max-steps 100 --detector grounding_dino --grounding-dino-max-image-side 384 --min-detection-confidence 0.25 --anchor-mode robot_viewpoint'
```

## Verification

Passed:

- Local focused tests: `36 passed`.
- Local compileall: clean.
- Local `git diff --check`: clean before docs updates.
- Remote focused tests: `25 passed`.
- Remote compileall: clean.
- Fixed projected prior quality reports:
  - vs viewpoint prior: nearest mean error `5.050678 m`, selected mean error
    `5.197824 m`, nearest-good `0/4`;
  - vs oracle prior: nearest mean error `5.657046 m`, selected mean error
    `5.798235 m`, nearest-good `1/4`.
- Robot-viewpoint prior quality reports:
  - vs viewpoint prior: nearest mean error `6.378549 m`, selected mean error
    `6.742113 m`, nearest-good `0/4`;
  - vs oracle prior: nearest mean error `5.049185 m`, selected mean error
    `5.398587 m`, nearest-good `0/4`.
- Robot-viewpoint prior + oracle TargetNav backend:
  SR `0/4`, SPL `0.0`, SoftSPL `0.0`, mean distance-to-goal
  `5.950337052345276`.

Not run:

- Full local test suite.
- Larger Habitat split.
- Query with a detector-injected local servo policy.
- Any real robot, ROS 2, or SLAM integration.

## Known Risks

- `robot_viewpoint` anchors currently store only x/z position, not heading,
  bearing, bbox, or local visual evidence in the memory prior.
- The current exploration policy often detects while rotating near the start
  pose, so first-detection robot poses are not good enough memory anchors.
- The oracle TargetNav query does not include the future visual servo stage
  the user described, so the `0/4` result is a diagnostic lower-bound for this
  incomplete method.
- The quality report is prior-only; it does not yet validate navigability,
  visibility, or floor correctness.

## Next Recommended Action

Implement a detector-confirmed approach stage:

1. When discovery sees the target, use bbox center/depth only as local control
   evidence.
2. Center the object and move to a stand-off distance or until confidence/area
   stabilizes.
3. Store the reached robot pose as the `robot_viewpoint` memory anchor.
4. Re-run anchor quality vs detector-positive viewpoints and query with both
   oracle TargetNav and detector-injected local servo.

This is the clean bridge from the privileged detector-positive viewpoint
diagnostic to a non-privileged, robot-deployable memory representation.
