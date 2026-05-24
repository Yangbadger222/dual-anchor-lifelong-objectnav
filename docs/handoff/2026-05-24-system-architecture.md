# Handoff: Hardware-Independent ObjectNav Architecture

Date: 2026-05-24  
Owner: Codex  
Status: Ready for Implementation

## Current State

The initial architecture for Dual-Anchor Lifelong Semantic ObjectNav has been formalized.

The design intentionally separates the system into:

1. hardware-independent ObjectNav core
2. replay and simulation harness
3. ROS 2 robot adapters

The Phase 1A direction has been refined through design discussion:

- design remains dual-anchor compatible
- implementation starts with indoor-only `indoor_map`
- first target is a wall-adjacent indoor `water_dispenser`
- first scene is `straight_corridor_one_water_dispenser`
- camera assumption is fixed front-facing
- navigation uses a verification viewpoint, not the object center
- Phase 1A includes memory reuse, stale, missing, and relocation evidence
- first map fixture is a partially unknown straight corridor with forward-sector reveal
- frontier goals are reachable known-free viewpoints, not raw frontier centroids
- first navigation backend is deterministic discrete stepping behind a replaceable `NavigationClient`
- core package should be `objectnav_core` with Pydantic models and no ROS imports
- memory uses SQLite as primary storage and JSON snapshots for debug/export
- trial logging records key events plus candidate scores at each replan, not every tick
- missing requires two failed checks, with the second check using in-place yaw scan
- related-work positioning is now explicit: OK-Robot, GOAT, 3D-Mem, DynaMem, OpenIN, SCOPE, R2F, SysNav, TrajRAG, and NavFoM are treated as nearby frontier work
- the main research gap is framed as trustworthy lifelong ObjectNav memory under stale objects, missing targets, coordinate-anchor uncertainty, and hardware-independent transfer
- learned detector/VLM/VLA integration is intentionally delayed until after deterministic Phase 1A and replay-based perception evaluation

The Chinese HTML reading version is available for quick review. No runtime code has been implemented yet.

## Files Touched

- `docs/design/2026-05-24-system-architecture.md`
- `docs/design/2026-05-24-system-architecture.zh.html`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-24-system-architecture.md`

## Commands Run

```bash
git status --short --branch
sed -n '1,220p' AGENTS.md
sed -n '1,220p' docs/templates/design_doc.md
sed -n '1,220p' docs/templates/handoff.md
sed -n '238,463p' /Users/badger/Desktop/car/vlm_architecture_routes.html
sed -n '464,690p' /Users/badger/Desktop/car/vlm_architecture_routes.html
sed -n '1099,1378p' /Users/badger/Desktop/car/vlm_architecture_routes.html
rg -n "^## |^### " docs/design/2026-05-24-system-architecture.md
test -f docs/design/2026-05-24-system-architecture.md && test -f docs/design/2026-05-24-system-architecture.zh.html && test -f docs/devlog/2026-05.md && printf 'required docs present\n'
python3 - <<'PY'
from html.parser import HTMLParser
from pathlib import Path

path = Path('docs/design/2026-05-24-system-architecture.zh.html')
html = path.read_text(encoding='utf-8')

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.hrefs = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'a' and 'href' in attrs:
            self.hrefs.append(attrs['href'])

parser = Parser()
parser.feed(html)
missing = [href for href in parser.hrefs if href.startswith('#') and href[1:] not in parser.ids]
external = [href for href in parser.hrefs if not href.startswith('#')]
print(f'html parsed: {path}')
print(f'ids: {len(parser.ids)}')
print(f'anchor hrefs: {len(parser.hrefs)}')
print(f'missing internal anchors: {missing}')
print(f'external links: {external}')
if missing or external:
    raise SystemExit(1)
PY
rg --pcre2 -n "\[[^\]]+\]\(|href=\"(?!#)" docs/design/2026-05-24-system-architecture.md docs/design/2026-05-24-system-architecture.zh.html
wc -l docs/design/2026-05-24-system-architecture.md docs/design/2026-05-24-system-architecture.zh.html docs/devlog/2026-05.md
rg -n "Pending|TODO|FIXME|<Title>|YYYY-MM-DD|<name|placeholder" docs/design/2026-05-24-system-architecture.md docs/design/2026-05-24-system-architecture.zh.html docs/devlog/2026-05.md
python3 - <<'PY'
from urllib.request import urlopen
from html.parser import HTMLParser
ids = ['2401.12202','2311.06430','2411.17735','2411.04999','2501.04279','2511.08935','2603.08475','2603.06914','2605.01700','2509.12129']
class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title = ''
    def handle_starttag(self, tag, attrs):
        if tag == 'title':
            self.in_title = True
    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
    def handle_data(self, data):
        if self.in_title:
            self.title += data
for arxivid in ids:
    html = urlopen(f'https://arxiv.org/abs/{arxivid}', timeout=10).read().decode('utf-8', 'ignore')
    p = P()
    p.feed(html)
    print(arxivid, p.title.strip().replace('\n', ' '))
PY
```

Attempted through the Node REPL:

```javascript
const { chromium } = await import('playwright');
```

This failed because `playwright` is not installed in the local Node environment.

## Verification

Passed:

- The design doc contains the required template sections: goal, non-goals, system boundary, inputs and outputs, interfaces, data flow, failure modes, verification plan, and research relevance.
- Required files exist.
- The HTML reading page parsed with Python's `HTMLParser`.
- All internal navigation anchors in the HTML page resolve to matching section ids.
- Related-work arXiv links were checked by fetching their page titles.
- The design Markdown and HTML page now contain intentional external arXiv links in the related-work section.

Noted:

- `xmllint --html --noout` reports HTML5 semantic tags such as `header`, `nav`, `section`, and `article` as invalid because it checks with older HTML parser rules. The page is still standard HTML5, and Python parsing plus anchor validation passed.

Not run:

- No runtime code tests, ROS 2 build, replay run, or robot test were run because this task only created documentation.
- No browser screenshot/render check was completed because the local Node REPL does not have `playwright` installed.

## Known Risks

- The architecture is still a design, not an implemented package.
- The exact first implementation layout is open: pure Python package, `ament_python` package with ROS-free inner modules, or a hybrid.
- The project still needs the `straight_corridor_one_water_dispenser_unknown` fixture and a water-dispenser fake-object trial harness before algorithm claims can be made.
- The future adapter layer must be reviewed carefully so real-robot topic names, launch paths, camera choices, and map paths do not leak into the core.
- Phase 1A includes missing and relocation behavior, so implementation must keep state transitions testable and avoid overfitting to one scripted run.
- Related work already covers semantic memory and foundation-model ObjectNav. The paper claim should not be "semantic memory for ObjectNav" by itself; it should emphasize dual-anchor lifelong memory repair, auditable verification, and hardware-independent transfer.
- Adding models too early risks hiding state-machine, memory, and anchor bugs behind perception noise.

## Next Recommended Step

1. Write an implementation plan for Phase 1A: deterministic indoor water-dispenser ObjectNav closed loop.
2. Decide the initial package layout and testing toolchain.
3. Implement the smallest testable path: Pydantic scene config, grid fixture, forward-sector reveal, frontier extraction, reachable frontier viewpoint selection, visibility-triggered fake water-dispenser source, verification viewpoint planner, SQLite memory store, state machine, trial logger, and metrics.
4. Add experiment report templates for the first baseline runs only after the closed loop is executable.

## Context for Next Contributor

The user wants the system developed away from the physical vehicle first, then integrated with the real robot after offline and replay verification. Preserve that boundary aggressively.

The first implementation should prove the architecture with fake targets before adding YOLO, VLM, RTK, or live Nav2 integration.

Model integration should start as offline/replay adapters, not as direct real-time control logic. Large-model calls should remain event-driven or low-frequency unless a future experiment proves otherwise.
