from shiny import reactive, render, ui
import pandas as pd
import time

from utils import fetch_ngram_timeseries, parse_manual_words, unique_words


POLITE_DELAY_SEC = 0.4
REFERENCE_WORD = "the"

def read_words_from_txt(path: str):
    words = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                words.append(line)

    return unique_words(words)


def read_words_from_excel(path: str):
    df = pd.read_excel(path)
    first_col = df.columns[0]

    words = (
        df[first_col]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )

    return unique_words(words)

def get_ngram_data_ui():
    return ui.div(
        ui.div("Get Ngram Data", class_="page-title"),

        ui.p(
            "Enter words manually or upload a TXT/Excel file. "
            "The app downloads raw relative frequencies from Google Ngram. "
            "Optionally, values can be converted to words per million.",
            class_="muted ngram-fetcher-intro"
        ),

        ui.panel_conditional(
            "input.user_mode === 'New here'",
            ui.div(
                ui.h3("New here? How this tab works"),
                ui.p("What this tab does: it fetches Google Ngram time-series data for your word list and prepares a clean year-by-year table."),
                ui.p("Main options: choose year range, corpus, and whether to convert output to words per million (PMW)."),
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
                        placeholder="Type one word per line",
                        rows=6
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
                        min=1500,
                        max=2019
                    ),

                    ui.input_numeric(
                        "year_end",
                        "End year",
                        value=2000,
                        min=1500,
                        max=2019
                    ),

                    ui.input_select(
                        "corpus",
                        "Corpus",
                        choices={
                            "26": "English 2019",
                            "27": "American English 2019",
                            "28": "British English 2019",
                            "29": "English Fiction 2019",
                        },
                        selected="26"
                    ),

                    ui.input_checkbox(
                        "convert_to_pmw",
                        "Convert to words per million (PMW)",
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

    def collect_words():
        words = []

        manual = parse_manual_words(input.manual_words())
        words.extend(manual)

        file_info = input.word_file()

        if file_info:
            path = file_info[0]["datapath"]
            name = file_info[0]["name"].lower()

            if name.endswith(".txt"):
                words.extend(read_words_from_txt(path))

            elif name.endswith((".xlsx", ".xls")):
                words.extend(read_words_from_excel(path))

        unique = unique_words(words)
        if REFERENCE_WORD not in unique:
            unique.insert(0, REFERENCE_WORD)

        return unique

    @reactive.effect
    @reactive.event(input.download_ngram)
    def _download_ngram_data():
        words = collect_words()

        if not words:
            status_text.set("No words provided. Type words manually or upload TXT/Excel file.")
            return

        year_start = int(input.year_start())
        year_end = int(input.year_end())

        if year_start > year_end:
            status_text.set("Start year cannot be greater than end year.")
            return

        corpus = int(input.corpus())
        convert_to_pmw = bool(input.convert_to_pmw())

        scale = (
            "words per million (PMW)"
            if convert_to_pmw
            else "raw relative frequency"
        )

        scale_text.set(scale)

        years = list(range(year_start, year_end + 1))
        rows = []

        status_text.set(f"Downloading data for {len(words)} words...")

        for i, word in enumerate(words, start=1):
            try:
                ts = fetch_ngram_timeseries(
                    word=word,
                    year_start=year_start,
                    year_end=year_end,
                    corpus=corpus,
                )

                expected_len = len(years)

                if not ts:
                    ts = [0.0] * expected_len

                ts = (ts + [0.0] * expected_len)[:expected_len]

                row = {"word": word}

                for y, value in zip(years, ts):
                    value = float(value)

                    if convert_to_pmw:
                        value = value * 1_000_000

                    row[str(y)] = value

                rows.append(row)

                time.sleep(POLITE_DELAY_SEC)

            except Exception as e:
                row = {"word": word}
                for y in years:
                    row[str(y)] = None
                rows.append(row)

                print(f"Error for {word}: {e}")

        df = pd.DataFrame(rows)

        numeric_cols = df.select_dtypes(include="number").columns
        df[numeric_cols] = df[numeric_cols].round(2)

        ngram_df.set(df)

        shared["uploaded_df"] = df
        shared["uploaded_years"] = years
        shared["uploaded_scale"] = scale

        choices = sorted(set(df["word"].dropna().unique().tolist() + [REFERENCE_WORD]))

        selected = input.selected_word()
        if selected is None:
            selected = []
        elif isinstance(selected, str):
            selected = [selected]

        selected = [w for w in selected if w in choices]
        if REFERENCE_WORD not in selected:
            selected.insert(0, REFERENCE_WORD)

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

        return render.DataGrid(
            df,
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
            "words per million (PMW)"
            if convert_to_pmw
            else "raw relative frequency"
        )

        note = (
            "PMW = raw relative frequency * 1,000,000"
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
