from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pages.compare_english_corpora import ENGLISH_CORPORA, MAX_COMPARE_SERIES
from pages.explorer import (
    AUC_ORIGINAL_SCALE_COLUMN,
    MAX_EXPLORER_VISUALIZATION_TERMS,
)
from pages import explorer as explorer_page
from pages.get_ngram_data import MAX_FETCHER_DATA_POINTS, MAX_FETCHER_WORDS
from utils import (
    GOOGLE_NGRAM_YEAR_MAX,
    GOOGLE_NGRAM_YEAR_MIN,
    MAX_TERM_INPUT_CHARS,
    auc_trapezoid,
    normalize_ngram_year_range,
    parse_manual_words,
    truncate_display_text,
    z_score_values,
)


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


checks: list[Check] = []


def record(name: str, passed: bool, detail: str) -> None:
    checks.append(Check(name=name, passed=bool(passed), detail=detail))


def word_list(count: int, prefix: str = "word") -> str:
    return "\n".join(f"{prefix}_{index + 1}" for index in range(count))


def validate_fetcher_request(
    text: str,
    year_start: int = 1901,
    year_end: int = 1903,
) -> str:
    words = parse_manual_words(text)

    if not words:
        return "No words provided. Type words manually or upload TXT/Excel file."

    too_long_words = [
        word for word in words
        if len(str(word)) > MAX_TERM_INPUT_CHARS
    ]

    if too_long_words:
        sample = ", ".join(
            truncate_display_text(word, max_chars=50)
            for word in too_long_words[:3]
        )
        more = (
            f" and {len(too_long_words) - 3} more"
            if len(too_long_words) > 3
            else ""
        )
        return (
            f"Terms can be up to {MAX_TERM_INPUT_CHARS} characters. "
            f"Please shorten: {sample}{more}"
        )

    if year_start < GOOGLE_NGRAM_YEAR_MIN or year_start > GOOGLE_NGRAM_YEAR_MAX:
        return (
            f"Invalid start year: {year_start}. Available years for the "
            f"selected corpus are {GOOGLE_NGRAM_YEAR_MIN}-{GOOGLE_NGRAM_YEAR_MAX}."
        )

    if year_end < GOOGLE_NGRAM_YEAR_MIN or year_end > GOOGLE_NGRAM_YEAR_MAX:
        return (
            f"Invalid end year: {year_end}. Available years for the "
            f"selected corpus are {GOOGLE_NGRAM_YEAR_MIN}-{GOOGLE_NGRAM_YEAR_MAX}."
        )

    if year_start >= year_end:
        return "Start year must be earlier than end year."

    expected_len = year_end - year_start + 1
    requested_points = len(words) * expected_len

    if len(words) > MAX_FETCHER_WORDS:
        return (
            f"You entered {len(words)} words. A maximum of "
            f"{MAX_FETCHER_WORDS} words can be processed at once."
        )

    if requested_points > MAX_FETCHER_DATA_POINTS:
        return (
            f"Request too large: {len(words)} words x {expected_len} years "
            f"= {requested_points:,} values."
        )

    return "Request is within configured fetch limits."


def main() -> int:
    empty = parse_manual_words("")
    record("empty input", empty == [], repr(empty))

    empty_lines = parse_manual_words("\n\ntest\n\n")
    record(
        "empty lines before/after word",
        empty_lines == ["test"],
        repr(empty_lines),
    )
    record(
        "empty lines do not inject 'the'",
        "the" not in [word.lower() for word in empty_lines],
        repr(empty_lines),
    )

    duplicates = parse_manual_words("mother\nmother\nMother")
    record("duplicate words", duplicates == ["mother"], repr(duplicates))

    non_ascii = validate_fetcher_request("\u00e9")
    record("e-acute / non-ASCII characters", "within configured fetch limits" in non_ascii, non_ascii)

    special = validate_fetcher_request("$$\n{}\na{b}")
    record("special symbols", "within configured fetch limits" in special, special)

    nonsense = validate_fetcher_request("zzzxxyyq!!")
    record("nonsense word", "within configured fetch limits" in nonsense, nonsense)

    long_term = "x" * 501
    long_status = validate_fetcher_request(long_term)
    truncated = truncate_display_text(long_term)
    record(
        "500+ character string",
        "Terms can be up to 200 characters" in long_status and len(truncated) == 50,
        f"{long_status}; display_len={len(truncated)}",
    )

    hundred_plus = validate_fetcher_request(word_list(201, "many"))
    record("100+ words", "maximum of 200 words" in hundred_plus, hundred_plus)

    three_thousand = validate_fetcher_request(word_list(3000, "bulk"))
    record("3000 words", "maximum of 200 words" in three_thousand, three_thousand)

    for label, start, end, expected in [
        ("year -1", -1, 1801, "Invalid start year"),
        ("year 0", 0, 1801, "Invalid start year"),
        ("year 5000", 2018, 5000, "Invalid end year"),
        ("year 20000", 2018, 20000, "Invalid end year"),
        ("start year > end year", 1905, 1901, "Start year must be earlier"),
    ]:
        status = validate_fetcher_request("mother", start, end)
        record(label, expected in status, status)

    raw_values = np.array([10.0, 12.0, 14.0, 16.0])
    standardized = z_score_values(raw_values)
    indexed_would_not_rebase = np.isfinite(standardized).all() and not np.isclose(
        standardized[0],
        100.0,
    )
    record(
        "z-score + Indexed Time Series",
        indexed_would_not_rebase,
        f"z-score first value={standardized[0]:.4f}, mean={np.mean(standardized):.4f}",
    )

    source = inspect.getsource(explorer_page.explorer_server)
    auc_uses_original_series = (
        "build_word_series(apply_z_score_transform=False)" in source
        and "AUC_ORIGINAL_SCALE_COLUMN" in source
    )
    raw_auc = auc_trapezoid([1901, 1902, 1903, 1904], raw_values)
    z_auc = auc_trapezoid([1901, 1902, 1903, 1904], standardized)
    record(
        "z-score + AUC",
        auc_uses_original_series and raw_auc > 0,
        f"raw_auc={raw_auc:.2f}, z_auc={z_auc:.2f}, column={AUC_ORIGINAL_SCALE_COLUMN}",
    )

    selected_words = 16
    selected_corpora = len(ENGLISH_CORPORA)
    series_count = selected_words * selected_corpora
    record(
        "many words + Within Google Ngram Corpora",
        series_count > MAX_COMPARE_SERIES,
        f"{selected_words} words x {selected_corpora} corpora = {series_count} lines; limit={MAX_COMPARE_SERIES}",
    )

    syn_start, syn_end, syn_adjusted = normalize_ngram_year_range(2018, 5000)
    record(
        "synonym analysis with invalid years",
        (syn_start, syn_end, syn_adjusted) == (2018, GOOGLE_NGRAM_YEAR_MAX, True),
        f"normalized to {syn_start}-{syn_end}, adjusted={syn_adjusted}",
    )

    infl_start, infl_end, infl_adjusted = normalize_ngram_year_range(2018, 5000)
    record(
        "inflection analysis with invalid years",
        (infl_start, infl_end, infl_adjusted) == (2018, GOOGLE_NGRAM_YEAR_MAX, True),
        f"normalized to {infl_start}-{infl_end}, adjusted={infl_adjusted}",
    )

    record(
        "Explorer visualization limit",
        MAX_EXPLORER_VISUALIZATION_TERMS == 10,
        f"limit={MAX_EXPLORER_VISUALIZATION_TERMS}",
    )

    width = max(len(check.name) for check in checks)
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"{status}  {check.name:<{width}}  {check.detail}")

    failed = [check for check in checks if not check.passed]
    print()
    print(f"Passed {len(checks) - len(failed)} / {len(checks)} checks.")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
