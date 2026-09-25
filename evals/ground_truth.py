"""Computes every eval question's ground truth by calling this project's
own real, already-unit-tested deterministic functions
(app.ai.tools / app.analytics.data_profile — pure Polars, no LLM
involved anywhere in this file) directly against the eval datasets.

This is a deliberate design choice, not an oversight: it would be
possible to write a second, independent implementation of "what's the
median revenue" or "how many duplicate rows" by hand here, but that
would only prove the eval's own arithmetic is self-consistent, not that
the app's answer is *right* — and any drift between a hand-rolled
duplicate implementation and the app's real one would silently produce
a wrong ground truth. Calling the app's real tool layer instead means
the eval is checking "did the AI orchestrate these exact tools and
report their exact numbers correctly," which is precisely what
docs/AI_ANALYTICS.md's hybrid engine promises. See docs/EVALS.md's
Methodology section.
"""
import sys
from pathlib import Path

_BACKEND = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(_BACKEND))

import polars as pl  # noqa: E402
from app.ai import tools  # noqa: E402

_DATASETS_DIR = Path(__file__).parent / "datasets"


def load_dataset(name: str) -> pl.DataFrame:
    return pl.read_csv(_DATASETS_DIR / f"{name}.csv")


class GroundTruth:
    """Lazily computes and caches every tool's real output for one
    dataset, so eval question definitions can just read a field off it
    instead of each re-running the same tool call."""

    def __init__(self, dataset_name: str) -> None:
        self.dataset_name = dataset_name
        self.df = load_dataset(dataset_name)
        self._cache: dict[str, dict] = {}

    def _cached(self, key: str, compute) -> dict:
        if key not in self._cache:
            self._cache[key] = compute()
        return self._cache[key]

    def profile(self) -> dict:
        return self._cached("profile", lambda: tools.get_dataset_profile(self.df))

    def missing_values(self) -> dict:
        return self._cached("missing_values", lambda: tools.get_missing_values(self.df))

    def duplicates(self) -> dict:
        return self._cached("duplicates", lambda: tools.get_duplicates(self.df))

    def duplicates_by(self, column: str) -> dict:
        return self._cached(
            f"duplicates_by:{column}", lambda: tools.get_duplicates(self.df, column=column)
        )

    def column_statistics(self, column: str) -> dict:
        return self._cached(
            f"column_stats:{column}", lambda: tools.get_column_statistics(self.df, column)
        )

    def unique_values(self, column: str, limit: int = 20) -> dict:
        return self._cached(
            f"unique:{column}", lambda: tools.get_unique_values(self.df, column, limit)
        )

    def group_by_aggregate(self, group_by: list[str], column: str | None, op: str) -> dict:
        key = f"group:{group_by}:{column}:{op}"
        return self._cached(
            key, lambda: tools.group_by_aggregate(self.df, group_by, column, op)
        )

    def filter_rows(self, column: str, op: str, value: object, limit: int = 20) -> dict:
        key = f"filter:{column}:{op}:{value}"
        return self._cached(key, lambda: tools.filter_rows(self.df, column, op, value, limit))

    def detect_outliers(self, column: str) -> dict:
        return self._cached(
            f"outliers:{column}", lambda: tools.detect_outliers(self.df, column)
        )

    def detect_logical_violations(self) -> dict:
        return self._cached(
            "logical_violations", lambda: tools.detect_logical_violations(self.df)
        )

    def detect_anomalies(self) -> dict:
        return self._cached("anomalies", lambda: tools.detect_anomalies(self.df))

    def calculate_correlation(self, column_a: str, column_b: str) -> dict:
        return self._cached(
            f"corr:{column_a}:{column_b}",
            lambda: tools.calculate_correlation(self.df, column_a, column_b),
        )

    def time_series_analysis(self, date_column: str, metric_column: str, freq: str = "day") -> dict:
        key = f"timeseries:{date_column}:{metric_column}:{freq}"
        return self._cached(
            key, lambda: tools.time_series_analysis(self.df, date_column, metric_column, freq)
        )

    def compare_groups(self, group_column: str, metric_column: str, op: str = "avg") -> dict:
        key = f"compare:{group_column}:{metric_column}:{op}"
        return self._cached(
            key, lambda: tools.compare_groups(self.df, group_column, metric_column, op)
        )

    def validate_formula(self, target_column: str, formula: str, tolerance_pct: float = 1.0) -> dict:
        key = f"formula:{target_column}:{formula}"
        return self._cached(
            key,
            lambda: tools.validate_formula(self.df, target_column, formula, tolerance_pct),
        )

    def top_records(self, column: str, n: int = 10) -> dict:
        return self._cached(f"top:{column}:{n}", lambda: tools.get_top_records(self.df, column, n))

    def bottom_records(self, column: str, n: int = 10) -> dict:
        return self._cached(
            f"bottom:{column}:{n}", lambda: tools.get_bottom_records(self.df, column, n)
        )


_INSTANCES: dict[str, GroundTruth] = {}


def ground_truth(dataset_name: str) -> GroundTruth:
    if dataset_name not in _INSTANCES:
        _INSTANCES[dataset_name] = GroundTruth(dataset_name)
    return _INSTANCES[dataset_name]
