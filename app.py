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
    ui.include_css(Path(__file__).parent / "www" / "styles.css"),

    ui.tags.script(
        """
        document.addEventListener("DOMContentLoaded", function () {
            const tabDescriptions = {
                "Ngram Data Fetcher": "Download Google Ngram data or upload word-year files.",
                "Explorer": "Explore word trajectories, AUC values, peaks and trends.",
                "Compare Corpora": "Compare English Google Ngram corpora.",
                "Cross-Corpus Analysis": "Compare uploaded corpora with shared years and AUC metrics.",
                "Synonyms": "Analyze synonym groups and concept-level trajectories.",
                "Inflections": "Generate and inspect inflected or related word forms."
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

            function setInfoButtonActive(isActive) {
                const infoButton = document.getElementById("show_app_info");
                if (!infoButton) return;

                if (isActive) {
                    infoButton.classList.add("info-button-active");
                } else {
                    infoButton.classList.remove("info-button-active");
                }
            }

            function isGuideModalOpen() {
                const guideBody = document.querySelector(".guide-modal-body");
                const guideModal = guideBody ? guideBody.closest(".modal") : null;

                return Boolean(
                    guideModal &&
                    (
                        guideModal.classList.contains("show") ||
                        guideModal.style.display === "block"
                    )
                );
            }

            let infoButtonSyncTimer = null;

            function syncInfoButtonState() {
                setInfoButtonActive(isGuideModalOpen());
            }

            function scheduleInfoButtonSync() {
                window.clearTimeout(infoButtonSyncTimer);
                infoButtonSyncTimer = window.setTimeout(syncInfoButtonState, 40);
            }

            function updateMode() {
                const selected = document.querySelector("input[name='user_mode']:checked");
                if (!selected) return;

                const newHere = selected.value === "New here";

                document.querySelectorAll(".nav-tabs .nav-link").forEach(function (tab) {
                    const label = tab.textContent.trim();
                    const item = tab.closest("li");

                    if (label === "Synonyms" || label === "Inflections") {
                        if (item) item.style.display = newHere ? "none" : "";
                    }
                });

                const active = document.querySelector(".nav-tabs .nav-link.active");
                if (active) {
                    const activeLabel = active.textContent.trim();
                    if (newHere && (activeLabel === "Synonyms" || activeLabel === "Inflections")) {
                        const firstTab = document.querySelector(".nav-tabs .nav-link");
                        if (firstTab) firstTab.click();
                    }
                }
            }

            decorateTabs();

            document.addEventListener("click", function (event) {
                const target = event.target;
                if (!target) return;

                if (target.id === "show_app_info" || target.closest("#show_app_info")) {
                    setInfoButtonActive(true);
                    window.setTimeout(syncInfoButtonState, 800);
                }
            });

            document.addEventListener("shown.bs.modal", function () {
                setInfoButtonActive(true);
            });

            document.addEventListener("hidden.bs.modal", function () {
                setInfoButtonActive(false);
            });

            const modalObserver = new MutationObserver(scheduleInfoButtonSync);
            modalObserver.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ["class", "style"],
            });

            document.addEventListener("change", function (event) {
                if (event.target && event.target.name === "user_mode") {
                    updateMode();
                }
            });

            syncInfoButtonState();
            setTimeout(updateMode, 300);
        });
        """
    ),

    ui.tags.script(
        """
        (function () {
            const DATAMUSE_URL = "https://api.datamuse.com/words";

            function sendResponse(payload) {
                if (!window.Shiny || !window.Shiny.setInputValue) return;
                window.Shiny.setInputValue(
                    "client_api_response",
                    JSON.stringify(payload),
                    { priority: "event" }
                );
            }

            function buildUrl(baseUrl, params) {
                const url = new URL(baseUrl);
                Object.entries(params).forEach(function ([key, value]) {
                    if (value !== undefined && value !== null && value !== "") {
                        url.searchParams.set(key, value);
                    }
                });
                return url.toString();
            }

            async function fetchJson(url) {
                const response = await fetch(url, {
                    method: "GET",
                    mode: "cors",
                    cache: "no-store",
                });

                if (!response.ok) {
                    throw new Error("HTTP " + response.status + " for " + url);
                }

                return await response.json();
            }

            async function fetchDatamuseSynonyms(message) {
                const word = String(message.word || "").trim().toLowerCase();

                if (!word) {
                    return { words: [] };
                }

                const data = await fetchJson(buildUrl(DATAMUSE_URL, {
                    rel_syn: word,
                    max: message.max_words || 40,
                }));

                const seen = new Set();
                const words = [word];
                seen.add(word);

                if (Array.isArray(data)) {
                    data.forEach(function (item) {
                        const candidate = String(item.word || "").trim().toLowerCase();
                        if (candidate && !seen.has(candidate)) {
                            seen.add(candidate);
                            words.push(candidate);
                        }
                    });
                }

                return { words: words.slice(0, message.max_words || 40) };
            }

            async function fetchDatamuseInflections(message) {
                const word = String(message.word || "").trim().toLowerCase();

                if (!word) {
                    return { words: [] };
                }

                const maxWords = message.max_words || 40;
                const requests = [
                    { sp: word + "*", max: maxWords },
                    { ml: word, sp: word.charAt(0) + "*", max: maxWords },
                    { rel_trg: word, max: maxWords },
                ];

                const seen = new Set();
                const words = [word];
                seen.add(word);

                for (const params of requests) {
                    const data = await fetchJson(buildUrl(DATAMUSE_URL, params));
                    if (Array.isArray(data)) {
                        data.forEach(function (item) {
                            const candidate = String(item.word || "").trim().toLowerCase();
                            if (candidate && !seen.has(candidate)) {
                                seen.add(candidate);
                                words.push(candidate);
                            }
                        });
                    }
                }

                return { words: words.slice(0, maxWords) };
            }

            async function handleClientApiRequest(message) {
                const base = {
                    request_id: message.request_id,
                    target: message.target,
                    kind: message.kind,
                    meta: message.meta || {},
                };

                try {
                    let data;

                    if (message.kind === "datamuse_synonyms") {
                        data = await fetchDatamuseSynonyms(message);
                    } else if (message.kind === "datamuse_inflections") {
                        data = await fetchDatamuseInflections(message);
                    } else {
                        throw new Error("Unknown client API request kind: " + message.kind);
                    }

                    sendResponse(Object.assign({}, base, data));
                } catch (error) {
                    sendResponse(Object.assign({}, base, {
                        error: error.message || String(error),
                    }));
                }
            }

            function installHandler() {
                if (!window.Shiny || !window.Shiny.addCustomMessageHandler) {
                    window.setTimeout(installHandler, 50);
                    return;
                }

                window.Shiny.addCustomMessageHandler("client_api_request", handleClientApiRequest);
            }

            installHandler();
        })();
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
        ui.div(
            "A workspace for exploring Google Ngram data and cross-corpus language trends",
            class_="subtitle"
        ),
        class_="main-header"
    ),

    ui.panel_conditional(
        "input.user_mode === 'New here'",
        ui.div(
            ui.h3("New here? Start with this workflow"),
            ui.p("1. Use Ngram Data Fetcher to download or upload word-frequency data."),
            ui.p("2. Go to Explorer to inspect trajectories, peaks, trends and AUC values."),
            ui.p("3. Use Compare Corpora or Cross-Corpus Analysis when you want to compare datasets."),
            ui.p("Tip: each tab includes a New here guidance box with step-by-step instructions and option explanations."),
            class_="guide-box",
        ),
    ),

    ui.navset_tab(
        ui.nav_panel("Ngram Data Fetcher", get_ngram_data_ui()),
        ui.nav_panel("Explorer", explorer_ui()),
        ui.nav_panel("Compare Corpora", get_compare_english_corpora_ui()),
        ui.nav_panel("Cross-Corpus Analysis", cross_corpus_ui()),
        ui.nav_panel("Synonyms", synonyms_explorer_ui()),
        ui.nav_panel("Inflections", inflections_explorer_ui()),
        id="main_navigation"
    ),

    ui.div(
        "© NGRAM LAB Dorota Siciak, iScience 2026",
        class_="footer-note"
    ),
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
                ui.div(
                    ui.h3("How to use NGRAM LAB"),
                    ui.div(
                        ui.h4("Getting Started"),
                        ui.p("Use this app to fetch, explore, and compare Google Ngram word-frequency data across words and corpora."),
                        ui.p("If you are new, click the settings icon in the top-left corner and switch to New here mode to see extra step-by-step guidance in every tab."),
                        class_="guide-modal-intro",
                    ),
                    ui.div(
                        ui.h4("Recommended Workflow"),
                        ui.tags.ol(
                            ui.tags.li("Use Ngram Data Fetcher to build or upload your base word-frequency dataset."),
                            ui.tags.li("Go to Explorer to inspect trajectories, trends, AUC, and correlations."),
                            ui.tags.li("Use Compare Corpora or Cross-Corpus Analysis when you want corpus-level validation."),
                        ),
                        class_="guide-modal-section",
                    ),
                    ui.div(
                        ui.h4("Tab-by-Tab Guide"),
                        ui.tags.ul(
                            ui.tags.li("Ngram Data Fetcher: collect clean year-by-year data for selected words."),
                            ui.tags.li("Explorer: run detailed single-dataset visual and statistical analysis."),
                            ui.tags.li("Compare Corpora: compare one word list across English, American, British, and Fiction corpora."),
                            ui.tags.li("Cross-Corpus Analysis: compare multiple uploaded datasets on shared years, including tests and timeseries summaries."),
                            ui.tags.li("Synonyms and Inflections: expand concepts into related forms and compare their historical dynamics."),
                        ),
                        class_="guide-modal-section",
                    ),
                    ui.div(
                        ui.h4("Outputs"),
                        ui.p("Each analysis tab supports downloadable Excel output so you can continue work outside the app."),
                        class_="guide-modal-section",
                    ),
                    class_="guide-modal-body",
                ),
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


if __name__ == "__main__":
    app.run(port=50817)
