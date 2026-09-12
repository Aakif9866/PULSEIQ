"""Cross-checks the LLM's structured findings against the actual tool-call
evidence gathered during the analysis (docs/AI_ANALYTICS.md's "never
hallucinate numbers" requirement). Not a formal proof-checker — it's a
real, if approximate, reconciliation: every numeric claim in a finding
must appear somewhere in the evidence pool of real numbers the tools
actually returned. A finding that doesn't match anything is not deleted
(the model may have summarized/rounded a real number in a way this
simple check misses) but is marked unverified and surfaced as a warning,
rather than silently trusted.
"""
from typing import Any

from app.schemas.analysis import Finding, ToolCallRecord

_TOLERANCE = 0.5  # absolute, matches "31" against "31.0"/"31.2" etc.


def _extract_numbers(obj: Any, into: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, int | float):
        into.add(float(obj))
    elif isinstance(obj, dict):
        # A collection's size is itself a real, exact fact derivable from
        # the tool's evidence — e.g. `{"columns_with_missing_values": {}}`
        # never spells out the literal number 0 anywhere, but "0 missing
        # columns" is still fully proven by that empty dict. Without this,
        # every "zero problems found" claim (the most common and most
        # important result for missing values/duplicates/anomalies) would
        # wrongly show as unverified.
        into.add(float(len(obj)))
        for value in obj.values():
            _extract_numbers(value, into)
    elif isinstance(obj, list):
        into.add(float(len(obj)))
        for item in obj:
            _extract_numbers(item, into)


def _build_evidence_pool(tool_calls: list[ToolCallRecord]) -> set[float]:
    pool: set[float] = set()
    for record in tool_calls:
        _extract_numbers(record.result, pool)
    return pool


def _matches_pool(value: float | int | str | None, pool: set[float]) -> bool:
    if value is None or isinstance(value, str):
        return True  # nothing numeric to check
    return any(abs(float(value) - candidate) <= _TOLERANCE for candidate in pool)


def validate_findings(
    findings: list[Finding], tool_calls: list[ToolCallRecord]
) -> tuple[list[Finding], list[str]]:
    """Returns (findings with .verified set appropriately, warnings)."""
    if not tool_calls:
        # No tools were called at all — nothing to reconcile against;
        # every numeric finding is unverifiable by construction.
        no_tools_warnings = (
            ["No analytical tools were used to produce this answer."] if findings else []
        )
        for finding in findings:
            finding.verified = False
        return findings, no_tools_warnings

    pool = _build_evidence_pool(tool_calls)
    warnings: list[str] = []

    for finding in findings:
        numeric_fields = [finding.value, finding.affected_rows, finding.total_rows]
        all_match = all(_matches_pool(v, pool) for v in numeric_fields)
        finding.verified = all_match
        if not all_match:
            warnings.append(
                f"Could not verify the numbers behind: \"{finding.claim}\" — "
                "shown with lower confidence."
            )
            if finding.confidence == "high":
                finding.confidence = "medium"

    return findings, warnings
