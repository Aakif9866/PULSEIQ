"""Pure unit tests for the deterministic chart-type rules table — no AI,
no database. See app/analytics/chart_suggestion.py's module docstring."""
from app.analytics.chart_suggestion import suggest_chart_type
from app.schemas.dataset_query import Aggregation, DatasetQueryRequest

DTYPES = {"region": "String", "order_date": "String", "revenue": "Int64"}


def test_no_aggregation_suggests_table():
    request = DatasetQueryRequest()
    assert suggest_chart_type(request, DTYPES) == "table"


def test_no_group_by_suggests_kpi():
    request = DatasetQueryRequest(aggregations=[Aggregation(op="sum", column="revenue")])
    assert suggest_chart_type(request, DTYPES) == "kpi"


def test_categorical_group_by_suggests_bar():
    request = DatasetQueryRequest(
        group_by=["region"], aggregations=[Aggregation(op="sum", column="revenue")]
    )
    assert suggest_chart_type(request, DTYPES) == "bar"


def test_date_named_group_by_suggests_line():
    request = DatasetQueryRequest(
        group_by=["order_date"], aggregations=[Aggregation(op="sum", column="revenue")]
    )
    assert suggest_chart_type(request, DTYPES) == "line"


def test_date_dtype_suggests_line_even_without_date_like_name():
    request = DatasetQueryRequest(
        group_by=["period"], aggregations=[Aggregation(op="sum", column="revenue")]
    )
    assert suggest_chart_type(request, {"period": "Date"}) == "line"


def test_multiple_group_by_columns_suggests_table():
    request = DatasetQueryRequest(
        group_by=["region", "order_date"], aggregations=[Aggregation(op="sum", column="revenue")]
    )
    assert suggest_chart_type(request, DTYPES) == "table"
