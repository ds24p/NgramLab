from shiny import reactive, render, ui
import pandas as pd

from utils import (
    GOOGLE_NGRAM_YEAR_MAX,
    GOOGLE_NGRAM_YEAR_MIN,
    MAX_TERM_INPUT_CHARS,
    get_corpus_year_range,
    fetch_ngram_timeseries,
    parse_manual_words,
    read_word_list_from_excel,
    read_word_list_from_txt,
    truncate_display_dataframe,
    truncate_display_text,
    unique_words,
)


MAX_FETCHER_WORDS = 200
MAX_FETCHER_DATA_POINTS = 50_000

def get_ngram_data_ui():
    return ui.div(
        ui.div("Get Ngram Data", class_="page-title"),

        ui.p(
            "Enter words manually or upload a TXT/Excel file. "
            "The app downloads raw relative frequencies from Google Ngram. "
            "Optionally, values can be converted to per million words (PMW).",
            class_="muted ngram-fetcher-intro"
        ),
        ui.panel_conditional(
            "input.user_mode === 'New here'",
            ui.div(
                ui.h3("New here? How this tab works"),
                ui.p("What this tab does: it fetches Google Ngram time-series data for your word list and prepares a clean year-by-year table."),
                ui.p("Main options: choose year range, corpus, and whether to convert output to per million words (PMW)."),
                ui.p("Step 1: add words manually or upload a TXT/Excel file (one word per line or in the first column)."),
                ui.p("Step 2: set Start year and End year, then choose the corpus you want to query."),
                ui.p("Step 3: keep PMW conversion enabled when you want easier comparison across words and corpora."),
                ui.p("Step 4: click Fetch Ngram data, review the table, then use Download Excel file for the next tabs."),
                class_="guide-box tab-guide-box",
            ),
        ),

        ui.layout_sidebar(

            ui.sidebar(

                ui.div(
                    ui.input_text_area(
                        "manual_words",
                        "Type words manually",
                        placeholder="Type one word per line or separate words with commas",
                        rows=6
                    ),
                ui.p(
                    f"Maximum {MAX_FETCHER_WORDS} words per request. "
                    f"Maximum {MAX_TERM_INPUT_CHARS} characters per term.",
                    class_="muted ngram-input-note"
                ),
                    class_="inner-card"
                ),

                ui.div(
                    ui.input_file(
                        "word_file",
                        "Or upload TXT / Excel file with words",
                        accept=[".txt", ".xlsx", ".xls"],
                        multiple=False
                    ),
                    class_="inner-card"
                ),

                ui.div(

                    ui.input_numeric(
                        "year_start",
                        "Start year",
                        value=1901,
                        min=GOOGLE_NGRAM_YEAR_MIN,
                        max=GOOGLE_NGRAM_YEAR_MAX
                    ),

                    ui.input_numeric(
                        "year_end",
                        "End year",
                        value=GOOGLE_NGRAM_YEAR_MAX,
                        min=GOOGLE_NGRAM_YEAR_MIN,
                        max=GOOGLE_NGRAM_YEAR_MAX
                    ),

                    ui.input_select(
                        "corpus",
                        "Corpus",
                        choices={
                            "26": "English 2019",
                            "27": "English Fiction 2019",
                            "28": "American English 2019",
                            "29": "British English 2019",
                            "31": "German 2019",
                            "33": "Italian 2019",
                        },
                        selected="26"
                    ),
                    ui.p(
                        "Use terms that correspond to the language of the selected corpus.",
                        class_="muted ngram-input-note"
                    ),
                    ui.output_text("corpus_year_range"),

                    ui.input_checkbox(
                        "convert_to_pmw",
                        "Convert to per million words (PMW)",
                        value=True
                    ),

                    ui.input_action_button(
                        "download_ngram",
                        "Fetch Ngram data",
                        class_="btn-primary"
                    ),

                    ui.download_button(
                        "download_ngram_xlsx",
                        "Download Excel file"
                    ),

                    class_="inner-card"
                ),
            ),

            ui.div(
                ui.output_text("ngram_status"),
                ui.output_data_frame("ngram_table"),
                class_="results-card"
            ),
        ),

        class_="card section-card"
    )


def get_ngram_data_server(input, output, session, shared):

    ngram_df = reactive.Value(None)
    status_text = reactive.Value("No data fetched yet.")
    scale_text = reactive.Value("raw relative frequency")

    @output
    @render.text
    def corpus_year_range():
        min_year, max_year = get_corpus_year_range(input.corpus())

        return (
            f"Available years for the selected corpus: "
            f"{min_year}–{max_year}"
        )

    @reactive.effect
    def _update_year_inputs_for_corpus():
        corpus = input.corpus()
        min_year, max_year = get_corpus_year_range(corpus)

        current_start = input.year_start()
        current_end = input.year_end()

        try:
            current_start = int(current_start)
        except (TypeError, ValueError):
            current_start = min_year

        try:
            current_end = int(current_end)
        except (TypeError, ValueError):
            current_end = max_year

        new_start = min(max(current_start, min_year), max_year)
        new_end = min(max(current_end, min_year), max_year)

        ui.update_numeric(
            "year_start",
            min=min_year,
            max=max_year,
            value=new_start,
        )

        ui.update_numeric(
            "year_end",
            min=min_year,
            max=max_year,
            value=new_end,
        )

    def collect_words():
        words = []

        manual = parse_manual_words(input.manual_words())
        words.extend(manual)

        file_info = input.word_file()

        if file_info:
            path = file_info[0]["datapath"]
            name = file_info[0]["name"].lower()

            if name.endswith(".txt"):
                words.extend(read_word_list_from_txt(path))

            elif name.endswith((".xlsx", ".xls")):
                words.extend(read_word_list_from_excel(path))

        unique = unique_words(words)
        return unique

    @reactive.effect
    @reactive.event(input.download_ngram)
    def _download_ngram_data():
        words = collect_words()

        if not words:
            status_text.set("No words provided. Type words manually or upload TXT/Excel file.")
            return

        too_long_words = [
            word for word in words
            if len(str(word)) > MAX_TERM_INPUT_CHARS
        ]

        if too_long_words:
            sample = ", ".join(
                truncate_display_text(word, max_chars=50)
                for word in too_long_words[:3]
            )
            more = (
                f" and {len(too_long_words) - 3} more"
                if len(too_long_words) > 3
                else ""
            )
            status_text.set(
                f"Terms can be up to {MAX_TERM_INPUT_CHARS} characters. "
                f"Please shorten: {sample}{more}"
            )
            return

        corpus = input.corpus()
        min_year, max_year = get_corpus_year_range(corpus)

        try:
            year_start = int(input.year_start())
            year_end = int(input.year_end())
        except (TypeError, ValueError):
            status_text.set(
                "Start year and end year must be valid numbers."
            )
            return


        if year_start < min_year or year_start > max_year:
            status_text.set(
                f"Invalid start year: {year_start}. "
                f"Available years for the selected corpus are "
                f"{min_year}–{max_year}."
            )
            return


        if year_end < min_year or year_end > max_year:
            status_text.set(
                f"Invalid end year: {year_end}. "
                f"Available years for the selected corpus are "
                f"{min_year}–{max_year}."
            )
            return


        if year_start >= year_end:
            status_text.set(
                "Start year must be earlier than end year."
            )
            return
        convert_to_pmw = bool(input.convert_to_pmw())

        scale = (
            "per million words (PMW)"
            if convert_to_pmw
            else "raw relative frequency"
        )

        scale_text.set(scale)
        years = list(range(year_start, year_end + 1))
        expected_len = len(years)
        requested_points = len(words) * expected_len

        if len(words) > MAX_FETCHER_WORDS:
            status_text.set(
                f"You entered {len(words)} words. "
                f"A maximum of {MAX_FETCHER_WORDS} words can be processed at once. "
                "Please reduce your list or split it into multiple requests."
            )
            return

        if requested_points > MAX_FETCHER_DATA_POINTS:
            status_text.set(
                f"Request too large: {len(words)} words x {expected_len} years "
                f"= {requested_points:,} values. Use max {MAX_FETCHER_DATA_POINTS:,} values per fetch "
                "by reducing the word list or year range."
            )
            return

        rows = []
        errors = []

        status_text.set(
            f"Downloading {len(words)} words for years {year_start}-{year_end}..."
        )

        for word in words:
            row = {"word": word}

            try:
                ts = fetch_ngram_timeseries(
                    word=word,
                    year_start=year_start,
                    year_end=year_end,
                    corpus=corpus,
                    smoothing=0,
                    case_insensitive=False,
                )

            except Exception as exc:
                errors.append(f"{word}: {exc}")

                for y in years:
                    row[str(y)] = None

                rows.append(row)
                continue

            # Google returned no frequency data for this word
            if not ts:
                errors.append(f"{word}: no frequency data found")

                for y in years:
                    row[str(y)] = None

                rows.append(row)
                continue

            # Google returned an incomplete time series
            if len(ts) != expected_len:
                errors.append(
                    f"{word}: incomplete frequency data "
                    f"({len(ts)} of {expected_len} years returned)"
                )

                for y in years:
                    row[str(y)] = None

                rows.append(row)
                continue

            # Valid time series
            for y, value in zip(years, ts):
                value = float(value)

                if convert_to_pmw:
                    value = value * 1_000_000

                row[str(y)] = value

            rows.append(row)

        df = pd.DataFrame(rows)
        numeric_cols = df.select_dtypes(include="number").columns
        df[numeric_cols] = df[numeric_cols].round(2)

        ngram_df.set(df)

        shared["uploaded_df"] = df
        shared["uploaded_years"] = years
        shared["uploaded_scale"] = scale

        data_version = shared.get("uploaded_data_version")
        if data_version is not None:
            data_version.set(int(data_version.get() or 0) + 1)

        choices = sorted(set(df["word"].dropna().unique().tolist()), key=str.casefold)

        try:
            selected = input.selected_word()
        except Exception:
            selected = []

        if selected is None:
            selected = []
        elif isinstance(selected, str):
            selected = [selected]

        selected = [w for w in selected if w in choices]

        if not selected:
            selected = choices[:1]

        try:
            ui.update_selectize(
                "selected_word",
                choices=choices,
                selected=selected
            )
        except Exception:
            pass

        status_text.set(
            f"Downloaded {len(df)} words for years {year_start}-{year_end}. "
            f"Values are {scale}."
        )

        if errors:
            status_text.set(
                f"Downloaded {len(df) - len(errors)} of {len(df)} words for "
                f"{year_start}-{year_end}. Values are {scale}. "
                f"{len(errors)} word(s) could not be fetched."
            )

    @output
    @render.text
    def ngram_status():
        return status_text.get()

    @output
    @render.data_frame
    def ngram_table():
        df = ngram_df.get()

        if df is None or df.empty:
            return render.DataGrid(
                pd.DataFrame({"message": ["No data downloaded yet."]}),
                filters=False
            )

        display_df = truncate_display_dataframe(df, columns=["word"])

        return render.DataGrid(
            display_df,
            filters=False,
            height="500px",
            width="100%",
            row_selection_mode="none",
            editable=False,
            styles=[
                {
                    "cols": [0],
                    "style": {
                        "position": "sticky",
                        "left": "0px",
                        "background-color": "white",
                        "z-index": "2",
                        "font-weight": "600",
                        "min-width": "180px",
                        "max-width": "280px",
                        "overflow": "hidden",
                        "text-overflow": "ellipsis",
                        "white-space": "nowrap",
                    },
                }
            ],
        )

    @output
    @render.download(
        filename=lambda: (
            "ngram_words_per_million.xlsx"
            if bool(input.convert_to_pmw())
            else "ngram_raw_relative_frequencies.xlsx"
        )
    )
    def download_ngram_xlsx():
        df = ngram_df.get()

        if df is None:
            df = pd.DataFrame()

        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name

        convert_to_pmw = bool(input.convert_to_pmw())

        scale = (
            "per million words (PMW)"
            if convert_to_pmw
            else "raw relative frequency"
        )

        note = (
            "PMW (per million words) = raw relative frequency * 1,000,000"
            if convert_to_pmw
            else "Raw relative frequency returned by Google Ngram"
        )

        export_df = df.copy()
        numeric_cols = export_df.select_dtypes(include="number").columns
        export_df[numeric_cols] = export_df[numeric_cols].round(2)

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            export_df.to_excel(writer, index=False, sheet_name="ngram_data")

            meta = pd.DataFrame({
                "setting": [
                    "scale",
                    "note",
                    "corpus",
                    "year_start",
                    "year_end",
                ],
                "value": [
                    scale,
                    note,
                    input.corpus(),
                    input.year_start(),
                    input.year_end(),
                ]
            })

            meta.to_excel(writer, index=False, sheet_name="meta")

        return path
