from shiny import reactive, render, ui
import pandas as pd
import urllib.parse
import urllib.request
import urllib.error
import json
import time
import random


POLITE_DELAY_SEC = 0.4


def fetch_ngram_timeseries(
    word: str,
    year_start: int,
    year_end: int,
    corpus: int,
    smoothing: int = 0,
    case_insensitive: bool = False,
    timeout: int = 30,
):
    params = {
        "content": word,
        "year_start": str(year_start),
        "year_end": str(year_end),
        "corpus": str(corpus),
        "smoothing": str(smoothing),
    }

    if case_insensitive:
        params["case_insensitive"] = "on"

    url = "https://books.google.com/ngrams/json?" + urllib.parse.urlencode(params)

    max_retries = 6
    backoff_base = 1.0

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")

            data = json.loads(raw)

            if not data:
                return []

            ts = data[0].get("timeseries", [])

            if not isinstance(ts, list):
                return []

            return ts

        except urllib.error.HTTPError as he:
            if he.code == 429:
                wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                time.sleep(wait)
                continue
            raise

        except urllib.error.URLError:
            wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
            time.sleep(wait)
            continue

    raise RuntimeError(f"Failed to fetch data for '{word}'.")


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


def parse_manual_words(text: str):
    if not text:
        return []

    raw_words = []

    for line in text.replace(",", "\n").splitlines():
        word = line.strip()
        if word:
            raw_words.append(word)

    return unique_words(raw_words)


def unique_words(words):
    out = []
    seen = set()

    for w in words:
        w = str(w).strip()
        if not w:
            continue

        key = w.lower()
        if key not in seen:
            seen.add(key)
            out.append(w)

    return out


def get_ngram_data_ui():
    return ui.div(
        ui.div("Get Ngram Data", class_="page-title"),

        ui.p(
            "Enter words manually or upload a TXT/Excel file. "
            "The app downloads raw relative frequencies from Google Ngram. "
            "Optionally, values can be converted to words per million.",
            class_="muted"
        ),

        ui.layout_sidebar(
            ui.sidebar(
                ui.input_text_area(
                    "manual_words",
                    "Type words manually",
                    placeholder="Example:\nlove\nwar\nfreedom",
                    rows=6
                ),

                ui.input_file(
                    "word_file",
                    "Or upload TXT / Excel file with words",
                    accept=[".txt", ".xlsx", ".xls"],
                    multiple=False
                ),

                ui.input_numeric("year_start", "Start year", value=1901, min=1500, max=2019),
                ui.input_numeric("year_end", "End year", value=2000, min=1500, max=2019),

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

                ui.input_numeric("smoothing", "Smoothing", value=0, min=0, max=50),
                ui.input_checkbox("case_insensitive", "Case insensitive", value=False),

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
            ),

            ui.div(
                ui.output_text("ngram_status"),
                ui.output_data_frame("ngram_table"),
                class_="card"
            )
        )
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

        return unique_words(words)

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
        smoothing = int(input.smoothing())
        case_insensitive = bool(input.case_insensitive())
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
                    smoothing=smoothing,
                    case_insensitive=case_insensitive,
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

        ngram_df.set(df)

        shared["uploaded_df"] = df
        shared["uploaded_years"] = years
        shared["uploaded_scale"] = scale

        choices = sorted(df["word"].dropna().unique().tolist())

        try:
            ui.update_select(
                "selected_word",
                choices=choices,
                selected=choices[0] if choices else None
            )
        except Exception:
            pass

        status_text.set(
            f"Downloaded {len(df)} words for years {year_start}–{year_end}. "
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

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="ngram_data")

            meta = pd.DataFrame({
                "setting": [
                    "scale",
                    "note",
                    "corpus",
                    "smoothing",
                    "case_insensitive",
                    "year_start",
                    "year_end",
                ],
                "value": [
                    scale,
                    note,
                    input.corpus(),
                    input.smoothing(),
                    input.case_insensitive(),
                    input.year_start(),
                    input.year_end(),
                ]
            })

            meta.to_excel(writer, index=False, sheet_name="meta")

        return path