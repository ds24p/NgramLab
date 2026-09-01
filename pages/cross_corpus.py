from __future__ import annotations

import io

import numpy as np
import pandas as pd

from shiny import reactive, render, ui

try:
    from shiny.types import FileInfo
except ImportError:
    FileInfo = dict

try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    from shinywidgets import output_widget, render_widget
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    plt = None
    HAS_MATPLOTLIB = False

from utils import load_word_year_matrix, auc_trapezoid


NGRAM_INFO_URL = "https://books.google.com/ngrams/info"
COHA_URL = "https://www.english-corpora.org/coha/"
TIME_CORPUS_URL = "https://www.english-corpora.org/time/"


def _build_word_index(df: pd.DataFrame) -> dict[str, pd.Series]:
    return {str(row["word"]): row for _, row in df.iterrows()}


def valid_years_for_word(
    word: str,
    dfs_years: list[tuple[pd.DataFrame, list[int], str]],
    candidate_years: list[int],
    exclude_zero_years: bool = False,
) -> list[int]:
    if not exclude_zero_years:
        return list(candidate_years)

    word_maps = []

    for df, _, _ in dfs_years:
        cache = getattr(df, "_word_index_cache", None)
        if cache is None:
            cache = _build_word_index(df)
            setattr(df, "_word_index_cache", cache)
        word_maps.append(cache)

    valid = []

    for year in candidate_years:
        keep = True

        for word_map in word_maps:
            row = word_map.get(word)

            if row is None:
                keep = False
                break

            value = pd.to_numeric(row.get(year, np.nan), errors="coerce")

            if (not np.isfinite(value)) or float(value) == 0.0:
                keep = False
                break

        if keep:
            valid.append(year)

    return valid


def compute_wordwise_auc_table(
    dfs_years: list[tuple[pd.DataFrame, list[int], str]],
    common_years: list[int],
    exclude_zero_years: bool = False,
) -> pd.DataFrame:
    names = [name for _, _, name in dfs_years]

    word_maps = []

    for df, _, _ in dfs_years:
        cache = getattr(df, "_word_index_cache", None)

        if cache is None:
            cache = _build_word_index(df)
            setattr(df, "_word_index_cache", cache)

        word_maps.append(cache)

    all_words = sorted(set().union(*[set(word_map.keys()) for word_map in word_maps]))

    rows = []

    for word in all_words:
        years_for_word = valid_years_for_word(
            word,
            dfs_years,
            common_years,
            exclude_zero_years=exclude_zero_years,
        )

        rec = {
            "word": word,
            "n_years_used": len(years_for_word),
        }

        for word_map, name in zip(word_maps, names):
            row = word_map.get(word)

            if row is None or not years_for_word:
                rec[f"auc_{name}"] = np.nan
            else:
                vals = row[years_for_word].to_numpy(dtype=float)
                rec[f"auc_{name}"] = auc_trapezoid(years_for_word, vals)

        rows.append(rec)

    return pd.DataFrame(rows)


def compare_frames(
    dfs_years: list[tuple[pd.DataFrame, list[int], str]],
    exclude_zero_years: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[int]]:
    if not dfs_years:
        raise ValueError("No datasets provided.")

    all_years = [years for _, years, _ in dfs_years]
    common_years = sorted(set.intersection(*map(set, all_years)))

    if not common_years:
        raise ValueError("No common years between the datasets.")

    merged = compute_wordwise_auc_table(
        dfs_years,
        common_years,
        exclude_zero_years=exclude_zero_years,
    )

    names = [name for _, _, name in dfs_years]

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            col_i = f"auc_{names[i]}"
            col_j = f"auc_{names[j]}"
            merged[f"diff_{names[j]}_minus_{names[i]}"] = merged[col_j] - merged[col_i]

    for name in names:
        col = f"auc_{name}"
        merged[f"rank_{col}"] = merged[col].rank(
            ascending=False,
            method="min"
        )

    auc_cols = [f"auc_{name}" for name in names]
    corr = merged[auc_cols].corr(method="pearson")

    auc_mode = "common_nonzero_per_word" if exclude_zero_years else "common_all_years"

    meta = pd.DataFrame(
        {
            "dataset": names + ["common"],
            "year_min": [min(years) for _, years, _ in dfs_years] + [min(common_years)],
            "year_max": [max(years) for _, years, _ in dfs_years] + [max(common_years)],
            "n_years": [len(years) for _, years, _ in dfs_years] + [len(common_years)],
            "AUC_mode": [auc_mode for _ in range(len(names) + 1)],
        }
    )

    merged = merged.sort_values(
        by=f"auc_{names[0]}",
        ascending=False,
        na_position="last"
    )

    return merged, corr, meta, common_years


def perform_statistical_tests(merged: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    if not HAS_SCIPY:
        return pd.DataFrame(
            {"Error": ["Scipy not available. Install with: pip install scipy"]}
        )

    results = []

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            name1 = names[i]
            name2 = names[j]

            col1 = f"auc_{name1}"
            col2 = f"auc_{name2}"

            auc1 = merged[col1].dropna()
            auc2 = merged[col2].dropna()

            if len(auc1) < 3 or len(auc2) < 3:
                continue

            try:
                _, p1 = stats.shapiro(auc1)
                _, p2 = stats.shapiro(auc2)

                normal1 = p1 > 0.05
                normal2 = p2 > 0.05
            except (ValueError, TypeError):
                normal1 = False
                normal2 = False

            if normal1 and normal2:
                test_name = "t-test"
                try:
                    stat, p_val = stats.ttest_ind(auc1, auc2)
                except (ValueError, TypeError):
                    stat, p_val = float("nan"), float("nan")
            else:
                test_name = "Mann-Whitney U"
                try:
                    stat, p_val = stats.mannwhitneyu(
                        auc1,
                        auc2,
                        alternative="two-sided"
                    )
                except (ValueError, TypeError):
                    stat, p_val = float("nan"), float("nan")

            results.append(
                {
                    "Pair": f"{name1} vs {name2}",
                    "Normality_1": "Yes" if normal1 else "No",
                    "Normality_2": "Yes" if normal2 else "No",
                    "Test": test_name,
                    "Statistic": round(float(stat), 4) if not np.isnan(stat) else "N/A",
                    "p-value": round(float(p_val), 4) if not np.isnan(p_val) else "N/A",
                    "Significant": "Yes" if (not np.isnan(p_val) and p_val < 0.05) else "No",
                }
            )

    return pd.DataFrame(results)


def trajectory_long(
    df: pd.DataFrame,
    dataset: str,
    word: str,
    years: list[int],
) -> pd.DataFrame:
    row = df.loc[df["word"] == word]

    if row.empty:
        return pd.DataFrame(
            {
                "year": years,
                "value": [np.nan] * len(years),
                "dataset": dataset,
            }
        )

    vals = row.iloc[0][years].to_numpy(dtype=float)

    return pd.DataFrame(
        {
            "year": years,
            "value": vals,
            "dataset": dataset,
        }
    )


def selected_word_auc(
    df: pd.DataFrame,
    years: list[int],
    word: str,
) -> float | None:
    row = df.loc[df["word"] == word]

    if row.empty or not years:
        return None

    vals = row.iloc[0][years].to_numpy(dtype=float)

    return auc_trapezoid(years, vals)


def selected_word_auc_values(
    dfs_years: list[tuple[pd.DataFrame, list[int], str]],
    word: str,
    years: list[int],
    exclude_zero_years: bool = False,
) -> tuple[dict[str, float | None], list[int]]:
    years_for_word = valid_years_for_word(
        word,
        dfs_years,
        years,
        exclude_zero_years=exclude_zero_years,
    )

    out = {}

    for df, _, name in dfs_years:
        out[name] = selected_word_auc(df, years_for_word, word)

    return out, years_for_word


def _safe_col_key(name: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(name).strip())
    return "_".join(part for part in cleaned.split("_") if part) or "dataset"


def compute_timeseries_tables(
    dfs_years: list[tuple[pd.DataFrame, list[int], str]],
    years: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not dfs_years or not years:
        return pd.DataFrame(), pd.DataFrame()

    names = [name for _, _, name in dfs_years]
    word_maps = []

    for df, _, _ in dfs_years:
        cache = getattr(df, "_word_index_cache", None)
        if cache is None:
            cache = _build_word_index(df)
            setattr(df, "_word_index_cache", cache)
        word_maps.append(cache)

    all_words = sorted(set().union(*[set(word_map.keys()) for word_map in word_maps]))

    pair_defs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            name1 = names[i]
            name2 = names[j]
            key1 = _safe_col_key(name1)
            key2 = _safe_col_key(name2)
            pair_defs.append(
                (
                    name1,
                    name2,
                    f"cor_{key1}_{key2}",
                    f"diff_{key1}_minus_{key2}",
                )
            )

    rows = []

    for word in all_words:
        rec = {"word": word}
        values_by_name = {}

        for word_map, name in zip(word_maps, names):
            row = word_map.get(word)
            if row is None:
                values_by_name[name] = np.full(len(years), np.nan)
            else:
                values_by_name[name] = row[years].to_numpy(dtype=float)

        for name1, name2, cor_col, diff_col in pair_defs:
            x = values_by_name[name1]
            y = values_by_name[name2]
            mask = np.isfinite(x) & np.isfinite(y)

            if mask.sum() >= 2:
                x_masked = x[mask]
                y_masked = y[mask]

                if np.nanstd(x_masked) == 0 or np.nanstd(y_masked) == 0:
                    corr = np.nan
                else:
                    corr = float(np.corrcoef(x_masked, y_masked)[0, 1])

                diff = float(np.mean((x - y)[mask]))
            else:
                corr = np.nan
                diff = np.nan

            rec[cor_col] = corr
            rec[diff_col] = diff

        rows.append(rec)

    timeseries_per_word = pd.DataFrame(rows)

    summary_rows = []

    for name1, name2, cor_col, diff_col in pair_defs:
        for metric, col in (("correlation", cor_col), ("difference", diff_col)):
            vals = pd.to_numeric(timeseries_per_word[col], errors="coerce").dropna()
            n = len(vals)

            if n == 0:
                mean = np.nan
                se = np.nan
                ci_lower = np.nan
                ci_upper = np.nan
            else:
                mean = float(vals.mean())
                se = float(vals.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan
                ci_lower = mean - 1.96 * se if np.isfinite(se) else np.nan
                ci_upper = mean + 1.96 * se if np.isfinite(se) else np.nan

            summary_rows.append(
                {
                    "comparison": f"{name1} vs {name2}",
                    "metric": metric,
                    "n": n,
                    "mean": mean,
                    "se": se,
                    "ci_lower_95": ci_lower,
                    "ci_upper_95": ci_upper,
                }
            )

    timeseries_summary = pd.DataFrame(summary_rows)

    return timeseries_per_word.round(4), timeseries_summary.round(4)


def cross_corpus_ui():
    return ui.div(
        ui.div("Cross-Corpora Comparisons", class_="page-title"),
        ui.p(
            "Compare word trajectories across uploaded datasets, compute AUC, test AUC differences, and examine correlations. "
            "Use this tab after downloading or preparing frequency tables from different corpora; upload one Excel file per corpus, then run the comparison on shared years.",
            class_="muted"
        ),

        ui.panel_conditional(
            "input.user_mode === 'New here'",
            ui.div(
                ui.h3("New here? How this tab works"),
                ui.p("What this tab does: it compares multiple uploaded corpus files on shared years and computes advanced cross-corpus statistics."),
                ui.p("Main options: number of files, dataset names, uploaded Excel files, exclusion of zero years, and selected year range."),
                ui.p("Step 1: download or prepare one word-by-year table for each corpus you want to compare, for example Google Ngram corpora, COHA, or another corpus source."),
                ui.p("Step 2: choose Number of files, then provide a name and upload one Excel file for each dataset."),
                ui.p("Step 3: click Run analysis to build all result tables (AUC, correlations, tests, timeseries)."),
                ui.p("Step 4: choose a word and adjust Year range to inspect per-word trajectories and AUC boxes."),
                ui.p("Step 5: use Timeseries per word and Timeseries summary to compare how strongly corpora co-move over time."),
                ui.p("Step 6: enable Exclude zero years when zeros should not be treated as meaningful values."),
                ui.h4("Required data format for uploaded files", class_="tab-guide-subtitle"),
                ui.p(
                    "Each uploaded Excel file should contain words in the first column. "
                    "Each following column should represent one year and contain frequency values "
                    "(preferably per million words (PMW) values)."
                ),
                ui.div(
                    ui.tags.table(
                        {"class": "tab-guide-format-table"},
                        ui.tags.thead(
                            ui.tags.tr(
                                ui.tags.th("word"),
                                ui.tags.th("1900"),
                                ui.tags.th("1901"),
                                ui.tags.th("1902"),
                                ui.tags.th("..."),
                            )
                        ),
                        ui.tags.tbody(
                            ui.tags.tr(
                                ui.tags.td("example_word_1"),
                                ui.tags.td("1.24"),
                                ui.tags.td("1.31"),
                                ui.tags.td("1.28"),
                                ui.tags.td("..."),
                            ),
                            ui.tags.tr(
                                ui.tags.td("example_word_2"),
                                ui.tags.td("0.45"),
                                ui.tags.td("0.49"),
                                ui.tags.td("0.52"),
                                ui.tags.td("..."),
                            ),
                        ),
                    ),
                    class_="tab-guide-format-card",
                ),
                class_="guide-box tab-guide-box",
            ),
        ),

        ui.layout_sidebar(
            ui.sidebar(
                ui.panel_conditional(
                    "input.cross_hide_resources_note == 0",
                    ui.div(
                        ui.div(
                            ui.div(
                                "Recommended sources for cross-corpus validation:",
                                class_="cross-resources-heading",
                            ),
                            ui.div(
                                ui.strong("Google Ngram corpora: "),
                                ui.a(
                                    "English Fiction",
                                    href=NGRAM_INFO_URL,
                                    target="_blank",
                                ),
                                " | ",
                                ui.a(
                                    "American English",
                                    href=NGRAM_INFO_URL,
                                    target="_blank",
                                ),
                                " | ",
                                ui.a(
                                    "British English",
                                    href=NGRAM_INFO_URL,
                                    target="_blank",
                                ),
                                " | ",
                                ui.a(
                                    "German",
                                    href=NGRAM_INFO_URL,
                                    target="_blank",
                                ),
                                " | ",
                                ui.a(
                                    "Italian",
                                    href=NGRAM_INFO_URL,
                                    target="_blank",
                                ),
                                " | ",
                                ui.a(
                                    "French",
                                    href=NGRAM_INFO_URL,
                                    target="_blank",
                                ),
                                " | ",
                                ui.a(
                                    "Spanish",
                                    href=NGRAM_INFO_URL,
                                    target="_blank",
                                ),
                                class_="cross-resources-line",
                            ),
                            ui.div(
                                ui.strong("Additional corpora: "),
                                ui.a(
                                    "COHA",
                                    href=COHA_URL,
                                    target="_blank",
                                ),
                                " | ",
                                ui.a(
                                    "TIME Magazine Corpus",
                                    href=TIME_CORPUS_URL,
                                    target="_blank",
                                ),
                                class_="cross-resources-line",
                            ),
                            class_="cross-resources-text",
                        ),
                        ui.input_action_button(
                            "cross_hide_resources_note",
                            "x",
                            class_="cross-resources-close",
                        ),
                        class_="cross-resources-note",
                    ),
                ),

                ui.input_numeric(
                    "cross_num_files",
                    "Number of files",
                    min=1,
                    max=10,
                    value=3
                ),

                ui.output_ui("cross_file_inputs_ui"),

                ui.input_action_button(
                    "cross_run_analysis",
                    "Run analysis",
                    class_="btn-primary"
                ),

                ui.hr(),

                ui.input_selectize(
                    "cross_word",
                    "Word",
                    choices=[],
                    selected=None
                ),

                ui.output_ui("cross_year_slider_ui"),

                ui.input_checkbox(
                    "cross_exclude_zero_years",
                    "Exclude zero years",
                    value=False
                ),

                ui.download_button(
                    "download_cross_xlsx",
                    "Download Excel file"
                ),

                ui.p(
                    "Assumption: input is already in per million words (PMW) scale, no additional conversion.",
                    class_="muted"
                ),

                width=350,
            ),

            ui.navset_tab(
                ui.nav_panel(
                    "Plot per word",
                    ui.output_ui("cross_status_ui"),
                    (
                        output_widget("cross_trajectory_plot")
                        if HAS_PLOTLY
                        else (
                            ui.output_plot("cross_trajectory_plot_base")
                            if HAS_MATPLOTLIB
                            else ui.p("No plotting backend available. Install matplotlib or plotly.")
                        )
                    ),
                    ui.output_ui("cross_auc_boxes"),
                ),

                ui.nav_panel(
                    "AUC per word",
                    ui.output_data_frame("cross_auc_table")
                ),

                ui.nav_panel(
                    "Correlations",
                    ui.output_data_frame("cross_corr_table")
                ),

                ui.nav_panel(
                    "Timeseries per word",
                    ui.output_data_frame("cross_timeseries_per_word_table")
                ),

                ui.nav_panel(
                    "Timeseries summary",
                    ui.output_data_frame("cross_timeseries_summary_table")
                ),

                ui.nav_panel(
                    "Tests",
                    ui.output_data_frame("cross_tests_table")
                ),

                ui.nav_panel(
                    "Meta",
                    ui.output_data_frame("cross_meta_table")
                ),
            ),
        ),

        class_="card"
    )


def cross_corpus_server(input_, output, session, _shared):

    @output
    @render.ui
    def cross_file_inputs_ui():
        num = input_.cross_num_files() or 3

        inputs = []

        for i in range(num):
            inputs.append(
                ui.div(
                    ui.input_text(
                        f"cross_name_{i}",
                        f"Name for file {i + 1}",
                        value="",
                        placeholder="enter the name for dataset"
                    ),
                    class_="cross-dataset-name-input",
                )
            )

            inputs.append(
                ui.input_file(
                    f"cross_file_{i}",
                    f"File {i + 1}",
                    accept=[".xlsx", ".xls"]
                )
            )

        return ui.div(*inputs)

    @reactive.calc
    def uploaded_paths() -> list[tuple[str, str]] | None:
        num = input_.cross_num_files() or 3

        paths = []

        for i in range(num):
            file_input = getattr(input_, f"cross_file_{i}")()
            name_input = getattr(input_, f"cross_name_{i}")()

            if not file_input or not name_input:
                return None

            info: FileInfo = file_input[0]  # type: ignore
            name = str(name_input).strip()

            if not name:
                return None

            paths.append((name, info["datapath"]))

        return paths

    analysis_datasets = reactive.Value(None)
    analysis_comparison = reactive.Value(None)
    analysis_tests = reactive.Value(pd.DataFrame())
    analysis_status = reactive.Value("Upload files and click Run analysis.")

    @reactive.effect
    @reactive.event(input_.cross_run_analysis)
    def _run_cross_analysis():
        paths = uploaded_paths()

        if paths is None:
            analysis_datasets.set(None)
            analysis_comparison.set(None)
            analysis_tests.set(pd.DataFrame())
            analysis_status.set("Provide a name and file for each dataset, then click Run analysis.")

            ui.update_selectize(
                "cross_word",
                choices=[],
                selected=None
            )
            return

        try:
            ds = []

            for name, path in paths:
                df, years = load_word_year_matrix(path)
                ds.append((df, years, name))

            comp = compare_frames(
                ds,
                exclude_zero_years=input_.cross_exclude_zero_years()
            )

            merged, _, _, common_years = comp
            names = [name for _, _, name in ds]
            tests = perform_statistical_tests(merged, names)

            analysis_datasets.set(ds)
            analysis_comparison.set(comp)
            analysis_tests.set(tests)
            analysis_status.set(
                f"Analysis complete for {len(ds)} datasets ({min(common_years)}-{max(common_years)}, n={len(common_years)} common years)."
            )
        except Exception as e:
            analysis_datasets.set(None)
            analysis_comparison.set(None)
            analysis_tests.set(pd.DataFrame({"Error": [str(e)]}))
            analysis_status.set(f"Analysis error: {e}")

            ui.update_selectize(
                "cross_word",
                choices=[],
                selected=None
            )

    @reactive.calc
    def datasets():
        return analysis_datasets.get()

    @reactive.calc
    def comparison():
        return analysis_comparison.get()

    @reactive.calc
    def statistical_tests():
        return analysis_tests.get()

    @reactive.effect
    def _update_word_choices():
        ds = datasets()

        if ds is None:
            ui.update_selectize(
                "cross_word",
                choices=[],
                selected=None
            )
            return

        words = sorted(set.union(*[set(df["word"]) for df, _, _ in ds]))

        selected = (
            input_.cross_word()
            if input_.cross_word() in words
            else (words[0] if words else None)
        )

        ui.update_selectize(
            "cross_word",
            choices=words,
            selected=selected
        )

    @output
    @render.ui
    def cross_year_slider_ui():
        comp = comparison()

        if comp is None:
            return ui.p("Year slider will appear after running analysis.")

        common_years = comp[3]

        return ui.input_slider(
            "cross_years",
            "Year range",
            min=min(common_years),
            max=max(common_years),
            value=(min(common_years), max(common_years)),
            step=1,
            sep="",
        )

    @reactive.calc
    def selected_years() -> list[int]:
        comp = comparison()

        if comp is None or input_.cross_years() is None:
            return []

        start, end = input_.cross_years()

        return [y for y in comp[3] if start <= y <= end]

    @reactive.calc
    def timeseries_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
        ds = datasets()
        years = selected_years()

        if ds is None or not years:
            return pd.DataFrame(), pd.DataFrame()

        return compute_timeseries_tables(ds, years)

    @reactive.calc
    def plot_data() -> pd.DataFrame:
        ds = datasets()
        word = input_.cross_word()
        years = selected_years()

        if ds is None or not word or not years:
            return pd.DataFrame(columns=["year", "value", "dataset"])

        frames = []

        for df, _, name in ds:
            frames.append(
                trajectory_long(
                    df,
                    name.upper(),
                    word,
                    years
                )
            )

        return pd.concat(frames, ignore_index=True)

    @output
    @render.ui
    def cross_status_ui():
        comp = comparison()

        if comp is None:
            return ui.div(
                {"class": "metric-box"},
                analysis_status.get()
            )

        common_years = comp[3]
        meta = comp[2]
        auc_mode = (
            str(meta["AUC_mode"].iloc[0])
            if not meta.empty and "AUC_mode" in meta.columns
            else "common_all_years"
        )

        mode_note = (
            "AUC mode: years with a zero in any corpus are excluded separately for each word."
            if auc_mode == "common_nonzero_per_word"
            else "AUC mode: all common years are used."
        )

        return ui.div(
            {"class": "metric-box"},
            ui.strong("Common years available: "),
            f"{min(common_years)}-{max(common_years)} (n={len(common_years)})",
            ui.br(),
            mode_note,
        )

    if HAS_PLOTLY:

        @output
        @render_widget
        def cross_trajectory_plot():
            df = plot_data()

            fig = go.Figure()

            if df.empty:
                fig.update_layout(title="No data to plot")
                return fig

            for dataset in df["dataset"].unique():
                sub = df[df["dataset"] == dataset]

                fig.add_trace(
                    go.Scatter(
                        x=sub["year"],
                        y=sub["value"],
                        mode="lines+markers",
                        name=dataset,
                        connectgaps=False,
                        hovertemplate=(
                            "Year=%{x}<br>Value=%{y}<extra>"
                            + dataset
                            + "</extra>"
                        ),
                    )
                )

            fig.update_layout(
                title=f"Trajectory of word: {input_.cross_word() or ''}",
                xaxis_title="Year",
                yaxis_title="Frequency",
                hovermode="x unified",
                legend_title="Dataset",
                height=520,
            )

            return fig

    else:

        @output
        @render.plot
        def cross_trajectory_plot_base():
            df = plot_data()

            fig, ax = plt.subplots(figsize=(10, 5))

            if df.empty:
                ax.set_title("No data to plot")
                return fig

            for dataset in df["dataset"].unique():
                sub = df[df["dataset"] == dataset]
                ax.plot(
                    sub["year"],
                    sub["value"],
                    marker="o",
                    label=dataset
                )

            ax.set_title(f"Trajectory of word: {input_.cross_word() or ''}")
            ax.set_xlabel("Year")
            ax.set_ylabel("Frequency")
            ax.legend()

            return fig

    @output
    @render.ui
    def cross_auc_boxes():
        ds = datasets()
        word = input_.cross_word()
        years = selected_years()

        if ds is None or not word or not years:
            return ui.p("Select a word and year range to see AUC values.")

        auc_map, years_used = selected_word_auc_values(
            ds,
            word,
            years,
            exclude_zero_years=input_.cross_exclude_zero_years(),
        )

        n = len(ds)
        width = max(2, min(12, 12 // n))

        boxes = []

        for _, _, name in ds:
            auc = auc_map.get(name)
            value = "word not found / no valid years" if auc is None else f"{auc:.2f}"

            boxes.append(
                ui.column(
                    width,
                    ui.div(
                        {"class": "metric-box"},
                        ui.strong(f"AUC ({name.upper()}, current range)"),
                        ui.br(),
                        value,
                    ),
                )
            )

        note = ""

        if input_.cross_exclude_zero_years():
            note = ui.div(
                {"class": "muted"},
                f"Years used for this word after excluding zeros: {len(years_used)}",
            )

        return ui.div(ui.row(*boxes), note)

    @output
    @render.data_frame
    def cross_auc_table():
        comp = comparison()

        if comp is None:
            return pd.DataFrame()

        df = comp[0].copy()
        auc_cols = [col for col in df.columns if col.startswith("auc_")]
        df[auc_cols] = df[auc_cols].round(2)

        return df

    @output
    @render.data_frame
    def cross_corr_table():
        comp = comparison()

        if comp is None:
            return pd.DataFrame()

        return comp[1].reset_index(names="metric")

    @output
    @render.data_frame
    def cross_timeseries_per_word_table():
        per_word, _ = timeseries_tables()
        return per_word

    @output
    @render.data_frame
    def cross_timeseries_summary_table():
        _, summary = timeseries_tables()
        return summary

    @output
    @render.data_frame
    def cross_tests_table():
        return statistical_tests()

    @output
    @render.data_frame
    def cross_meta_table():
        comp = comparison()

        if comp is None:
            return pd.DataFrame()

        return comp[2]

    @session.download(filename="AUC_comparison_shiny.xlsx")
    def download_cross_xlsx():
        comp = comparison()
        ds = datasets()

        if comp is None or ds is None:
            return

        merged, corr, meta, _ = comp
        tests = statistical_tests()
        timeseries_per_word, timeseries_summary = timeseries_tables()

        nonzero_comp = compare_frames(
            ds,
            exclude_zero_years=True
        )

        nonzero_merged = nonzero_comp[0]

        buffer = io.BytesIO()

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            merged.to_excel(
                writer,
                index=False,
                sheet_name="AUC_per_word"
            )

            nonzero_merged.to_excel(
                writer,
                index=False,
                sheet_name="AUC_excluding_zero_years"
            )

            corr.to_excel(
                writer,
                sheet_name="AUC_correlations"
            )

            timeseries_per_word.to_excel(
                writer,
                index=False,
                sheet_name="Timeseries_per_word"
            )

            timeseries_summary.to_excel(
                writer,
                index=False,
                sheet_name="Timeseries_summary"
            )

            meta.to_excel(
                writer,
                index=False,
                sheet_name="Meta"
            )

            tests.to_excel(
                writer,
                index=False,
                sheet_name="Statistical_tests"
            )

        buffer.seek(0)

        yield buffer.read()

