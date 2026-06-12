from pathlib import Path

from shiny import App, reactive, render, ui

from pages.get_ngram_data import get_ngram_data_server, get_ngram_data_ui
from pages.explorer import explorer_server, explorer_ui
from pages.cross_corpus import cross_corpus_server, cross_corpus_ui
from pages.synonyms_explorer import synonyms_explorer_server, synonyms_explorer_ui
from pages.inflections_explorer import (
    inflections_explorer_server,
    inflections_explorer_ui,
)
from pages.compare_english_corpora import (
    get_compare_english_corpora_server,
    get_compare_english_corpora_ui,
)


TAB_DESCRIPTIONS = {
    "Ngram Data Fetcher": "Download Google Ngram data or upload word-year files.",
    "Explorer": "Explore word trajectories, AUC values, peaks and trends.",
    "Compare Corpora": "Compare English Google Ngram corpora.",
    "Cross-Corpus Analysis": "Compare uploaded corpora with shared years and AUC metrics.",
    "Synonyms": "Analyze synonym groups and concept-level trajectories.",
    "Inflections": "Generate and inspect inflected or related word forms.",
}

ROUTES = [
    {
        "path": "/fetcher",
        "label": "Ngram Data Fetcher",
        "value": "fetcher",
        "ui": get_ngram_data_ui,
    },
    {
        "path": "/explorer",
        "label": "Explorer",
        "value": "explorer",
        "ui": explorer_ui,
    },
    {
        "path": "/compare-corpora",
        "label": "Compare Corpora",
        "value": "compare-corpora",
        "ui": get_compare_english_corpora_ui,
    },
    {
        "path": "/cross-corpus",
        "label": "Cross-Corpus Analysis",
        "value": "cross-corpus",
        "ui": cross_corpus_ui,
    },
    {
        "path": "/synonyms",
        "label": "Synonyms",
        "value": "synonyms",
        "ui": synonyms_explorer_ui,
    },
    {
        "path": "/inflections",
        "label": "Inflections",
        "value": "inflections",
        "ui": inflections_explorer_ui,
    },
]

ROUTE_BY_PATH = {route["path"]: route for route in ROUTES}
ROUTE_ALIASES = {
    "": "/fetcher",
    "/": "/fetcher",
    "/ngram-data": "/fetcher",
    "/ngram-data-fetcher": "/fetcher",
    "/compare": "/compare-corpora",
    "/cross-corpus-analysis": "/cross-corpus",
}

APP_SHARED_DATA = {
    "uploaded_df": None,
    "uploaded_years": [],
    "uploaded_scale": None,
}


def normalize_route_path(path):
    if not path:
        return "/fetcher"

    path = "/" + str(path).strip("/")
    path = ROUTE_ALIASES.get(path, path)

    if path not in ROUTE_BY_PATH:
        return "/fetcher"

    return path


def route_for_request(request):
    url = getattr(request, "url", None)
    path = getattr(url, "path", "/fetcher")
    return ROUTE_BY_PATH[normalize_route_path(path)]


def common_head():
    return (
        ui.include_css(Path(__file__).parent / "www" / "styles.css"),
        ui.tags.script(
            """
            document.addEventListener("DOMContentLoaded", function () {
                const mobileNavToggle = document.getElementById("mobile_nav_toggle");
                const mobileNavBreakpoint = 1080;
                document.body.classList.remove("mobile-nav-open");
                const routePaths = new Set([
                    "/fetcher",
                    "/explorer",
                    "/compare-corpora",
                    "/cross-corpus",
                    "/synonyms",
                    "/inflections"
                ]);
                const routeAliases = {
                    "/": "/fetcher",
                    "/ngram-data": "/fetcher",
                    "/ngram-data-fetcher": "/fetcher",
                    "/compare": "/compare-corpora",
                    "/cross-corpus-analysis": "/cross-corpus"
                };
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
                    document.querySelectorAll(".route-nav .nav-link").forEach(function (tab) {
                        const label = tab.textContent.trim();
                        const description = tab.dataset.description || tabDescriptions[label];

                        if (!description) return;

                        tab.removeAttribute("title");

                        tab.addEventListener("mouseenter", function () {
                            tooltip.innerHTML = "<strong>" + label + "</strong>" + description;

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

                function normalizeClientRoute(route) {
                    route = "/" + String(route || "").replace(/^#?\\/?/, "").replace(/\\/+$/, "");

                    if (route === "/") {
                        return "/fetcher";
                    }

                    route = routeAliases[route] || route;

                    return routePaths.has(route) ? route : "/fetcher";
                }

                function routeFromHash() {
                    const hash = window.location.hash || "#/fetcher";
                    return normalizeClientRoute(hash.replace(/^#/, ""));
                }

                function syncRoute() {
                    const route = routeFromHash();

                    document.querySelectorAll(".route-nav .nav-link").forEach(function (tab) {
                        const isActive = tab.dataset.route === route;
                        tab.classList.toggle("active", isActive);
                    });

                    if (window.Shiny && window.Shiny.setInputValue) {
                        window.Shiny.setInputValue(
                            "active_route",
                            route,
                            { priority: "event" }
                        );
                    }

                    setMobileNavOpen(false);
                }

                function setMobileNavOpen(isOpen) {
                    document.body.classList.toggle("mobile-nav-open", isOpen);

                    if (mobileNavToggle) {
                        mobileNavToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
                        mobileNavToggle.setAttribute(
                            "aria-label",
                            isOpen ? "Close navigation menu" : "Open navigation menu"
                        );
                    }
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

                    document.querySelectorAll(".route-nav .nav-link").forEach(function (tab) {
                        const label = tab.textContent.trim();
                        const item = tab.closest("li");

                        if (label === "Synonyms" || label === "Inflections") {
                            if (item) item.style.display = newHere ? "none" : "";
                        }
                    });

                    const active = document.querySelector(".route-nav .nav-link.active");
                    if (active) {
                        const activeLabel = active.textContent.trim();
                        if (newHere && (activeLabel === "Synonyms" || activeLabel === "Inflections")) {
                            window.location.hash = "#/fetcher";
                            syncRoute();
                        }
                    }
                }

                decorateTabs();
                window.addEventListener("hashchange", syncRoute);

                if (mobileNavToggle) {
                    mobileNavToggle.addEventListener("click", function (event) {
                        event.preventDefault();
                        event.stopPropagation();
                        setMobileNavOpen(!document.body.classList.contains("mobile-nav-open"));
                    });
                }

                if (!window.location.hash) {
                    window.history.replaceState(null, "", "#/fetcher");
                }

                document.addEventListener("click", function (event) {
                    const target = event.target;
                    if (!target) return;

                    if (target.id === "show_app_info" || target.closest("#show_app_info")) {
                        setInfoButtonActive(true);
                        window.setTimeout(syncInfoButtonState, 800);
                    }

                    const routeLink = target.closest(".route-nav .nav-link");

                    if (routeLink) {
                        setMobileNavOpen(false);
                    }

                    if (
                        window.innerWidth <= mobileNavBreakpoint &&
                        document.body.classList.contains("mobile-nav-open") &&
                        !target.closest(".route-nav") &&
                        !target.closest("#mobile_nav_toggle")
                    ) {
                        setMobileNavOpen(false);
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

                window.addEventListener("resize", function () {
                    if (window.innerWidth > mobileNavBreakpoint) {
                        setMobileNavOpen(false);
                    }
                });

                syncInfoButtonState();
                syncRoute();
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
    )


def top_tools_ui():
    return (
        ui.div(class_="mobile-topbar", **{"aria-hidden": "true"}),
        ui.div(
            ui.tags.details(
                ui.tags.summary("⚙"),
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
                    ui.a(
                        "iScience",
                        href="https://iscience.uni-konstanz.de/",
                        target="_blank",
                    ),
                    ui.a(
                        "University of Konstanz",
                        href="https://www.uni-konstanz.de/",
                        target="_blank",
                    ),
                    ui.a(
                        "About author",
                        href="https://ds24p.github.io/personal_website/",
                        target="_blank",
                    ),
                    ui.a("Related papers", href="#"),
                    class_="dropdown-card",
                ),
                class_="uni-dropdown",
            ),
            class_="top-right-uni",
        ),
        ui.tags.button(
            ui.tags.span(class_="mobile-nav-line"),
            ui.tags.span(class_="mobile-nav-line"),
            ui.tags.span(class_="mobile-nav-line"),
            type="button",
            id="mobile_nav_toggle",
            class_="mobile-nav-toggle",
            **{
                "aria-label": "Open navigation menu",
                "aria-expanded": "false",
            },
        ),
    )


def app_header_ui():
    return (
        ui.div(
            ui.div(
                ui.div("NGRAM LAB", class_="main-title"),
                ui.img(src="logo.png", class_="app-logo"),
                class_="brand-lockup",
            ),
            ui.div(
                "A workspace for exploring Google Ngram data and cross-corpus language trends",
                class_="subtitle",
            ),
            class_="main-header",
        ),
        ui.panel_conditional(
            "input.user_mode === 'New here'",
            ui.div(
                ui.h3("New here? Start with this workflow"),
                ui.p("1. Use Ngram Data Fetcher to download or upload word-frequency data."),
                ui.p("2. Go to Explorer to inspect trajectories, peaks, trends and AUC values."),
                ui.p("3. Use Compare Corpora or Cross-Corpus Analysis when you want to compare datasets."),
                ui.p("Tip: each page includes a New here guidance box with step-by-step instructions and option explanations."),
                class_="guide-box",
            ),
        ),
    )


def navigation_ui():
    links = []

    for route in ROUTES:
        links.append(
            ui.tags.li(
                ui.a(
                    route["label"],
                    href=f"#{route['path']}",
                    class_="nav-link",
                    **{
                        "data-route": route["path"],
                        "data-value": route["label"],
                        "data-description": TAB_DESCRIPTIONS[route["label"]],
                    },
                ),
                class_="nav-item",
            )
        )

    return ui.tags.ul(
        *links,
        class_="nav nav-tabs route-nav",
        id="main_navigation",
    )


def app_ui(request):
    return ui.page_fluid(
        *common_head(),
        *top_tools_ui(),
        *app_header_ui(),
        navigation_ui(),
        ui.output_ui("route_content"),
        ui.div(
            "© NGRAM LAB Dorota Siciak, iScience 2026",
            class_="footer-note",
        ),
    )


def server(input_, output, session):
    shared = APP_SHARED_DATA

    def active_route():
        try:
            route_path = input_.active_route()
        except Exception:
            route_path = "/fetcher"

        return ROUTE_BY_PATH[normalize_route_path(route_path)]

    @output
    @render.ui
    def route_content():
        route = active_route()
        route_ui = (
            route["ui"](shared)
            if route["value"] == "explorer"
            else route["ui"]()
        )

        return ui.div(
            route_ui,
            class_="route-page",
            **{"data-route": route["value"]},
        )

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
                        ui.p("If you are new, click the settings icon in the top-left corner and switch to New here mode to see extra step-by-step guidance on every page."),
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
                        ui.h4("Page-by-Page Guide"),
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
                        ui.p("Each analysis page supports downloadable Excel output so you can continue work outside the app."),
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
        shared,
    )

    cross_corpus_server(input_, output, session, shared)
    synonyms_explorer_server(input_, output, session, shared)
    inflections_explorer_server(input_, output, session, shared)


app = App(
    app_ui,
    server,
    static_assets=Path(__file__).parent / "www",
)


if __name__ == "__main__":
    app.run(port=50817)
