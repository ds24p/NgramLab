from shiny import render, ui
from shinywidgets import output_widget, render_widget
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from itertools import combinations
import tempfile


TREND_COLORS = {
    "rising": "#7C3AED",   # violet
    "falling": "#F2C94C",  # yellow
    "stable": "#9CA3AF",   # grey
    "unknown": "#111827",
}


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
            ui.input_selectize(
                "selected_word",
                "Choose up to 5 words",
                choices=[],
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
                "The word 'the' is always included as an example reference in every chart and table.",
                class_="muted section-description"
            ),

            ui.div(
                ui.h3("Time Series Comparison", class_="table-section-title"),
                ui.p(
                    "Interactive raw/PMW or z-score trajectories for selected words. Click Run analysis to update results.",
                    class_="muted section-description"
                ),
                output_widget("trajectory_plot"),
                class_="analysis-section"
            ),

            ui.div(
                ui.h3("Indexed Time Series Comparison", class_="table-section-title"),
                ui.p(
                    "Each word starts at 100 in its first available year, making growth and decline easier to compare.",
                    class_="muted section-description"
                ),
                output_widget("indexed_trajectory_plot"),
                class_="analysis-section"
            ),

            ui.div(
                ui.h3("Segmented Trend Plot", class_="table-section-title"),
                ui.p(
                    "Rising segments are violet, falling segments are yellow, and stable segments are grey.",
                    class_="muted section-description"
                ),
                output_widget("segmented_trend_plot"),
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
                    output_widget("correlation_heatmap"),
                    class_="centered-plot-container"
                ),
                class_="analysis-section heatmap-section"
            ),

            class_="card"
        ),

        ui.tags.style(
            """
            .explorer-hero {
                background: #ffffff;
                border: 1px solid #e7e0d8;
                border-bottom: none;
                border-radius: 22px 22px 0 0;
                padding: 26px 28px;
                margin-bottom: 0;
                box-shadow: 0 10px 30px rgba(30, 20, 10, 0.04);
            }

            .explorer-hero + .card {
                margin-top: 0 !important;
                background: #ffffff !important;
                border: 1px solid #e7e0d8 !important;
                border-top: none !important;
                border-radius: 0 0 22px 22px !important;
                box-shadow: 0 10px 30px rgba(30, 20, 10, 0.04);
            }

            .explorer-hero .page-title {
                margin-bottom: 8px;
            }

            .explorer-hero-text {
                max-width: 900px;
                margin-bottom: 0;
                font-size: 15px;
                line-height: 1.55;
            }

            .standardisation-control {
                margin: 12px 0 14px 0;
                padding: 12px 14px;
                background: #fbfaf8;
                border: 1px solid #eee8dc;
                border-radius: 16px;
            }

            .run-analysis-button,
            #download_explorer_excel {
                border-radius: 8px !important;
                padding: 9px 18px !important;
                font-weight: 700 !important;
                line-height: 1.2 !important;
                box-shadow: none !important;
            }

            .run-analysis-button {
                margin: 4px 12px 12px 0;
                background: #7C3AED !important;
                border-color: #7C3AED !important;
                color: white !important;
            }

            #download_explorer_excel {
                margin: 4px 0 12px 0;
            }

            #trajectory_scale_note,
            #indexed_scale_note,
            #segmented_scale_note,
            #heatmap_scale_note {
                display: block;
                width: 100%;
                margin-top: 8px;
                margin-bottom: 0;
                font-size: 13px;
                font-weight: 650;
                color: #6b7280;
                text-align: center;
            }

            .analysis-section {
                margin-top: 34px;
                padding-top: 22px;
                border-top: 1px solid #eee8dc;
            }

            .analysis-section:first-of-type {
                margin-top: 22px;
            }

            .table-section-title {
                font-size: 22px;
                font-weight: 750;
                color: #1f2933;
                margin-bottom: 6px;
            }

            .section-description {
                margin-bottom: 16px;
                font-size: 14px;
            }

            .centered-plot-container {
                display: flex;
                justify-content: center;
                align-items: center;
                width: 100%;
            }

            .segmented-filter-controls {
                display: flex;
                flex-wrap: wrap;
                gap: 14px;
                margin-bottom: 16px;
            }

            .segmented-filter-controls .form-group,
            .segmented-filter-controls > div {
                min-width: 260px;
                flex: 1;
                font-size: 16px;
            }

            .segmented-filter-controls input,
            .segmented-filter-controls .selectize-control {
                font-size: 16px;
            }

            .heatmap-section {
                text-align: center;
                padding-bottom: 8px;
            }

            .shiny-data-grid {
                margin-top: 10px;
            }
            """
        )
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

    def get_year_columns(df, years):
        cols = []

        for y in years:
            if y in df.columns:
                cols.append(y)
            elif str(y) in df.columns:
                cols.append(str(y))

        return cols

    def analysis_has_run():
        return int(input.run_explorer_analysis() or 0) > 0

    def use_z_score():
        return bool(input.use_z_score())

    def active_scale_label():
        if use_z_score():
            return "z-score"
        return shared.get("uploaded_scale", "raw score") or "raw score"

    def score_note():
        return "Scale: z-score results" if use_z_score() else "Scale: raw score"

    def z_score_values(values):
        values = np.asarray(values, dtype=float)
        mean = np.nanmean(values) if np.isfinite(values).any() else np.nan
        std = np.nanstd(values) if np.isfinite(values).any() else np.nan

        if not np.isfinite(std) or std == 0:
            return np.zeros_like(values, dtype=float)

        return (values - mean) / std

    def round_numeric_df(df, digits=2):
        if df.empty:
            return df

        out = df.copy()
        numeric_cols = out.select_dtypes(include=[np.number]).columns
        out[numeric_cols] = out[numeric_cols].round(digits)
        return out

    def apply_common_plot_layout(fig, title, yaxis_title, height=500, margin=None):
        if margin is None:
            margin = dict(l=70, r=45, t=82, b=70)

        fig.update_layout(
            title=dict(text=title, font=dict(size=28), x=0.02),
            xaxis_title="Year",
            yaxis_title=yaxis_title,
            height=height,
            hovermode="x unified",
            margin=margin,
            font=dict(size=20),
            legend=dict(
                orientation="h",
                y=-0.2,
                x=0.5,
                xanchor="center",
                font=dict(size=18),
            ),
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        fig.update_xaxes(title_font=dict(size=22), tickfont=dict(size=20))
        fig.update_yaxes(title_font=dict(size=22), tickfont=dict(size=20))
        return fig

    def get_selected_data():
        df = shared["uploaded_df"]
        years = shared["uploaded_years"]
        words = get_selected_words()

        if not analysis_has_run():
            return None, [], []

        if df is None or df.empty or not years or not words:
            return None, [], []

        year_cols = get_year_columns(df, years)

        if not year_cols:
            return None, [], []

        selected_df = df[df["word"].isin(words)].copy()

        return selected_df, years, year_cols

    def auc_trapezoid(years, values):
        x = np.asarray(years, dtype=float)
        y = np.asarray(values, dtype=float)
        y = np.where(np.isfinite(y), y, 0.0)

        if len(x) < 2:
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

    def trend_label(slope):
        if not np.isfinite(slope):
            return "unknown"

        if slope > 0:
            return "rising"

        if slope < 0:
            return "falling"

        return "stable"

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
                if use_z_score():
                    values = z_score_values(values)
                out[word] = values

        reference_word = "the"
        uploaded_df = shared.get("uploaded_df")
        if reference_word not in out and uploaded_df is not None and not uploaded_df.empty:
            if reference_word in uploaded_df["word"].values:
                ref_row = uploaded_df[uploaded_df["word"] == reference_word].iloc[0]
                ref_values = ref_row[year_cols].to_numpy(dtype=float)
                if use_z_score():
                    ref_values = z_score_values(ref_values)
                out[reference_word] = ref_values

        return out, years

    def build_segmented_trend_df():
        series, years = build_word_series()

        rows = []

        for word, values in series.items():
            rows.extend(segment_trends_for_word(word, years, values))

        return pd.DataFrame(rows)

    def get_segmented_trend_filters():
        trends = input.segmented_trend_filter_trend() or []
        years = input.segmented_trend_filter_year() or []
        words = input.segmented_trend_filter_word() or []
        if isinstance(years, str):
            years = [years]
        if isinstance(words, str):
            words = [words]

        year_values = [int(y) for y in years if str(y).isdigit()]
        word_values = [str(w).strip().lower() for w in words if str(w).strip()]
        return trends, year_values, word_values

    def filter_segmented_trend_df(df):
        if df.empty:
            return df

        trends, years, words = get_segmented_trend_filters()

        if trends:
            df = df[df["Trend"].isin(trends)]

        if years:
            df = df[df["Start year"].isin(years) | df["End year"].isin(years)]

        if words:
            df = df[df["Word"].astype(str).str.lower().isin(words)]

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

    @output
    @render_widget
    def trajectory_plot():
        series, years = build_word_series()

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
            height=500,
        )

        return fig

    @output
    @render_widget
    def indexed_trajectory_plot():
        series, years = build_word_series()

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
            height=500,
        )

        return fig

    @output
    @render_widget
    def segmented_trend_plot():
        series, years = build_word_series()

        if not series:
            return empty_figure("No selected words to segment.")

        fig = go.Figure()
        legend_added = set()

        for word, values in series.items():
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

            segments = segment_trends_for_word(word, years, values)
            segments = filter_segmented_trend_df(pd.DataFrame(segments)).to_dict("records")

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
                        textposition="top center",
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
            height=620,
            margin=dict(l=70, r=50, t=82, b=95),
        )
        fig.update_layout(
            hovermode="closest",
            legend=dict(
                title=dict(text="Segment type", font=dict(size=15)),
                orientation="h",
                y=-0.18,
                x=0.5,
                xanchor="center",
                font=dict(size=14),
            ),
        )

        return fig

    @output
    @render.data_frame
    def word_metrics_table():
        df = build_metrics_df()

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
        df = build_segmented_trend_df()
        df = filter_segmented_trend_df(df)

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
        df = build_pairwise_df()

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
        df = build_correlation_matrix_df()

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
        series, years = build_word_series()

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
                textfont=dict(size=16),
                colorbar=dict(
                    title=dict(text="Pearson<br>correlation", font=dict(size=15)),
                    tickfont=dict(size=14),
                    len=0.78,
                    thickness=18,
                    x=1.03,
                )
            )
        )

        size = 520 + 25 * len(words)

        fig.update_layout(
            title=dict(
                text=f"Time-series correlation heatmap ({score_note().replace('Scale: ', '')})",
                x=0.5,
                xanchor="center",
                font=dict(size=22),
            ),
            width=size + 120,
            height=size,
            margin=dict(l=90, r=120, t=70, b=90),
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(size=14),
            xaxis=dict(
                side="bottom",
                tickangle=35,
                constrain="domain",
                tickfont=dict(size=15),
            ),
            yaxis=dict(
                autorange="reversed",
                scaleanchor="x",
                scaleratio=1,
                constrain="domain",
                tickfont=dict(size=15),
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
        yearly_df = round_numeric_df(build_yearly_df())
        metrics_df = round_numeric_df(build_metrics_df())
        segmented_df = round_numeric_df(build_segmented_trend_df())
        pairwise_df = round_numeric_df(build_pairwise_df())
        corr_df = round_numeric_df(build_correlation_matrix_df())

        series, years = build_word_series()

        meta_df = pd.DataFrame({
            "setting": [
                "selected_words",
                "number_of_selected_words",
                "year_start",
                "year_end",
                "scale",
            ],
            "value": [
                ", ".join(series.keys()) if series else "",
                len(series),
                min(years) if years else "",
                max(years) if years else "",
                active_scale_label(),
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