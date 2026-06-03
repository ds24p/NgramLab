from shiny import reactive, render, ui
import pandas as pd
import numpy as np
import tempfile
import plotly.graph_objects as go
from shinywidgets import output_widget, render_widget

from utils import (
    auc_trapezoid,
    fetch_ngram_timeseries,
    parse_manual_words,
    safe_corr,
    slope_per_year,
    trend_label,
)


ENGLISH_CORPORA = {
    "26": "English 2019",
    "27": "American English 2019",
    "28": "British English 2019",
    "29": "English Fiction 2019",
}

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
            "Values are converted from raw relative frequencies to per million words (PMW).",
            class_="muted compare-corpora-intro"
        ),

        ui.panel_conditional(
            "input.user_mode === 'New here'",
            ui.div(
                ui.h3("New here? How this tab works"),
                ui.p("What this tab does: it compares the same words across English, American, British, and Fiction corpora."),
                ui.p("Main options: word list, selected corpora, year range, and Google smoothing parameter."),
                ui.p("Step 1: paste words (one per line) and select the corpora you want to compare."),
                ui.p("Step 2: set Start year and End year, then optionally increase smoothing for less noisy curves."),
                ui.p("Step 3: click Compare corpora to build interactive trend lines and summary tables."),
                ui.p("Step 4: check Trend Plot for trajectories, AUC Comparison for totals, and Summary Answers for interpretation."),
                ui.p("Step 5: export with Download Excel file when you want to reuse results in external analysis."),
                class_="guide-box tab-guide-box",
            ),
        ),

        ui.layout_sidebar(
            ui.sidebar(
                ui.div(
                    ui.input_text_area(
                        "compare_words",
                        "Words to compare",
                        placeholder="Type one word per line",
                        rows=7
                    ),

                    ui.div(
                        ui.input_checkbox_group(
                            "selected_corpora",
                            "Select English corpora",
                            choices=ENGLISH_CORPORA,
                            selected=list(ENGLISH_CORPORA.keys())
                        ),
                        class_="compare-corpora-corpus-group",
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

                    ui.input_action_button(
                        "run_english_corpus_comparison",
                        "Compare corpora",
                        class_="btn-primary"
                    ),

                    ui.download_button(
                        "download_english_corpus_comparison_xlsx",
                        "Download Excel file"
                    ),
                    class_="inner-card compare-corpora-controls",
                ),
            ),

            ui.div(
                ui.div(
                    ui.output_text("english_corpus_status"),
                    class_="section-description",
                ),

                ui.div(
                    ui.h3("Trend Plot", class_="table-section-title"),
                    ui.p(
                        "Interactive per million words (PMW) trajectories for each selected word and corpus.",
                        class_="muted section-description",
                    ),
                    ui.div(
                        ui.div(
                            output_widget("english_corpus_plot", width="100%"),
                            class_="explorer-plot-inner",
                        ),
                        class_="explorer-plot-scroll",
                    ),
                    class_="analysis-section",
                ),

                ui.div(
                    ui.h3("Summary Answers", class_="table-section-title"),
                    ui.p(
                        "Interpretive comparisons of American, British, Fiction, and general English trajectories.",
                        class_="muted section-description",
                    ),
                    ui.output_data_frame("english_corpus_summary"),
                    class_="analysis-section",
                ),

                ui.div(
                    ui.h3("AUC Comparison", class_="table-section-title"),
                    ui.p(
                        "AUC totals and directional differences between selected English corpora.",
                        class_="muted section-description",
                    ),
                    ui.output_data_frame("english_corpus_auc"),
                    class_="analysis-section",
                ),

                ui.div(
                    ui.h3("Yearly PMW Data", class_="table-section-title"),
                    ui.p(
                        "Year-by-year per million words (PMW) values downloaded from Google Ngram.",
                        class_="muted section-description",
                    ),
                    ui.output_data_frame("english_corpus_yearly"),
                    class_="analysis-section",
                ),

                class_="results-card compare-corpora-results"
            )
        ),
        class_="card section-card compare-corpora-section",
    )


def get_compare_english_corpora_server(input, output, session, shared):
    yearly_df_value = reactive.Value(None)
    auc_df_value = reactive.Value(None)
    summary_df_value = reactive.Value(None)

    status_text = reactive.Value("No comparison run yet.")

    def finish_comparison(words, selected_corpora, year_start, year_end, years, yearly_df):
        selected_corpus_names = set(selected_corpora.values())

        series_by_word_corpus = {
            (word, corpus): group.sort_values("year")["pmw"].to_numpy(dtype=float)
            for (word, corpus), group in yearly_df.groupby(["word", "corpus"], sort=False)
        }

        auc_rows = []
        summary_rows = []

        for word in words:
            def get_series(name):
                return series_by_word_corpus.get((word, name), np.full(len(years), np.nan))

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

            if "American English 2019" in selected_corpus_names and "British English 2019" in selected_corpus_names:
                if auc_american > auc_british:
                    more_common_us_uk = "more frequent in American English"
                elif auc_american < auc_british:
                    more_common_us_uk = "more frequent in British English"
                else:
                    more_common_us_uk = "same total frequency in American and British English"

                trend_us = trend_label(slope_american, threshold=0.000001)
                trend_uk = trend_label(slope_british, threshold=0.000001)

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

            if "English Fiction 2019" in selected_corpus_names and "English 2019" in selected_corpus_names:
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

        for df in (yearly_df, auc_df, summary_df):
            numeric_cols = [
                col
                for col in df.select_dtypes(include="number").columns
                if col != "raw_relative_frequency"
            ]
            df[numeric_cols] = df[numeric_cols].round(2)

        yearly_df_value.set(yearly_df)
        auc_df_value.set(auc_df)
        summary_df_value.set(summary_df)

        shared["english_corpus_yearly_df"] = yearly_df
        shared["english_corpus_auc_df"] = auc_df
        shared["english_corpus_summary_df"] = summary_df

        status_text.set(
            f"Comparison complete. Downloaded {len(words)} words for "
            f"{year_start}-{year_end}. Values are per million words (PMW)."
        )

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
                        case_insensitive=False,
                    )
                except Exception as exc:
                    print(f"Error for {word} / {corpus_name}: {exc}")

                    for year in years:
                        yearly_rows.append({
                            "word": word,
                            "corpus_id": corpus_id,
                            "corpus": corpus_name,
                            "year": year,
                            "pmw": np.nan,
                            "raw_relative_frequency": np.nan,
                        })

                    continue

                if not ts:
                    ts = [0.0] * expected_len

                ts = (ts + [0.0] * expected_len)[:expected_len]

                for year, raw_value in zip(years, ts):
                    raw_value = float(raw_value)

                    yearly_rows.append({
                        "word": word,
                        "corpus_id": corpus_id,
                        "corpus": corpus_name,
                        "year": year,
                        "pmw": raw_value * 1_000_000,
                        "raw_relative_frequency": raw_value,
                    })

        yearly_df = pd.DataFrame(yearly_rows)
        finish_comparison(words, selected_corpora, year_start, year_end, years, yearly_df)

    @output
    @render.text
    def english_corpus_status():
        return status_text.get()

    @output
    @render_widget
    def english_corpus_plot():
        df = yearly_df_value.get()

        if df is None or df.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No data to plot yet.",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=16),
            )
            fig.update_layout(
                height=420,
                margin=dict(l=30, r=30, t=50, b=30),
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                paper_bgcolor="white",
                plot_bgcolor="white",
            )
            return fig

        fig = go.Figure()

        for word in df["word"].dropna().unique():
            sub_word = df[df["word"] == word]

            for corpus in sub_word["corpus"].dropna().unique():
                sub = sub_word[sub_word["corpus"] == corpus].sort_values("year")

                fig.add_trace(
                    go.Scatter(
                        x=sub["year"],
                        y=sub["pmw"],
                        mode="lines+markers",
                        name=f"{word} - {corpus}",
                        marker=dict(size=5),
                        hovertemplate=(
                            "Word: "
                            + str(word)
                            + "<br>Corpus: "
                            + str(corpus)
                            + "<br>Year: %{x}<br>PMW: %{y:.3f}<extra></extra>"
                        ),
                    )
                )

        fig.update_layout(
            autosize=True,
            title=dict(
                text="Word Frequency Over Time by English Corpus",
                x=0.01,
                xanchor="left",
                font=dict(size=24),
            ),
            xaxis_title="Year",
            yaxis_title="Per million words (PMW)",
            height=620,
            margin=dict(l=82, r=58, t=112, b=138),
            hovermode="x unified",
            font=dict(size=18),
            legend=dict(
                orientation="h",
                y=-0.24,
                x=0.5,
                xanchor="center",
                font=dict(size=14),
            ),
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        fig.update_xaxes(
            title_font=dict(size=20),
            tickfont=dict(size=17),
            automargin=True,
            tickangle=0,
            showgrid=True,
            gridcolor="rgba(156, 163, 175, 0.22)",
        )
        fig.update_yaxes(
            title_font=dict(size=20),
            tickfont=dict(size=17),
            automargin=True,
            showgrid=True,
            gridcolor="rgba(156, 163, 175, 0.22)",
        )

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
                "year_start",
                "year_end",
            ],
            "value": [
                "English",
                ", ".join(selected_corpora.values()),
                "per million words (PMW)",
                "PMW (per million words) = raw relative frequency * 1,000,000",
                input.compare_smoothing(),
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
