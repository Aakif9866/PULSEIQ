"""Loads a stored dataset file into an in-memory Polars DataFrame.

Datasets are re-loaded from storage on every profile/query call rather than
cached — simple and correct for this phase's scale (QUERY_ROW_LIMIT-bounded
results over dev-sized files). Revisit if this becomes a bottleneck.
"""
import io
from pathlib import PurePosixPath

import polars as pl

from app.core.exceptions import UnsupportedFileFormatError
from app.models.dataset import Dataset
from app.storage.base import StorageProvider

# A leading zero followed by another digit means the zero is semantically
# part of the value (zip code, SKU, employee id, ...), not a number —
# Polars' own inference doesn't know this and silently strips it.
_LEADING_ZERO_INT = r"^-?0\d+$"
_PLAIN_INT = r"^-?\d+$"
_PLAIN_NUMBER = r"^-?\d+(\.\d+)?$"


def _read_csv_preserving_leading_zeros(buffer: io.BytesIO) -> pl.DataFrame:
    """Reads with schema inference off (every column comes back as String,
    nulls preserved as real nulls) and casts each column to Int64/Float64
    myself — except any column where a value would lose a leading zero."""
    df = pl.read_csv(buffer, infer_schema_length=0)

    for name in df.columns:
        non_null = df[name].drop_nulls()
        if non_null.len() == 0:
            continue
        if non_null.str.contains(_LEADING_ZERO_INT).any():
            continue  # keep as string — a leading zero here must survive

        dtype: type[pl.DataType] | None = None
        if non_null.str.contains(_PLAIN_INT).all():
            dtype = pl.Int64
        elif non_null.str.contains(_PLAIN_NUMBER).all():
            dtype = pl.Float64

        if dtype is not None:
            df = df.with_columns(pl.col(name).cast(dtype, strict=False))

    return df


def load_dataframe(storage: StorageProvider, dataset: Dataset) -> pl.DataFrame:
    extension = PurePosixPath(dataset.original_filename).suffix.lower()
    with storage.open(dataset.storage_key) as f:
        data = f.read()
    buffer = io.BytesIO(data)

    if extension == ".csv":
        return _read_csv_preserving_leading_zeros(buffer)
    if extension == ".xlsx":
        return pl.read_excel(buffer, engine="openpyxl")

    # Legacy .xls is accepted at upload time (see ALLOWED_UPLOAD_EXTENSIONS)
    # but openpyxl can't read it and we don't carry a dependency for it yet.
    raise UnsupportedFileFormatError(extension)
