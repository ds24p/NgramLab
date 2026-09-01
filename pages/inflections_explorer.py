from shiny import reactive, render, ui
from shiny.types import SilentException
from shinywidgets import output_widget, render_widget
import pandas as pd
import plotly.graph_objects as go
import tempfile
import uuid

from utils import (
    GOOGLE_NGRAM_YEAR_MAX,
    GOOGLE_NGRAM_YEAR_MIN,
    PMW_LABEL,
    build_ngram_auc_df,
    build_ngram_group_mean_df,
    build_ngram_wide_df,
    clean_lower_terms,
    fetch_google_ngram_pmw,
    normalize_ngram_year_range,
    parse_manual_words,
    parse_client_api_payload,
    read_lower_terms_from_excel,
    read_lower_terms_from_txt,
)


DATAMUSE_ABOUT_URL = "https://www.datamuse.com/api/"
GOOGLE_NGRAM_INF_URL = "https://books.google.com/ngrams/info"
WIKTIONARY_URL = "https://www.wiktionary.org/"


def inflections_explorer_ui():
    return ui.div(
        ui.div("Inflections Explorer", class_="page-title"),
        ui.p(
            "Explore manually curated inflected forms using Google Ngram data. "
            "All values are displayed as per million words (PMW) and rounded to 2 decimals.",
            class_="muted"
        ),
        ui.div(
            "Scale: per million words (PMW). PMW (per million words) = raw Google Ngram relative frequency * 1,000,000.",
            class_="inflections-scale-note",
        ),
        ui.div(
            ui.div(
                "Recommended resources for finding inflections:",
                class_="language-resources-note-title",
            ),
            ui.div(
                ui.strong("Google Ngram: "),
                ui.a(
                    "_INF inflection search",
                    href=GOOGLE_NGRAM_INF_URL,
                    target="_blank",
                ),
                " | ",
                ui.a(
                    "Wiktionary",
                    href=WIKTIONARY_URL,
                    target="_blank",
                ),
                class_="language-resources-note-line",
            ),
            ui.div(
                ui.strong("English: "),
                ui.a(
                    "Wiktionary English",
                    href="https://en.wiktionary.org/",
                    target="_blank",
                ),
                " | ",
                ui.a(
                    "WordReference Conjugator",
                    href="https://www.wordreference.com/conj/enverbs.aspx",
                    target="_blank",
                ),
                class_="language-resources-note-line",
            ),
            ui.div(
                ui.strong("German: "),
                ui.a(
                    "Verbformen",
                    href="https://www.verbformen.com/",
                    target="_blank",
                ),
                " | ",
                ui.a(
                    "DWDS",
                    href="https://www.dwds.de/wb/",
                    target="_blank",
                ),
                class_="language-resources-note-line",
            ),
            ui.div(
                ui.strong("Italian: "),
                ui.a(
                    "Italian Verbs",
                    href="https://www.italian-verbs.com/",
                    target="_blank",
                ),
                " | ",
                ui.a(
                    "Treccani Vocabolario",
                    href="https://www.treccani.it/vocabolario/",
                    target="_blank",
                ),
                class_="language-resources-note-line",
            ),
            class_="language-resources-note",
        ),

        ui.panel_conditional(
            "input.user_mode === 'New here'",
            ui.div(
                ui.h3("New here? How this tab works"),
                ui.p("What this tab does: it compares manually selected inflected forms in Google Ngram data."),
                ui.p("Main options: corpus, year range, smoothing, and the list of forms you want to analyze."),
                ui.p("Step 1: choose corpus, years, and smoothing."),
                ui.p("Step 2: add your forms manually from the recommended dictionaries."),
                ui.p("Step 3: optionally generate Datamuse candidates and select any useful forms."),
                ui.p("Step 4: click Fetch Google Ngram data, then inspect Plot, Data, and AUC."),
                class_="guide-box tab-guide-box",
            ),
        ),

        ui.layout_columns(
            ui.input_numeric(
                "infl_year_start",
                "Start year",
                value=GOOGLE_NGRAM_YEAR_MIN,
                min=GOOGLE_NGRAM_YEAR_MIN,
                max=GOOGLE_NGRAM_YEAR_MAX,
            ),
            ui.input_numeric(
                "infl_year_end",
                "End year",
                value=2019,
                min=GOOGLE_NGRAM_YEAR_MIN,
                max=GOOGLE_NGRAM_YEAR_MAX,
            ),
        ),
        ui.p(
            f"Google Ngram 2019 corpora are queried for years "
            f"{GOOGLE_NGRAM_YEAR_MIN}-{GOOGLE_NGRAM_YEAR_MAX}. "
            "Use forms that match the selected corpus language.",
            class_="muted explorer-control-note",
        ),

        ui.layout_columns(
            ui.input_select(
                "infl_corpus",
                "Corpus",
                choices={
                    "eng_2019": "English 2019",
                    "eng_us_2019": "American English 2019",
                    "eng_gb_2019": "British English 2019",
                    "eng_fiction_2019": "English Fiction 2019",
                },
                selected="eng_2019",
            ),
            ui.input_numeric(
                "infl_smoothing",
                "Smoothing",
                value=3,
                min=0,
                max=10,
            ),
        ),

        ui.layout_columns(
            ui.div(
                ui.input_text_area(
                    "infl_manual_terms",
                    "Add forms manually",
                    value="",
                    rows=6,
                    placeholder="One form per line or comma-separated, e.g.\nmother\nmothers\nmother's\nmothering",
                ),
                ui.p(
                    "Forms typed here are detected before Fetch Google Ngram data runs.",
                    class_="muted inflections-manual-hint",
                ),
                ui.output_ui("infl_manual_terms_preview"),
                class_="inflections-manual-entry",
            ),
            ui.div(
                ui.input_file(
                    "infl_terms_file",
                    "Or upload TXT / Excel file with forms",
                    accept=[".txt", ".xlsx", ".xls"],
                    multiple=False,
                ),
                ui.p(
                    "TXT: one form per line. Excel: forms in the first column.",
                    class_="muted inflections-file-hint",
                ),
                class_="inflections-file-entry",
            ),
            col_widths=(7, 5),
            class_="inflections-source-controls",
        ),

        ui.div(
            "Alternative option: find inflections with the use of Datamuse (",
            ui.a(
                "about Datamuse API",
                href=DATAMUSE_ABOUT_URL,
                target="_blank",
            ),
            ").",
            class_="inflections-alternative-note",
        ),

        ui.div(
            ui.input_text(
                "infl_base_word",
                "Base word for Datamuse",
                value="",
                placeholder="e.g. mother"
            ),
            ui.input_action_button(
                "infl_generate",
                "Generate candidate forms"
            ),
            class_="inflections-datamuse-controls",
        ),

        ui.output_ui("infl_checkbox_group"),

        ui.layout_columns(
            ui.input_action_button("infl_select_all", "Select all"),
            ui.input_action_button("infl_select_none", "Clear all"),
            class_="inflections-selection-actions",
        ),

        ui.br(),

        ui.input_action_button(
            "infl_fetch",
            "Fetch Google Ngram data",
        ),

        ui.download_button(
            "download_inflections_xlsx",
            "Download Excel file"
        ),

        ui.hr(),

        ui.output_text("infl_status"),

        ui.navset_tab(
            ui.nav_panel(
                "Plot",
                ui.div(
                    output_widget("infl_plot", width="100%"),
                    class_="inflections-plot-container",
                ),
            ),
            ui.nav_panel(
                "Data",
                ui.output_data_frame("infl_data_table")
            ),
            ui.nav_panel(
                "AUC",
                ui.output_data_frame("infl_auc_table")
            ),
            ui.nav_panel(
                "Group Mean",
                ui.output_data_frame("infl_group_mean_table"),
                ui.div(
                    output_widget("infl_group_mean_plot", width="100%"),
                    class_="inflections-plot-container",
                ),
            ),
        ),

        class_="card"
    )


def inflections_explorer_server(input_, output, session, _shared):

    ngram_data = reactive.Value(pd.DataFrame())
    candidate_forms = reactive.Value([])
    pending_datamuse_request = reactive.Value(None)
    manual_terms_state = reactive.Value([])

    def clean_terms_from_text(lines: str) -> list[str]:
        return clean_lower_terms(parse_manual_words(lines))

    def selected_candidate_forms() -> list[str]:
        if not candidate_forms():
            return []

        try:
            selected = input_.infl_selected_forms()
        except (AttributeError, SilentException):
            return []

        if selected is None:
            return []

        if isinstance(selected, str):
            return [selected]

        return list(selected)

    def selected_terms_for_fetch(manual_text: str | None = None) -> list[str]:
        manual_terms = clean_terms_from_text(manual_text) if manual_text is not None else manual_terms_state()
        file_terms = []
        file_info = input_.infl_terms_file()
        base_terms = clean_terms_from_text(input_.infl_base_word() or "")

        if file_info:
            path = file_info[0]["datapath"]
            name = file_info[0]["name"].lower()

            if name.endswith(".txt"):
                file_terms.extend(read_lower_terms_from_txt(path))
            elif name.endswith((".xlsx", ".xls")):
                file_terms.extend(read_lower_terms_from_excel(path))

        selected_terms = selected_candidate_forms()

        if not manual_terms and not file_terms and not selected_terms:
            return clean_lower_terms(base_terms)

        return clean_lower_terms(manual_terms + file_terms + selected_terms)

    def fetch_ngram_data_for_terms(manual_text: str | None = None):
        terms = selected_terms_for_fetch(manual_text)

        if not terms:
            ngram_data.set(pd.DataFrame({"error": ["Add at least one manual form or select a Datamuse candidate."]}))
            return

        if len(terms) > 12:
            ngram_data.set(pd.DataFrame({"error": ["Use max 12 forms at once."]}))
            return

        try:
            year_start = int(input_.infl_year_start())
            year_end = int(input_.infl_year_end())
        except (TypeError, ValueError):
            ngram_data.set(pd.DataFrame({"error": ["Start year and end year must be valid numbers."]}))
            return

        year_start, year_end, _ = normalize_ngram_year_range(year_start, year_end)

        try:
            ui.update_numeric("infl_year_start", value=year_start)
            ui.update_numeric("infl_year_end", value=year_end)
        except Exception:
            pass

        if year_start > year_end:
            ngram_data.set(pd.DataFrame({"error": ["Start year cannot be greater than end year."]}))
            return

        try:
            df = fetch_google_ngram_pmw(
                terms=terms,
                year_start=year_start,
                year_end=year_end,
                corpus=input_.infl_corpus(),
                smoothing=int(input_.infl_smoothing()),
            )
        except Exception as exc:
            ngram_data.set(pd.DataFrame({"error": [f"Could not fetch Google Ngram data: {exc}"]}))
            return

        if df.empty:
            ngram_data.set(pd.DataFrame({"error": ["No data returned from Google Ngram."]}))
        else:
            ngram_data.set(df)

    def build_wide_df() -> pd.DataFrame:
        return build_ngram_wide_df(ngram_data())

    def build_auc_df() -> pd.DataFrame:
        return build_ngram_auc_df(ngram_data())

    def build_group_mean_df() -> pd.DataFrame:
        return build_ngram_group_mean_df(ngram_data())

    def apply_common_plot_layout(fig, title, yaxis_title):
        fig.update_layout(
            title=dict(
                text=title,
                x=0.01,
                xanchor="left",
                font=dict(size=25),
            ),
            xaxis_title="Year",
            yaxis_title=yaxis_title,
            autosize=True,
            height=640,
            hovermode="x unified",
            margin=dict(l=84, r=44, t=92, b=116),
            font=dict(size=18),
            legend=dict(
                orientation="h",
                y=-0.2,
                x=0.5,
                xanchor="center",
                font=dict(size=16),
            ),
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        fig.update_xaxes(
            showgrid=True,
            gridcolor="rgba(17, 24, 39, 0.10)",
            title_font=dict(size=21),
            tickfont=dict(size=17),
        )
        fig.update_yaxes(
            showgrid=True,
            gridcolor="rgba(17, 24, 39, 0.10)",
            title_font=dict(size=21),
            tickfont=dict(size=17),
        )
        return fig

    def empty_figure(message: str):
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=16),
        )
        fig.update_layout(
            autosize=True,
            height=460,
            margin=dict(l=40, r=30, t=50, b=40),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        return fig

    @reactive.effect
    @reactive.event(input_.infl_generate)
    async def _generate_forms():
        request_id = uuid.uuid4().hex
        pending_datamuse_request.set(request_id)
        await session.send_custom_message(
            "client_api_request",
            {
                "request_id": request_id,
                "target": "inflections_datamuse",
                "kind": "datamuse_inflections",
                "word": input_.infl_base_word(),
                "max_words": 40,
            },
        )

    @output
    @render.ui
    def infl_checkbox_group():
        forms = candidate_forms()

        if not forms:
            return ui.p(
                "Generate Datamuse candidates if you want optional suggestions.",
                class_="muted"
            )

        return ui.div(
            ui.input_checkbox_group(
                "infl_selected_forms",
                "Select Datamuse candidates to include",
                choices=forms,
                selected=[],
            ),
            class_="inflections-candidate-list",
        )

    @reactive.effect
    @reactive.event(input_.infl_select_all)
    def _select_all():
        forms = candidate_forms()

        if forms:
            ui.update_checkbox_group(
                "infl_selected_forms",
                selected=forms
            )

    @reactive.effect
    @reactive.event(input_.infl_select_none)
    def _select_none():
        ui.update_checkbox_group(
            "infl_selected_forms",
            selected=[]
        )

    @reactive.effect
    def _sync_manual_terms():
        manual_terms_state.set(clean_terms_from_text(input_.infl_manual_terms() or ""))

    @output
    @render.ui
    def infl_manual_terms_preview():
        terms = manual_terms_state()

        if not terms:
            return ui.p("No manual forms detected yet.", class_="muted inflections-manual-detected")

        sample = ", ".join(terms[:8])
        more = "" if len(terms) <= 8 else f" (+{len(terms) - 8} more)"

        return ui.p(
            f"Manual forms detected: {sample}{more}",
            class_="muted inflections-manual-detected",
        )

    @reactive.effect
    @reactive.event(input_.infl_fetch)
    def _fetch_data():
        manual_text = input_.infl_manual_terms() or ""
        fetch_ngram_data_for_terms(manual_text)

    @reactive.effect
    @reactive.event(input_.client_api_response)
    def _handle_client_api_response():
        payload = parse_client_api_payload(input_.client_api_response())
        target = payload.get("target")

        if target == "inflections_datamuse":
            if payload.get("request_id") != pending_datamuse_request():
                return

            if payload.get("error"):
                candidate_forms.set([])
                ngram_data.set(pd.DataFrame({"error": [f"Could not fetch Datamuse candidates: {payload['error']}"]}))
                return

            candidate_forms.set(clean_lower_terms(payload.get("words", [])))
            return

    @reactive.calc
    def wide_df_data():
        return build_wide_df()

    @reactive.calc
    def auc_df_data():
        return build_auc_df()

    @reactive.calc
    def group_mean_df_data():
        return build_group_mean_df()

    @output
    @render.text
    def infl_status():
        df = ngram_data()

        if df.empty:
            return "Add forms manually or upload TXT/Excel forms, optionally choose Datamuse candidates, then fetch Google Ngram data. Values are per million words (PMW)."

        if "error" in df.columns:
            return f"Error: {df['error'].iloc[0]}"

        return f"Loaded {df['term'].nunique()} forms across {df['year'].nunique()} years. Values are {PMW_LABEL}, rounded to 2 decimals."

    @output
    @render_widget
    def infl_plot():
        df = ngram_data()

        if df.empty or "error" in df.columns:
            return empty_figure("No Ngram data yet.")

        fig = go.Figure()

        for term, group in df.groupby("term"):
            group = group.sort_values("year")
            fig.add_trace(
                go.Scatter(
                    x=group["year"],
                    y=group["frequency"],
                    mode="lines+markers",
                    name=term,
                    line=dict(width=3),
                    marker=dict(size=5, opacity=0.85),
                    hovertemplate=(
                        "Form: %{fullData.name}<br>"
                        "Year: %{x}<br>"
                        "PMW: %{y:.2f}<extra></extra>"
                    ),
                )
            )

        apply_common_plot_layout(
            fig,
            title="Google Ngram inflection trajectories",
            yaxis_title="Frequency per million words (PMW)",
        )

        return fig

    @output
    @render.data_frame
    def infl_data_table():
        return wide_df_data()

    @output
    @render.data_frame
    def infl_auc_table():
        return auc_df_data()

    @output
    @render.data_frame
    def infl_group_mean_table():
        return group_mean_df_data()

    @output
    @render_widget
    def infl_group_mean_plot():
        df = group_mean_df_data()

        if df.empty:
            return empty_figure("No group mean data yet.")

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df["year"],
                y=df["mean_pmw"],
                mode="lines+markers",
                name="Group mean",
                line=dict(width=4, color="#6d28d9"),
                marker=dict(size=6, opacity=0.9),
                hovertemplate=(
                    "Year: %{x}<br>"
                    "Group mean per million words (PMW): %{y:.2f}<extra></extra>"
                ),
            )
        )

        apply_common_plot_layout(
            fig,
            title="Mean frequency across selected inflections",
            yaxis_title="Mean frequency per million words (PMW)",
        )

        return fig

    @output
    @render.download(filename=lambda: "inflections_ngram_pmw.xlsx")
    def download_inflections_xlsx():
        df = ngram_data()

        if df.empty or "error" in df.columns:
            long_df = pd.DataFrame(columns=["term", "year", "pmw"])
        else:
            long_df = df.rename(columns={"frequency": "pmw"}).copy()
            long_df["pmw"] = long_df["pmw"].round(2)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name

        meta = pd.DataFrame({
            "setting": [
                "scale",
                "note",
                "corpus",
                "year_start",
                "year_end",
                "smoothing",
            ],
            "value": [
                PMW_LABEL,
                "PMW (per million words) = raw Google Ngram relative frequency * 1,000,000",
                input_.infl_corpus(),
                input_.infl_year_start(),
                input_.infl_year_end(),
                input_.infl_smoothing(),
            ],
        })

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            long_df.to_excel(writer, index=False, sheet_name="long_data")
            wide_df_data().to_excel(writer, index=False, sheet_name="yearly_data")
            auc_df_data().to_excel(writer, index=False, sheet_name="auc")
            group_mean_df_data().to_excel(writer, index=False, sheet_name="group_mean")
            meta.to_excel(writer, index=False, sheet_name="meta")

        return path
