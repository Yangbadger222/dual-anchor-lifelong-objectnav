# Experiment Report: 2D Grid Trace Generator

Date: 2026-05-26  
Owner: Codex  
Status: Completed

## Question

Can a lightweight 2D statistical grid trace generate sequential evidence events and replay them through the usability-memory algorithm before Habitat or real robot logs are ready?

## Hypothesis

A fixed-seed trace should cover the core event families needed for the next algorithm iteration:

- stable visible memories should remain usable and often be trusted
- removed or moved memories should lose usability and retire
- occluded memories should avoid false deletion and recover after positive evidence
- blocked access should reduce usability and retire
- quarantined OOD depth failures should not corrupt belief
- nearby same-class ambiguity should expose association pressure through `association_candidates`
- inflated corridor blockage should make path cost rise even when the obstacle body does not intersect the path centerline
- stale path-cost cache should expose stale-vs-refreshed decision flips
- multi-object association replay should show how often nearest-neighbor association would attach positive evidence to the wrong memory, and how often a JPDA-lite gate rejects ambiguous or false-positive observations

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, base commit `e828e1f`, with uncommitted implementation changes |
| Machine | macOS Darwin arm64 |
| Dataset / bag / map | Synthetic 2D statistical trace |
| Simulator / robot | None |
| Key parameters | seed `17`, episodes `100000`, steps per episode `8` |
| Python | `Python 3.13.12` |

## Command

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_grid_trace_experiment --output runs/grid_trace/latest --seed 17 --episodes 100000 --steps-per-episode 8
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Total events | 800000 | 100000 episodes x 8 steps |
| Positive evidence | 170199 | Stable/revealed/ambiguous targets |
| Non-confirmation evidence | 160966 | Removed, stale, and ambiguous targets |
| Unknown evidence | 171493 | Occlusion, OOD, stale, and ambiguity |
| Occluded evidence | 122221 | Occluded/revealed, blocked, and inflated scenarios |
| Access-blocked evidence | 119566 | Blocked, stale, inflated, and removed scenarios |
| Quarantined OOD events | 88888 | `ood_depth_failure` scenario |
| Trust decisions | 200798 | Rate `0.2510` |
| Verify decisions | 336952 | Rate `0.4212` |
| Search decisions | 130948 | Rate `0.1637` |
| Retire decisions | 131302 | Rate `0.1641` |
| Inflation-blocked events | 155554 | Includes inflated corridor and stale path-cost scenarios |
| Stale-cost events | 88888 | `stale_path_cost` scenario |
| Decision flips after refresh | 133269 | Stale/cached decision changed after fresh cost |
| Stale cache error rate | 0.8750 | Fraction of stale-cost events where stale decision was misleading |
| Mean cached-to-fresh cost ratio | 15.7189 | Fresh path costs were much larger than cached costs |
| Association events | 177776 | Multi-candidate same-class observations |
| Nearest-neighbor wrong associations | 22222 | Forced nearest assignment would update the wrong memory |
| JPDA-lite rejected ambiguous events | 44444 | Ambiguous or false-positive observations left unassigned |
| Ghost positive writes prevented | 22222 | False positives that nearest-neighbor would have written |

## Scenario Results

| Scenario | Final `p_usable` | Final decision | Notes |
|---|---:|---|---|
| `stable_visible` | 0.9789 | trust | Repeated positive evidence preserved high validity. |
| `removed_or_moved` | 0.0646 | retire | Non-confirmation and scene-change evidence retired the memory. |
| `occluded_then_revealed` | 0.9083 | verify | Positive recovery prevented false deletion. |
| `blocked_access` | 0.0921 | retire | Access blockage made the memory unusable for default navigation. |
| `ood_depth_failure` | 0.9000 | verify | Quarantined events left belief unchanged. |
| `nearby_same_class` | 0.5682 | verify | Ambiguity produced up to 3 association candidates. |
| `inflated_corridor_block` | 0.0654 | retire | Inflation blocked the path even when the obstacle body did not intersect the path centerline. |
| `stale_path_cost` | 0.1687 | retire | Refreshing path cost caused 77777 decision flips in this scenario. |
| `multi_object_association` | 0.7509 | trust | JPDA-lite rejected 44444 ambiguous events and prevented 22222 ghost positive writes. |

## Observations

- The trace generator now exercises sequential belief and decision behavior rather than isolated single-step formulas.
- OOD quarantine behaved as intended: even FREE-like events did not damage belief when marked quarantined.
- Removed and blocked cases retired through low usability without needing a strong physical disappearance claim.
- Inflation, stale-cache, and association cases changed the decision mix substantially. Verify is still the largest class, but search and retire remain meaningful and trust rises when association confidence is strong.
- The generated `events.csv` contains 800001 lines including the header and is about 288 MB, so it should remain ignored under `runs/`.

## Result

The 2D trace generator is suitable as the first pre-Habitat Monte Carlo logic layer. It should still be treated as adversarial synthetic testing, not as sensor-realistic validation or a paper benchmark.

## Follow-up

- Use Habitat depth noise and real XJTLU bags to replace hand-set event probabilities.
- Add parameter sweeps for obstacle inflation radius, cache refresh threshold, and opportunistic verification value.
- Replace JPDA-lite gate constants with learned or trace-calibrated association likelihoods once real logs exist.
