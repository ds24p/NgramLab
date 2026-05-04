from shiny import render, ui
from shinywidgets import output_widget, render_widget
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from itertools import combinations
import tempfile


TREND_COLORS = {
    "rising": "green",
    "falling": "red",
    "stable": "gray",
    "unknown": "black",
}


def explorer_ui():
    return ui.div(
        ui.div("Explorer", class_="page-title"),

        ui.p(
            "Select up to 5 words and compare their frequency trajectories, "
            "AUC values, peaks, trends, pairwise correlations, and segmented trend patterns.",
            class_="muted"
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

            ui.download_button(
                "download_explorer_excel",
                "Download as Excel file"
            ),

            ui.div(
                ui.h3("Time Series Comparison", class_="table-section-title"),
                ui.p(
                    "Interactive raw or PMW frequency trajectories for selected words.",
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
                    "Rising segments are green, falling segments are red, and stable segments are gray.",
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

    def get_selected_data():
        df = shared["uploaded_df"]
        years = shared["uploaded_years"]
        words = get_selected_words()

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

        if selected_df is None or selected_df.empty:
            return {}, years

        out = {}

        for _, row in selected_df.iterrows():
            word = row["word"]
            values = row[year_cols].to_numpy(dtype=float)
            out[word] = values

        return out, years

    def build_segmented_trend_df():
        series, years = build_word_series()

        rows = []

        for word, values in series.items():
            rows.extend(segment_trends_for_word(word, years, values))

        return pd.DataFrame(rows)

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
                    hovertemplate=(
                        "Word: %{fullData.name}<br>"
                        "Year: %{x}<br>"
                        "Frequency: %{y}<extra></extra>"
                    )
                )
            )

        scale = shared.get("uploaded_scale", "frequency")

        fig.update_layout(
            title="Word trajectories over time",
            xaxis_title="Year",
            yaxis_title=scale,
            height=500,
            hovermode="x unified",
            margin=dict(l=60, r=30, t=70, b=60),
            legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
            paper_bgcolor="white",
            plot_bgcolor="white",
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
                    hovertemplate=(
                        "Word: %{fullData.name}<br>"
                        "Year: %{x}<br>"
                        "Index: %{y:.2f}<extra></extra>"
                    )
                )
            )

        fig.add_hline(y=100, line_dash="dash", opacity=0.5)

        fig.update_layout(
            title="Indexed trajectories: first available year = 100",
            xaxis_title="Year",
            yaxis_title="Index",
            height=500,
            hovermode="x unified",
            margin=dict(l=60, r=30, t=70, b=60),
            legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
            paper_bgcolor="white",
            plot_bgcolor="white",
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
                            "Frequency: %{y}<extra></extra>"
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
                            "Frequency: %{y}<extra></extra>"
                        )
                    )
                )

        scale = shared.get("uploaded_scale", "frequency")

        fig.update_layout(
            title="Segmented local trends",
            xaxis_title="Year",
            yaxis_title=scale,
            height=620,
            hovermode="closest",
            margin=dict(l=60, r=40, t=70, b=90),
            legend=dict(
                title="Segment type",
                orientation="h",
                y=-0.18,
                x=0.5,
                xanchor="center",
            ),
            paper_bgcolor="white",
            plot_bgcolor="white",
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

        if df.empty:
            return render.DataGrid(
                pd.DataFrame({"Message": ["No segmented trend data yet."]}),
                filters=False
            )

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
                    "Correlation: %{z:.3f}<extra></extra>"
                ),
                colorbar=dict(
                    title="Pearson<br>correlation",
                    len=0.78,
                    thickness=18,
                    x=1.03,
                )
            )
        )

        size = 520 + 25 * len(words)

        fig.update_layout(
            title=dict(
                text="Time-series correlation heatmap",
                x=0.5,
                xanchor="center",
            ),
            width=size + 120,
            height=size,
            margin=dict(l=90, r=120, t=70, b=90),
            paper_bgcolor="white",
            plot_bgcolor="white",
            xaxis=dict(
                side="bottom",
                tickangle=35,
                constrain="domain",
            ),
            yaxis=dict(
                autorange="reversed",
                scaleanchor="x",
                scaleratio=1,
                constrain="domain",
            ),
        )

        return fig

    @output
    @render.download(
        filename=lambda: "explorer_analysis.xlsx"
    )
    def download_explorer_excel():
        yearly_df = build_yearly_df()
        metrics_df = build_metrics_df()
        segmented_df = build_segmented_trend_df()
        pairwise_df = build_pairwise_df()
        corr_df = build_correlation_matrix_df()

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
                shared.get("uploaded_scale", "frequency"),
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