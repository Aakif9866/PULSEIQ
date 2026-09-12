from app.ai.answer_validator import validate_findings
from app.schemas.analysis import Finding, ToolCallRecord


def _tool_call(tool: str, result: dict) -> ToolCallRecord:
    return ToolCallRecord(tool=tool, arguments={}, result=result)


_NO_MISSING_VALUES = {"row_count": 8, "columns_with_missing_values": {}}


def test_finding_matching_real_tool_output_is_verified():
    tool_calls = [_tool_call("get_missing_values", _NO_MISSING_VALUES)]
    findings = [
        Finding(
            claim="row count",
            value=8,
            affected_rows=None,
            total_rows=8,
            confidence="high",
        )
    ]
    verified, warnings = validate_findings(findings, tool_calls)
    assert verified[0].verified is True
    assert warnings == []


def test_zero_count_claim_is_verified_from_an_empty_collection():
    # The literal number 0 never appears anywhere in this tool result — it
    # is only provable as "the length of an empty dict". Without crediting
    # collection sizes as evidence, the single most common finding shape
    # ("0 missing values found") would always be wrongly marked unverified.
    tool_calls = [_tool_call("get_missing_values", _NO_MISSING_VALUES)]
    findings = [Finding(claim="missing values", value=0, total_rows=8, confidence="high")]
    verified, warnings = validate_findings(findings, tool_calls)
    assert verified[0].verified is True
    assert warnings == []


def test_fabricated_number_is_marked_unverified_and_downgraded():
    tool_calls = [_tool_call("get_missing_values", _NO_MISSING_VALUES)]
    findings = [Finding(claim="missing values", value=42, confidence="high")]
    verified, warnings = validate_findings(findings, tool_calls)
    assert verified[0].verified is False
    assert verified[0].confidence == "medium"  # downgraded, never silently trusted
    assert len(warnings) == 1


def test_unverified_finding_is_kept_not_deleted():
    tool_calls = [_tool_call("get_missing_values", _NO_MISSING_VALUES)]
    findings = [Finding(claim="missing values", value=999, confidence="low")]
    verified, _ = validate_findings(findings, tool_calls)
    assert len(verified) == 1  # never silently dropped, only flagged


def test_no_tool_calls_means_every_finding_is_unverifiable():
    findings = [Finding(claim="something", value=1)]
    verified, warnings = validate_findings(findings, [])
    assert verified[0].verified is False
    assert warnings == ["No analytical tools were used to produce this answer."]


def test_no_tool_calls_and_no_findings_produces_no_warnings():
    verified, warnings = validate_findings([], [])
    assert verified == []
    assert warnings == []


def test_string_or_null_values_never_fail_verification():
    tool_calls = [_tool_call("get_missing_values", {"row_count": 8})]
    findings = [Finding(claim="category name", value="Electronics")]
    verified, warnings = validate_findings(findings, tool_calls)
    assert verified[0].verified is True
    assert warnings == []
