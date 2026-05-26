# Handoff: Habitat-Sim Usability Memory Replay

Date: 2026-05-26  
Owner: Codex  
Status: Ready for Implementation

## Current State

The next Habitat-Sim step has been documented but not implemented. The repository now has a `docs/simulation/` area, a detailed Chinese HTML operation guide, and a repository file-management policy covering Habitat datasets, third-party clones, and generated artifacts.

No Habitat code was added and no simulator was run in this task.

## Files Touched

- `README.md`
- `.gitignore`
- `docs/README.md`
- `docs/repository-file-management.md`
- `docs/design/2026-05-26-habitat-sim-usability-replay.md`
- `docs/simulation/README.md`
- `docs/simulation/2026-05-26-habitat-sim-usability-memory.zh.html`
- `docs/handoff/2026-05-26-habitat-sim-usability-replay.md`
- `docs/devlog/2026-05.md`

## Commands Run

```bash
git status --short --branch
find . -maxdepth 3 -type f | sed 's#^./##' | sort | head -240
find docs -maxdepth 3 -type f | sort
find src -maxdepth 5 -type f | sort
find . -name '.DS_Store' -delete
find . -type d -name '__pycache__' -prune -exec rm -rf {} +
rm -rf .pytest_cache
git check-ignore -v .DS_Store docs/.DS_Store src/.DS_Store runs/.DS_Store runs/grid_trace/latest/events.csv runs/localization_bag_audit/latest/summary.json datasets/habitat/foo.glb third_party/habitat-sim/foo
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests -q
python3 -m compileall -q src/objectnav_core/objectnav_core
```

## Verification

- Full core pytest: 37 tests passed.
- Python compile check: exited successfully.
- File existence checks passed for the HTML guide, repository management doc, design doc, handoff, and implementation plan.
- Cache cleanup was repeated after verification; `.DS_Store`, `__pycache__`, and `.pytest_cache` counts were zero.

The user explicitly said not to check HTML rendering, so no browser/render validation is expected.

## Known Risks

- Habitat-Sim install commands can change; the HTML document points to official Habitat docs and keeps commands as a project-side operating plan.
- Mac support may be fragile for Habitat-Sim. Linux + NVIDIA GPU remains the safer execution target.
- The first Habitat stage should use oracle semantic evidence to isolate algorithm behavior. Detector integration should be a later ablation.
- Dataset paths and scene assets must stay ignored.

## Next Recommended Step

1. Decide execution machine: local Mac if Habitat-Sim installs cleanly, otherwise Linux/NVIDIA.
2. Create the `objectnav-habitat` conda environment.
3. Download one small Replica or ReplicaCAD scene outside git.
4. Implement a no-Habitat unit-tested trace schema before importing Habitat.
5. Run a 20-episode smoke before larger Monte Carlo.

## Context for Next Contributor

The intended target CLI is documented in `docs/design/2026-05-26-habitat-sim-usability-replay.md`. Keep Habitat dependencies optional so `objectnav_core` tests still run on machines without ROS or Habitat.
