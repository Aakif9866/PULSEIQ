"""The eval question set — docs/PHASES.md Phase 8 step 3. Every
`expected_value` below is read directly off a real call into
app.ai.tools (see ground_truth.py), never hand-typed/guessed.

`expected_tools`: at least one of these must appear in the response's
tool_calls for the "tool selection" metric to count as correct — a list
because more than one tool can legitimately answer some questions (e.g.
a dataset-wide profile call also contains missing-value/duplicate/
outlier info).

`comparable_to_ask`: whether this question has a single-query shape the
legacy /ask endpoint could plausibly also answer (a straightforward
group/filter/aggregate) — used to decide which questions the runner
also sends through /ask for a head-to-head comparison. Multi-step and
open-ended questions are never comparable — /ask cannot investigate,
only run one query and describe it.
"""
from dataclasses import dataclass, field
from typing import Any

from ground_truth import ground_truth

_ecom = ground_truth("ecommerce")
_emp = ground_truth("employees")


@dataclass
class EvalQuestion:
    id: str
    dataset: str
    question: str
    category: str  # a tool name, "multi_step", or "nl_to_sql"
    expected_tools: list[str]
    expected_value: Any
    value_description: str
    comparable_to_ask: bool = False
    notes: str = ""
    tolerance_pct: float = 2.0
    extra_matches: list[Any] = field(default_factory=list)


QUESTIONS: list[EvalQuestion] = [
    # ---------------------------------------------------- ecommerce ----
    EvalQuestion(
        "ecom-profile-1", "ecommerce", "Give me a full profile of this dataset.",
        "get_dataset_profile", ["get_dataset_profile"],
        _ecom.profile()["dataset"]["rows"], "row count",
    ),
    EvalQuestion(
        "ecom-colstats-1", "ecommerce", "What's the average revenue per order?",
        "get_column_statistics", ["get_column_statistics", "get_dataset_profile"],
        round(_ecom.column_statistics("revenue")["mean"], 2), "mean revenue",
        comparable_to_ask=True,
    ),
    EvalQuestion(
        "ecom-colstats-2", "ecommerce", "What's the median unit price?",
        "get_column_statistics", ["get_column_statistics", "get_dataset_profile"],
        _ecom.column_statistics("unit_price")["median"], "median unit price",
    ),
    EvalQuestion(
        "ecom-missing-1", "ecommerce", "Are there any missing values in this dataset, and which column?",
        "get_missing_values", ["get_missing_values", "get_dataset_profile"],
        _ecom.missing_values()["columns_with_missing_values"]["region"]["missing_count"],
        "missing count in region", extra_matches=["region"],
    ),
    EvalQuestion(
        "ecom-dup-1", "ecommerce", "Are there any duplicate rows in this dataset?",
        "get_duplicates", ["get_duplicates", "get_dataset_profile", "detect_anomalies"],
        _ecom.duplicates()["duplicate_rows"], "duplicate row count",
        comparable_to_ask=True,
    ),
    EvalQuestion(
        "ecom-dup-2", "ecommerce", "Are there any duplicate order IDs?",
        "get_duplicates", ["get_duplicates"],
        _ecom.duplicates_by("order_id")["duplicate_value_count"], "duplicate order_id count",
        extra_matches=["ORD0001"],
    ),
    EvalQuestion(
        "ecom-unique-1", "ecommerce", "What regions are represented in this data?",
        "get_unique_values", ["get_unique_values", "get_column_statistics"],
        sorted(_ecom.unique_values("region")["values"]), "distinct regions",
    ),
    EvalQuestion(
        "ecom-group-1", "ecommerce", "What's the total revenue by category? Which category earns the most?",
        "group_by_aggregate", ["group_by_aggregate"],
        max(_ecom.group_by_aggregate(["category"], "revenue", "sum")["rows"], key=lambda r: r[1])[0],
        "top category by revenue", comparable_to_ask=True,
    ),
    EvalQuestion(
        "ecom-group-2", "ecommerce", "How many orders come from each region?",
        "group_by_aggregate", ["group_by_aggregate"],
        max(
            (r for r in _ecom.group_by_aggregate(["region"], None, "count")["rows"] if r[0] is not None),
            key=lambda r: r[1],
        )[1],
        "largest region order count", comparable_to_ask=True,
    ),
    EvalQuestion(
        "ecom-filter-1", "ecommerce", "How many orders were returned?",
        "filter_rows", ["filter_rows", "group_by_aggregate"],
        _ecom.filter_rows("status", "eq", "returned")["matched_row_count"], "returned order count",
        comparable_to_ask=True,
    ),
    EvalQuestion(
        "ecom-filter-2", "ecommerce", "How many orders have revenue greater than 10000?",
        "filter_rows", ["filter_rows"],
        _ecom.filter_rows("revenue", "gt", 10000)["matched_row_count"], "high-revenue order count",
        comparable_to_ask=True,
    ),
    EvalQuestion(
        "ecom-outlier-1", "ecommerce", "Are there any statistical outliers in revenue?",
        "detect_outliers", ["detect_outliers", "detect_anomalies", "get_dataset_profile"],
        _ecom.detect_outliers("revenue")["count"], "revenue outlier count",
    ),
    EvalQuestion(
        "ecom-outlier-2", "ecommerce", "Are there outliers in the unit price column?",
        "detect_outliers", ["detect_outliers", "detect_anomalies", "get_dataset_profile"],
        _ecom.detect_outliers("unit_price")["count"], "unit_price outlier count",
    ),
    EvalQuestion(
        "ecom-logical-1", "ecommerce", "Are there any impossible or invalid customer ages?",
        "detect_logical_violations", ["detect_logical_violations", "detect_anomalies"],
        _ecom.detect_logical_violations()["violations"]["customer_age"]["violation_count"],
        "invalid age count",
    ),
    EvalQuestion(
        "ecom-anomaly-1", "ecommerce", "Find the most important anomalies in this dataset.",
        "detect_anomalies", ["detect_anomalies", "get_dataset_profile", "detect_outliers", "get_duplicates"],
        _ecom.duplicates()["duplicate_rows"], "duplicate rows (one real anomaly among several)",
    ),
    EvalQuestion(
        "ecom-corr-1", "ecommerce", "How correlated are units sold and revenue?",
        "calculate_correlation", ["calculate_correlation"],
        _ecom.calculate_correlation("units", "revenue")["correlation"], "units/revenue correlation",
        tolerance_pct=5.0,
    ),
    EvalQuestion(
        "ecom-corr-2", "ecommerce", "Is customer age correlated with revenue?",
        "calculate_correlation", ["calculate_correlation"],
        _ecom.calculate_correlation("customer_age", "revenue")["correlation"],
        "age/revenue correlation", tolerance_pct=15.0,
        notes="Near-zero correlation by design (age is randomly generated) — checks the "
        "model reports a weak/no relationship, not a fabricated strong one.",
    ),
    EvalQuestion(
        "ecom-timeseries-1", "ecommerce", "Show total revenue by month over time.",
        "time_series_analysis", ["time_series_analysis"],
        len(_ecom.time_series_analysis("order_date", "revenue", "month")["series"]),
        "number of monthly buckets",
    ),
    EvalQuestion(
        "ecom-compare-1", "ecommerce", "Compare average revenue between regions.",
        "compare_groups", ["compare_groups", "group_by_aggregate"],
        max(
            (g for g in _ecom.compare_groups("region", "revenue", "avg")["groups"] if g["group"] is not None),
            key=lambda g: g["value"],
        )["group"],
        "region with highest average revenue",
    ),
    EvalQuestion(
        "ecom-formula-1", "ecommerce",
        "Does the revenue column actually match units times unit price minus the discount?",
        "validate_formula", ["validate_formula"],
        _ecom.validate_formula("revenue", "units * unit_price * (1 - discount_pct / 100)")["mismatched_rows"],
        "formula mismatch count",
    ),
    EvalQuestion(
        "ecom-formula-2", "ecommerce",
        "Check whether revenue calculations are correct across all orders.",
        "validate_formula", ["validate_formula"],
        _ecom.validate_formula("revenue", "units * unit_price * (1 - discount_pct / 100)")["mismatched_rows"],
        "formula mismatch count (rephrased)",
    ),
    EvalQuestion(
        "ecom-top-1", "ecommerce", "What are the top 5 highest-revenue orders?",
        "get_top_records", ["get_top_records"],
        _ecom.top_records("revenue", 5)["rows"][0]["order_id"], "highest-revenue order id",
    ),
    EvalQuestion(
        "ecom-bottom-1", "ecommerce", "What are the 5 lowest-revenue orders?",
        "get_bottom_records", ["get_bottom_records"],
        _ecom.bottom_records("revenue", 5)["rows"][0]["order_id"], "lowest-revenue order id",
    ),
    EvalQuestion(
        "ecom-multi-1", "ecommerce",
        "Is the unusually high revenue in this dataset caused by bad data or a real large order?",
        "multi_step", ["detect_outliers", "validate_formula", "get_top_records", "detect_anomalies"],
        _ecom.top_records("revenue", 1)["rows"][0]["order_id"],
        "the real large order behind the revenue outlier",
        notes="Requires combining outlier detection with formula validation or inspecting "
        "the actual row — a single query cannot answer this.",
    ),
    EvalQuestion(
        "ecom-multi-2", "ecommerce",
        "Give me a complete executive summary of this dataset's data quality.",
        "multi_step",
        [
            "get_dataset_profile", "detect_anomalies", "get_duplicates",
            "detect_logical_violations", "detect_outliers",
        ],
        _ecom.duplicates()["duplicate_rows"], "duplicate rows (one of several quality issues expected)",
    ),
    EvalQuestion(
        "ecom-sql-1", "ecommerce", "Show total units and revenue per category, sorted by revenue descending.",
        "nl_to_sql", ["ask-sql"],
        max(_ecom.group_by_aggregate(["category"], "revenue", "sum")["rows"], key=lambda r: r[1])[0],
        "top category by revenue (via SQL)",
    ),
    EvalQuestion(
        "ecom-sql-2", "ecommerce",
        "What's the average revenue for delivered orders in the Electronics category?",
        "nl_to_sql", ["ask-sql"],
        round(
            _ecom.df.filter(
                (_ecom.df["status"] == "delivered") & (_ecom.df["category"] == "Electronics")
            )["revenue"].mean(),
            2,
        ),
        "avg revenue, delivered Electronics orders",
    ),
    # ---------------------------------------------------- employees ----
    EvalQuestion(
        "emp-profile-1", "employees", "Summarize this employee dataset.",
        "get_dataset_profile", ["get_dataset_profile"],
        _emp.profile()["dataset"]["rows"], "row count",
    ),
    EvalQuestion(
        "emp-colstats-1", "employees", "What's the average salary?",
        "get_column_statistics", ["get_column_statistics", "get_dataset_profile"],
        round(_emp.column_statistics("salary")["mean"], 2), "mean salary",
        comparable_to_ask=True,
    ),
    EvalQuestion(
        "emp-colstats-2", "employees", "What's the median years of experience?",
        "get_column_statistics", ["get_column_statistics", "get_dataset_profile"],
        _emp.column_statistics("years_experience")["median"], "median years of experience",
    ),
    EvalQuestion(
        "emp-missing-1", "employees", "Which columns have missing values, and how many?",
        "get_missing_values", ["get_missing_values", "get_dataset_profile"],
        _emp.missing_values()["columns_with_missing_values"]["salary"]["missing_count"],
        "missing count in salary", extra_matches=["salary"],
    ),
    EvalQuestion(
        "emp-dup-1", "employees", "Are there any duplicate employee records?",
        "get_duplicates", ["get_duplicates", "get_dataset_profile", "detect_anomalies"],
        _emp.duplicates()["duplicate_rows"], "duplicate row count",
        comparable_to_ask=True,
    ),
    EvalQuestion(
        "emp-dup-2", "employees", "Are there any duplicate employee IDs?",
        "get_duplicates", ["get_duplicates"],
        _emp.duplicates_by("employee_id")["duplicate_value_count"], "duplicate employee_id count",
    ),
    EvalQuestion(
        "emp-unique-1", "employees", "What departments exist in this dataset?",
        "get_unique_values", ["get_unique_values", "get_column_statistics"],
        sorted(_emp.unique_values("department")["values"]), "distinct departments",
    ),
    EvalQuestion(
        "emp-group-1", "employees", "What's the average salary by department? Which department pays the most?",
        "group_by_aggregate", ["group_by_aggregate", "compare_groups"],
        max(_emp.group_by_aggregate(["department"], "salary", "avg")["rows"], key=lambda r: r[1])[0],
        "top-paying department", comparable_to_ask=True,
    ),
    EvalQuestion(
        "emp-group-2", "employees", "How many employees are in each department?",
        "group_by_aggregate", ["group_by_aggregate"],
        max(_emp.group_by_aggregate(["department"], None, "count")["rows"], key=lambda r: r[1])[1],
        "largest department headcount", comparable_to_ask=True,
    ),
    EvalQuestion(
        "emp-filter-1", "employees", "How many employees work remotely?",
        "filter_rows", ["filter_rows", "group_by_aggregate"],
        _emp.filter_rows("remote", "eq", True)["matched_row_count"], "remote employee count",
        comparable_to_ask=True,
    ),
    EvalQuestion(
        "emp-filter-2", "employees", "How many employees have a performance score of 5?",
        "filter_rows", ["filter_rows"],
        _emp.filter_rows("performance_score", "eq", 5)["matched_row_count"], "top-performer count",
        comparable_to_ask=True,
    ),
    EvalQuestion(
        "emp-outlier-1", "employees", "Are there any salary outliers in this dataset?",
        "detect_outliers", ["detect_outliers", "detect_anomalies", "get_dataset_profile"],
        _emp.detect_outliers("salary")["count"], "salary outlier count",
    ),
    EvalQuestion(
        "emp-logical-1", "employees", "Are there any employees with an invalid or out-of-range age?",
        "detect_logical_violations", ["detect_logical_violations", "detect_anomalies", "detect_outliers"],
        _emp.detect_logical_violations()["violations"].get("age", {}).get("violation_count", 0),
        "age rule-violation count (0 expected — a 4-year-old employee is implausible but "
        "numerically within the tool's generic 0-120 rule; a real finding either way)",
        notes="Deliberately checks the tool's actual (generic, not domain-tuned) behavior "
        "rather than what a human would flag.",
    ),
    EvalQuestion(
        "emp-anomaly-1", "employees", "Find anomalies in this employee dataset.",
        "detect_anomalies", ["detect_anomalies", "get_dataset_profile", "detect_outliers", "get_duplicates"],
        _emp.duplicates()["duplicate_rows"], "duplicate rows (one real anomaly among several)",
    ),
    EvalQuestion(
        "emp-corr-1", "employees", "Is there a correlation between years of experience and salary?",
        "calculate_correlation", ["calculate_correlation"],
        _emp.calculate_correlation("years_experience", "salary")["correlation"],
        "experience/salary correlation", tolerance_pct=20.0,
        notes="Near-zero by design (both randomly generated) — checks the model doesn't "
        "fabricate a strong relationship.",
    ),
    EvalQuestion(
        "emp-corr-2", "employees", "Is age correlated with performance score?",
        "calculate_correlation", ["calculate_correlation"],
        _emp.calculate_correlation("age", "performance_score")["correlation"],
        "age/performance correlation", tolerance_pct=20.0,
    ),
    EvalQuestion(
        "emp-timeseries-1", "employees", "Show total salary by hire month over time.",
        "time_series_analysis", ["time_series_analysis"],
        len(_emp.time_series_analysis("hire_date", "salary", "month")["series"]),
        "number of monthly hire buckets",
    ),
    EvalQuestion(
        "emp-compare-1", "employees", "Compare average years of experience across departments.",
        "compare_groups", ["compare_groups", "group_by_aggregate"],
        max(
            _emp.compare_groups("department", "years_experience", "avg")["groups"],
            key=lambda g: g["value"],
        )["group"],
        "most-experienced department on average",
    ),
    EvalQuestion(
        "emp-top-1", "employees", "Who are the 5 highest-paid employees?",
        "get_top_records", ["get_top_records"],
        _emp.top_records("salary", 5)["rows"][0]["employee_id"], "highest-paid employee id",
    ),
    EvalQuestion(
        "emp-bottom-1", "employees", "Who are the 5 lowest-paid employees?",
        "get_bottom_records", ["get_bottom_records"],
        _emp.bottom_records("salary", 5)["rows"][0]["employee_id"], "lowest-paid employee id",
    ),
    EvalQuestion(
        "emp-multi-1", "employees", "Is the highest salary in this dataset a legitimate outlier or a data error?",
        "multi_step", ["detect_outliers", "get_top_records", "detect_anomalies"],
        _emp.top_records("salary", 1)["rows"][0]["employee_id"], "the employee behind the salary outlier",
    ),
    EvalQuestion(
        "emp-multi-2", "employees", "Give me a complete data quality summary for this dataset.",
        "multi_step",
        ["get_dataset_profile", "detect_anomalies", "get_missing_values", "get_duplicates", "detect_outliers"],
        _emp.missing_values()["columns_with_missing_values"]["salary"]["missing_count"],
        "missing salary count (one of several quality issues expected)",
    ),
    EvalQuestion(
        "emp-sql-1", "employees", "What's the average salary per department, sorted from highest to lowest?",
        "nl_to_sql", ["ask-sql"],
        max(_emp.group_by_aggregate(["department"], "salary", "avg")["rows"], key=lambda r: r[1])[0],
        "top-paying department (via SQL)",
    ),
    EvalQuestion(
        "emp-sql-2", "employees", "How many employees have more than 10 years of experience?",
        "nl_to_sql", ["ask-sql"],
        _emp.filter_rows("years_experience", "gt", 10)["matched_row_count"],
        "count of employees with 10+ years experience",
    ),
]

assert len({q.id for q in QUESTIONS}) == len(QUESTIONS), "duplicate question id"
