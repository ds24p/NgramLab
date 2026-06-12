# NGRAM LAB

*A workspace for exploring Google Ngram data and cross-corpus word trends.*

---

# Overview

**NGRAM LAB** is an interactive Python-based application for exploring, visualizing, and comparing word frequency trajectories across multiple historical text corpora.

The application was designed for research workflows involving:

- Google Ngram datasets
- corpus comparison
- diachronic language analysis
- psychological and cultural trend analysis
- synonym and inflection exploration
- trajectory-based statistical analysis

The tool combines:

- interactive visualizations
- statistical summaries
- AUC (Area Under the Curve) analysis
- correlation analysis
- cross-corpus comparisons
- exportable research outputs

---

# Main Features

## 1. Google Ngram Data Retrieval

- Download word trajectories directly from Google Ngram
- Support for multiple corpora:
  - English
  - American English
  - British English
  - English Fiction
  - German
  - Italian
- Adjustable smoothing
- Case-insensitive search option
- Multi-word comparisons

---

  ## 2. Explorer

        Interactive analysis environment for uploaded datasets.

        Includes:

        - trajectory plots
        - indexed comparisons
        - AUC calculations
        - segmented trend analysis
        - peak year detection
        - pairwise correlations
        - correlation heatmaps
        - z-score normalization
        - summary statistics

        Users can compare multiple words simultaneously and explore long-term frequency changes over time.

        ---

  ## 3. Synonyms Explorer

        Allows exploration of semantically related words.

        Features include:

        - synonym group analysis
        - mean trajectory computation
        - group-level AUC calculations
        - comparison of synonym trajectories
        - visualization of conceptual trends instead of individual lexical items

        This functionality was inspired by methodological recommendations regarding improved reliability of Google Ngram studies through synonym usage.

        ---

  ## 4. Inflections Explorer

        Morphological expansion utilities for:

        - inflections
        - related forms
        - derivational forms
        - lemma-based variants

        Supports exploratory linguistic analysis and broader lexical coverage.

        ---

  ## 5. Cross-Corpus Analysis

        Compare multiple corpora simultaneously.

        Supported workflows include:

        - uploading multiple Excel datasets
        - comparing AUC values across corpora
        - computing Pearson/Spearman correlations
        - ranking trajectories
        - identifying shared-year overlaps
        - statistical testing between corpora

        The analysis pipeline supports:

        - Welch t-tests
        - Mann–Whitney U tests
        - Shapiro–Wilk normality tests

        ---

  ## 6. Excel Export

        Generate structured Excel reports containing:

        - AUC tables
        - rankings
        - pairwise differences
        - correlation matrices
        - metadata
        - statistical summaries
        - trajectory comparison results

        ---

  # Data Format

        Input datasets should follow a simple matrix structure:

        | word | 1900 | 1901 | 1902 | ... |
        |------|------|------|------|------|
        | love | 12.3 | 12.1 | 11.8 | ... |
        | war  | 8.2  | 8.6  | 9.1  | ... |

        Requirements:

        - first column = word
        - remaining columns = years
        - values = word frequencies
        - Excel format (`.xlsx`)

        ---

  # Technologies Used

      ## Core Stack

        - Python
        - Shiny for Python
        - Pandas
        - NumPy
        - SciPy
        - Plotly
        - OpenPyXL

        ## Additional Libraries

        - Matplotlib
        - shinywidgets
        - requests
        - urllib

        ---

        # Statistical Methods

        ## Area Under the Curve (AUC)

        NGRAM LAB computes word trajectory magnitude using trapezoidal integration:

        ```math
        AUC = \int_{t_0}^{t_n} f(t)\,dt
        ```

        This allows comparison of long-term word prevalence across corpora.

        ---

        ## Correlation Analysis

        Supported:

        - Pearson correlation
        - Spearman correlation
        - trajectory similarity analysis

        ---

        ## Standardization

        The application supports:

        - z-score normalization
        - indexed trajectories
        - shared-year filtering
        - exclusion of zero-year overlaps

        These procedures improve comparability between corpora of different scales.

        ---

        # Research Motivation

        Google Ngram data has become increasingly popular in:

        - digital humanities
        - psychology
        - linguistics
        - cultural analytics
        - computational social science

        However, historical corpora present several methodological challenges:

        - changing corpus sizes
        - OCR artifacts
        - semantic ambiguity
        - dominance of high-frequency words
        - inconsistent coverage over time

        NGRAM LAB was created to provide a transparent and reproducible environment for addressing these issues through interactive analysis tools and standardized workflows.

        ---

        # Related Research

        The project was influenced by:

        - Michel et al. (2011), *Quantitative Analysis of Culture Using Millions of Digitized Books*
        - Younes & Reips (2019), *Guideline for improving the reliability of Google Ngram studies*
        - research on corpus validation and psychological trend analysis

        ---

        # Example Workflow

        1. Upload or retrieve word trajectories
        2. Select words or synonym groups
        3. Explore trajectories interactively
        4. Compute AUC statistics
        5. Compare corpora
        6. Export results to Excel

        ---

        # Project Status

        NGRAM LAB is an actively evolving research and educational project developed in the context of corpus-based trend analysis and methodological validation studies.

        ---

        # Author

        **Dorota Siciak**  
        University of Konstanz — iScience Group
