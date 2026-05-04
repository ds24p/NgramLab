from shiny import reactive, render, ui
import pandas as pd
import numpy as np
import urllib.parse
import urllib.request
import urllib.error
import json
import time
import random
import tempfile
import matplotlib.pyplot as plt


POLITE_DELAY_SEC = 0.4

ENGLISH_CORPORA = {
    "26": "English 2019",
    "27": "American English 2019",
    "28": "British English 2019",
    "29": "English Fiction 2019",
}


def fetch_ngram_timeseries(
    word: str,
    year_start: int,
    year_end: int,
    corpus: int,
    smoothing: int = 0,
    case_insensitive: bool = False,
    timeout: int = 30,
):
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
                headers={"User-Agent": "Mozilla/5.0"}
            )

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")

            data = json.loads(raw)

            if not data:
                return []

            ts = data[0].get("timeseries", [])

            if not isinstance(ts, list):
                return []

            return ts

        except urllib.error.HTTPError as he:
            if he.code == 429:
                wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                time.sleep(wait)
                continue
            raise

        except urllib.error.URLError:
            wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
            time.sleep(wait)
            continue

    raise RuntimeError(f"Failed to fetch data for '{word}'.")


def unique_words(words):
    out = []
    seen = set()

    for w in words:
        w = str(w).strip()
        if not w:
            continue

        key = w.lower()

        if key not in seen:
            seen.add(key)
            out.append(w)

    return out


def parse_manual_words(text: str):
    if not text:
        return []

    raw_words = []

    for line in text.replace(",", "\n").splitlines():
        word = line.strip()

        if word:
            raw_words.append(word)

    return unique_words(raw_words)


def auc_trapezoid(years, values):
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)

    y = np.where(np.isfinite(y), y, 0.0)

    if len(x) < 2 or len(y) < 2:
        return 0.0

    return float(np.sum((y[1:] + y[:-1]) / 2 * (x[1:] - x[:-1])))


def safe_corr(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)

    mask = np.isfinite(a) & np.isfinite(b)

    if mask.sum() < 2:
        return np.nan

    if np.nanstd(a[mask]) == 0 or np.nanstd(b[mask]) == 0:
        return np.nan

    return float(np.corrcoef(a[mask], b[mask])[0, 1])


def slope_per_year(years, values):
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)

    mask = np.isfinite(x) & np.isfinite(y)

    if mask.sum() < 2:
        return np.nan

    return float(np.polyfit(x[mask], y[mask], 1)[0])


def trend_label(slope, threshold=0.000001):
    if not np.isfinite(slope):
        return "unknown"

    if slope > threshold:
        return "rising"

    if slope < -threshold:
        return "falling"

    return "stable"


def safe_peak_year(years, values):
    values = np.asarray(values, dtype=float)

    if not np.isfinite(values).any():
        return np.nan

    return years[int(np.nanargmax(values))]


def safe_ratio(a, b):
    if not np.isfinite(a) or not np.isfinite(b) or b == 0:
        return np.nan

    return a / b


def get_compare_english_corpora_ui():
    return ui.div(
        ui.div("Compare English Corpora", class_="page-title"),

        ui.p(
            "Compare selected English Google Ngram corpora. "
            "Values are converted from raw relative frequencies to words per million.",
            class_="muted"
        ),

        ui.layout_sidebar(
            ui.sidebar(
                ui.input_text_area(
                    "compare_words",
                    "Words to compare",
                    placeholder="Example:\nlove\nwar\nfreedom",
                    rows=7
                ),

                ui.input_checkbox_group(
                    "selected_corpora",
                    "Select English corpora",
                    choices=ENGLISH_CORPORA,
                    selected=list(ENGLISH_CORPORA.keys())
                ),

                ui.input_numeric(
                    "compare_year_start",
                    "Start year",
                    value=1901,
                    min=1500,
                    max=2019
                ),

                ui.input_numeric(
                    "compare_year_end",
                    "End year",
                    value=2000,
                    min=1500,
                    max=2019
                ),

                ui.input_numeric(
                    "compare_smoothing",
                    "Smoothing",
                    value=0,
                    min=0,
                    max=50
                ),

                ui.input_checkbox(
                    "compare_case_insensitive",
                    "Case insensitive",
                    value=False
                ),

                ui.input_action_button(
                    "run_english_corpus_comparison",
                    "Compare corpora",
                    class_="btn-primary"
                ),

                ui.download_button(
                    "download_english_corpus_comparison_xlsx",
                    "Download comparison Excel"
                ),
            ),

            ui.div(
                ui.output_text("english_corpus_status"),

                ui.h4("Trend plot"),
                ui.output_plot("english_corpus_plot"),

                ui.h4("Summary answers"),
                ui.output_data_frame("english_corpus_summary"),

                ui.h4("AUC comparison"),
                ui.output_data_frame("english_corpus_auc"),

                ui.h4("Yearly PMW data"),
                ui.output_data_frame("english_corpus_yearly"),

                class_="card"
            )
        )
    )


def get_compare_english_corpora_server(input, output, session, shared):
    yearly_df_value = reactive.Value(None)
    auc_df_value = reactive.Value(None)
    summary_df_value = reactive.Value(None)

    status_text = reactive.Value("No comparison run yet.")

    @reactive.effect
    @reactive.event(input.run_english_corpus_comparison)
    def _run_comparison():
        words = parse_manual_words(input.compare_words())

        if not words:
            status_text.set("No words provided.")
            return

        selected_ids = list(input.selected_corpora())

        if not selected_ids:
            status_text.set("Select at least one corpus.")
            return

        selected_corpora = {
            cid: ENGLISH_CORPORA[cid]
            for cid in selected_ids
            if cid in ENGLISH_CORPORA
        }

        year_start = int(input.compare_year_start())
        year_end = int(input.compare_year_end())

        if year_start > year_end:
            status_text.set("Start year cannot be greater than end year.")
            return

        smoothing = int(input.compare_smoothing())
        case_insensitive = bool(input.compare_case_insensitive())

        years = list(range(year_start, year_end + 1))
        expected_len = len(years)

        yearly_rows = []

        status_text.set(
            f"Downloading Google Ngram data for {len(words)} words "
            f"across {len(selected_corpora)} selected English corpora..."
        )

        for word in words:
            for corpus_id, corpus_name in selected_corpora.items():
                try:
                    ts = fetch_ngram_timeseries(
                        word=word,
                        year_start=year_start,
                        year_end=year_end,
                        corpus=int(corpus_id),
                        smoothing=smoothing,
                        case_insensitive=case_insensitive,
                    )

                    if not ts:
                        ts = [0.0] * expected_len

                    ts = (ts + [0.0] * expected_len)[:expected_len]

                    for year, raw_value in zip(years, ts):
                        pmw = float(raw_value) * 1_000_000

                        yearly_rows.append({
                            "word": word,
                            "corpus_id": corpus_id,
                            "corpus": corpus_name,
                            "year": year,
                            "pmw": pmw,
                            "raw_relative_frequency": float(raw_value),
                        })

                    time.sleep(POLITE_DELAY_SEC)

                except Exception as e:
                    print(f"Error for {word} / {corpus_name}: {e}")

                    for year in years:
                        yearly_rows.append({
                            "word": word,
                            "corpus_id": corpus_id,
                            "corpus": corpus_name,
                            "year": year,
                            "pmw": np.nan,
                            "raw_relative_frequency": np.nan,
                        })

        yearly_df = pd.DataFrame(yearly_rows)

        auc_rows = []
        summary_rows = []

        for word in words:
            word_df = yearly_df[yearly_df["word"] == word]

            corpus_series = {}

            for corpus_id, corpus_name in selected_corpora.items():
                sub = (
                    word_df[word_df["corpus"] == corpus_name]
                    .sort_values("year")
                )

                values = sub["pmw"].to_numpy(dtype=float)
                corpus_series[corpus_name] = values

            def get_series(name):
                return corpus_series.get(name, np.full(len(years), np.nan))

            english = get_series("English 2019")
            american = get_series("American English 2019")
            british = get_series("British English 2019")
            fiction = get_series("English Fiction 2019")

            auc_english = auc_trapezoid(years, english)
            auc_american = auc_trapezoid(years, american)
            auc_british = auc_trapezoid(years, british)
            auc_fiction = auc_trapezoid(years, fiction)

            auc_row = {
                "word": word,
                "auc_english": auc_english,
                "auc_american": auc_american,
                "auc_british": auc_british,
                "auc_fiction": auc_fiction,
                "american_minus_british": auc_american - auc_british,
                "fiction_minus_english": auc_fiction - auc_english,
                "american_british_ratio": safe_ratio(auc_american, auc_british),
                "fiction_english_ratio": safe_ratio(auc_fiction, auc_english),
            }

            auc_rows.append(auc_row)

            corr_us_uk = safe_corr(american, british)
            corr_fiction_english = safe_corr(fiction, english)

            slope_american = slope_per_year(years, american)
            slope_british = slope_per_year(years, british)
            slope_english = slope_per_year(years, english)
            slope_fiction = slope_per_year(years, fiction)

            peak_american = safe_peak_year(years, american)
            peak_british = safe_peak_year(years, british)
            peak_english = safe_peak_year(years, english)
            peak_fiction = safe_peak_year(years, fiction)

            if "American English 2019" in selected_corpora.values() and "British English 2019" in selected_corpora.values():
                if auc_american > auc_british:
                    more_common_us_uk = "more frequent in American English"
                elif auc_american < auc_british:
                    more_common_us_uk = "more frequent in British English"
                else:
                    more_common_us_uk = "same total frequency in American and British English"

                trend_us = trend_label(slope_american)
                trend_uk = trend_label(slope_british)

                if trend_us == trend_uk:
                    trend_answer = f"similar direction: both {trend_us}"
                else:
                    trend_answer = f"different direction: American {trend_us}, British {trend_uk}"

                peak_same_us_uk = (
                    "same peak year"
                    if peak_american == peak_british
                    else "different peak year"
                )
            else:
                more_common_us_uk = "American and British comparison unavailable"
                trend_answer = "American and British comparison unavailable"
                peak_same_us_uk = "American and British comparison unavailable"

            if "English Fiction 2019" in selected_corpora.values() and "English 2019" in selected_corpora.values():
                if auc_fiction > auc_english:
                    fiction_answer = "more frequent in English Fiction than general English"
                elif auc_fiction < auc_english:
                    fiction_answer = "less frequent in English Fiction than general English"
                else:
                    fiction_answer = "same total frequency in Fiction and general English"
            else:
                fiction_answer = "Fiction and general English comparison unavailable"

            summary_rows.append({
                "word": word,

                "american_vs_british_answer": more_common_us_uk,
                "auc_american": auc_american,
                "auc_british": auc_british,
                "american_minus_british": auc_american - auc_british,
                "american_british_ratio": safe_ratio(auc_american, auc_british),

                "trend_answer": trend_answer,
                "slope_american": slope_american,
                "slope_british": slope_british,
                "correlation_american_british": corr_us_uk,

                "peak_answer": peak_same_us_uk,
                "peak_year_american": peak_american,
                "peak_year_british": peak_british,

                "fiction_vs_general_answer": fiction_answer,
                "auc_english": auc_english,
                "auc_fiction": auc_fiction,
                "fiction_minus_english": auc_fiction - auc_english,
                "fiction_english_ratio": safe_ratio(auc_fiction, auc_english),
                "correlation_fiction_english": corr_fiction_english,
                "slope_english": slope_english,
                "slope_fiction": slope_fiction,
                "peak_year_english": peak_english,
                "peak_year_fiction": peak_fiction,
            })

        auc_df = pd.DataFrame(auc_rows)
        summary_df = pd.DataFrame(summary_rows)

        yearly_df_value.set(yearly_df)
        auc_df_value.set(auc_df)
        summary_df_value.set(summary_df)

        shared["english_corpus_yearly_df"] = yearly_df
        shared["english_corpus_auc_df"] = auc_df
        shared["english_corpus_summary_df"] = summary_df

        status_text.set(
            f"Comparison complete. Downloaded {len(words)} words for "
            f"{year_start}–{year_end}. Values are PMW."
        )

    @output
    @render.text
    def english_corpus_status():
        return status_text.get()

    @output
    @render.plot
    def english_corpus_plot():
        df = yearly_df_value.get()

        if df is None or df.empty:
            fig, ax = plt.subplots(figsize=(9, 4))
            ax.text(
                0.5,
                0.5,
                "No data to plot yet.",
                ha="center",
                va="center",
                transform=ax.transAxes
            )
            ax.set_axis_off()
            return fig

        fig, ax = plt.subplots(figsize=(11, 5))

        for word in df["word"].dropna().unique():
            sub_word = df[df["word"] == word]

            for corpus in sub_word["corpus"].dropna().unique():
                sub = sub_word[sub_word["corpus"] == corpus].sort_values("year")

                ax.plot(
                    sub["year"],
                    sub["pmw"],
                    label=f"{word} – {corpus}"
                )

        ax.set_title("Word frequency over time by English corpus")
        ax.set_xlabel("Year")
        ax.set_ylabel("Words per million")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.25)

        return fig

    @output
    @render.data_frame
    def english_corpus_summary():
        df = summary_df_value.get()

        if df is None or df.empty:
            return render.DataGrid(
                pd.DataFrame({"message": ["No comparison yet."]}),
                filters=False
            )

        return render.DataGrid(
            df,
            filters=False,
            height="500px",
            width="100%",
            row_selection_mode="none",
            editable=False
        )

    @output
    @render.data_frame
    def english_corpus_auc():
        df = auc_df_value.get()

        if df is None or df.empty:
            return render.DataGrid(
                pd.DataFrame({"message": ["No AUC data yet."]}),
                filters=False
            )

        return render.DataGrid(
            df,
            filters=False,
            height="400px",
            width="100%",
            row_selection_mode="none",
            editable=False
        )

    @output
    @render.data_frame
    def english_corpus_yearly():
        df = yearly_df_value.get()

        if df is None or df.empty:
            return render.DataGrid(
                pd.DataFrame({"message": ["No yearly data yet."]}),
                filters=False
            )

        return render.DataGrid(
            df,
            filters=False,
            height="500px",
            width="100%",
            row_selection_mode="none",
            editable=False
        )

    @output
    @render.download(
        filename=lambda: "english_corpus_comparison.xlsx"
    )
    def download_english_corpus_comparison_xlsx():
        yearly_df = yearly_df_value.get()
        auc_df = auc_df_value.get()
        summary_df = summary_df_value.get()

        if yearly_df is None:
            yearly_df = pd.DataFrame()

        if auc_df is None:
            auc_df = pd.DataFrame()

        if summary_df is None:
            summary_df = pd.DataFrame()

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name

        selected_ids = list(input.selected_corpora())

        selected_corpora = {
            cid: ENGLISH_CORPORA[cid]
            for cid in selected_ids
            if cid in ENGLISH_CORPORA
        }

        meta = pd.DataFrame({
            "setting": [
                "language_group",
                "selected_corpora",
                "scale",
                "conversion",
                "smoothing",
                "case_insensitive",
                "year_start",
                "year_end",
            ],
            "value": [
                "English",
                ", ".join(selected_corpora.values()),
                "words per million",
                "PMW = raw relative frequency * 1,000,000",
                input.compare_smoothing(),
                input.compare_case_insensitive(),
                input.compare_year_start(),
                input.compare_year_end(),
            ]
        })

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            summary_df.to_excel(writer, index=False, sheet_name="summary_answers")
            auc_df.to_excel(writer, index=False, sheet_name="auc_comparison")
            yearly_df.to_excel(writer, index=False, sheet_name="yearly_pmw_data")
            meta.to_excel(writer, index=False, sheet_name="meta")

        return path