import re
import json
import time
import random
from functools import lru_cache
import urllib.error
import urllib.parse
import urllib.request
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


def get_year_columns(df: pd.DataFrame, years: list[int]) -> list[int | str]:
    cols: list[int | str] = []
    for year in years:
        if year in df.columns:
            cols.append(year)
        elif str(year) in df.columns:
            cols.append(str(year))
    return cols


def safe_corr(a, b) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)

    mask = np.isfinite(a) & np.isfinite(b)

    if mask.sum() < 2:
        return np.nan

    if np.nanstd(a[mask]) == 0 or np.nanstd(b[mask]) == 0:
        return np.nan

    return float(np.corrcoef(a[mask], b[mask])[0, 1])


def slope_per_year(years, values) -> float:
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)

    mask = np.isfinite(x) & np.isfinite(y)

    if mask.sum() < 2:
        return np.nan

    return float(np.polyfit(x[mask], y[mask], 1)[0])


def trend_label(slope: float, threshold: float = 0.0) -> str:
    if not np.isfinite(slope):
        return "unknown"

    if slope > threshold:
        return "rising"

    if slope < -threshold:
        return "falling"

    return "stable"


def z_score_values(values):
    values = np.asarray(values, dtype=float)
    mean = np.nanmean(values) if np.isfinite(values).any() else np.nan
    std = np.nanstd(values) if np.isfinite(values).any() else np.nan

    if not np.isfinite(std) or std == 0:
        return np.zeros_like(values, dtype=float)

    return (values - mean) / std


def smooth_series(values, window: int = 3):
    arr = np.asarray(values, dtype=float)
    window = int(window)

    if window <= 1 or arr.size == 0:
        return arr.copy()

    return (
        pd.Series(arr)
        .rolling(window=window, center=True, min_periods=1)
        .mean()
        .to_numpy(dtype=float)
    )


def round_numeric_df(df: pd.DataFrame, digits: int = 2) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    numeric_cols = out.select_dtypes(include=[np.number]).columns
    out[numeric_cols] = out[numeric_cols].round(digits)
    return out


def unique_words(words) -> list[str]:
    out = []
    seen = set()

    for word in words:
        word = str(word).strip()
        if not word:
            continue

        key = word.lower()

        if key not in seen:
            seen.add(key)
            out.append(word)

    return out


def parse_manual_words(text: str) -> list[str]:
    if not text:
        return []

    raw_words: list[str] = []

    for line in text.replace(",", "\n").splitlines():
        word = line.strip()

        if word:
            raw_words.append(word)

    return unique_words(raw_words)


@lru_cache(maxsize=2048)
def _fetch_ngram_timeseries_cached(
    word: str,
    year_start: int,
    year_end: int,
    corpus: int,
    smoothing: int,
    case_insensitive: bool,
    timeout: int,
) -> tuple[float, ...]:
    params = {
        "content": word,
        "year_start": str(year_start),
        "year_end": str(year_end),
        "corpus": str(corpus),
        "smoothing": str(smoothing),
    }

    if case_insensitive:
        params["case_insensitive"] = "on"

    url = "https://books.google.com/ngrams/json?" + urllib.parse.urlencode(params)

    max_retries = 6
    backoff_base = 1.0

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
            )

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")

            data = json.loads(raw)

            if not data:
                return tuple()

            ts = data[0].get("timeseries", [])

            if not isinstance(ts, list):
                return tuple()

            return tuple(float(v) for v in ts)

        except urllib.error.HTTPError as http_error:
            if http_error.code == 429:
                wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                time.sleep(wait)
                continue
            raise

        except urllib.error.URLError:
            wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
            time.sleep(wait)
            continue

    raise RuntimeError(f"Failed to fetch data for '{word}'.")


def fetch_ngram_timeseries(
    word: str,
    year_start: int,
    year_end: int,
    corpus: int,
    smoothing: int = 0,
    case_insensitive: bool = False,
    timeout: int = 30,
):
    ts = _fetch_ngram_timeseries_cached(
        str(word),
        int(year_start),
        int(year_end),
        int(corpus),
        int(smoothing),
        bool(case_insensitive),
        int(timeout),
    )
    return list(ts)
