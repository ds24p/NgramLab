import re
import json
import random
import time
from functools import lru_cache
import urllib.error
import urllib.parse
import urllib.request
import pandas as pd
import numpy as np

try:
    import pyodide_http
except ImportError:
    pyodide_http = None

if pyodide_http is not None:
    pyodide_http.patch_all()


PMW_MULTIPLIER = 1_000_000
PMW_LABEL = "per million words (PMW)"
GOOGLE_NGRAM_JSON_URL = "https://books.google.com/ngrams/json"
GOOGLE_NGRAM_YEAR_MIN = 1800
GOOGLE_NGRAM_YEAR_MAX = 2019
DISPLAY_TEXT_MAX_CHARS = 50
MAX_TERM_INPUT_CHARS = 200

CORPUS_RANGES = {
    "26": (1800, 2019),       # English 2019
    "27": (1800, 2019),       # American English 2019
    "28": (1800, 2019),       # British English 2019
    "29": (1800, 2019),       # English Fiction 2019
    "31": (1800, 2019),       # German 2019
    "33": (1800, 2019),       # Italian 2019
}

def get_corpus_year_range(corpus: str) -> tuple[int, int]:
    return CORPUS_RANGES.get(
        str(corpus),
        (GOOGLE_NGRAM_YEAR_MIN, GOOGLE_NGRAM_YEAR_MAX),
    )

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


def normalize_ngram_year_range(year_start: int, year_end: int) -> tuple[int, int, bool]:
    original_start = int(year_start)
    original_end = int(year_end)

    start = (
        original_start
        if GOOGLE_NGRAM_YEAR_MIN <= original_start <= GOOGLE_NGRAM_YEAR_MAX
        else GOOGLE_NGRAM_YEAR_MIN
    )
    end = (
        original_end
        if GOOGLE_NGRAM_YEAR_MIN <= original_end <= GOOGLE_NGRAM_YEAR_MAX
        else GOOGLE_NGRAM_YEAR_MAX
    )

    if start > end:
        start = GOOGLE_NGRAM_YEAR_MIN
        end = GOOGLE_NGRAM_YEAR_MAX

    return start, end, start != original_start or end != original_end


def truncate_display_text(value, max_chars: int = DISPLAY_TEXT_MAX_CHARS):
    try:
        if pd.isna(value):
            return value
    except (TypeError, ValueError):
        pass

    text = str(value)

    if len(text) <= max_chars:
        return text

    if max_chars <= 3:
        return text[:max_chars]

    return f"{text[:max_chars - 3]}..."


def truncate_display_dataframe(
    df: pd.DataFrame,
    columns: list[str] | tuple[str, ...],
    max_chars: int = DISPLAY_TEXT_MAX_CHARS,
) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    for column in columns:
        if column in out.columns:
            out[column] = out[column].map(
                lambda value: truncate_display_text(value, max_chars=max_chars)
            )

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


def clean_lower_terms(terms) -> list[str]:
    out = []
    seen = set()

    for term in terms:
        term = str(term).strip().lower()
        if not term or term in seen:
            continue

        seen.add(term)
        out.append(term)

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


def read_word_list_from_txt(path: str) -> list[str]:
    words = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            word = line.strip()
            if word:
                words.append(word)

    return unique_words(words)


def read_word_list_from_excel(path: str) -> list[str]:
    df = pd.read_excel(path)

    if df.empty:
        return []

    first_col = df.columns[0]
    words = (
        df[first_col]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )

    return unique_words(words)


def read_lower_terms_from_txt(path: str) -> list[str]:
    return clean_lower_terms(read_word_list_from_txt(path))


def read_lower_terms_from_excel(path: str) -> list[str]:
    return clean_lower_terms(read_word_list_from_excel(path))


def build_ngram_request_url(params: dict) -> str:
    query = urllib.parse.urlencode(params)
    return GOOGLE_NGRAM_JSON_URL + "?" + query


def _read_json_url(url: str, timeout: int = 30):
    max_retries = 6
    backoff_base = 1.0

    for attempt in range(1, max_retries + 1):
        try:
            headers = {}

            if pyodide_http is None:
                headers["User-Agent"] = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0 Safari/537.36"
                )

            req = urllib.request.Request(
                url,
                headers=headers,
            )

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")

            return json.loads(raw)

        except urllib.error.HTTPError as http_error:
            if http_error.code == 429 and attempt < max_retries:
                wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                time.sleep(wait)
                continue
            raise

        except urllib.error.URLError:
            if attempt < max_retries:
                wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                time.sleep(wait)
                continue
            raise

    raise RuntimeError("Failed to fetch Google Ngram data.")


@lru_cache(maxsize=2048)
def _fetch_ngram_timeseries_cached(
    word: str,
    year_start: int,
    year_end: int,
    corpus: str,
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

    url = build_ngram_request_url(params)
    data = _read_json_url(url, timeout=timeout)

    if not data:
        return tuple()

    item = next(
        (
            entry
            for entry in data
            if isinstance(entry, dict) and entry.get("ngram") == word
        ),
        data[0],
    )

    ts = item.get("timeseries", []) if isinstance(item, dict) else []

    if not isinstance(ts, list):
        return tuple()

    return tuple(float(v) for v in ts)


def fetch_ngram_timeseries(
    word: str,
    year_start: int,
    year_end: int,
    corpus: int | str,
    smoothing: int = 0,
    case_insensitive: bool = False,
    timeout: int = 30,
):
    min_year, max_year = get_corpus_year_range(str(corpus))

    if not (
        min_year <= year_start < year_end <= max_year
    ):
        raise ValueError(
            f"Invalid year range {year_start}–{year_end}. "
            f"Available years for corpus {corpus}: "
            f"{min_year}–{max_year}."
        )

    ts = _fetch_ngram_timeseries_cached(
        str(word),
        year_start,
        year_end,
        str(corpus),
        int(smoothing),
        bool(case_insensitive),
        int(timeout),
    )
    return list(ts)


@lru_cache(maxsize=256)
def _fetch_google_ngram_pmw_rows_cached(
    terms: tuple[str, ...],
    year_start: int,
    year_end: int,
    corpus: str,
    smoothing: int,
    timeout: int,
) -> tuple[tuple[str, int, float], ...]:
    query = ",".join(terms)
    url = build_ngram_request_url(
        {
            "content": query,
            "year_start": year_start,
            "year_end": year_end,
            "corpus": corpus,
            "smoothing": smoothing,
        },
    )

    data = _read_json_url(url, timeout=timeout)
    years = list(range(year_start, year_end + 1))
    rows = []
    seen_terms = set()

    for item in data:
        if not isinstance(item, dict):
            continue

        term = item.get("ngram")
        values = item.get("timeseries", [])

        if not term or not isinstance(values, list):
            continue

        seen_terms.add(str(term).strip().lower())

        for year, value in zip(years, values):
            rows.append((term, year, round(float(value) * PMW_MULTIPLIER, 2)))

    for term in terms:
        term_key = str(term).strip().lower()

        if term_key and term_key not in seen_terms:
            rows.extend((term, year, 0.0) for year in years)

    return tuple(rows)


def fetch_google_ngram_pmw(
    terms: list[str],
    year_start: int,
    year_end: int,
    corpus: str,
    smoothing: int,
    timeout: int = 30,
) -> pd.DataFrame:
    clean = tuple(t.strip() for t in terms if str(t).strip())

    if not clean:
        return pd.DataFrame()

    year_start, year_end, _ = normalize_ngram_year_range(year_start, year_end)

    if year_start > year_end:
        return pd.DataFrame()

    rows = _fetch_google_ngram_pmw_rows_cached(
        clean,
        year_start,
        year_end,
        str(corpus),
        int(smoothing),
        int(timeout),
    )

    return pd.DataFrame(rows, columns=["term", "year", "frequency"])


def build_ngram_wide_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "error" in df.columns:
        return pd.DataFrame()

    wide_df = (
        df.pivot_table(
            index="year",
            columns="term",
            values="frequency",
            aggfunc="first"
        )
        .reset_index()
    )

    wide_df.columns.name = None

    numeric_cols = wide_df.columns.drop("year")
    wide_df[numeric_cols] = wide_df[numeric_cols].round(2)

    return wide_df


def build_ngram_auc_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "error" in df.columns:
        return pd.DataFrame()

    rows = []

    for term, group in df.groupby("term"):
        group = group.sort_values("year")
        years = group["year"].tolist()
        values = group["frequency"].to_numpy(dtype=float)

        rows.append(
            {
                "term": term,
                "auc": round(auc_trapezoid(years, values), 2),
                "mean_pmw": round(float(np.nanmean(values)), 2),
                "max_pmw": round(float(np.nanmax(values)), 2),
            }
        )

    return pd.DataFrame(rows).sort_values("auc", ascending=False)


def build_ngram_group_mean_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "error" in df.columns:
        return pd.DataFrame()

    result = (
        df.groupby("year", as_index=False)["frequency"]
        .mean()
        .rename(columns={"frequency": "mean_pmw"})
    )
    result["mean_pmw"] = result["mean_pmw"].round(2)

    return result


def parse_client_api_payload(payload) -> dict:
    if not payload:
        return {}

    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return {}

    if isinstance(payload, dict):
        return payload

    return {}
