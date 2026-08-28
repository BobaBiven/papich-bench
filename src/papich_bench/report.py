"""Render a ``RunReport`` as a leaderboard plus per-flow transcripts.

Two renderers share the same aggregation: ``to_markdown`` (stdout / files) and
``to_html`` (a standalone self-contained page). The Rich console leaderboard in
the CLI reuses ``RunReport.leaderboard`` directly.
"""

from __future__ import annotations

import html
from collections.abc import Callable

from papich_bench.models import SCORE_LABELS, FlowResult, RunReport, StepResult


def _score_cell(step: StepResult) -> str:
    if not step.answer.ok:
        return "ERROR"
    if step.judgement is None:
        return "not judged"
    j = step.judgement
    return f"found={j.found_score} truthful={j.truthful_score}"


def to_markdown(report: RunReport) -> str:
    lines: list[str] = ["# papich-bench results\n"]
    lines.append(f"- **Dataset:** `{report.dataset}`")
    lines.append(f"- **Judge:** `{report.judge_model}`")
    lines.append(f"- **Answerers:** {', '.join(report.answerers)}")
    lines.append(f"- **Run at:** {report.created_at.isoformat(timespec='seconds')}\n")

    lines.append("## Leaderboard\n")
    lines.append(
        "| Rank | Answerer | Score | Judged | Found (avg) | Truthful (avg) | Errors | Latency |"
    )
    lines.append("| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for rank, row in enumerate(report.leaderboard(), start=1):
        lines.append(
            f"| {rank} | {row.answerer} | {row.score_pct:.0f}% | {row.n}/{row.n_total} | "
            f"{row.mean_found:.2f} | {row.mean_truthful:.2f} | "
            f"{row.n_errors} | {row.mean_latency_s:.1f}s |"
        )
    lines.append("")

    lines.append("## Per-item breakdown\n")
    for fr in report.results:
        lines.extend(_flow_markdown(fr))
    return "\n".join(lines)


def _flow_markdown(fr: FlowResult) -> list[str]:
    multi = len(fr.flow.steps) > 1
    heading = f"### {fr.flow.id}" + ("  _(flow)_" if multi else f": {fr.flow.steps[0].prompt}")
    out = [heading + "\n"]
    for run in fr.runs:
        out.append(f"**{run.answerer}**")
        for step in run.steps:
            label = f"`{step.step_id}` " if multi else ""
            if multi:
                out.append(f"> {label}Q: {step.prompt}")
            out.append(f"> {label}— {_score_cell(step)}")
            if not step.answer.ok:
                out.append(f"> error: {step.answer.error}\n")
                continue
            out.append(f"> {step.answer.text.strip() or '(empty answer)'}")
            if step.judgement is not None:
                j = step.judgement
                out.append(
                    f"> _found ({SCORE_LABELS[j.found_score]}):_ {j.found_reasoning}  "
                    f"_truthful ({SCORE_LABELS[j.truthful_score]}):_ {j.truthful_reasoning}"
                )
            elif step.judge_error:
                out.append(f"> _judge error:_ {step.judge_error}")
            if multi:
                out.append(f"> _→ next: {step.next}_")
            out.append("")
        out.append("")
    return out


def to_html(report: RunReport) -> str:
    def esc(text: str) -> str:
        return html.escape(text)

    rows = "\n".join(
        f"<tr><td>{rank}</td><td>{esc(r.answerer)}</td>"
        f"<td class='num'>{r.score_pct:.0f}%</td>"
        f"<td class='num'>{r.n}/{r.n_total}</td>"
        f"<td class='num'>{r.mean_found:.2f}</td>"
        f"<td class='num'>{r.mean_truthful:.2f}</td>"
        f"<td class='num'>{r.n_errors}</td>"
        f"<td class='num'>{r.mean_latency_s:.1f}s</td></tr>"
        for rank, r in enumerate(report.leaderboard(), start=1)
    )
    flows = "\n".join(_flow_html(fr, esc) for fr in report.results)
    return _HTML_TEMPLATE.format(
        dataset=esc(report.dataset),
        judge=esc(report.judge_model),
        answerers=esc(", ".join(report.answerers)),
        created=esc(report.created_at.isoformat(timespec="seconds")),
        rows=rows,
        flows=flows,
    )


def _flow_html(fr: FlowResult, esc: Callable[[str], str]) -> str:
    multi = len(fr.flow.steps) > 1
    if multi:
        title = f"{esc(fr.flow.id)} (flow)"
    else:
        title = f"{esc(fr.flow.id)}: {esc(fr.flow.steps[0].prompt)}"
    parts = [f"<div class='q'><h3>{title}</h3>"]
    for run in fr.runs:
        parts.append(f"<div class='ans'><strong>{esc(run.answerer)}</strong>")
        for step in run.steps:
            if multi:
                parts.append(f"<p class='meta'>Q ({esc(step.step_id)}): {esc(step.prompt)}</p>")
            parts.append(f"<p class='score'>{_score_cell(step)}</p>")
            if not step.answer.ok:
                parts.append(f"<p class='err'>{esc(step.answer.error or '')}</p>")
                continue
            parts.append(f"<blockquote>{esc(step.answer.text.strip() or '(empty)')}</blockquote>")
            if step.judgement is not None:
                j = step.judgement
                parts.append(
                    f"<p class='judge'><em>found:</em> {esc(j.found_reasoning)}<br>"
                    f"<em>truthful:</em> {esc(j.truthful_reasoning)}</p>"
                )
            if multi:
                parts.append(f"<p class='meta'>→ next: {esc(step.next)}</p>")
        parts.append("</div>")
    parts.append("</div>")
    return "\n".join(parts)


_HTML_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>papich-bench results</title>
<style>
  body {{ font: 15px/1.5 -apple-system, system-ui, sans-serif; max-width: 900px;
         margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ margin-bottom: .25rem; }}
  .meta-block {{ color: #555; margin-bottom: 1.5rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
  th, td {{ padding: .5rem .75rem; border-bottom: 1px solid #e2e2e2; text-align: left; }}
  th {{ background: #f6f6f6; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tr:first-child td {{ font-weight: 600; }}
  .q {{ border-top: 2px solid #eee; padding-top: 1rem; margin-top: 1.5rem; }}
  .ans {{ margin: .75rem 0; }}
  blockquote {{ margin: .4rem 0; padding: .4rem .8rem; border-left: 3px solid #ccc;
                background: #fafafa; }}
  .judge {{ color: #444; font-size: .9em; }}
  .score {{ color: #333; font-size: .9em; font-weight: 600; margin: .2rem 0; }}
  .err {{ color: #b00020; }}
  .meta {{ color: #666; margin: .2rem 0; }}
</style></head><body>
<h1>papich-bench results</h1>
<div class="meta-block">
  Dataset <code>{dataset}</code> &middot; Judge <code>{judge}</code> &middot;
  {answerers} &middot; {created}
</div>
<h2>Leaderboard</h2>
<table>
<tr><th>Rank</th><th>Answerer</th><th>Score</th><th>Judged</th><th>Found</th><th>Truthful</th>
<th>Errors</th><th>Latency</th></tr>
{rows}
</table>
<h2>Per-item breakdown</h2>
{flows}
</body></html>
"""
