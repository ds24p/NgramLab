from pathlib import Path
from shiny import App, ui

from pages.get_ngram_data import get_ngram_data_ui, get_ngram_data_server
from pages.explorer import explorer_ui, explorer_server
from pages.cross_corpus import cross_corpus_ui, cross_corpus_server
from pages.synonyms_explorer import synonyms_explorer_ui, synonyms_explorer_server
from pages.inflections_explorer import inflections_explorer_ui, inflections_explorer_server
from pages.compare_english_corpora import get_compare_english_corpora_ui, get_compare_english_corpora_server



app_ui = ui.page_fluid(
    ui.tags.style(
        """
        body {
            background: #f7f5f0;
            color: #1f2933;
            font-family: Inter, Arial, sans-serif;
        }

        .main-header {
            text-align: center;
            padding-top: 32px;
            padding-bottom: 12px;
        }

        .main-title {
            font-size: 60px;
            font-weight: 800;
            letter-spacing: 6px;
            margin-bottom: 8px;
        }

        .subtitle {
            font-size: 15px;
            color: #6b7280;
            margin-bottom: 22px;
        }

        .nav-tabs {
            justify-content: center;
            border-bottom: 1px solid #d8d2c4;
            margin-bottom: 24px;
        }

        .nav-tabs .nav-link {
            color: #374151;
            font-weight: 600;
            border-radius: 999px;
            margin: 0 4px;
            padding: 8px 16px;
        }

        .nav-tabs .nav-link.active {
            background: #1f2933;
            color: white;
            border-color: #1f2933;
        }

        .card {
            background: white;
            border-radius: 22px;
            padding: 24px;
            box-shadow: 0 12px 28px rgba(31, 41, 51, 0.08);
            border: 1px solid #eee8dc;
            margin-bottom: 18px;
        }

        .page-title {
            font-size: 28px;
            font-weight: 750;
            margin-bottom: 12px;
        }

        .muted {
            color: #6b7280;
        }
        """
    ),

    ui.div(
        ui.div(
            ui.div("NGRAM LAB", class_="main-title"),
            ui.img(src="logo.png", height="200px", style="margin-left: 0px;"),
            style="""
                display: flex;
                justify-content: center;
                align-items: center;
            """
        ),
        ui.div("A workspace for exploring Google Ngram data", class_="subtitle"),
        class_="main-header"
    ),

    ui.navset_tab(
        ui.nav_panel("Ngram Data Fetcher", get_ngram_data_ui()),
        ui.nav_panel("Explorer", explorer_ui()),

        ui.nav_panel(
            "Compare Corpora",
            get_compare_english_corpora_ui()
        ),

        ui.nav_panel("Cross-Corpus Analysis", cross_corpus_ui()),
        ui.nav_panel("Synonyms Explorer", synonyms_explorer_ui()),
        ui.nav_panel("Inflections Explorer", inflections_explorer_ui()),
        id="main_navigation"
    )
)


def server(input_, output, session):
    shared = {
        "uploaded_df": None,
        "uploaded_years": []
    }

    get_ngram_data_server(input_, output, session, shared)
    explorer_server(input_, output, session, shared)
    get_compare_english_corpora_server(
        input_,
        output,
        session,
        shared
    )

    cross_corpus_server(input_, output, session, shared)
    synonyms_explorer_server(input_, output, session, shared)
    inflections_explorer_server(input_, output, session, shared)


app = App(
    app_ui,
    server,
    static_assets=Path(__file__).parent / "www"
)