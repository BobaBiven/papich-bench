"""Render a ``RunReport`` as a leaderboard plus a per-question breakdown.

Two renderers share the same aggregation: ``to_markdown`` (stdout / files) and
``to_html`` (a standalone self-contained page). The Rich console leaderboard in
the CLI reuses ``RunReport.leaderboard`` directly.
"""

from __future__ import annotations

import html

from papich_bench.models import SCORE_LABELS, JudgedAnswer, QuestionResult, RunReport


def _score_cell(ja: JudgedAnswer) -> str:
    if not ja.answer.ok:
        return "ERROR"
    if ja.judgement is None:
        return "not judged"
    j = ja.judgement
    return f"found={j.found_score} truthful={j.truthful_score}"


def to_markdown(report: RunReport) -> str:
    lines: list[str] = []
    lines.append("# papich_bench results\n")
    lines.append(f"- **Dataset:** `{report.dataset}`")
    lines.append(f"- **Judge:** `{report.judge_model}`")
    lines.append(f"- **Answerers:** {', '.join(report.answerers)}")
    lines.append(f"- **Run at:** {report.created_at.isoformat(timespec='seconds')}\n")

    lines.append("## Leaderboard\n")
    lines.append("| Rank | Answerer | Score | Found (avg) | Truthful (avg) | Errors | Latency |")
    lines.append("| ---: | --- | ---: | ---: | ---: | ---: | ---: |")
    for rank, row in enumerate(report.leaderboard(), start=1):
        lines.append(
            f"| {rank} | {row.answerer} | {row.score_pct:.0f}% | "
            f"{row.mean_found:.2f} | {row.mean_truthful:.2f} | "
            f"{row.n_errors} | {row.mean_latency_s:.1f}s |"
        )
    lines.append("")

    lines.append("## Per-question breakdown\n")
    for qr in report.results:
        lines.extend(_question_markdown(qr))
    return "\n".join(lines)


def _question_markdown(qr: QuestionResult) -> list[str]:
    q = qr.question
    out = [f"### {q.id}: {q.prompt}\n"]
    if q.wanted:
        out.append(f"_Wanted:_ {q.wanted}\n")
    out.append(f"_Reference:_ {q.reference_answer}\n")
    for ja in qr.answers:
        out.append(f"**{ja.answer.answerer}** — {_score_cell(ja)}")
        if not ja.answer.ok:
            out.append(f"> error: {ja.answer.error}\n")
            continue
        answer_text = ja.answer.text.strip() or "(empty answer)"
        out.append(f"> {answer_text}\n")
        if ja.judgement is not None:
            j = ja.judgement
            out.append(
                f"> _found ({SCORE_LABELS[j.found_score]}):_ {j.found_reasoning}  "
                f"_truthful ({SCORE_LABELS[j.truthful_score]}):_ {j.truthful_reasoning}\n"
            )
        elif ja.judge_error:
            out.append(f"> _judge error:_ {ja.judge_error}\n")
    out.append("")
    return out


def to_html(report: RunReport) -> str:
    def esc(text: str) -> str:
        return html.escape(text)

    rows = "\n".join(
        f"<tr><td>{rank}</td><td>{esc(r.answerer)}</td>"
        f"<td class='num'>{r.score_pct:.0f}%</td>"
        f"<td class='num'>{r.mean_found:.2f}</td>"
        f"<td class='num'>{r.mean_truthful:.2f}</td>"
        f"<td class='num'>{r.n_errors}</td>"
        f"<td class='num'>{r.mean_latency_s:.1f}s</td></tr>"
        for rank, r in enumerate(report.leaderboard(), start=1)
    )

    questions = "\n".join(_question_html(qr, esc) for qr in report.results)

    return _HTML_TEMPLATE.format(
        dataset=esc(report.dataset),
        judge=esc(report.judge_model),
        answerers=esc(", ".join(report.answerers)),
        created=esc(report.created_at.isoformat(timespec="seconds")),
        rows=rows,
        questions=questions,
    )


def _question_html(qr: QuestionResult, esc) -> str:  # type: ignore[no-untyped-def]
    q = qr.question
    parts = [f"<div class='q'><h3>{esc(q.id)}: {esc(q.prompt)}</h3>"]
    if q.wanted:
        parts.append(f"<p class='meta'><em>Wanted:</em> {esc(q.wanted)}</p>")
    parts.append(f"<p class='meta'><em>Reference:</em> {esc(q.reference_answer)}</p>")
    for ja in qr.answers:
        name = esc(ja.answer.answerer)
        parts.append(f"<div class='ans'><strong>{name}</strong> — {_score_cell(ja)}")
        if not ja.answer.ok:
            parts.append(f"<p class='err'>{esc(ja.answer.error or '')}</p></div>")
            continue
        parts.append(f"<blockquote>{esc(ja.answer.text.strip() or '(empty)')}</blockquote>")
        if ja.judgement is not None:
            j = ja.judgement
            parts.append(
                f"<p class='judge'><em>found:</em> {esc(j.found_reasoning)}<br>"
                f"<em>truthful:</em> {esc(j.truthful_reasoning)}</p>"
            )
        parts.append("</div>")
    parts.append("</div>")
    return "\n".join(parts)


_HTML_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>papich_bench results</title>
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
  .err {{ color: #b00020; }}
  .meta {{ color: #666; margin: .2rem 0; }}
</style></head><body>
<h1>papich_bench results</h1>
<div class="meta-block">
  Dataset <code>{dataset}</code> &middot; Judge <code>{judge}</code> &middot;
  {answerers} &middot; {created}
</div>
<h2>Leaderboard</h2>
<table>
<tr><th>Rank</th><th>Answerer</th><th>Score</th><th>Found</th><th>Truthful</th>
<th>Errors</th><th>Latency</th></tr>
{rows}
</table>
<h2>Per-question breakdown</h2>
{questions}
</body></html>
"""
