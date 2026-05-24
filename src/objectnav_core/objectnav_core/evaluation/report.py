from __future__ import annotations

import json
import sqlite3
from html import escape
from pathlib import Path
from typing import Any


def generate_phase1a_report(artifact_dir: str | Path) -> Path:
    artifact_path = Path(artifact_dir)
    summary = _read_json(artifact_path / "summary.json")
    memory_snapshot = _read_json(artifact_path / "memory_snapshot.json")
    events = _read_events(artifact_path / "events.jsonl")
    persisted_metrics = _read_persisted_trial_metrics(artifact_path / "memory.sqlite")

    html = _render_report(
        summary=summary,
        memory_snapshot=memory_snapshot,
        events=events,
        persisted_metrics=persisted_metrics,
    )
    report_path = artifact_path / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return report_path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_persisted_trial_metrics(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        with sqlite3.connect(path) as connection:
            rows = connection.execute(
                """
                SELECT trial_id, metrics_json
                FROM trial_metrics
                ORDER BY trial_id
                """
            ).fetchall()
    except sqlite3.OperationalError:
        return {}
    return {trial_id: json.loads(metrics_json) for trial_id, metrics_json in rows}


def _render_report(
    summary: dict[str, Any],
    memory_snapshot: dict[str, Any],
    events: list[dict[str, Any]],
    persisted_metrics: dict[str, dict[str, Any]],
) -> str:
    runs = summary["runs"]
    objects = memory_snapshot.get("objects", [])
    relations = memory_snapshot.get("relations", [])
    frontier_events = [event for event in events if event.get("event_type") == "frontier_selected"]
    success_count = sum(1 for run in runs if run["metrics"].get("success"))
    max_path = max((run["metrics"].get("path_length_m", 0.0) for run in runs), default=1.0) or 1.0

    run_rows = "\n".join(_render_run_row(run) for run in runs)
    path_rows = "\n".join(_render_path_bar(run, max_path) for run in runs)
    object_rows = "\n".join(_render_object_row(obj) for obj in objects)
    relation_rows = "\n".join(_render_relation_row(relation) for relation in relations)
    frontier_rows = "\n".join(_render_frontier_row(event) for event in frontier_events)
    artifact_rows = "\n".join(
        _render_artifact_row(name, filename)
        for name, filename in summary.get("artifact_files", {}).items()
    )
    persisted_rows = "\n".join(
        _render_persisted_metric_row(trial_id, metrics)
        for trial_id, metrics in persisted_metrics.items()
    )

    if not relation_rows:
        relation_rows = '<tr><td colspan="3">No relations recorded.</td></tr>'
    if not frontier_rows:
        frontier_rows = '<tr><td colspan="7">No frontier score events recorded.</td></tr>'
    if not persisted_rows:
        persisted_rows = '<tr><td colspan="4">No persisted trial_metrics rows found.</td></tr>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Phase 1A ObjectNav 实验报告</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f4;
      --paper: #ffffff;
      --ink: #18212b;
      --muted: #657181;
      --line: #d9dfd5;
      --green: #2f6f59;
      --blue: #315f88;
      --gold: #a66b1d;
      --red: #9b3f3f;
      --soft-green: #e7f1ec;
      --soft-blue: #e8eef5;
      --soft-gold: #f7eddc;
      --soft-red: #f6e7e5;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
        "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      line-height: 1.62;
      letter-spacing: 0;
    }}
    .page {{ width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 30px 0 56px; }}
    header {{ padding: 28px 0 18px; }}
    .eyebrow {{ color: var(--green); font-size: 13px; font-weight: 800; text-transform: uppercase; }}
    h1 {{ max-width: 980px; margin: 8px 0 0; font-size: clamp(32px, 5vw, 56px); line-height: 1.12; letter-spacing: 0; }}
    .subtitle {{ max-width: 920px; margin: 14px 0 0; color: var(--muted); font-size: 18px; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 9px; margin-top: 18px; }}
    nav a {{ border: 1px solid var(--line); border-radius: 8px; background: rgba(255,255,255,.82); padding: 8px 11px; color: var(--ink); text-decoration: none; }}
    section {{ margin-top: 28px; padding: 24px; border: 1px solid var(--line); border-radius: 8px; background: rgba(255,255,255,.92); }}
    h2 {{ margin: 0 0 14px; font-size: 25px; line-height: 1.25; letter-spacing: 0; }}
    h3 {{ margin: 18px 0 8px; font-size: 17px; letter-spacing: 0; }}
    code {{ padding: 2px 6px; border: 1px solid #d6ddd2; border-radius: 5px; background: #f9fbf7; font-family: "SFMono-Regular", Consolas, monospace; font-size: .92em; }}
    .grid {{ display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }}
    .metric {{ grid-column: span 3; border: 1px solid var(--line); border-radius: 8px; background: var(--paper); padding: 14px; }}
    .metric strong {{ display: block; color: var(--muted); font-size: 13px; }}
    .metric span {{ display: block; margin-top: 6px; font-size: 29px; font-weight: 850; }}
    table {{ width: 100%; margin-top: 14px; border-collapse: collapse; border: 1px solid var(--line); background: var(--paper); }}
    th, td {{ padding: 10px 11px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ background: #edf2ed; font-weight: 800; white-space: nowrap; }}
    .pill {{ display: inline-flex; border-radius: 999px; padding: 3px 9px; background: var(--soft-green); color: var(--green); font-size: 13px; font-weight: 800; white-space: nowrap; }}
    .pill.blue {{ background: var(--soft-blue); color: var(--blue); }}
    .pill.gold {{ background: var(--soft-gold); color: var(--gold); }}
    .pill.red {{ background: var(--soft-red); color: var(--red); }}
    .bar-row {{ display: grid; grid-template-columns: 230px 1fr 90px; gap: 12px; align-items: center; margin-top: 12px; }}
    .bar-track {{ height: 15px; overflow: hidden; border-radius: 999px; background: #e8ece5; }}
    .bar {{ height: 100%; border-radius: 999px; background: var(--blue); }}
    .callout {{ margin-top: 14px; border-left: 5px solid var(--green); border-radius: 7px; background: var(--soft-green); padding: 13px 15px; }}
    .callout.warn {{ border-left-color: var(--gold); background: var(--soft-gold); }}
    footer {{ margin-top: 28px; color: var(--muted); font-size: 14px; }}
    @media (max-width: 820px) {{
      .metric {{ grid-column: span 6; }}
      .bar-row {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 560px) {{ .metric {{ grid-column: 1 / -1; }} }}
  </style>
</head>
<body>
  <div class="page">
    <header>
      <div class="eyebrow">Phase 1A · Deterministic ObjectNav · Generated report</div>
      <h1>室内饮水机 ObjectNav 实验报告</h1>
      <p class="subtitle">
        本报告由 Phase 1A artifacts 自动生成，展示 deterministic ROS-free ObjectNav 核心结果。
        它不包含真实 ROS 2、Nav2、检测模型或机器人实验结果。
      </p>
      <nav aria-label="报告导航">
        <a href="#overview">概览</a>
        <a href="#runs">Trial</a>
        <a href="#scores">Frontier Score Terms</a>
        <a href="#memory">Memory</a>
        <a href="#artifacts">Artifacts</a>
        <a href="#limits">边界</a>
      </nav>
    </header>

    <section id="overview">
      <h2>概览</h2>
      <div class="grid">
        <div class="metric"><strong>Scene</strong><span>{escape(str(summary["scene_id"]))}</span></div>
        <div class="metric"><strong>Target</strong><span>{escape(str(summary["target_class"]))}</span></div>
        <div class="metric"><strong>Trial Success</strong><span>{success_count}/{len(runs)}</span></div>
        <div class="metric"><strong>Events</strong><span>{len(events)}</span></div>
      </div>
      <div class="callout">
        <strong>Anchor:</strong>
        <code>{escape(str(summary["anchor"]["anchor_id"]))}</code>
        / <code>{escape(str(summary["anchor"]["anchor_type"]))}</code>
        / <code>{escape(str(summary["anchor"]["frame_id"]))}</code>
      </div>
    </section>

    <section id="runs">
      <h2>四个 Trial 结果</h2>
      <table>
        <tr>
          <th>Trial</th><th>结果</th><th>Final State</th><th>Path</th><th>Nav Goals</th>
          <th>Candidate Types</th><th>final_candidate_score</th><th>Events</th>
        </tr>
        {run_rows}
      </table>
      <h3>路径长度对比</h3>
      {path_rows}
    </section>

    <section id="scores">
      <h2>Frontier Score Terms</h2>
      <p>这些记录来自 <code>events.jsonl</code> 的 <code>frontier_selected</code> 事件，用于审计 baseline frontier policy。</p>
      <table>
        <tr>
          <th>Trial</th><th>Policy</th><th>Candidate</th><th>information_gain</th>
          <th>path_cost_m</th><th>revisit_penalty</th><th>score</th>
        </tr>
        {frontier_rows}
      </table>
    </section>

    <section id="memory">
      <h2>Memory 状态与 Relocation</h2>
      <table>
        <tr><th>Object</th><th>Class</th><th>State</th><th>Pose</th><th>Verification Viewpoint</th></tr>
        {object_rows}
      </table>
      <h3>Relations</h3>
      <table>
        <tr><th>Source</th><th>Relation</th><th>Target</th></tr>
        {relation_rows}
      </table>
      <h3>Persisted trial_metrics</h3>
      <table>
        <tr><th>Trial</th><th>Success</th><th>Final State</th><th>Path</th></tr>
        {persisted_rows}
      </table>
    </section>

    <section id="artifacts">
      <h2>Artifacts</h2>
      <table>
        <tr><th>Name</th><th>File</th></tr>
        {artifact_rows}
      </table>
    </section>

    <section id="limits">
      <h2>边界</h2>
      <div class="callout warn">
        当前结果来自确定性仿真：默认 Phase 1A trial 仍使用直线离散执行，A* 用于离线 path-cost 和 baseline policy scoring。
        尚未运行 ROS 2、Nav2、真实检测器、VLM、RTK 或机器人实验。
      </div>
    </section>

    <footer>
      Generated from <code>summary.json</code>, <code>memory_snapshot.json</code>,
      <code>events.jsonl</code>, and SQLite <code>trial_metrics</code>.
    </footer>
  </div>
</body>
</html>
"""


def _render_run_row(run: dict[str, Any]) -> str:
    metrics = run["metrics"]
    success_class = "" if metrics.get("success") else " red"
    candidate_types = ", ".join(metrics.get("selected_candidate_types", []))
    return f"""<tr>
  <td><code>{escape(run["trial_id"])}</code></td>
  <td><span class="pill{success_class}">{_yes_no(metrics.get("success"))}</span></td>
  <td>{escape(str(metrics.get("final_state")))}</td>
  <td>{_format_float(metrics.get("path_length_m"))} m</td>
  <td>{metrics.get("num_nav_goals", 0)}</td>
  <td>{escape(candidate_types)}</td>
  <td>{_format_optional_float(metrics.get("final_candidate_score"))}</td>
  <td>{run.get("event_count", 0)}</td>
</tr>"""


def _render_path_bar(run: dict[str, Any], max_path: float) -> str:
    path_length = float(run["metrics"].get("path_length_m", 0.0))
    width = min(100.0, (path_length / max_path) * 100.0)
    return f"""<div class="bar-row">
  <div><code>{escape(run["trial_id"])}</code></div>
  <div class="bar-track"><div class="bar" style="width: {width:.0f}%"></div></div>
  <div>{path_length:.2f} m</div>
</div>"""


def _render_object_row(obj: dict[str, Any]) -> str:
    pose = obj.get("pose", {})
    viewpoint = obj.get("verification_viewpoint") or {}
    return f"""<tr>
  <td><code>{escape(obj.get("object_id", ""))}</code></td>
  <td>{escape(obj.get("class_name", ""))}</td>
  <td><span class="pill {_state_class(obj.get("state"))}">{escape(obj.get("state", ""))}</span></td>
  <td>{_pose_text(pose)}</td>
  <td>{_pose_text(viewpoint)}</td>
</tr>"""


def _render_relation_row(relation: dict[str, Any]) -> str:
    return f"""<tr>
  <td><code>{escape(relation.get("source_object_id", ""))}</code></td>
  <td>{escape(relation.get("relation_type", ""))}</td>
  <td><code>{escape(relation.get("target_object_id", ""))}</code></td>
</tr>"""


def _render_frontier_row(event: dict[str, Any]) -> str:
    payload = event.get("payload", {})
    return f"""<tr>
  <td><code>{escape(event.get("trial_id", ""))}</code></td>
  <td>{escape(str(payload.get("policy", "")))}</td>
  <td>{escape(str(payload.get("candidate_type", "")))}</td>
  <td>{_format_optional_float(payload.get("information_gain"))}</td>
  <td>{_format_optional_float(payload.get("path_cost_m"))}</td>
  <td>{_format_optional_float(payload.get("revisit_penalty"))}</td>
  <td>{_format_optional_float(payload.get("score"))}</td>
</tr>"""


def _render_artifact_row(name: str, filename: str) -> str:
    return f"<tr><td>{escape(name)}</td><td><code>{escape(filename)}</code></td></tr>"


def _render_persisted_metric_row(trial_id: str, metrics: dict[str, Any]) -> str:
    return f"""<tr>
  <td><code>{escape(trial_id)}</code></td>
  <td>{_yes_no(metrics.get("success"))}</td>
  <td>{escape(str(metrics.get("final_state")))}</td>
  <td>{_format_float(metrics.get("path_length_m"))} m</td>
</tr>"""


def _format_float(value: object) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _format_optional_float(value: object) -> str:
    if value is None:
        return "-"
    return _format_float(value)


def _yes_no(value: object) -> str:
    return "success" if bool(value) else "failed"


def _pose_text(pose: dict[str, Any]) -> str:
    if not pose:
        return "-"
    return f"x={_format_float(pose.get('x'))}, y={_format_float(pose.get('y'))}, yaw={_format_float(pose.get('yaw'))}"


def _state_class(state: object) -> str:
    if state == "missing":
        return "red"
    if state == "reusable":
        return "blue"
    return ""
