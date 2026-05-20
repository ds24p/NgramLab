from pathlib import Path
from shiny import App, ui, reactive

from pages.get_ngram_data import get_ngram_data_ui, get_ngram_data_server
from pages.explorer import explorer_ui, explorer_server
from pages.cross_corpus import cross_corpus_ui, cross_corpus_server
from pages.synonyms_explorer import synonyms_explorer_ui, synonyms_explorer_server
from pages.inflections_explorer import inflections_explorer_ui, inflections_explorer_server
from pages.compare_english_corpora import (
    get_compare_english_corpora_ui,
    get_compare_english_corpora_server,
)


app_ui = ui.page_fluid(
    ui.tags.style(
        """
        :root {
            --bg: #f7f5f0;
            --ink: #1f2933;
            --muted: #6b7280;
            --violet: #7c3aed;
            --violet-dark: #4c1d95;
            --violet-soft: #f4f0ff;
            --violet-border: #d8c8ff;
            --yellow: #facc15;
            --black: #111827;
            --border: #ded7c8;
        }

        body {
            background: var(--bg);
            color: var(--ink);
            font-family: Inter, Arial, sans-serif;
        }

        .top-left-tools {
            position: absolute;
            top: 18px;
            left: 22px;
            z-index: 1000;
            display: flex;
            align-items: flex-start;
            gap: 10px;
        }

        .top-right-uni {
            position: absolute;
            top: 12px;
            right: 22px;
            z-index: 1000;
        }

        .tool-dropdown,
        .uni-dropdown {
            position: relative;
        }

        .tool-dropdown summary,
        .uni-dropdown summary,
        .info-button {
            list-style: none;
            cursor: pointer;
            background: white;
            border: 1px solid var(--border);
            border-radius: 999px;
            box-shadow: 0 8px 20px rgba(31, 41, 51, 0.08);
            color: #b7a7df;
            font-size: 15px;
            font-family: Inter, Arial, sans-serif;
            font-weight: 600;
            transition: all 0.18s ease;
        }

        .tool-dropdown summary {
            width: 64px;
            height: 64px;
            padding: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 30px;
        }

        .tool-dropdown summary:hover,
        .uni-dropdown summary:hover,
        .info-button:hover {
            transform: translateY(-1px);
            box-shadow: 0 12px 26px rgba(76, 29, 149, 0.14);
            border-color: var(--violet-border);
            background: var(--violet-soft);
        }

        .tool-dropdown summary::-webkit-details-marker,
        .uni-dropdown summary::-webkit-details-marker {
            display: none;
        }

        .info-button {
            width: 64px;
            height: 64px;
            padding: 0;
            font-size: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .dropdown-card {
            position: absolute;
            top: 78px;
            left: 0;
            min-width: 260px;
            background: white;
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 20px 22px;
            box-shadow: 0 16px 36px rgba(31, 41, 51, 0.16);
            font-family: Inter, Arial, sans-serif;
            color: var(--black);
        }

        .dropdown-card label,
        .dropdown-card .control-label,
        .dropdown-card .form-check-label {
            font-family: Inter, Arial, sans-serif !important;
            color: var(--black);
            font-size: 16px;
            font-weight: 600;
        }

        .dropdown-card .control-label {
            font-size: 18px;
            font-weight: 800;
            margin-bottom: 10px;
        }

        .dropdown-card input[type="radio"] {
            accent-color: var(--violet-dark);
        }

        .uni-dropdown .dropdown-card {
            right: 0;
            left: auto;
            min-width: 260px;
            top: 82px;
        }

        .dropdown-card a {
            display: block;
            color: var(--black);
            text-decoration: none;
            font-weight: 700;
            padding: 8px 6px;
            border-radius: 10px;
            font-family: Inter, Arial, sans-serif;
        }

        .dropdown-card a:hover {
            background: var(--violet-soft);
            color: var(--violet-dark);
        }

        .uni-logo {
            height: 78px;
            width: auto;
            max-width: 260px;
            object-fit: contain;
            cursor: pointer;
            display: block;
        }

        .uni-dropdown summary {
            padding: 8px 16px;
            min-width: 210px;
            height: 92px;
            display: flex;
            align-items: center;
            justify-content: center;
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
            color: var(--ink);
        }

        .subtitle {
                font-size: 15px;
                color: var(--muted);
                margin-bottom: 22px;

                font-style: italic;
                font-family: Georgia, serif;
        }

        .nav-tabs {
            justify-content: center;
            border-bottom: 1px solid var(--border);
            margin-bottom: 24px;
        }

        .nav-tabs .nav-link {
            position: relative;
            color: var(--black);
            font-weight: 700;
            border-radius: 999px;
            margin: 0 4px;
            padding: 8px 16px;
            transition: all 0.18s ease;
            font-family: Inter, Arial, sans-serif;
        }

        .nav-tabs .nav-link:hover {
            background: var(--violet-soft);
            color: var(--violet-dark);
            border-color: var(--violet-border);
        }

        .nav-tabs .nav-link.active {
            background: linear-gradient(135deg, var(--violet-dark), var(--violet));
            color: white;
            border-color: var(--violet-dark);
            box-shadow: 0 8px 22px rgba(124, 58, 237, 0.22);
        }

        .custom-tab-tooltip {
            position: fixed;
            display: none;
            max-width: 280px;
            background: linear-gradient(135deg, #fbf9ff, #f1eaff);
            color: var(--black);
            border: 1px solid var(--violet-border);
            border-radius: 14px;
            padding: 12px 14px;
            box-shadow: 0 14px 28px rgba(76, 29, 149, 0.16);
            font-family: Inter, Arial, sans-serif;
            font-size: 14px;
            line-height: 1.45;
            z-index: 3000;
            pointer-events: none;
        }

        .custom-tab-tooltip strong {
            display: block;
            color: var(--violet-dark);
            font-size: 15px;
            font-weight: 800;
            margin-bottom: 4px;
        }

        .custom-tab-tooltip::after {
            content: "";
            position: absolute;
            bottom: -8px;
            left: 36px;
            width: 14px;
            height: 14px;
            background: #f1eaff;
            border-right: 1px solid var(--violet-border);
            border-bottom: 1px solid var(--violet-border);
            transform: rotate(45deg);
        }

        .card {
            background: white;
            border-radius: 22px;
            padding: 24px;
            box-shadow: 0 12px 28px rgba(31, 41, 51, 0.08);
            border: 1px solid #eee8dc;
            margin-bottom: 18px;
        }

        .guide-box {
            max-width: 900px;
            margin: 0 auto 22px auto;
            background: #fff8db;
            border: 1px solid #f3d86b;
            border-left: 7px solid var(--yellow);
            border-radius: 18px;
            padding: 18px 22px;
            box-shadow: 0 10px 24px rgba(31, 41, 51, 0.06);
            font-family: Inter, Arial, sans-serif;
        }

        .guide-box h3 {
            margin-top: 0;
            color: var(--violet-dark);
            font-weight: 800;
        }

        .page-title {
            font-size: 28px;
            font-weight: 750;
            margin-bottom: 12px;
        }

        .muted {
            color: var(--muted);
        }

        .modal-content {
            border-radius: 22px;
            border: 1px solid var(--border);
            font-family: Inter, Arial, sans-serif;
            box-shadow: 0 22px 50px rgba(31, 41, 51, 0.20);
        }

        .modal-title,
        .modal-content h3 {
            color: var(--violet-dark);
            font-weight: 800;
            font-family: Inter, Arial, sans-serif;
        }

        .modal-content p {
            color: var(--ink);
            font-size: 15px;
            line-height: 1.55;
            font-family: Inter, Arial, sans-serif;
        }

        .modal-footer .btn {
            border-radius: 999px;
            font-family: Inter, Arial, sans-serif;
            font-weight: 700;
        }

        .footer-note {
            text-align: center;
            margin-top: 26px;
            margin-bottom: 12px;

            color: #8b8b95;

            font-size: 14px;
            font-family: Inter, Arial, sans-serif;

            opacity: 0.92;

            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }

        .footer-note::before {
            content: "✦";
            color: #7c3aed;
            font-size: 14px;
        }

        .footer-note::after {
            content: "✦";
            color: #7c3aed;
            font-size: 14px;
        }
        """
    ),

    ui.tags.script(
        """
        document.addEventListener("DOMContentLoaded", function () {
            const tabDescriptions = {
                "Ngram Data Fetcher": "Download Google Ngram data or upload word-year files.",
                "Explorer": "Explore word trajectories, AUC values, peaks and trends.",
                "Compare Corpora": "Compare English Google Ngram corpora.",
                "Cross-Corpus Analysis": "Compare uploaded corpora with shared years and AUC metrics.",
                "Synonyms Explorer": "Analyze synonym groups and concept-level trajectories.",
                "Inflections Explorer": "Generate and inspect inflected or related word forms."
            };

            const tooltip = document.createElement("div");
            tooltip.className = "custom-tab-tooltip";
            document.body.appendChild(tooltip);

            function decorateTabs() {
                document.querySelectorAll(".nav-tabs .nav-link").forEach(function (tab) {
                    const label = tab.textContent.trim();

                    if (!tabDescriptions[label]) return;

                    tab.removeAttribute("title");

                    tab.addEventListener("mouseenter", function () {
                        tooltip.innerHTML = "<strong>" + label + "</strong>" + tabDescriptions[label];

                        const rect = tab.getBoundingClientRect();
                        tooltip.style.display = "block";

                        const tooltipWidth = tooltip.offsetWidth;
                        const left = rect.left + rect.width / 2 - tooltipWidth / 2;
                        const top = rect.top - tooltip.offsetHeight - 14;

                        tooltip.style.left = Math.max(16, left) + "px";
                        tooltip.style.top = Math.max(16, top) + "px";
                    });

                    tab.addEventListener("mouseleave", function () {
                        tooltip.style.display = "none";
                    });
                });
            }

            function updateMode() {
                const selected = document.querySelector("input[name='user_mode']:checked");
                if (!selected) return;

                const newHere = selected.value === "New here";

                document.querySelectorAll(".nav-tabs .nav-link").forEach(function (tab) {
                    const label = tab.textContent.trim();
                    const item = tab.closest("li");

                    if (label === "Synonyms Explorer" || label === "Inflections Explorer") {
                        if (item) item.style.display = newHere ? "none" : "";
                    }
                });

                const active = document.querySelector(".nav-tabs .nav-link.active");
                if (active) {
                    const activeLabel = active.textContent.trim();
                    if (newHere && (activeLabel === "Synonyms Explorer" || activeLabel === "Inflections Explorer")) {
                        const firstTab = document.querySelector(".nav-tabs .nav-link");
                        if (firstTab) firstTab.click();
                    }
                }
            }

            decorateTabs();

            document.addEventListener("change", function (event) {
                if (event.target && event.target.name === "user_mode") {
                    updateMode();
                }
            });

            setTimeout(updateMode, 300);
        });
        """
    ),

    ui.div(
        ui.tags.details(
            ui.tags.summary("⚙️"),
            ui.div(
                ui.input_radio_buttons(
                    "user_mode",
                    "View mode",
                    choices=["New here", "Advanced user"],
                    selected="Advanced user",
                ),
                class_="dropdown-card",
            ),
            class_="tool-dropdown",
        ),
        ui.input_action_button("show_app_info", "?", class_="info-button"),
        class_="top-left-tools",
    ),

    ui.div(
        ui.tags.details(
            ui.tags.summary(
                ui.img(src="uni_konstanz_logo.svg", class_="uni-logo")
            ),
            ui.div(
                ui.a("iScience", href="https://iscience.uni-konstanz.de/", target="_blank"),
                ui.a("University of Konstanz", href="https://www.uni-konstanz.de/", target="_blank"),
                ui.a("About author", href="https://ds24p.github.io/personal_website/", target="_blank"),
                ui.a("Related papers", href="#"),
                class_="dropdown-card",
            ),
            class_="uni-dropdown",
        ),
        class_="top-right-uni",
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

    ui.panel_conditional(
        "input.user_mode === 'New here'",
        ui.div(
            ui.h3("New here? Start with this workflow"),
            ui.p("1. Use Ngram Data Fetcher to download or upload word-frequency data."),
            ui.p("2. Go to Explorer to inspect trajectories, peaks, trends and AUC values."),
            ui.p("3. Use Compare Corpora or Cross-Corpus Analysis when you want to compare datasets."),
            class_="guide-box",
        ),
    ),

    ui.navset_tab(
        ui.nav_panel("Ngram Data Fetcher", get_ngram_data_ui()),
        ui.nav_panel("Explorer", explorer_ui()),
        ui.nav_panel("Compare Corpora", get_compare_english_corpora_ui()),
        ui.nav_panel("Cross-Corpus Analysis", cross_corpus_ui()),
        ui.nav_panel("Synonyms Explorer", synonyms_explorer_ui()),
        ui.nav_panel("Inflections Explorer", inflections_explorer_ui()),
        id="main_navigation"
    ),

    ui.div(
    "© NGRAM LAB Dorota Siciak, iScience 2026",
    class_="footer-note"),
)


def server(input_, output, session):
    shared = {
        "uploaded_df": None,
        "uploaded_years": []
    }

    @reactive.effect
    @reactive.event(input_.show_app_info)
    def _show_app_info():
        ui.modal_show(
            ui.modal(
                ui.h3("How to use NGRAM LAB"),
                ui.p("Use this app to fetch, explore and compare Google Ngram word-frequency data."),
                ui.p("Start with Ngram Data Fetcher if you need to download or upload data."),
                ui.p("Use Explorer for single-dataset word trajectories, AUC values and trend inspection."),
                ui.p("Use Compare Corpora or Cross-Corpus Analysis for corpus-level comparisons."),
                ui.p("Advanced users can also inspect synonym groups and inflected or related word forms."),
                title="Application guide",
                easy_close=True,
                footer=ui.modal_button("Close"),
            )
        )

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