from shiny import reactive, render, ui
import pandas as pd
import numpy as np
import requests
import urllib.parse
import matplotlib.pyplot as plt

from utils import auc_trapezoid


def fetch_synonyms(word: str, max_words: int = 15) -> list[str]:
    word = word.strip().lower()

    if not word:
        return []

    url = "https://api.datamuse.com/words"

    response = requests.get(
        url,
        params={
            "rel_syn": word,
            "max": max_words,
        },
        timeout=30,
    )

    response.raise_for_status()
    data = response.json()

    synonyms = [item["word"] for item in data if "word" in item]

    return list(dict.fromkeys([word] + synonyms))


def fetch_google_ngram(
    terms: list[str],
    year_start: int,
    year_end: int,
    corpus: str,
    smoothing: int,
) -> pd.DataFrame:
    terms = [t.strip() for t in terms if t.strip()]

    if not terms:
        return pd.DataFrame()

    query = ",".join(terms)

    url = (
        "https://books.google.com/ngrams/json?"
        + urllib.parse.urlencode(
            {
                "content": query,
                "year_start": year_start,
                "year_end": year_end,
                "corpus": corpus,
                "smoothing": smoothing,
            }
        )
    )

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()

    years = list(range(year_start, year_end + 1))
    rows = []

    for item in data:
        term = item["ngram"]
        values = item["timeseries"]

        for year, value in zip(years, values):
            rows.append(
                {
                    "term": term,
                    "year": year,
                    "frequency": value,
                }
            )

    return pd.DataFrame(rows)


def synonyms_explorer_ui():
    return ui.div(
        ui.div("Synonyms Explorer", class_="page-title"),
        ui.p(
            "Find synonyms, select the ones you want, and compare their Google Ngram trajectories.",
            class_="muted"
        ),
        ui.div(
            ui.div(
                "Recommended resources for finding synonyms:",
                class_="language-resources-note-title",
            ),
            ui.div(
                ui.strong("English: "),
                ui.a(
                    "Thesaurus.com",
                    href="https://www.thesaurus.com/",
                    target="_blank",
                ),
                " | ",
                ui.a(
                    "Merriam-Webster Thesaurus",
                    href="https://www.merriam-webster.com/thesaurus",
                    target="_blank",
                ),
                class_="language-resources-note-line",
            ),
            ui.div(
                ui.strong("German: "),
                ui.a(
                    "Duden Synonyme",
                    href="https://www.duden.de/synonyme",
                    target="_blank",
                ),
                " | ",
                ui.a(
                    "OpenThesaurus",
                    href="https://www.openthesaurus.de/",
                    target="_blank",
                ),
                class_="language-resources-note-line",
            ),
            ui.div(
                ui.strong("Italian: "),
                ui.a(
                    "Treccani Sinonimi",
                    href="https://www.treccani.it/sinonimi/",
                    target="_blank",
                ),
                " | ",
                ui.a(
                    "Sinonimi-Contrari",
                    href="https://www.sinonimi-contrari.it/",
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
                ui.p("What this tab does: it finds synonyms for a base word and compares their Google Ngram trajectories."),
                ui.p("Main options: base word, max number of synonyms, corpus, year range, and smoothing."),
                ui.p("Step 1: enter a base word and click Find synonyms."),
                ui.p("Step 2: review generated words, keep the useful ones, remove noise, or add your own words manually."),
                ui.p("Step 3: choose corpus, years, and smoothing, then click Fetch Google Ngram data."),
                ui.p("Step 4: inspect Plot for dynamics, Data for raw values, and AUC for aggregate comparisons."),
                class_="guide-box tab-guide-box",
            ),
        ),

        ui.layout_columns(
            ui.input_text(
                "syn_base_word",
                "Base word",
                value="freedom",
                placeholder="e.g. freedom"
            ),
            ui.input_numeric(
                "syn_max_words",
                "Max synonyms",
                value=15,
                min=1,
                max=30,
            ),
        ),

        ui.layout_columns(
            ui.input_numeric(
                "syn_year_start",
                "Start year",
                value=1800,
                min=1500,
                max=2022,
            ),
            ui.input_numeric(
                "syn_year_end",
                "End year",
                value=2019,
                min=1500,
                max=2022,
            ),
        ),

        ui.layout_columns(
            ui.input_select(
                "syn_corpus",
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
                "syn_smoothing",
                "Smoothing",
                value=3,
                min=0,
                max=10,
            ),
        ),

        ui.input_action_button(
            "syn_find",
            "Find synonyms"
        ),

        ui.br(),
        ui.br(),

        ui.output_ui("syn_checkbox_group"),

        ui.layout_columns(
            ui.input_action_button("syn_select_all", "Select all"),
            ui.input_action_button("syn_select_none", "Clear all"),
        ),

        ui.br(),

        ui.input_text_area(
            "syn_custom_terms",
            "Edit / add words manually",
            value="",
            rows=6,
            placeholder="Type one word per line. You can delete suggested synonyms or add your own."
        ),

        ui.input_action_button(
            "syn_apply_manual_terms",
            "Apply manual list"
        ),

        ui.br(),
        ui.br(),

        ui.input_action_button(
            "syn_fetch",
            "Fetch Google Ngram data"
        ),

        ui.hr(),

        ui.output_text("syn_status"),

        ui.navset_tab(
            ui.nav_panel(
                "Plot",
                ui.output_plot("syn_plot")
            ),
            ui.nav_panel(
                "Data",
                ui.output_data_frame("syn_data_table")
            ),
            ui.nav_panel(
                "AUC",
                ui.output_data_frame("syn_auc_table")
            ),
        ),

        class_="card"
    )


def synonyms_explorer_server(input, output, session, shared):

    ngram_data = reactive.Value(pd.DataFrame())
    candidate_synonyms = reactive.Value([])

    def clean_terms(lines: str) -> list[str]:
        terms = [
            line.strip()
            for line in lines.splitlines()
            if line.strip()
        ]
        return list(dict.fromkeys(terms))

    @reactive.effect
    @reactive.event(input.syn_find)
    def _find_synonyms():
        try:
            words = fetch_synonyms(
                input.syn_base_word(),
                max_words=int(input.syn_max_words())
            )
            candidate_synonyms.set(words)

            ui.update_text_area(
                "syn_custom_terms",
                value="\n".join(words)
            )

        except Exception as e:
            candidate_synonyms.set([])
            ngram_data.set(pd.DataFrame({"error": [f"Could not fetch synonyms: {e}"]}))

    @reactive.effect
    @reactive.event(input.syn_apply_manual_terms)
    def _apply_manual_terms():
        words = clean_terms(input.syn_custom_terms())

        candidate_synonyms.set(words)

        ui.update_checkbox_group(
            "syn_selected_terms",
            choices=words,
            selected=words
        )

    @output
    @render.ui
    def syn_checkbox_group():
        words = candidate_synonyms()

        if not words:
            return ui.p("Find synonyms first or add words manually.", class_="muted")

        return ui.input_checkbox_group(
            "syn_selected_terms",
            "Select words to analyze",
            choices=words,
            selected=words,
        )

    @reactive.effect
    @reactive.event(input.syn_select_all)
    def _select_all():
        words = candidate_synonyms()

        if words:
            ui.update_checkbox_group(
                "syn_selected_terms",
                selected=words
            )

    @reactive.effect
    @reactive.event(input.syn_select_none)
    def _select_none():
        ui.update_checkbox_group(
            "syn_selected_terms",
            selected=[]
        )

    @reactive.effect
    @reactive.event(input.syn_fetch)
    def _fetch_ngram_data():
        terms = input.syn_selected_terms()

        if not terms:
            ngram_data.set(pd.DataFrame({"error": ["Select at least one word."]}))
            return

        if len(terms) > 12:
            ngram_data.set(pd.DataFrame({"error": ["Use max 12 words at once."]}))
            return

        try:
            df = fetch_google_ngram(
                terms=list(terms),
                year_start=int(input.syn_year_start()),
                year_end=int(input.syn_year_end()),
                corpus=input.syn_corpus(),
                smoothing=int(input.syn_smoothing()),
            )

            if df.empty:
                ngram_data.set(pd.DataFrame({"error": ["No data returned from Google Ngram."]}))
            else:
                ngram_data.set(df)

        except Exception as e:
            ngram_data.set(pd.DataFrame({"error": [str(e)]}))

    @output
    @render.text
    def syn_status():
        df = ngram_data()

        if df.empty:
            return "Find synonyms, edit/select words if needed, then fetch Google Ngram data."

        if "error" in df.columns:
            return f"Error: {df['error'].iloc[0]}"

        return f"Loaded {df['term'].nunique()} words across {df['year'].nunique()} years."

    @output
    @render.plot
    def syn_plot():
        df = ngram_data()

        fig, ax = plt.subplots(figsize=(9, 5))

        if df.empty or "error" in df.columns:
            ax.text(0.5, 0.5, "No Ngram data yet.", ha="center", va="center")
            ax.set_axis_off()
            return fig

        for term, group in df.groupby("term"):
            group = group.sort_values("year")
            ax.plot(group["year"], group["frequency"], label=term)

        ax.set_title(f"Google Ngram synonym trajectories: {input.syn_base_word()}")
        ax.set_xlabel("Year")
        ax.set_ylabel("Frequency")
        ax.grid(True, alpha=0.25)
        ax.legend()

        return fig

    @output
    @render.data_frame
    def syn_data_table():
        df = ngram_data()

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

    @output
    @render.data_frame
    def syn_auc_table():
        df = ngram_data()

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
                    "mean_frequency": round(float(np.nanmean(values)), 8),
                    "max_frequency": round(float(np.nanmax(values)), 8),
                }
            )

        result = pd.DataFrame(rows).sort_values("auc", ascending=False)

        return result
