from shiny import reactive, render, ui
import pandas as pd
import numpy as np
import requests
import urllib.parse
import matplotlib.pyplot as plt

from utils import auc_trapezoid


try:
    from lemminflect import getAllInflections
    HAS_LEMMINFLECT = True
except ImportError:
    HAS_LEMMINFLECT = False

try:
    from wordfreq import zipf_frequency
    HAS_WORDFREQ = True
except ImportError:
    HAS_WORDFREQ = False


SPECIAL_WORD_FAMILIES = {
    "mother": ["mother", "mothers", "mother's", "motherhood", "mothering", "mothered", "maternal", "maternity"],
    "father": ["father", "fathers", "father's", "fatherhood", "fathering", "fathered", "paternal", "paternity"],
    "child": ["child", "children", "childhood", "childish", "childlike"],
    "woman": ["woman", "women", "womanhood", "womanly", "feminine", "femininity"],
    "man": ["man", "men", "manhood", "manly", "masculine", "masculinity"],
}


def clean_terms(terms: list[str]) -> list[str]:
    out = []
    for term in terms:
        term = str(term).strip().lower()
        if term and term not in out:
            out.append(term)
    return out


def get_strict_inflections(word: str) -> list[str]:
    forms = [word]

    if HAS_LEMMINFLECT:
        try:
            inflections = getAllInflections(word)
            for values in inflections.values():
                forms.extend(values)
        except (AttributeError, TypeError, ValueError):
            pass

    # fallback / supplement
    forms.extend([
        f"{word}s",
        f"{word}'s",
        f"{word}ed",
        f"{word}ing",
    ])

    return clean_terms(forms)


def get_derivational_forms(word: str) -> list[str]:
    suffixes = [
        "hood",
        "ness",
        "ship",
        "less",
        "ful",
        "ly",
        "er",
        "ers",
        "ism",
        "ist",
        "ity",
        "al",
        "ation",
    ]

    forms = [word]
    forms.extend([f"{word}{suffix}" for suffix in suffixes])

    if word.endswith("e"):
        stem = word[:-1]
        forms.extend([
            f"{stem}ing",
            f"{stem}ed",
            f"{stem}er",
            f"{stem}ers",
            f"{stem}ion",
            f"{stem}ity",
        ])

    return clean_terms(forms)


def get_related_forms_datamuse(word: str, max_words: int = 20) -> list[str]:
    forms = []

    try:
        response = requests.get(
            "https://api.datamuse.com/words",
            params={
                "ml": word,
                "sp": f"{word[0]}*",
                "max": max_words,
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        forms.extend([item["word"] for item in data if "word" in item])
    except (requests.RequestException, ValueError):
        pass

    try:
        response = requests.get(
            "https://api.datamuse.com/words",
            params={
                "rel_trg": word,
                "max": max_words,
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        forms.extend([item["word"] for item in data if "word" in item])
    except (requests.RequestException, ValueError):
        pass

    return clean_terms(forms)


def filter_rare_words(terms: list[str], min_zipf: float = 2.5) -> list[str]:
    if not HAS_WORDFREQ:
        return terms

    kept = []
    for term in terms:
        # wordfreq działa najlepiej dla pojedynczych słów bez apostrofów
        check_term = term.replace("'s", "")
        try:
            score = zipf_frequency(check_term, "en")
            if score >= min_zipf:
                kept.append(term)
        except (TypeError, ValueError):
            kept.append(term)

    return clean_terms(kept)


def generate_word_family(
    base_word: str,
    include_inflections: bool = True,
    include_derivations: bool = True,
    include_related: bool = True,
    filter_rare: bool = False,
) -> list[str]:
    word = base_word.strip().lower()

    if not word:
        return []

    candidates = [word]

    if word in SPECIAL_WORD_FAMILIES:
        candidates.extend(SPECIAL_WORD_FAMILIES[word])

    if include_inflections:
        candidates.extend(get_strict_inflections(word))

    if include_derivations:
        candidates.extend(get_derivational_forms(word))

    if include_related:
        candidates.extend(get_related_forms_datamuse(word))

    candidates = clean_terms(candidates)

    if filter_rare:
        candidates = filter_rare_words(candidates)

    return candidates[:30]


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


def inflections_explorer_ui():
    return ui.div(
        ui.div("Inflections Explorer", class_="page-title"),
        ui.p(
            "Explore inflected, derived and morphologically related forms using Google Ngram data.",
            class_="muted"
        ),
        ui.div(
            ui.div(
                "Recommended resources for finding inflections:",
                class_="language-resources-note-title",
            ),
            ui.div(
                ui.strong("English: "),
                ui.a(
                    "Wiktionary",
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
                ui.p("What this tab does: it generates inflected, derivational, and related forms and compares their trajectories."),
                ui.p("Main options: base word, corpus, year range, smoothing, and checkboxes controlling how forms are generated."),
                ui.p("Step 1: set a base word and choose whether to include strict inflections, derivations, and related forms."),
                ui.p("Step 2: click Generate candidate forms, then review/edit the list manually."),
                ui.p("Step 3: select forms to analyze and click Fetch Google Ngram data."),
                ui.p("Step 4: use Plot to compare curves, Data for year-by-year values, and AUC for ranking forms."),
                class_="guide-box tab-guide-box",
            ),
        ),

        ui.layout_columns(
            ui.input_text(
                "infl_base_word",
                "Base word",
                value="mother",
                placeholder="e.g. mother"
            ),
            ui.input_numeric(
                "infl_year_start",
                "Start year",
                value=1800,
                min=1500,
                max=2022,
            ),
            ui.input_numeric(
                "infl_year_end",
                "End year",
                value=2019,
                min=1500,
                max=2022,
            ),
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
            ui.input_checkbox(
                "infl_use_inflections",
                "Strict inflections",
                value=True,
            ),
            ui.input_checkbox(
                "infl_use_derivations",
                "Derivational forms",
                value=True,
            ),
            ui.input_checkbox(
                "infl_use_related",
                "Related forms",
                value=True,
            ),
            ui.input_checkbox(
                "infl_filter_rare",
                "Filter rare words",
                value=False,
            ),
        ),

        ui.input_action_button(
            "infl_generate",
            "Generate candidate forms"
        ),

        ui.br(),
        ui.br(),

        ui.output_ui("infl_checkbox_group"),

        ui.layout_columns(
            ui.input_action_button("infl_select_all", "Select all"),
            ui.input_action_button("infl_select_none", "Clear all"),
        ),

        ui.br(),

        ui.input_text_area(
            "infl_custom_terms",
            "Edit / add forms manually",
            value="",
            rows=6,
            placeholder="One form per line. You can delete generated forms or add your own."
        ),

        ui.input_action_button(
            "infl_apply_manual_terms",
            "Apply manual list"
        ),

        ui.br(),
        ui.br(),

        ui.input_action_button(
            "infl_fetch",
            "Fetch Google Ngram data"
        ),

        ui.hr(),

        ui.output_text("infl_status"),

        ui.navset_tab(
            ui.nav_panel(
                "Plot",
                ui.output_plot("infl_plot")
            ),
            ui.nav_panel(
                "Data",
                ui.output_data_frame("infl_data_table")
            ),
            ui.nav_panel(
                "AUC",
                ui.output_data_frame("infl_auc_table")
            ),
        ),

        class_="card"
    )


def inflections_explorer_server(input_, output, _session, _shared):

    ngram_data = reactive.Value(pd.DataFrame())
    candidate_forms = reactive.Value([])

    def clean_terms_from_text(lines: str) -> list[str]:
        terms = [
            line.strip()
            for line in lines.splitlines()
            if line.strip()
        ]
        return clean_terms(terms)

    @reactive.effect
    @reactive.event(input_.infl_generate)
    def _generate_forms():
        forms = generate_word_family(
            base_word=input_.infl_base_word(),
            include_inflections=input_.infl_use_inflections(),
            include_derivations=input_.infl_use_derivations(),
            include_related=input_.infl_use_related(),
            filter_rare=input_.infl_filter_rare(),
        )

        candidate_forms.set(forms)

        ui.update_text_area(
            "infl_custom_terms",
            value="\n".join(forms)
        )

    @reactive.effect
    @reactive.event(input_.infl_apply_manual_terms)
    def _apply_manual_terms():
        forms = clean_terms_from_text(input_.infl_custom_terms())

        candidate_forms.set(forms)

        ui.update_checkbox_group(
            "infl_selected_forms",
            choices=forms,
            selected=forms
        )

    @output
    @render.ui
    def infl_checkbox_group():
        forms = candidate_forms()

        if not forms:
            return ui.p("Generate forms first or add forms manually.", class_="muted")

        return ui.input_checkbox_group(
            "infl_selected_forms",
            "Select forms to analyze",
            choices=forms,
            selected=forms,
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
    @reactive.event(input_.infl_fetch)
    def _fetch_data():
        terms = input_.infl_selected_forms()

        if not terms:
            ngram_data.set(pd.DataFrame({"error": ["Select at least one form."]}))
            return

        if len(terms) > 12:
            ngram_data.set(pd.DataFrame({"error": ["Use max 12 forms at once."]}))
            return

        try:
            df = fetch_google_ngram(
                terms=list(terms),
                year_start=int(input_.infl_year_start()),
                year_end=int(input_.infl_year_end()),
                corpus=input_.infl_corpus(),
                smoothing=int(input_.infl_smoothing()),
            )

            if df.empty:
                ngram_data.set(pd.DataFrame({"error": ["No data returned from Google Ngram."]}))
            else:
                ngram_data.set(df)

        except (requests.RequestException, ValueError, TypeError) as e:
            ngram_data.set(pd.DataFrame({"error": [str(e)]}))

    @output
    @render.text
    def infl_status():
        df = ngram_data()

        extras = []
        if not HAS_LEMMINFLECT:
            extras.append("LemmInflect not installed")
        if not HAS_WORDFREQ:
            extras.append("wordfreq not installed")

        note = ""
        if extras:
            note = " | Optional modules: " + ", ".join(extras)

        if df.empty:
            return "Generate forms, edit/add forms if needed, select the forms you want, then fetch Google Ngram data." + note

        if "error" in df.columns:
            return f"Error: {df['error'].iloc[0]}" + note

        return f"Loaded {df['term'].nunique()} forms across {df['year'].nunique()} years." + note

    @output
    @render.plot
    def infl_plot():
        df = ngram_data()

        fig, ax = plt.subplots(figsize=(9, 5))

        if df.empty or "error" in df.columns:
            ax.text(0.5, 0.5, "No Ngram data yet.", ha="center", va="center")
            ax.set_axis_off()
            return fig

        for term, group in df.groupby("term"):
            group = group.sort_values("year")
            ax.plot(group["year"], group["frequency"], label=term)

        ax.set_title(f"Google Ngram word-family trajectories: {input_.infl_base_word()}")
        ax.set_xlabel("Year")
        ax.set_ylabel("Frequency")
        ax.grid(True, alpha=0.25)
        ax.legend()

        return fig

    @output
    @render.data_frame
    def infl_data_table():
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
    def infl_auc_table():
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
