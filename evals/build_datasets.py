"""Generates the two eval sample datasets deterministically (seeded
random) so a re-run produces byte-identical CSVs — the ground truth in
ground_truth.py is computed against these exact files, not against
"a" random e-commerce/employees dataset that changes between runs.

Both datasets deliberately carry the same kinds of real data-quality
issues used throughout this project's own testing (duplicates, an
out-of-range value, a formula mismatch, statistical outliers) so the
eval set can exercise every one of the 16 analytical tools meaningfully,
not just group-by/aggregate ones.
"""
import random
from pathlib import Path

import polars as pl

_OUT_DIR = Path(__file__).parent / "datasets"
_SEED = 20260925  # today's date, Phase 8 step 3 — fixed, not re-rolled


def build_ecommerce(n: int = 120) -> pl.DataFrame:
    rng = random.Random(_SEED)
    categories = ["Electronics", "Home", "Beauty", "Sports", "Books"]
    regions = ["North", "South", "East", "West"]
    order_ids = [f"ORD{i:04d}" for i in range(1, n + 1)]
    customer_ids = [f"C{rng.randint(1, n // 3):04d}" for _ in range(n)]
    categories_col = [rng.choice(categories) for _ in range(n)]
    regions_col = [rng.choice(regions) for _ in range(n)]
    units = [rng.randint(1, 5) for _ in range(n)]
    unit_price = [round(rng.uniform(50, 800), 2) for _ in range(n)]
    discount_pct = [rng.choice([0, 0, 0, 5, 10, 15]) for _ in range(n)]
    customer_age = [rng.randint(18, 70) for _ in range(n)]
    dates = [f"2024-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}" for _ in range(n)]
    status = [rng.choice(["delivered", "delivered", "delivered", "returned"]) for _ in range(n)]

    revenue = [
        round(u * p * (1 - d / 100), 2) for u, p, d in zip(units, unit_price, discount_pct, strict=False)
    ]

    # --- deliberate, deterministic data-quality issues ---
    # 3 exact duplicate rows (indices 10-12 copy row 0's values).
    for i in (10, 11, 12):
        order_ids[i] = order_ids[0]
        customer_ids[i] = customer_ids[0]
        categories_col[i] = categories_col[0]
        regions_col[i] = regions_col[0]
        units[i] = units[0]
        unit_price[i] = unit_price[0]
        discount_pct[i] = discount_pct[0]
        customer_age[i] = customer_age[0]
        dates[i] = dates[0]
        status[i] = status[0]
        revenue[i] = revenue[0]
    # A logical violation: an impossible age.
    customer_age[20] = -4
    customer_age[21] = 143
    # A formula mismatch: revenue doesn't match units*price*(1-discount).
    revenue[30] = 0.0
    # A statistical outlier: one enormous order.
    units[40] = 90
    unit_price[40] = 4999.0
    discount_pct[40] = 0
    revenue[40] = round(90 * 4999.0, 2)

    # 6 missing values in region — a real, deliberate gap for
    # get_missing_values to have something meaningful to find.
    regions_with_nulls: list[str | None] = list(regions_col)
    for i in (50, 51, 52, 53, 54, 55):
        regions_with_nulls[i] = None

    return pl.DataFrame(
        {
            "order_id": order_ids,
            "customer_id": customer_ids,
            "category": categories_col,
            "region": regions_with_nulls,
            "units": units,
            "unit_price": unit_price,
            "discount_pct": discount_pct,
            "revenue": revenue,
            "customer_age": customer_age,
            "order_date": dates,
            "status": status,
        }
    )


def build_employees(n: int = 100) -> pl.DataFrame:
    rng = random.Random(_SEED + 1)
    departments = ["Engineering", "Sales", "Support", "Marketing", "Finance"]
    employee_ids = [f"E{i:04d}" for i in range(1, n + 1)]
    names_dept = [rng.choice(departments) for _ in range(n)]
    age = [rng.randint(22, 60) for _ in range(n)]
    salary = [round(rng.uniform(40000, 150000), 2) for _ in range(n)]
    years_experience = [round(rng.uniform(0, 25), 1) for _ in range(n)]
    performance_score = [rng.randint(1, 5) for _ in range(n)]
    hire_dates = [
        f"20{rng.randint(15, 24):02d}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
        for _ in range(n)
    ]
    remote = [rng.choice([True, False]) for _ in range(n)]

    # --- deliberate, deterministic data-quality issues ---
    for i in (5, 6):
        employee_ids[i] = employee_ids[0]
        names_dept[i] = names_dept[0]
        age[i] = age[0]
        salary[i] = salary[0]
        years_experience[i] = years_experience[0]
        performance_score[i] = performance_score[0]
        hire_dates[i] = hire_dates[0]
        remote[i] = remote[0]
    performance_score[15] = 9  # out of the 1-5 scale
    age[16] = 4  # implausible
    salary[25] = 950000.0  # a real outlier

    # 4 missing values in salary.
    salary_with_nulls: list[float | None] = list(salary)
    for i in (40, 41, 42, 43):
        salary_with_nulls[i] = None

    return pl.DataFrame(
        {
            "employee_id": employee_ids,
            "department": names_dept,
            "age": age,
            "salary": salary_with_nulls,
            "years_experience": years_experience,
            "performance_score": performance_score,
            "hire_date": hire_dates,
            "remote": remote,
        }
    )


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    build_ecommerce().write_csv(_OUT_DIR / "ecommerce.csv")
    build_employees().write_csv(_OUT_DIR / "employees.csv")
    print(f"Wrote datasets to {_OUT_DIR}")


if __name__ == "__main__":
    main()
