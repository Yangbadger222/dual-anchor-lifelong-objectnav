# Handoff: Usability-Centered Lifelong Object Memory

Date: 2026-05-26  
Owner: Codex  
Status: First Stress Harness and 2D Trace Generator Implemented; Ready for Review

## Current State

The algorithmic research direction has been rewritten from "dual-anchor alignment as the main contribution" to "usability-centered lifelong object memory."

The new direction treats long-term memory as useful for ObjectNav only when it is likely to be navigable, confirmable, and not repeatedly contradicted by task evidence. It explicitly separates:

- `P_existence`: object may still exist
- `P_location_valid`: remembered location may still be correct
- `P_usable`: memory is worth using for navigation decisions

The design does not claim to prove object disappearance. It instead retires memories from default navigation decisions when they become persistently unverifiable, inaccessible, low-value, or contradictory.

The real-vehicle boundary is now explicit:

- `/Users/badger/Desktop/dual-anchor-lifelong-objectnav` owns the algorithm core, deterministic simulation, trace replay, metrics, reports, and paper experiments.
- `/Users/badger/Desktop/XJTLU-autonomous-vehicle` owns the live robot stack, RTK, RGB-D camera integration, FAST-LIO2/PGO/Nav2 runtime, rosbag collection, and final small live-robot closure.

The design document now lists concrete XJTLU launch modes and topics that should feed future trace replay.

A first ROS-free implementation slice now exists in `src/objectnav_core`. It implements the belief split, evidence updates, expected-cost decision policy, and a fixed-seed stress runner for pre-robot testing.

The first stress run exposed and fixed a decision-cost pathology: `B_remaining` must not clip each failed branch with `min(...)`, because that makes likely failure look cheap when the robot is nearly out of budget. It is now treated as a feasibility constraint/diagnostic rather than as the expected-cost cap.

A lightweight 2D grid trace generator now adds the next pre-Habitat layer. It emits sequential trace rows with pose, evidence, true/nearest/JPDA-lite association fields, path-blocked flags, cached/fresh costs, inflation flags, beliefs, and decisions. Habitat and XJTLU bag converters should target this same event shape later.

## Files Touched

- `docs/design/2026-05-26-usability-centered-lifelong-object-memory.md`
- `docs/design/2026-05-26-usability-centered-lifelong-object-memory.zh.html`
- `docs/design/2026-05-26-2d-grid-trace-generator.md`
- `docs/devlog/2026-05.md`
- `docs/experiments/2026-05-26-2d-grid-trace-generator.md`
- `docs/experiments/2026-05-26-usability-memory-stress-harness.md`
- `docs/handoff/2026-05-26-usability-centered-lifelong-object-memory.md`
- `README.md`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/objectnav_core/cli/run_grid_trace_experiment.py`
- `src/objectnav_core/objectnav_core/cli/run_usability_stress.py`
- `src/objectnav_core/objectnav_core/evaluation/grid_trace_experiment.py`
- `src/objectnav_core/objectnav_core/evaluation/usability_stress.py`
- `src/objectnav_core/objectnav_core/memory/usability.py`
- `src/objectnav_core/tests/test_grid_trace_experiment.py`
- `src/objectnav_core/tests/test_ros_packaging.py`
- `src/objectnav_core/tests/test_usability_memory.py`
- `src/objectnav_core/tests/test_usability_stress.py`

## Commands Run

```bash
git status --short --branch
sed -n '1,220p' docs/templates/design_doc.md
sed -n '1,220p' docs/templates/devlog_entry.md
sed -n '1,220p' docs/templates/handoff.md
sed -n '1,220p' docs/design/2026-05-25-dual-anchor-lifelong-objectnav-architecture.zh.html
tail -n 80 docs/devlog/2026-05.md
sed -n '1,180p' /Users/badger/Desktop/XJTLU-autonomous-vehicle/scripts/data_collection/record_bag.sh
sed -n '100,150p' /Users/badger/Desktop/XJTLU-autonomous-vehicle/src/bringup/launch/system_gps_corridor.launch.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_usability_memory.py src/objectnav_core/tests/test_usability_stress.py src/objectnav_core/tests/test_ros_packaging.py -q
python3 -m compileall -q src/objectnav_core/objectnav_core
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests -q
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_usability_stress --output runs/usability_stress/latest --seed 13 --monte-carlo-runs 200
git rev-parse --short HEAD
python3 --version
uname -a
python3 -m json.tool runs/usability_stress/latest/summary.json
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_usability_memory.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_grid_trace_experiment.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_grid_trace_experiment --output runs/grid_trace/latest --seed 17 --episodes 100000 --steps-per-episode 8
find runs/grid_trace/latest -maxdepth 1 -type f -print | sort
python3 -m json.tool runs/grid_trace/latest/summary.json
sed -n '1,8p' runs/grid_trace/latest/events.csv
wc -l runs/grid_trace/latest/events.csv
du -h runs/grid_trace/latest/events.csv runs/grid_trace/latest/summary.json runs/grid_trace/latest/trace_report.html
```

Verification commands are listed in the Verification section.

## Verification

Passed:

- Focused usability, stress-runner, and packaging tests passed before the budget-clipping fix: 10 tests.
- A regression test for the budget-clipped trust sample failed before the fix with `DecisionType.TRUST`, then passed after the expected-cost correction.
- Focused usability tests passed after the fix: 9 tests.
- Core test suite passed after the fix: 31 tests.
- Python compile check passed for `src/objectnav_core/objectnav_core`.
- The fixed-seed stress runner wrote `runs/usability_stress/latest/summary.json`, `runs/usability_stress/latest/decision_boundary.csv`, and `runs/usability_stress/latest/stress_report.html`.
- Stress-run summary for seed `13`, 200 Monte Carlo runs after the budget-clipping fix: trust `6`, verify `19`, search `136`, retire `39`.
- The problematic `P_v=0.0324` sample now has `cost_trust=76.22`, `cost_verify=58.52`, `cost_search=57.59`, and no longer chooses trust.
- 2D grid trace tests passed: 2 tests.
- Packaging test passed after adding `objectnav_grid_trace_experiment`: 1 test.
- The fixed-seed 2D trace run wrote `runs/grid_trace/latest/summary.json`, `runs/grid_trace/latest/events.csv`, and `runs/grid_trace/latest/trace_report.html`.
- 2D trace summary for seed `17`, 100000 episodes, 8 steps per episode: 800000 events; decisions trust `200798`, verify `336952`, search `130948`, retire `131302`.
- 2D trace decision rates: trust `0.2510`, verify `0.4212`, search `0.1637`, retire `0.1641`.
- 2D trace evidence counts: positive `170199`, non-confirmation `160966`, unknown `171493`, occluded `122221`, access-blocked `119566`, free `44444`, scene-changed `11111`.
- 2D path-cost metrics: inflation-blocked events `155554`, stale-cost events `88888`, decision flips after refresh `133269`, stale cache error rate `0.875`, mean cached-to-fresh cost ratio `15.7189`.
- 2D association metrics: association events `177776`, nearest-neighbor wrong associations `22222`, JPDA-lite rejected ambiguous events `44444`, ghost positive writes prevented `22222`, nearest-neighbor wrong-association rate `0.125`, mean association margin `0.6336`.
- `runs/grid_trace/latest/events.csv` has 800001 lines including the header and is about 288 MB.
- Synthetic scenario outcomes matched expectations: ghost memory retired, false-deletion guard recovered after positive evidence, and quarantined negative evidence left belief unchanged.
- The design Markdown includes the required design-template sections: goal, non-goals, background, system boundary, inputs and outputs, interfaces, data flow, failure modes, verification plan, research relevance, and open questions.
- The Markdown now contains the XJTLU real-vehicle interface section with launch modes, topic groups, future RGB-D/detector interfaces, and `TraceEvent`.
- Text search confirmed the HTML contains the XJTLU interface section and MathJax configuration.
- Placeholder scan found no unresolved template markers in the new design, HTML, or this handoff.

Not run:

- No ROS 2, Nav2, simulation, or replay tests were run for the stress harness because it is intentionally ROS-free.
- No real RGB-D, RTK, detector, or robot logs were used.
- No browser render screenshot was captured for the HTML page.
- No post-update browser/HTML rendering check was run because the user requested not to check HTML rendering.
- An earlier lightweight HTML parser/anchor check passed before the later XJTLU/MathJax update, but it was not repeated after the user requested no HTML checks.

## Known Risks

- The design is only partially implemented. The first deterministic slice exists, but trace replay, detector/depth evidence extraction, data association stress, path-cost cache invalidation, and robot integration are still missing.
- The 2D trace generator is statistical and deliberately not sensor-realistic. It should not be used as paper evidence without Habitat and real-bag replay.
- The 100000-episode CSV is large. Keep generated `runs/*` artifacts ignored unless a specific result is intentionally archived.
- `P_usable` update weights and event magnitudes are currently engineering priors; they must be validated against replay, not tuned only by intuition.
- Cheap verification before global search is still not fully modeled. After the budget-clipping fix, a very low-`P_v` sample may correctly avoid trust but choose search over verify under pure expected task cost. If opportunistic verification is desired, its memory-maintenance value must be modeled explicitly.
- Real RGB-D logs may show that FREE evidence is extremely rare, so non-confirmation and access-blocked retirement must be implemented early.
- The path-cost cache invalidation design depends on costmap revision/change tracking that does not yet exist in the core.
- Detector output, depth ROI evidence, and local visibility classification are not represented in the current `ObjectObservation` schema.
- The older dual-anchor HTML design remains untracked and should be either superseded, tracked, or removed deliberately in a separate cleanup decision.
- MathJax formula rendering in the HTML uses an external CDN; local offline viewing will show raw TeX if the CDN is unavailable unless a vendored renderer is added later.
- XJTLU camera and detector topic names are expected names. Final names must be confirmed after RTK and the depth camera are installed.

## Next Recommended Step

1. Decide whether cheap verification before search should be a separate opportunistic-maintenance action, and if yes add an explicit cost/value term.
2. Replace the hand-coded JPDA-lite margin gate with trace-calibrated association likelihoods.
3. Add a true multi-hypothesis buffer for unresolved observations instead of only rejecting ambiguous observations.
4. Sweep inflation radius, cache refresh thresholds, and opportunistic verification value.
5. Define a Habitat converter that outputs the same trace columns from noisy depth and semantic observations.
6. Define a real RGB-D/pose/costmap trace schema that converts XJTLU robot logs into the same event shape.
7. Once RTK and the depth camera are ready in the XJTLU repository, record short bags and replay them through the ROS-free harness before live ObjectNav closure.
8. Keep generated `runs/*/latest/` outputs reproducible but untracked unless a specific result should be archived as a formal artifact.

## Context for Next Contributor

Do not start by integrating GroundingDINO, RTK, or live Nav2 into this new method. The next useful step is to make the ROS-free implementation harsher: attack association, depth failure, stale path cost, and long-horizon garbage collection before connecting it to real logs.

The intended paper claim is not "we know whether an object exists." The claim is:

> We maintain long-term object memories according to their ObjectNav usability under unreliable perception, reducing false writes, false deletion, and repeated wasted navigation.

Keep dual-anchor support as infrastructure. It should affect geometry and cross-session reuse, but it should not be the method's main novelty.
