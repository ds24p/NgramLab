from shiny import reactive, render, ui
from shinywidgets import output_widget, render_widget
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from itertools import combinations
import tempfile
import textwrap

from utils import (
    auc_trapezoid,
    get_year_columns,
    round_numeric_df,
    safe_corr,
    smooth_series,
    slope_per_year,
    trend_label,
    z_score_values,
)


TREND_COLORS = {
    "rising": "#7C3AED",   # violet
    "falling": "#F2C94C",  # yellow
    "stable": "#9CA3AF",   # grey
    "unknown": "#111827",
}

REFERENCE_WORD = "the"
DEFAULT_REFERENCE_YEARS = list(range(1901, 2001))


def default_reference_values():
    x = np.linspace(0, 1, len(DEFAULT_REFERENCE_YEARS))
    return (0.6 + 0.6 * x + 0.05 * np.sin(4 * np.pi * x)).tolist()


def explorer_ui():
    return ui.div(
        ui.div(
            ui.div("Explorer", class_="page-title"),
            ui.p(
                "Select up to 5 words and compare their frequency trajectories, "
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
                    ui.p("Main options: choose up to 5 words, optional z-score standardisation, optional smoothing, then run analysis."),
                    ui.p("Step 1: select words from the list populated in Ngram Data Fetcher."),
                    ui.p("Step 2: enable Z-score when you want to compare shapes instead of absolute levels."),
                    ui.p("Step 3: enable smoothing and set window size to reduce short-term noise."),
                    ui.p("Step 4: click Run analysis and inspect plots in order: Time Series, Indexed, Segmented Trend."),
                    ui.p("Step 5: use Word Metrics and Pairwise/Correlation tables to compare words quantitatively."),
                    class_="guide-box tab-guide-box",
                ),
            ),

            ui.input_selectize(
                "selected_word",
                "Choose up to 5 words",
                choices=[REFERENCE_WORD],
                selected=[REFERENCE_WORD],
                multiple=True,
                options={
                    "maxItems": 5,
                    "placeholder": "Select words..."
                }
            ),

            ui.div(
                ui.input_checkbox(
                    "use_z_score",
                    "Z-score results (standardisation)",
                    value=False
                ),
                class_="standardisation-control"
            ),

            ui.div(
                ui.input_checkbox(
                    "apply_smoothing",
                    "Apply smoothing",
                    value=False
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
                    class_="standardisation-control smoothing-control",
                ),
            ),

            ui.input_action_button(
                "run_explorer_analysis",
                "Run analysis",
                class_="run-analysis-button"
            ),

            ui.download_button(
                "download_explorer_excel",
                "Download as Excel file"
            ),

            ui.p(
                "The word 'the' is available for reference",
                class_="muted section-description"
            ),

            ui.div(
                ui.h3("Time Series Comparison", class_="table-section-title"),
                ui.p(
                    "Interactive raw/per million words (PMW) or z-score trajectories for selected words. Click Run analysis to update results.",
                    class_="muted section-description"
                ),
                ui.div(
                    ui.div(
                        output_widget("trajectory_plot", width="100%"),
                        class_="explorer-plot-inner",
                    ),
                    class_="explorer-plot-scroll",
                ),
                class_="analysis-section"
            ),

            ui.div(
                ui.h3("Indexed Time Series Comparison", class_="table-section-title"),
                ui.p(
                    "Each word starts at 100 in its first available year, making growth and decline easier to compare.",
                    class_="muted section-description"
                ),
                ui.div(
                    ui.div(
                        output_widget("indexed_trajectory_plot", width="100%"),
                        class_="explorer-plot-inner",
                    ),
                    class_="explorer-plot-scroll",
                ),
                class_="analysis-section"
            ),

            ui.div(
                ui.h3("Segmented Trend Plot", class_="table-section-title"),
                ui.p(
                    "Rising segments are violet, falling segments are yellow, and stable segments are grey.",
                    class_="muted section-description"
                ),
                ui.div(
                    ui.div(
                        output_widget("segmented_trend_plot", width="100%"),
                        class_="explorer-plot-inner",
                    ),
                    class_="explorer-plot-scroll",
                ),
                class_="analysis-section"
            ),

            ui.div(
                ui.h3("Word Metrics", class_="table-section-title"),
                ui.p(
                    "Summary statistics for each selected word: AUC, average frequency, peak year, global trend, and shape.",
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
                            "maxItems": 5,
                        },
                    ),
                    ui.input_selectize(
                        "segmented_trend_filter_year",
                        "Filter segmented trend rows by year",
                        choices=[str(y) for y in range(1900, 2025)],
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
                    "Direct comparison between every pair of selected words.",
                    class_="muted section-description"
                ),
                ui.output_data_frame("pairwise_comparison_table"),
                class_="analysis-section"
            ),

            ui.div(
                ui.h3("Time-Series Correlation Matrix", class_="table-section-title"),
                ui.p(
                    "Pearson correlations between word trajectories.",
                    class_="muted section-description"
                ),
                ui.output_data_frame("correlation_matrix_table"),
                class_="analysis-section"
            ),

            ui.div(
                ui.h3("Correlation Heatmap", class_="table-section-title"),
                ui.p(
                    "Interactive square heatmap of Pearson correlations.",
                    class_="muted section-description"
                ),
                ui.div(
                    ui.div(
                        output_widget("correlation_heatmap", width="100%"),
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
        selected = input.selected_word()

        if selected is None:
            return []

        if isinstance(selected, str):
            selected = [selected]

        return list(selected)[:5]

    def analysis_has_run():
        return int(input.run_explorer_analysis() or 0) > 0

    def use_z_score():
        return bool(input.use_z_score())

    def use_smoothing():
        return bool(input.apply_smoothing())

    def smoothing_window():
        value = input.smoothing_window()

        if value is None:
            return 3

        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return 3

    def active_scale_label():
        smoothing_note = ""

        if use_smoothing():
            smoothing_note = f" (smoothed, window={smoothing_window()})"

        if use_z_score():
            return "z-score" + smoothing_note
        return (shared.get("uploaded_scale", "raw score") or "raw score") + smoothing_note

    def score_note():
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
        df = shared["uploaded_df"]
        years = shared["uploaded_years"]
        words = get_selected_words()

        if (df is None or df.empty or not years) and words == [REFERENCE_WORD]:
            years = DEFAULT_REFERENCE_YEARS
            year_cols = [str(y) for y in years]
            row = {"word": REFERENCE_WORD}
            for y, value in zip(years, default_reference_values()):
                row[str(y)] = value
            return pd.DataFrame([row]), years, year_cols

        if df is None or df.empty or not years:
            return None, [], []

        year_cols = get_year_columns(df, years)

        if not year_cols:
            return None, [], []

        selected_words = list(words)

        if not analysis_has_run() and not selected_words:
            return None, [], []

        selected_df = df[df["word"].isin(selected_words)].copy()

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

    def build_word_series():
        selected_df, years, year_cols = get_selected_data()

        if not years or not year_cols:
            return {}, years

        out = {}

        if selected_df is not None:
            for _, row in selected_df.iterrows():
                word = row["word"]
                values = row[year_cols].to_numpy(dtype=float)

                if use_smoothing():
                    values = smooth_series(values, window=smoothing_window())

                if use_z_score():
                    values = z_score_values(values)
                out[word] = values

        # Reference word 'the' is included through the selected_word control by default.

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
        series, years = build_word_series()

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
                "AUC": auc,
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

            auc_a = metrics_by_word[word_a]["AUC"]
            auc_b = metrics_by_word[word_b]["AUC"]

            auc_ratio = auc_a / auc_b if auc_b != 0 else np.nan

            rows.append({
                "Word A": word_a,
                "Word B": word_b,
                "Time-series correlation": safe_corr(values_a, values_b),
                "AUC A": auc_a,
                "AUC B": auc_b,
                "AUC difference A - B": auc_a - auc_b,
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
    @reactive.event(input.run_explorer_analysis, input.selected_word)
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
            return empty_figure("Fetch Ngram data first, then select up to 5 words.")

        fig = go.Figure()

        for word, values in series.items():
            fig.add_trace(
                go.Scatter(
                    x=years,
                    y=values,
                    mode="lines+markers",
                    name=word,
                    line=dict(
                        width=4,
                        dash="dash" if word == "the" else "solid",
                    ),
                    marker=dict(size=6, opacity=0.85),
                    hovertemplate=(
                        "Word: %{fullData.name}<br>"
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

        for word, values in series.items():
            values = np.asarray(values, dtype=float)
            finite = np.isfinite(values)

            if not finite.any():
                continue

            first_valid = values[finite][0]
            indexed = values if first_valid == 0 else values / first_valid * 100

            fig.add_trace(
                go.Scatter(
                    x=years,
                    y=indexed,
                    mode="lines+markers",
                    name=word,
                    line=dict(
                        width=4,
                        dash="dash" if word == "the" else "solid",
                    ),
                    marker=dict(size=6, opacity=0.85),
                    hovertemplate=(
                        "Word: %{fullData.name}<br>"
                        "Year: %{x}<br>"
                        "Index: %{y:.2f}<extra></extra>"
                    )
                )
            )

        fig.add_hline(y=100, line_dash="dash", opacity=0.5)

        apply_common_plot_layout(
            fig,
            title=f"Indexed trajectories: first available year = 100 ({score_note().replace('Scale: ', '')})",
            yaxis_title="Index",
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

            values = np.asarray(values, dtype=float)

            fig.add_trace(
                go.Scatter(
                    x=years,
                    y=values,
                    mode="lines",
                    line=dict(color="rgba(0,0,0,0.18)", width=1),
                    name=f"{word} full trajectory",
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
                        text=[f"{word} peak"],
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

        return render.DataGrid(
            df,
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

        return render.DataGrid(
            df,
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

        return render.DataGrid(
            df,
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

        return render.DataGrid(
            df,
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
                ticktext=[wrap_axis_label(word) for word in words],
                automargin=True,
            ),
            yaxis=dict(
                autorange="reversed",
                scaleanchor="x",
                scaleratio=1,
                constrain="domain",
                tickfont=dict(size=14),
                tickmode="array",
                tickvals=words,
                ticktext=[wrap_axis_label(word) for word in words],
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
                "apply_smoothing",
                "smoothing_window",
            ],
            "value": [
                ", ".join(series.keys()) if series else "",
                len(series),
                min(years) if years else "",
                max(years) if years else "",
                active_scale_label(),
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
