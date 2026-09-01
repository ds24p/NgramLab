from shiny import reactive, render, ui
from shinywidgets import output_widget, render_widget
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from itertools import combinations
import tempfile
import textwrap

from utils import (
    GOOGLE_NGRAM_YEAR_MAX,
    GOOGLE_NGRAM_YEAR_MIN,
    auc_trapezoid,
    get_year_columns,
    round_numeric_df,
    safe_corr,
    smooth_series,
    slope_per_year,
    truncate_display_dataframe,
    truncate_display_text,
    trend_label,
    z_score_values,
)


TREND_COLORS = {
    "rising": "#7C3AED",   # violet
    "falling": "#F2C94C",  # yellow
    "stable": "#9CA3AF",   # grey
    "unknown": "#111827",
}
MAX_EXPLORER_VISUALIZATION_TERMS = 10
AUC_ORIGINAL_SCALE_COLUMN = "AUC (original scale)"
AUC_A_ORIGINAL_SCALE_COLUMN = "AUC A (original scale)"
AUC_B_ORIGINAL_SCALE_COLUMN = "AUC B (original scale)"
AUC_DIFF_ORIGINAL_SCALE_COLUMN = "AUC difference A - B (original scale)"


def explorer_word_choices(shared=None):
    df = shared.get("uploaded_df") if shared else None

    if df is None or df.empty or "word" not in df.columns:
        return []

    words = df["word"].dropna().astype(str).tolist()
    return sorted(set(words), key=str.casefold)


def explorer_ui(shared=None):
    word_choices = explorer_word_choices(shared)

    return ui.div(
        ui.div(
            ui.div("Explorer", class_="page-title"),
            ui.p(
                f"Select up to {MAX_EXPLORER_VISUALIZATION_TERMS} words and compare their frequency trajectories, "
                "AUC values, peaks, trends, pairwise correlations, and segmented trend patterns.",
                class_="muted explorer-hero-text"
            ),
            class_="explorer-hero"
        ),

        ui.div(
            ui.panel_conditional(
                "input.user_mode === 'New here'",
                ui.div(
                    ui.h3("New here? How this tab works"),
                    ui.p("What this tab does: it analyzes uploaded word trajectories and shows trends, correlations, and summary metrics."),
                    ui.p(f"Main options: choose up to {MAX_EXPLORER_VISUALIZATION_TERMS} words, optional z-score standardisation, optional smoothing, then run analysis."),
                    ui.p("Step 1: select words from the list populated in Ngram Data Fetcher."),
                    ui.p("Step 2: enable Z-score when you want to compare shapes instead of absolute levels."),
                    ui.p("Step 3: enable smoothing and set window size to reduce short-term noise."),
                    ui.p("Step 4: click Run analysis and inspect plots in order: Time Series, Indexed, Segmented Trend."),
                    ui.p("Step 5: use Word Metrics and Pairwise/Correlation tables to compare words quantitatively."),
                    class_="guide-box tab-guide-box",
                ),
            ),

            ui.output_ui("explorer_data_notice"),

            ui.input_selectize(
                "selected_word",
                f"Choose up to {MAX_EXPLORER_VISUALIZATION_TERMS} words",
                choices=word_choices,
                selected=[],
                multiple=True,
                options={
                    "maxItems": MAX_EXPLORER_VISUALIZATION_TERMS,
                    "placeholder": "Select words..."
                }
            ),
            ui.p(
                "Start in Ngram Data Fetcher: fetch or upload word-frequency data, then return here and choose words from that dataset.",
                class_="muted explorer-control-note",
            ),

            ui.div(
                ui.input_checkbox(
                    "use_z_score",
                    "Z-score results (standardisation)",
                    value=False
                ),
                ui.p(
                    "Z-score turns each selected word into mean 0 and standard deviation 1 for plots. AUC is always computed from the original frequency values, not z-score values.",
                    class_="muted explorer-control-note",
                ),
                class_="standardisation-control"
            ),

            ui.div(
                ui.input_checkbox(
                    "apply_smoothing",
                    "Apply smoothing",
                    value=False
                ),
                ui.p(
                    "Smoothing applies a moving average to reduce short-term noise in the trajectories.",
                    class_="muted explorer-control-note",
                ),
                class_="standardisation-control"
            ),

            ui.panel_conditional(
                "input.apply_smoothing",
                ui.div(
                    ui.input_numeric(
                        "smoothing_window",
                        "Choose size of smoothing",
                        value=3,
                        min=1,
                    ),
                    ui.p(
                        "Window = 3 means a 3-year moving average: each point is averaged with nearby years. Larger windows smooth more, but hide more short-term variation.",
                        class_="muted explorer-control-note",
                    ),
                    class_="standardisation-control smoothing-control",
                ),
            ),

            ui.output_ui("explorer_run_button"),
            ui.div(
                ui.span(class_="explorer-loading-spinner"),
                ui.span("Running analysis..."),
                id="explorer_loading_state",
                class_="explorer-loading-state",
                **{"aria-live": "polite", "aria-hidden": "true"},
            ),
            ui.output_text("explorer_status"),
            ui.p(
                "Select at least one word, then click Run analysis to update results.",
                class_="muted explorer-control-note",
            ),
            ui.download_button(
                "download_explorer_excel",
                "Download as Excel file"
            ),
            ui.p(
                "The Excel download uses the last Run analysis settings. If z-score is enabled, exported yearly data follows the plotted values while AUC stays on the original frequency scale.",
                class_="muted explorer-download-note",
            ),

            ui.div(
                ui.h3("Time Series Comparison", class_="table-section-title"),
                ui.p(
                    "Interactive raw/per million words (PMW) or z-score trajectories for selected words. Click Run analysis to update results.",
                    class_="muted section-description"
                ),
                ui.div(
                    ui.div(
                        output_widget("trajectory_plot", width="100%", fill=True),
                        class_="explorer-plot-inner",
                    ),
                    class_="explorer-plot-scroll",
                ),
                id="explorer_results_anchor",
                class_="analysis-section explorer-chart-section"
            ),

            ui.div(
                ui.h3("Indexed Time Series Comparison", class_="table-section-title"),
                ui.p(
                    "Each word starts at 100 in its first available year. When z-score is enabled, standardized values are shown directly instead of rebasing near-zero z-scores.",
                    class_="muted section-description"
                ),
                ui.div(
                    ui.div(
                        output_widget("indexed_trajectory_plot", width="100%", fill=True),
                        class_="explorer-plot-inner",
                    ),
                    class_="explorer-plot-scroll",
                ),
                class_="analysis-section explorer-chart-section"
            ),

            ui.div(
                ui.h3("Segmented Trend Plot", class_="table-section-title"),
                ui.p(
                    "Rising segments are violet, falling segments are yellow, and stable segments are grey.",
                    class_="muted section-description"
                ),
                ui.div(
                    ui.div(
                        output_widget("segmented_trend_plot", width="100%", fill=True),
                        class_="explorer-plot-inner",
                    ),
                    class_="explorer-plot-scroll",
                ),
                class_="analysis-section explorer-chart-section"
            ),

            ui.div(
                ui.h3("Word Metrics", class_="table-section-title"),
                ui.p(
                    "Summary statistics for each selected word. AUC (area under the curve) is computed from the original frequency values, so it stays interpretable and non-standardized when z-score plots are enabled.",
                    class_="muted section-description"
                ),
                ui.output_data_frame("word_metrics_table"),
                class_="analysis-section"
            ),

            ui.div(
                ui.h3("Segmented Trend Analysis", class_="table-section-title"),
                ui.p(
                    "Breaks each trajectory into local periods of increase, decrease, or stability.",
                    class_="muted section-description"
                ),
                ui.div(
                    ui.input_selectize(
                        "segmented_trend_filter_trend",
                        "Filter segmented trend rows by trend",
                        choices=["rising", "falling", "stable", "unknown"],
                        selected=["rising", "falling", "stable", "unknown"],
                        multiple=True,
                        options={"placeholder": "Choose trend(s)..."},
                    ),
                    ui.input_selectize(
                        "segmented_trend_filter_word",
                        "Filter segmented trend rows by word",
                        choices=[],
                        multiple=True,
                        options={
                            "placeholder": "Type or choose word(s)...",
                            "maxItems": MAX_EXPLORER_VISUALIZATION_TERMS,
                        },
                    ),
                    ui.input_selectize(
                        "segmented_trend_filter_year",
                        "Filter segmented trend rows by year",
                        choices=[
                            str(y)
                            for y in range(
                                GOOGLE_NGRAM_YEAR_MIN,
                                GOOGLE_NGRAM_YEAR_MAX + 1,
                            )
                        ],
                        multiple=True,
                        options={"placeholder": "Choose year(s)...", "maxItems": 10},
                    ),
                    class_="segmented-filter-controls",
                ),
                ui.output_data_frame("segmented_trend_table"),
                class_="analysis-section"
            ),

            ui.div(
                ui.h3("Pairwise Word Comparisons", class_="table-section-title"),
                ui.p(
                    "Direct comparison between every pair of selected words. Correlation describes similarity of shape over time; AUC difference is computed from the original frequency values.",
                    class_="muted section-description"
                ),
                ui.output_data_frame("pairwise_comparison_table"),
                class_="analysis-section"
            ),

            ui.div(
                ui.h3("Time-Series Correlation Matrix", class_="table-section-title"),
                ui.p(
                    "Pearson correlations between word trajectories. Values close to 1 move together; values close to -1 move in opposite directions.",
                    class_="muted section-description"
                ),
                ui.output_data_frame("correlation_matrix_table"),
                class_="analysis-section"
            ),

            ui.div(
                ui.h3("Correlation Heatmap", class_="table-section-title"),
                ui.p(
                    "Interactive square heatmap of Pearson correlations for quick visual comparison of trajectory similarity.",
                    class_="muted section-description"
                ),
                ui.div(
                    ui.div(
                        output_widget("correlation_heatmap", width="100%", fill=True),
                        class_="explorer-plot-inner explorer-heatmap-inner",
                    ),
                    class_="centered-plot-container explorer-plot-scroll",
                ),
                class_="analysis-section heatmap-section"
            ),

            class_="card explorer-results-card"
        ),
        class_="explorer-page",
    )


def explorer_server(input, output, session, shared):
    analysis_state = reactive.Value(None)
    analysis_status = reactive.Value("")

    def uploaded_data_version():
        data_version = shared.get("uploaded_data_version")

        if data_version is None:
            return 0

        try:
            return int(data_version.get() or 0)
        except (TypeError, ValueError):
            return 0

    def has_uploaded_data():
        uploaded_data_version()

        df = shared.get("uploaded_df")
        years = shared.get("uploaded_years") or []

        return (
            df is not None
            and not df.empty
            and "word" in df.columns
            and bool(years)
        )

    @output
    @render.ui
    def explorer_data_notice():
        if not has_uploaded_data():
            return ui.div(
                ui.strong("No data loaded yet."),
                " Go to Ngram Data Fetcher to retrieve word-frequency data.",
                class_="explorer-data-notice explorer-data-notice-warning",
                **{"aria-live": "polite"},
            )

        df = shared.get("uploaded_df")
        word_count = int(df["word"].dropna().nunique()) if df is not None else 0

        return ui.div(
            f"Data loaded from Ngram Data Fetcher: {word_count} term(s) available. ",
            f"Choose up to {MAX_EXPLORER_VISUALIZATION_TERMS} terms, then click Run analysis.",
            class_="explorer-data-notice explorer-data-notice-ready",
            **{"aria-live": "polite"},
        )

    @output
    @render.ui
    def explorer_run_button():
        data_ready = has_uploaded_data()

        return ui.input_action_button(
            "run_explorer_analysis",
            "Run analysis",
            class_="run-analysis-button",
            disabled=not data_ready,
            title=(
                "Run analysis"
                if data_ready
                else "Retrieve data in Ngram Data Fetcher first."
            ),
        )

    @output
    @render.text
    def explorer_status():
        return analysis_status.get()
    
    def empty_figure(message):
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=16)
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

    def get_selected_words():
        try:
            selected = input.selected_word()
        except Exception:
            return []

        if selected is None:
            return []

        if isinstance(selected, str):
            selected = [selected]

        return list(selected)

    def analysis_has_run():
        return analysis_state.get() is not None

    def current_analysis():
        return analysis_state.get()

    @reactive.effect
    def _sync_selected_word_choices_from_shared_data():
        uploaded_data_version()
        choices = explorer_word_choices(shared)
        selected = get_selected_words()
        selected = [word for word in selected if word in choices]

        if not selected and choices:
            selected = choices[:1]

        try:
            ui.update_selectize(
                "selected_word",
                choices=choices,
                selected=selected[:MAX_EXPLORER_VISUALIZATION_TERMS],
            )
        except Exception:
            pass

    def live_use_z_score():
        return bool(input.use_z_score())

    def live_use_smoothing():
        return bool(input.apply_smoothing())

    def live_smoothing_window():
        value = input.smoothing_window()

        if value is None:
            return 3

        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return 3

    def use_z_score():
        state = current_analysis()
        return bool(state["use_z_score"]) if state else False

    def use_smoothing():
        state = current_analysis()
        return bool(state["apply_smoothing"]) if state else False

    def smoothing_window():
        state = current_analysis()
        return int(state["smoothing_window"]) if state else 3

    @reactive.effect
    @reactive.event(input.run_explorer_analysis)
    async def _capture_explorer_analysis():
        if int(input.run_explorer_analysis() or 0) <= 0:
            return

        await session.send_custom_message(
            "set_explorer_loading",
            {"is_loading": True},
        )

        try:
            df = shared.get("uploaded_df")
            years = shared.get("uploaded_years") or []

            if df is None or df.empty or "word" not in df.columns or not years:
                analysis_state.set(None)
                analysis_status.set(
                    "No data loaded yet. Go to Ngram Data Fetcher to retrieve word-frequency data."
                )
                return

            words = get_selected_words()

            if not words:
                analysis_state.set(None)
                analysis_status.set(
                    "Please select at least one word before running the analysis."
                )
                return

            if len(words) > MAX_EXPLORER_VISUALIZATION_TERMS:
                analysis_state.set(None)
                analysis_status.set(
                    f"Please select up to {MAX_EXPLORER_VISUALIZATION_TERMS} terms for visualization."
                )
                return

            year_cols = get_year_columns(df, years)

            if not year_cols:
                analysis_state.set(None)
                analysis_status.set(
                    "No valid year data were found in the current dataset."
                )
                return

            selected_df = df[df["word"].isin(words)].copy()

            if selected_df.empty:
                analysis_state.set(None)
                analysis_status.set(
                    "No frequency data were found for the selected terms and corpus. "
                    "Please check the terms, language, corpus, and year range."
                )
                return

            numeric_data = selected_df[year_cols].apply(
                pd.to_numeric,
                errors="coerce",
            )

            values = numeric_data.to_numpy(dtype=float)

            if values.size == 0 or not np.isfinite(values).any():
                analysis_state.set(None)
                analysis_status.set(
                    "No frequency data were found for the selected terms and corpus. "
                    "Please check the terms, language, corpus, and year range."
                )
                return

            analysis_state.set({
                "selected_words": words,
                "use_z_score": live_use_z_score(),
                "apply_smoothing": live_use_smoothing(),
                "smoothing_window": live_smoothing_window(),
            })

            analysis_status.set(
                f"Analysis completed for {len(words)} selected word(s)."
            )

            await session.send_custom_message(
                "scroll_to_element",
                {
                    "selector": "#explorer_results_anchor",
                    "delay_ms": 180,
                },
            )
        finally:
            await session.send_custom_message(
                "set_explorer_loading",
                {"is_loading": False},
            )

    def active_scale_label():
        smoothing_note = ""

        if use_smoothing():
            smoothing_note = f" (smoothed, window={smoothing_window()})"

        if use_z_score():
            return "z-score" + smoothing_note
        return (shared.get("uploaded_scale", "raw score") or "raw score") + smoothing_note

    def score_note():
        if not analysis_has_run():
            return "Click Run analysis to update results."

        scale_part = "z-score results" if use_z_score() else "raw score"

        if use_smoothing():
            return f"Scale: {scale_part}, smoothing={smoothing_window()}-year moving average"

        return f"Scale: {scale_part}"

    def wrap_plot_text(text, width=58):
        return "<br>".join(
            textwrap.wrap(
                str(text),
                width=width,
                break_long_words=False,
                break_on_hyphens=False,
            )
        )

    def wrap_axis_label(text, width=14):
        return "<br>".join(
            textwrap.wrap(
                str(text),
                width=width,
                break_long_words=True,
                break_on_hyphens=False,
            )
        )

    def apply_common_plot_layout(fig, title, yaxis_title, height=640, margin=None):
        if margin is None:
            margin = dict(l=82, r=58, t=112, b=138)

        fig.update_layout(
            autosize=True,
            title=dict(
                text=wrap_plot_text(title),
                font=dict(size=25),
                x=0.01,
                xanchor="left",
                y=0.94,
                yanchor="top",
                pad=dict(t=10, b=8),
            ),
            xaxis_title="Year",
            yaxis_title=yaxis_title,
            height=height,
            hovermode="x unified",
            margin=margin,
            font=dict(size=18),
            legend=dict(
                orientation="h",
                y=-0.24,
                x=0.5,
                xanchor="center",
                font=dict(size=16),
            ),
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        fig.update_xaxes(
            title_font=dict(size=20),
            tickfont=dict(size=17),
            automargin=True,
            tickangle=0,
        )
        fig.update_yaxes(
            title_font=dict(size=20),
            tickfont=dict(size=17),
            automargin=True,
        )
        return fig

    def get_selected_data():
        state = current_analysis()

        if state is None:
            return None, [], []

        df = shared.get("uploaded_df")
        years = shared.get("uploaded_years") or []

        if df is None or df.empty:
            return None, [], []

        if "word" not in df.columns:
            return None, [], []

        if not years:
            return None, [], []

        words = list(state.get("selected_words", []))

        if not words:
            return None, [], []

        year_cols = get_year_columns(df, years)

        if not year_cols:
            return None, [], []

        selected_df = df[df["word"].isin(words)].copy()

        if selected_df.empty:
            return None, [], []

        return selected_df, years, year_cols

    def local_trend_label(delta, tolerance):
        if not np.isfinite(delta):
            return "unknown"

        if delta > tolerance:
            return "rising"

        if delta < -tolerance:
            return "falling"

        return "stable"

    def trajectory_shape_label(segments):
        trends = [s["Trend"] for s in segments if s["Trend"] != "stable"]

        if not trends:
            return "stable"

        compressed = []

        for trend in trends:
            if not compressed or compressed[-1] != trend:
                compressed.append(trend)

        if compressed == ["rising"]:
            return "consistent growth"

        if compressed == ["falling"]:
            return "consistent decline"

        if compressed == ["rising", "falling"]:
            return "rise then fall"

        if compressed == ["falling", "rising"]:
            return "fall then rise"

        return "fluctuating / unstable"

    def segment_trends_for_word(word, years, values):
        values = np.asarray(values, dtype=float)

        if len(years) < 2 or len(values) < 2:
            return []

        finite_values = values[np.isfinite(values)]

        if len(finite_values) == 0:
            return []

        value_range = float(np.nanmax(finite_values) - np.nanmin(finite_values))
        tolerance = value_range * 0.01 if value_range != 0 else 0.0

        point_trends = []

        for i in range(len(values) - 1):
            start_value = values[i]
            end_value = values[i + 1]

            if not np.isfinite(start_value) or not np.isfinite(end_value):
                trend = "unknown"
                delta = np.nan
            else:
                delta = end_value - start_value
                trend = local_trend_label(delta, tolerance)

            point_trends.append({
                "start_index": i,
                "end_index": i + 1,
                "trend": trend,
                "delta": delta,
            })

        segments = []

        current_trend = point_trends[0]["trend"]
        start_index = point_trends[0]["start_index"]

        for item in point_trends[1:]:
            if item["trend"] == current_trend:
                continue

            end_index = item["start_index"]

            start_year = years[start_index]
            end_year = years[end_index]
            start_value = values[start_index]
            end_value = values[end_index]

            absolute_change = (
                float(end_value - start_value)
                if np.isfinite(start_value) and np.isfinite(end_value)
                else np.nan
            )

            percent_change = (
                float((absolute_change / start_value) * 100)
                if np.isfinite(absolute_change) and start_value != 0
                else np.nan
            )

            segments.append({
                "Word": word,
                "Start year": start_year,
                "End year": end_year,
                "Trend": current_trend,
                "Start frequency": start_value,
                "End frequency": end_value,
                "Absolute change": absolute_change,
                "Percent change": percent_change,
                "Segment length": end_year - start_year,
            })

            current_trend = item["trend"]
            start_index = item["start_index"]

        end_index = point_trends[-1]["end_index"]

        start_year = years[start_index]
        end_year = years[end_index]
        start_value = values[start_index]
        end_value = values[end_index]

        absolute_change = (
            float(end_value - start_value)
            if np.isfinite(start_value) and np.isfinite(end_value)
            else np.nan
        )

        percent_change = (
            float((absolute_change / start_value) * 100)
            if np.isfinite(absolute_change) and start_value != 0
            else np.nan
        )

        segments.append({
            "Word": word,
            "Start year": start_year,
            "End year": end_year,
            "Trend": current_trend,
            "Start frequency": start_value,
            "End frequency": end_value,
            "Absolute change": absolute_change,
            "Percent change": percent_change,
            "Segment length": end_year - start_year,
        })

        return segments

    def build_word_series(apply_z_score_transform=True):
        selected_df, years, year_cols = get_selected_data()

        if not years or not year_cols:
            return {}, years

        out = {}

        if selected_df is not None:
            for _, row in selected_df.iterrows():
                word = row["word"]
                values = pd.to_numeric(
                    row[year_cols],
                    errors="coerce",
                ).to_numpy(dtype=float)

                if use_smoothing():
                    values = smooth_series(values, window=smoothing_window())

                if apply_z_score_transform and use_z_score():
                    values = z_score_values(values)
                out[word] = values

        return out, years

    def build_segmented_trend_df():
        series, years = build_word_series()

        rows = []

        for word, values in series.items():
            rows.extend(segment_trends_for_word(word, years, values))

        return pd.DataFrame(rows)

    def list_filter_values(value):
        if value is None:
            return []

        if isinstance(value, str):
            return [value]

        return list(value)

    def get_segmented_trend_filters():
        trends = list_filter_values(input.segmented_trend_filter_trend())
        years = list_filter_values(input.segmented_trend_filter_year())
        words = list_filter_values(input.segmented_trend_filter_word())

        trend_values = [str(t).strip() for t in trends if str(t).strip()]
        year_values = [
            int(year)
            for year in (str(y).strip() for y in years)
            if year.isdigit()
        ]
        word_values = {str(w).strip().casefold() for w in words if str(w).strip()}

        return trend_values, year_values, word_values

    def filter_segmented_trend_df(df):
        if df.empty:
            return df

        trends, years, words = get_segmented_trend_filters()

        if trends:
            df = df[df["Trend"].isin(trends)]

        if years:
            df = df[df["Start year"].isin(years) | df["End year"].isin(years)]

        if words:
            df = df[df["Word"].astype(str).str.casefold().isin(words)]

        return df

    def build_metrics_df():
        series, years = build_word_series(apply_z_score_transform=False)

        rows = []

        for word, values in series.items():
            values = np.asarray(values, dtype=float)

            auc = auc_trapezoid(years, values)
            mean_value = float(np.nanmean(values)) if np.isfinite(values).any() else np.nan
            max_value = float(np.nanmax(values)) if np.isfinite(values).any() else np.nan
            min_value = float(np.nanmin(values)) if np.isfinite(values).any() else np.nan
            slope = slope_per_year(years, values)

            if np.isfinite(values).any():
                peak_index = int(np.nanargmax(values))
                peak_year = years[peak_index]
            else:
                peak_year = np.nan

            segments = segment_trends_for_word(word, years, values)
            shape = trajectory_shape_label(segments)

            rows.append({
                "Word": word,
                AUC_ORIGINAL_SCALE_COLUMN: auc,
                "Mean frequency": mean_value,
                "Maximum frequency": max_value,
                "Minimum frequency": min_value,
                "Peak year": peak_year,
                "Global slope per year": slope,
                "Global trend": trend_label(slope),
                "Trajectory shape": shape,
                "Number of trend segments": len(segments),
            })

        return pd.DataFrame(rows)

    def build_pairwise_df():
        series, years = build_word_series()
        metrics = build_metrics_df()

        if len(series) < 2 or metrics.empty:
            return pd.DataFrame()

        metrics_by_word = metrics.set_index("Word").to_dict(orient="index")
        rows = []

        for word_a, word_b in combinations(series.keys(), 2):
            values_a = series[word_a]
            values_b = series[word_b]

            auc_a = metrics_by_word[word_a][AUC_ORIGINAL_SCALE_COLUMN]
            auc_b = metrics_by_word[word_b][AUC_ORIGINAL_SCALE_COLUMN]

            auc_ratio = auc_a / auc_b if auc_b != 0 else np.nan

            rows.append({
                "Word A": word_a,
                "Word B": word_b,
                "Time-series correlation": safe_corr(values_a, values_b),
                AUC_A_ORIGINAL_SCALE_COLUMN: auc_a,
                AUC_B_ORIGINAL_SCALE_COLUMN: auc_b,
                AUC_DIFF_ORIGINAL_SCALE_COLUMN: auc_a - auc_b,
                "AUC ratio A / B": auc_ratio,
                "Peak year A": metrics_by_word[word_a]["Peak year"],
                "Peak year B": metrics_by_word[word_b]["Peak year"],
                "Peak year difference": (
                    metrics_by_word[word_a]["Peak year"]
                    - metrics_by_word[word_b]["Peak year"]
                ),
                "Global trend A": metrics_by_word[word_a]["Global trend"],
                "Global trend B": metrics_by_word[word_b]["Global trend"],
                "Trajectory shape A": metrics_by_word[word_a]["Trajectory shape"],
                "Trajectory shape B": metrics_by_word[word_b]["Trajectory shape"],
            })

        return pd.DataFrame(rows)

    def build_correlation_matrix_df():
        series, years = build_word_series()

        if len(series) < 2:
            return pd.DataFrame()

        words = list(series.keys())
        matrix = pd.DataFrame(index=words, columns=words, dtype=float)

        for word_a in words:
            for word_b in words:
                matrix.loc[word_a, word_b] = safe_corr(
                    series[word_a],
                    series[word_b]
                )

        return matrix.reset_index().rename(columns={"index": "Word"})

    def build_yearly_df():
        series, years = build_word_series()

        if not series:
            return pd.DataFrame()

        rows = []

        for word, values in series.items():
            for year, value in zip(years, values):
                rows.append({
                    "Word": word,
                    "Year": year,
                    "Frequency": value,
                })

        return pd.DataFrame(rows)

    @reactive.calc
    def word_series_data():
        return build_word_series()

    @reactive.calc
    def segmented_trend_df_data():
        return build_segmented_trend_df()

    @reactive.calc
    def filtered_segmented_trend_df_data():
        return filter_segmented_trend_df(segmented_trend_df_data())

    @reactive.calc
    def metrics_df_data():
        return build_metrics_df()

    @reactive.calc
    def pairwise_df_data():
        return build_pairwise_df()

    @reactive.calc
    def correlation_matrix_df_data():
        return build_correlation_matrix_df()

    @reactive.calc
    def yearly_df_data():
        return build_yearly_df()

    @reactive.effect
    @reactive.event(input.run_explorer_analysis)
    def _sync_segmented_word_filter_choices():
        if not analysis_has_run():
            ui.update_selectize(
                "segmented_trend_filter_word",
                choices=[],
                selected=[],
            )
            return

        segments_df = segmented_trend_df_data()
        choices = (
            sorted(
                segments_df["Word"].dropna().astype(str).unique().tolist(),
                key=str.casefold,
            )
            if not segments_df.empty and "Word" in segments_df
            else []
        )

        choices_by_key = {word.casefold(): word for word in choices}
        current = list_filter_values(input.segmented_trend_filter_word())

        selected = [
            choices_by_key[key]
            for key in (str(word).strip().casefold() for word in current)
            if key in choices_by_key
        ]

        ui.update_selectize(
            "segmented_trend_filter_word",
            choices=choices,
            selected=selected,
        )

    @output
    @render_widget
    def trajectory_plot():
        series, years = word_series_data()

        if not series:
            return empty_figure(
                f"Fetch Ngram data first, then select up to {MAX_EXPLORER_VISUALIZATION_TERMS} words."
            )

        fig = go.Figure()

        for word, values in series.items():
            display_word = truncate_display_text(word, max_chars=40)

            fig.add_trace(
                go.Scatter(
                    x=years,
                    y=values,
                    mode="lines+markers",
                    name=display_word,
                    line=dict(
                        width=4,
                        dash="solid",
                    ),
                    marker=dict(size=6, opacity=0.85),
                    customdata=[word for _ in years],
                    hovertemplate=(
                        "Word: %{customdata}<br>"
                        "Year: %{x}<br>"
                        "Frequency: %{y:.2f}<extra></extra>"
                    )
                )
            )

        scale = active_scale_label()

        apply_common_plot_layout(
            fig,
            title=f"Word trajectories over time ({score_note().replace('Scale: ', '')})",
            yaxis_title=scale,
            height=640,
        )

        return fig

    @output
    @render_widget
    def indexed_trajectory_plot():
        series, years = word_series_data()

        if not series:
            return empty_figure("No selected words to compare.")

        fig = go.Figure()
        y_label = "Z-score" if use_z_score() else "Index"

        for word, values in series.items():
            display_word = truncate_display_text(word, max_chars=40)
            values = np.asarray(values, dtype=float)
            finite = np.isfinite(values)

            if not finite.any():
                continue

            if use_z_score():
                plotted_values = values
                y_label = "Z-score"
                hover_label = "Z-score"
            else:
                first_valid = values[finite][0]
                plotted_values = values if first_valid == 0 else values / first_valid * 100
                y_label = "Index"
                hover_label = "Index"

            fig.add_trace(
                go.Scatter(
                    x=years,
                    y=plotted_values,
                    mode="lines+markers",
                    name=display_word,
                    line=dict(
                        width=4,
                        dash="solid",
                    ),
                    marker=dict(size=6, opacity=0.85),
                    customdata=[word for _ in years],
                    hovertemplate=(
                        "Word: %{customdata}<br>"
                        "Year: %{x}<br>"
                        f"{hover_label}: "
                        "%{y:.2f}<extra></extra>"
                    )
                )
            )

        if use_z_score():
            fig.add_hline(y=0, line_dash="dash", opacity=0.5)
            title = f"Standardized trajectories ({score_note().replace('Scale: ', '')})"
        else:
            fig.add_hline(y=100, line_dash="dash", opacity=0.5)
            title = f"Indexed trajectories: first available year = 100 ({score_note().replace('Scale: ', '')})"

        apply_common_plot_layout(
            fig,
            title=title,
            yaxis_title=y_label,
            height=640,
        )

        return fig

    @output
    @render_widget
    def segmented_trend_plot():
        series, years = word_series_data()
        segments_df = filtered_segmented_trend_df_data()

        if not series:
            return empty_figure("No selected words to segment.")

        if segments_df.empty:
            return empty_figure("No segmented trend data matches the current filters.")

        fig = go.Figure()
        legend_added = set()
        plotted_words = set(segments_df["Word"].dropna().astype(str).tolist())

        for word, values in series.items():
            if str(word) not in plotted_words:
                continue

            display_word = truncate_display_text(word, max_chars=40)
            values = np.asarray(values, dtype=float)

            fig.add_trace(
                go.Scatter(
                    x=years,
                    y=values,
                    mode="lines",
                    line=dict(color="rgba(0,0,0,0.18)", width=1),
                    name=f"{display_word} full trajectory",
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

            segments = (
                segments_df[segments_df["Word"] == word].to_dict("records")
                if not segments_df.empty
                else []
            )

            for segment in segments:
                start_year = segment["Start year"]
                end_year = segment["End year"]
                trend = segment["Trend"]

                start_idx = years.index(start_year)
                end_idx = years.index(end_year)

                x = years[start_idx:end_idx + 1]
                y = values[start_idx:end_idx + 1]

                showlegend = trend not in legend_added
                legend_added.add(trend)

                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=y,
                        mode="lines+markers",
                        line=dict(
                            color=TREND_COLORS.get(trend, "black"),
                            width=4,
                        ),
                        marker=dict(size=6),
                        name=trend,
                        legendgroup=trend,
                        showlegend=showlegend,
                        customdata=[[word, trend, start_year, end_year] for _ in x],
                        hovertemplate=(
                            "Word: %{customdata[0]}<br>"
                            "Trend: %{customdata[1]}<br>"
                            "Segment: %{customdata[2]}–%{customdata[3]}<br>"
                            "Year: %{x}<br>"
                            "Frequency: %{y:.2f}<extra></extra>"
                        )
                    )
                )

            if np.isfinite(values).any():
                peak_idx = int(np.nanargmax(values))

                fig.add_trace(
                    go.Scatter(
                        x=[years[peak_idx]],
                        y=[values[peak_idx]],
                        mode="markers+text",
                        marker=dict(color="black", size=9),
                        text=[f"{display_word} peak"],
                        textfont=dict(size=14),
                        textposition="top center",
                        cliponaxis=False,
                        name=f"{word} peak",
                        showlegend=False,
                        hovertemplate=(
                            f"Word: {word}<br>"
                            f"Peak year: {years[peak_idx]}<br>"
                            "Frequency: %{y:.2f}<extra></extra>"
                        )
                    )
                )

        scale = active_scale_label()

        apply_common_plot_layout(
            fig,
            title=f"Segmented local trends ({score_note().replace('Scale: ', '')})",
            yaxis_title=scale,
            height=720,
            margin=dict(l=82, r=58, t=112, b=158),
        )
        fig.update_layout(
            hovermode="closest",
            legend=dict(
                title=dict(text="Segment type", font=dict(size=14)),
                orientation="h",
                y=-0.22,
                x=0.5,
                xanchor="center",
                font=dict(size=14),
            ),
        )

        return fig

    @output
    @render.data_frame
    def word_metrics_table():
        df = metrics_df_data()

        if df.empty:
            return render.DataGrid(
                pd.DataFrame({"Message": ["No word metrics yet."]}),
                filters=False
            )

        df = round_numeric_df(df)

        display_df = truncate_display_dataframe(df, columns=["Word"])

        return render.DataGrid(
            display_df,
            filters=False,
            height="320px",
            width="100%",
            row_selection_mode="none",
            editable=False
        )

    @output
    @render.data_frame
    def segmented_trend_table():
        df = filtered_segmented_trend_df_data()

        if df.empty:
            return render.DataGrid(
                pd.DataFrame({"Message": ["No segmented trend data yet."]}),
                filters=False
            )

        df = round_numeric_df(df)

        display_df = truncate_display_dataframe(df, columns=["Word"])

        return render.DataGrid(
            display_df,
            filters=False,
            height="360px",
            width="100%",
            row_selection_mode="none",
            editable=False
        )

    @output
    @render.data_frame
    def pairwise_comparison_table():
        df = pairwise_df_data()

        if df.empty:
            return render.DataGrid(
                pd.DataFrame({"Message": ["Select at least two words."]}),
                filters=False
            )

        df = round_numeric_df(df)

        display_df = truncate_display_dataframe(df, columns=["Word A", "Word B"])

        return render.DataGrid(
            display_df,
            filters=False,
            height="360px",
            width="100%",
            row_selection_mode="none",
            editable=False
        )

    @output
    @render.data_frame
    def correlation_matrix_table():
        df = correlation_matrix_df_data()

        if df.empty:
            return render.DataGrid(
                pd.DataFrame({"Message": ["Select at least two words."]}),
                filters=False
            )

        df = round_numeric_df(df)

        display_df = truncate_display_dataframe(df, columns=["Word"])

        return render.DataGrid(
            display_df,
            filters=False,
            height="260px",
            width="100%",
            row_selection_mode="none",
            editable=False
        )

    @output
    @render_widget
    def correlation_heatmap():
        series, years = word_series_data()

        if len(series) < 2:
            return empty_figure("Select at least two words.")

        words = list(series.keys())
        matrix = np.zeros((len(words), len(words)), dtype=float)

        for i, word_a in enumerate(words):
            for j, word_b in enumerate(words):
                matrix[i, j] = safe_corr(series[word_a], series[word_b])

        text = []

        for row in matrix:
            text.append([
                "NA" if not np.isfinite(v) else f"{v:.2f}"
                for v in row
            ])

        fig = go.Figure(
            data=go.Heatmap(
                z=matrix,
                x=words,
                y=words,
                zmin=-1,
                zmax=1,
                zmid=0,
                colorscale="RdBu",
                reversescale=True,
                text=text,
                texttemplate="%{text}",
                hovertemplate=(
                    "Word A: %{y}<br>"
                    "Word B: %{x}<br>"
                    "Correlation: %{z:.2f}<extra></extra>"
                ),
                textfont=dict(size=15),
                colorbar=dict(
                    title=dict(text="Pearson<br>correlation", font=dict(size=14)),
                    tickfont=dict(size=14),
                    len=0.78,
                    thickness=18,
                    x=1.03,
                )
            )
        )

        size = 620 + 35 * len(words)

        fig.update_layout(
            autosize=True,
            title=dict(
                text=wrap_plot_text(
                    f"Time-series correlation heatmap ({score_note().replace('Scale: ', '')})",
                    width=54,
                ),
                x=0.5,
                xanchor="center",
                y=0.94,
                yanchor="top",
                font=dict(size=21),
                pad=dict(t=10, b=8),
            ),
            width=size + 180,
            height=size + 80,
            margin=dict(l=165, r=155, t=96, b=165),
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(size=14),
            xaxis=dict(
                side="bottom",
                tickangle=32,
                constrain="domain",
                tickfont=dict(size=14),
                tickmode="array",
                tickvals=words,
                ticktext=[
                    wrap_axis_label(truncate_display_text(word, max_chars=40))
                    for word in words
                ],
                automargin=True,
                constraintoward="center",
            ),
            yaxis=dict(
                autorange="reversed",
                scaleanchor="x",
                scaleratio=1,
                constrain="domain",
                constraintoward="middle",
                tickfont=dict(size=14),
                tickmode="array",
                tickvals=words,
                ticktext=[
                    wrap_axis_label(truncate_display_text(word, max_chars=40))
                    for word in words
                ],
                automargin=True,
            ),
        )

        return fig


    @output
    @render.text
    def trajectory_scale_note():
        return score_note()

    @output
    @render.text
    def indexed_scale_note():
        return score_note()

    @output
    @render.text
    def segmented_scale_note():
        return score_note()

    @output
    @render.text
    def heatmap_scale_note():
        return score_note()

    @output
    @render.download(
        filename=lambda: "explorer_analysis.xlsx"
    )
    def download_explorer_excel():
        yearly_df = round_numeric_df(yearly_df_data())
        metrics_df = round_numeric_df(metrics_df_data())
        segmented_df = round_numeric_df(segmented_trend_df_data())
        pairwise_df = round_numeric_df(pairwise_df_data())
        corr_df = round_numeric_df(correlation_matrix_df_data())

        series, years = word_series_data()

        meta_df = pd.DataFrame({
            "setting": [
                "selected_words",
                "number_of_selected_words",
                "year_start",
                "year_end",
                "scale",
                "metric_scale",
                "apply_smoothing",
                "smoothing_window",
            ],
            "value": [
                ", ".join(series.keys()) if series else "",
                len(series),
                min(years) if years else "",
                max(years) if years else "",
                active_scale_label(),
                "original frequency values (z-score not applied)",
                use_smoothing(),
                smoothing_window() if use_smoothing() else "",
            ]
        })

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            yearly_df.to_excel(writer, index=False, sheet_name="yearly_data")
            metrics_df.to_excel(writer, index=False, sheet_name="word_metrics")
            segmented_df.to_excel(writer, index=False, sheet_name="segmented_trends")
            pairwise_df.to_excel(writer, index=False, sheet_name="pairwise_comparisons")
            corr_df.to_excel(writer, index=False, sheet_name="correlation_matrix")
            meta_df.to_excel(writer, index=False, sheet_name="meta")

        return path
