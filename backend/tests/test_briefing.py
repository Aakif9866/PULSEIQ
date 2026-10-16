"""Dataset briefing: deterministic, schema-aware, and honest about what
doesn't apply. Numbers are worked out by hand from the frames below."""

import polars as pl
import pytest

from app.analytics.briefing import build_briefing
from app.core.config import settings


def _frame() -> pl.DataFrame:
    # 2024-01..2024-07 (span >= 180 days -> monthly). July: North 10, South 40.
    dates = [
        "2024-01-05",
        "2024-02-05",
        "2024-03-05",
        "2024-04-05",
        "2024-05-05",
        "2024-06-05",
        "2024-06-20",
        "2024-07-05",
        "2024-07-06",
    ]
    return pl.DataFrame(
        {
            "order_id": [f"o{i}" for i in range(9)],
            "order_date": dates,
            "region": [
                "North",
                "South",
                "North",
                "South",
                "North",
                "North",
                "South",
                "North",
                "South",
            ],
            "customer_age": [30, 40, 50, 30, 40, 50, 30, 40, 50],
            "revenue": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 30.0, 10.0, 40.0],
        }
    )


def _brief(df=None, **kw):
    defaults = dict(
        columns_profile=None, correlations=None, duplicate_row_count=0, data_quality_score=95.0
    )
    return build_briefing(df if df is not None else _frame(), **{**defaults, **kw})


def test_column_roles_are_detected_from_the_data():
    o = _brief()["overview"]
    assert o["date_columns"] == ["order_date"]
    assert o["metric_columns"][0] == "revenue"  # business-metric name ranks first
    assert "order_id" in o["id_columns"] and "order_id" not in o["dimension_columns"]
    assert o["dimension_columns"] == ["region"]


def test_metric_summary_values():
    revenue = next(m for m in _brief()["metrics"] if m["column"] == "revenue")
    assert (revenue["sum"], revenue["min"], revenue["max"]) == (290.0, 10.0, 60.0)


def test_trend_is_monthly_with_latest_change_and_driver():
    t = _brief()["trend"]
    assert t["freq"] == "month" and len(t["series"]) == 7
    lc = t["latest_change"]
    # June 90 -> July 50: -40. North 60 -> 10 (-50) is the top driver.
    assert (lc["previous_value"], lc["current_value"], lc["change"]) == (90.0, 50.0, -40.0)
    assert lc["top_contributor"]["segment"] == "North"
    assert lc["top_contributor"]["share_of_change_pct"] == 125.0


def test_segments_rank_groups_by_total():
    s = _brief()["segments"]
    assert s["dimension"] == "region" and s["groups"][0] == {"group": "North", "value": 160.0}
    assert s["top_share_pct"] == round(160 / 290 * 100, 2)


def test_quality_and_relationships_come_from_the_stored_profile():
    b = _brief(
        columns_profile=[
            {"name": "revenue", "null_count": 2, "null_percentage": 22.2, "outlier_count": 1}
        ],
        correlations=[
            {"column_a": "revenue", "column_b": "customer_age", "correlation": -0.8},
            {"column_a": "revenue", "column_b": "x", "correlation": 0.2},
        ],
        duplicate_row_count=3,
    )
    assert [q["kind"] for q in b["quality"]] == ["duplicates", "missing", "outliers"]
    assert b["relationships"] == [
        {
            "column_a": "revenue",
            "column_b": "customer_age",
            "correlation": -0.8,
            "direction": "negative",
        }
    ]


def test_suggested_questions_name_real_columns_and_periods():
    qs = _brief()["suggested_questions"]
    assert qs[0] == "Why did revenue change in 2024-07 compared with 2024-06?"
    assert any("Which region" in q for q in qs)
    assert all("{" not in q for q in qs)


def test_sections_that_do_not_apply_are_omitted_not_invented():
    text_only = pl.DataFrame({"name": ["a", "b", "c"], "city": ["x", "y", "x"]})
    b = _brief(text_only)
    assert b["trend"] is None and b["segments"] is None and b["metrics"] == []
    assert b["suggested_questions"] == ["Summarize this dataset and its most important columns."]


# ------------------------------------------------------------- endpoint ----


@pytest.fixture(autouse=True)
def _local_storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_STORAGE_ROOT", str(tmp_path))


def _token(client, email):
    return client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "correct-horse-1"}
    ).json()["tokens"]["access_token"]


def test_briefing_endpoint_and_owner_isolation(client):
    csv = _frame().write_csv().encode()
    owner = {"Authorization": f"Bearer {_token(client, 'brief-owner@pulseiq.dev')}"}
    ds = client.post(
        "/api/v1/datasets", headers=owner, files={"file": ("s.csv", csv, "text/csv")}
    ).json()["id"]

    resp = client.get(f"/api/v1/datasets/{ds}/briefing", headers=owner)
    assert resp.status_code == 200
    assert resp.json()["trend"]["latest_change"]["change"] == -40.0

    intruder = {"Authorization": f"Bearer {_token(client, 'brief-intruder@pulseiq.dev')}"}
    assert client.get(f"/api/v1/datasets/{ds}/briefing", headers=intruder).status_code == 404
    assert client.get(f"/api/v1/datasets/{ds}/briefing").status_code == 401


def test_unique_continuous_numbers_are_metrics_not_ids():
    df = pl.DataFrame({"region": ["a", "b", "a", "b"], "revenue": [1.5, 2.25, 3.75, 4.0]})
    o = _brief(df)["overview"]
    assert o["metric_columns"] == ["revenue"] and o["id_columns"] == []


def test_prices_and_ages_are_averaged_not_totalled_and_never_the_headline():
    df = pl.DataFrame(
        {
            "order_date": ["2024-01-01", "2024-02-01", "2024-03-01"],
            "unit_price": [9.5, 10.0, 12.0],
            "customer_age": [30, 40, 50],
        }
    )
    b = _brief(df)
    assert {m["column"]: m["additive"] for m in b["metrics"]} == {
        "unit_price": False,
        "customer_age": False,
    }
    assert b["trend"] is None  # a "total price per month" trend would be meaningless


def test_daily_data_names_days_not_the_same_month_twice():
    df = pl.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "region": ["a", "b", "a"],
            "revenue": [1.0, 2.0, 5.0],
        }
    )
    lc = _brief(df)["trend"]["latest_change"]
    assert (lc["previous_label"], lc["current_label"]) == ("2024-01-02", "2024-01-03")
    assert _brief(df)["suggested_questions"][0] == (
        "Why did revenue change in 2024-01-03 compared with 2024-01-02?"
    )
