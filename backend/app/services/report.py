"""Standalone HTML report for one saved insight.

Built only from data the application already validated and stored: the
insight's answer, its findings (with their verified flags), the tool calls
that produced the numbers, and the dataset's own profile. Nothing here is
LLM-written at report time, so a report can't say more than the analysis
proved. Every value is HTML-escaped; the file has no scripts and no
external resources, so it opens anywhere and prints cleanly to PDF.
"""

from datetime import UTC, datetime
from html import escape
from typing import Any

from app.models.dataset import Dataset
from app.schemas.insight import InsightRead

_MAX_TABLE_ROWS = 20
_MAX_CHART_BARS = 12

_TOOL_LABELS = {
    "get_dataset_profile": "Dataset profile",
    "get_column_statistics": "Column statistics",
    "get_missing_values": "Missing values",
    "get_duplicates": "Duplicate rows",
    "get_unique_values": "Distinct values",
    "group_by_aggregate": "Grouped aggregation",
    "filter_rows": "Filtered rows",
    "detect_outliers": "Outlier detection (IQR)",
    "detect_logical_violations": "Range-rule check",
    "detect_anomalies": "Anomaly scan",
    "calculate_correlation": "Correlation",
    "time_series_analysis": "Time series",
    "compare_groups": "Group comparison",
    "explain_change": "Change and contribution analysis",
    "validate_formula": "Formula check",
    "get_top_records": "Top records",
    "get_bottom_records": "Bottom records",
}

_CSS = """
body{font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:#1d1d1f;
max-width:860px;margin:40px auto;padding:0 24px}
h1{font-size:28px;letter-spacing:-.02em;margin:0 0 4px}h2{font-size:18px;margin:32px 0 8px;
letter-spacing:-.01em}.meta{color:#6e6e73;font-size:13px}.summary{font-size:16px;background:#f5f5f7;
border-radius:12px;padding:16px 18px}table{border-collapse:collapse;width:100%;font-size:13px;
margin:8px 0}th,td{border-bottom:1px solid #e5e5ea;padding:6px 8px;text-align:left;
vertical-align:top}
th{color:#6e6e73;font-weight:600}td.n{text-align:right;font-variant-numeric:tabular-nums}
.ok{color:#248a3d;font-weight:600}.warn{color:#b25000;font-weight:600}.box{border:1px solid #e5e5ea;
border-radius:12px;padding:12px 16px;margin:10px 0}.box h3{margin:0 0 4px;font-size:14px}
code{font:12px ui-monospace,Menlo,monospace;background:#f5f5f7;padding:1px 4px;border-radius:4px}
ul{padding-left:20px}footer{margin-top:40px;color:#86868b;font-size:12px}
@media print{body{margin:0}.box,.summary{break-inside:avoid}}
"""


def _utc(moment: datetime) -> str:
    """Timestamps come back from the database in the session's local zone;
    convert before labelling them UTC (a naive one is already UTC)."""
    aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    return aware.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _e(value: Any) -> str:
    return escape("" if value is None else str(value))


def _fmt(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return _e(value if value is not None else "—")
    if isinstance(value, int | float):
        return f"{value:,.2f}".rstrip("0").rstrip(".") if isinstance(value, float) else f"{value:,}"
    return _e(value)


def _table(columns: list[Any], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{_e(c)}</th>" for c in columns)
    body = "".join(
        "<tr>"
        + "".join(
            f'<td class="n">{_fmt(v)}</td>' if isinstance(v, int | float) else f"<td>{_fmt(v)}</td>"
            for v in row
        )
        + "</tr>"
        for row in rows[:_MAX_TABLE_ROWS]
    )
    more = (
        f'<p class="meta">Showing {_MAX_TABLE_ROWS} of {len(rows)} rows.</p>'
        if len(rows) > _MAX_TABLE_ROWS
        else ""
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>{more}"


def _bar_chart(labels: list[Any], values: list[float]) -> str:
    """A plain inline SVG bar chart: no script, renders and prints anywhere."""
    pairs = [(str(lbl), float(v)) for lbl, v in zip(labels, values, strict=False) if v is not None]
    pairs = pairs[:_MAX_CHART_BARS]
    if not pairs:
        return ""
    peak = max(abs(v) for _, v in pairs) or 1.0
    row_h, label_w, bar_w = 24, 160, 420
    parts = []
    for i, (label, value) in enumerate(pairs):
        y = i * row_h
        width = abs(value) / peak * bar_w
        color = "#0071e3" if value >= 0 else "#d70015"
        parts.append(
            f'<text x="{label_w - 8}" y="{y + 16}" text-anchor="end" font-size="12" '
            f'fill="#1d1d1f">{_e(label[:24])}</text>'
            f'<rect x="{label_w}" y="{y + 4}" width="{width:.1f}" height="16" rx="3" '
            f'fill="{color}"/>'
            f'<text x="{label_w + width + 6:.1f}" y="{y + 16}" font-size="12" '
            f'fill="#6e6e73">{_fmt(value)}</text>'
        )
    height = len(pairs) * row_h
    return (
        f'<svg role="img" viewBox="0 0 {label_w + bar_w + 120} {height}" width="100%" '
        f'style="max-width:700px">{"".join(parts)}</svg>'
    )


def _render_result(tool: str, result: dict[str, Any]) -> str:
    if "omitted" in result or "error" in result:
        return (
            f'<p class="meta">{_e(result.get("omitted") or "Failed: " + str(result["error"]))}</p>'
        )
    if tool == "explain_change":
        out = [
            f"<p>{_e(result.get('previous_period'))} → {_e(result.get('current_period'))}: "
            f"{_fmt(result.get('previous_value'))} → {_fmt(result.get('current_value'))} "
            f"(change {_fmt(result.get('change'))}"
            + (
                f", {_fmt(result.get('pct_change'))}%"
                if result.get("pct_change") is not None
                else ""
            )
            + ")</p>"
        ]
        for b in result.get("breakdowns", [])[:3]:
            top = b.get("top_contributors", [])
            out.append(f"<p class='meta'>By {_e(b.get('dimension'))}</p>")
            out.append(
                _table(
                    ["Segment", "Before", "After", "Change", "Share of change %"],
                    [
                        [
                            s.get("segment"),
                            s.get("previous"),
                            s.get("current"),
                            s.get("change"),
                            s.get("share_of_change_pct"),
                        ]
                        for s in top
                    ],
                )
            )
        return "".join(out)
    if isinstance(result.get("columns"), list) and isinstance(result.get("rows"), list):
        rows = result["rows"]
        chart = ""
        if (
            len(result["columns"]) == 2
            and rows
            and all(isinstance(r[1], int | float) for r in rows if len(r) == 2)
        ):
            chart = _bar_chart([r[0] for r in rows], [r[1] for r in rows])
        return chart + _table(result["columns"], rows)
    scalars = [(k, v) for k, v in result.items() if isinstance(v, str | int | float | bool)]
    if scalars:
        return _table(["Measure", "Value"], [[k.replace("_", " "), v] for k, v in scalars])
    return '<p class="meta">Structured result; see the app for full detail.</p>'


def _version_note(insight: InsightRead, dataset: Dataset) -> str:
    computed = insight.dataset_version
    if computed is None or computed == dataset.version:
        return f"Version {dataset.version}, the dataset's current data"
    return (
        f'<span class="warn">Computed on version {computed}; the dataset is now at version '
        f"{dataset.version}.</span> These results describe the older data"
    )


def render_insight_report(insight: InsightRead, dataset: Dataset) -> str:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    saved = _utc(insight.created_at)
    verified_line = (
        f"{len([f for f in insight.findings if f.verified])} of {len(insight.findings)} "
        "findings verified against computed results."
    )
    verified = [f for f in insight.findings if f.verified]

    findings_rows = "".join(
        "<tr>"
        f"<td>{_e(f.claim)}</td>"
        f'<td class="n">{_fmt(f.value)}{" " + _e(f.unit) if f.unit else ""}</td>'
        + ('<td class="ok">Verified</td>' if f.verified else '<td class="warn">Not verified</td>')
        + f"<td>{_e(f.confidence)}</td><td>{_e(f.calculation)}</td></tr>"
        for f in insight.findings
    )
    findings_html = (
        "<table><thead><tr><th>Finding</th><th>Value</th><th>Status</th><th>Confidence</th>"
        f"<th>How it was calculated</th></tr></thead><tbody>{findings_rows}</tbody></table>"
        if insight.findings
        else '<p class="meta">No structured findings were recorded for this answer.</p>'
    )

    evidence_html = "".join(
        f'<div class="box"><h3>{_e(_TOOL_LABELS.get(t.tool, t.tool))}</h3>'
        f'<p class="meta"><code>{_e(t.tool)}</code> '
        + ", ".join(
            f"{_e(k)}=<code>{_e(v)}</code>" for k, v in t.arguments.items() if v is not None
        )
        + f"</p>{_render_result(t.tool, t.result)}</div>"
        for t in insight.tool_calls
    ) or (
        '<p class="meta">The computations behind this insight weren\'t stored '
        "(it was saved before evidence was kept). Re-run it in PulseIQ to see them.</p>"
    )

    caveats: list[str] = []
    for col in dataset.columns_profile or []:
        if col.get("null_count"):
            caveats.append(
                f"{col['null_count']} missing values in {col['name']}"
                + (f" ({col['null_percentage']}%)" if col.get("null_percentage") else "")
            )
        if col.get("outlier_count"):
            n = col["outlier_count"]
            caveats.append(f"{n} statistical outlier{'s' if n != 1 else ''} in {col['name']}")
    if dataset.duplicate_row_count:
        n = dataset.duplicate_row_count
        caveats.append(f"{n} duplicate row{'s' if n != 1 else ''}")
    for t in insight.tool_calls:
        if t.tool == "explain_change":
            caveats += [str(c) for c in t.result.get("caveats", [])]
    unverified = len(insight.findings) - len(verified)
    if unverified:
        caveats.append(
            f"{unverified} finding(s) could not be matched to a computed result and are "
            "marked not verified."
        )
    caveats_html = (
        "<ul>" + "".join(f"<li>{_e(c)}</li>" for c in dict.fromkeys(caveats)) + "</ul>"
        if caveats
        else "<p>No data-quality issues were recorded for this dataset.</p>"
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(insight.title)} · PulseIQ report</title><style>{_CSS}</style></head><body>
<header>
<p class="meta">PulseIQ analyst report</p>
<h1>{_e(insight.title)}</h1>
<p class="meta">Generated {generated} · Insight saved {_e(saved)}</p>
</header>

<h2>Dataset</h2>
<table><tbody>
<tr><th>File</th><td>{_e(dataset.original_filename)}</td></tr>
<tr><th>Size</th><td>{_fmt(dataset.row_count)} rows · {_fmt(dataset.column_count)} columns</td></tr>
<tr><th>Data quality score</th><td>{_fmt(dataset.data_quality_score)}</td></tr>
<tr><th>Version</th><td>{_version_note(insight, dataset)}
(dataset <code>{_e(dataset.id)}</code>).</td></tr>
</tbody></table>

<h2>Question</h2>
<p>{_e(insight.question)}</p>

<h2>Executive summary</h2>
<div class="summary">{_e(insight.answer)}</div>

<h2>Key findings</h2>
<p class="meta">{verified_line}</p>
{findings_html}

<h2>Supporting calculations</h2>
{evidence_html}

<h2>Data-quality caveats and limitations</h2>
{caveats_html}

<h2>Methodology</h2>
<ul>
<li>Every number was computed by deterministic analytical tools over the full dataset (all
{_fmt(dataset.row_count)} rows), not estimated by the language model.</li>
<li>The model chose which computations to run and wrote the summary. Each finding's value was then
checked against the computed results; findings that didn't match are marked
<span class="warn">Not verified</span>.</li>
<li>Contribution analysis shows where a change happened, not why. It is not proof of cause.</li>
<li>This report is a snapshot of the analysis as saved. Re-run the question in PulseIQ for a fresh
computation.</li>
</ul>
<footer>Generated by PulseIQ from stored, validated analysis results.</footer>
</body></html>
"""
