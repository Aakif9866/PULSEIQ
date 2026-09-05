"""Computes the column-level profile shown in the dataset explorer."""
from dataclasses import dataclass
from typing import Any

import polars as pl


@dataclass
class DatasetProfile:
    row_count: int
    column_count: int
    columns: list[dict[str, Any]]  # [{"name", "dtype", "null_count"}, ...]


def profile_dataframe(df: pl.DataFrame) -> DatasetProfile:
    null_counts = df.null_count().row(0, named=True)
    columns = [
        {"name": name, "dtype": str(dtype), "null_count": null_counts[name]}
        for name, dtype in df.schema.items()
    ]
    return DatasetProfile(row_count=df.height, column_count=df.width, columns=columns)
