import re
import pandas as pd
import numpy as np


def year_columns(df: pd.DataFrame) -> list[int]:
    years = []
    for col in df.columns:
        value = str(col).strip()
        if re.fullmatch(r"\d{4}", value):
            year = int(value)
            if 1400 <= year <= 2100:
                years.append(year)
    return sorted(set(years))


def load_word_year_matrix(path: str) -> tuple[pd.DataFrame, list[int]]:
    df = pd.read_excel(path)

    word_col = df.columns[0]
    df = df.rename(columns={word_col: "word"})
    df["word"] = df["word"].astype(str).str.strip()

    years = year_columns(df)

    rename_map = {}
    for col in df.columns:
        value = str(col).strip()
        if re.fullmatch(r"\d{4}", value):
            year = int(value)
            if year in years:
                rename_map[col] = year

    df = df.rename(columns=rename_map)
    df = df[["word"] + years].copy()

    for year in years:
        df[year] = pd.to_numeric(df[year], errors="coerce")

    return df, years


def auc_trapezoid(years: list[int], values: np.ndarray) -> float:
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)
    y = np.where(np.isfinite(y), y, 0.0)

    try:
        return float(np.trapezoid(y, x))
    except AttributeError:
        return float(np.trapz(y, x))