import polars as pl

from app.ai.follow_ups import suggest_follow_ups
from app.ai.tools import explain_change
from app.schemas.analysis import ToolCallRecord


def _df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "date": [
                "2024-02-03",
                "2024-02-10",
                "2024-03-05",
                "2024-03-09",
                "2024-03-20",
                "2024-03-21",
            ],
            "region": ["North", "South", "North", "South", "North", "South"],
            "channel": ["web", "web", "web", "store", "web", "store"],
            "revenue": [100.0, 50.0, 30.0, 60.0, 10.0, 5.0],
        }
    )


def _call(tool: str, args: dict, result: dict) -> ToolCallRecord:
    return ToolCallRecord(tool=tool, arguments=args, result=result)


def test_after_a_change_analysis_suggests_drilling_into_the_top_contributor():
    df = _df()
    result = explain_change(df, "date", "revenue", dimensions=["region"])
    qs = suggest_follow_ups(df, "why?", [_call("explain_change", {}, result)])
    assert qs[0].startswith("Show the 2024-03 rows where region is North")
    assert "Break the change in revenue down by channel." in qs  # a dimension not yet used
    assert len(qs) <= 3


def test_after_a_group_by_suggests_the_why_and_another_dimension():
    args = {"group_by": ["region"], "column": "revenue", "op": "sum"}
    qs = suggest_follow_ups(
        _df(), "revenue by region", [_call("group_by_aggregate", args, {"rows": []})]
    )
    assert qs[0] == "Why did revenue change in the latest period, and which segments drove it?"
    assert "Break revenue down by channel within each region." in qs


def test_failed_tool_calls_are_ignored_and_generic_suggestions_use_real_columns():
    failed = _call("explain_change", {}, {"error": "boom"})
    qs = suggest_follow_ups(_df(), "q", [failed])
    # region and channel tie on cardinality; either is a valid real column.
    assert qs[0] in {
        "Which region has the highest total revenue?",
        "Which channel has the highest total revenue?",
    }
    assert qs[1:] == [
        "Why did revenue change in the latest period?",
        "Are there outliers in revenue?",
    ]


def test_never_suggests_the_question_just_asked():
    qs = suggest_follow_ups(_df(), "Are there outliers in revenue?", [])
    assert "Are there outliers in revenue?" not in qs
