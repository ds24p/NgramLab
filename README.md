# NGRAM LAB

**A workspace for exploring Google Ngram data, cross-corpus trends, synonyms, and inflections.**

NGRAM LAB is an interactive research tool built with **Python Shiny** for exploring historical word-frequency trajectories across multiple text corpora. It supports Google Ngram data retrieval, corpus comparison, statistical analysis, and exportable research outputs.

---

## Features

### Google Ngram Retrieval

- Direct access to Google Ngram trajectories
- Multiple corpora support:
  - English
  - American English
  - British English
  - English Fiction
  - German
  - Italian
- Case-insensitive search
- Multi-word comparison
- Adjustable smoothing

### Explorer

Interactive environment for trajectory analysis.

**Includes:**

- Trajectory plots
- Indexed comparisons
- AUC calculations
- Segmented trend analysis
- Peak-year detection
- Correlation analysis
- Correlation heatmaps
- Z-score normalization
- Summary statistics

### Synonyms

Analyze groups of semantically related words instead of single lexical items.

**Features:**

- Synonym group analysis
- Mean trajectory computation
- Group-level AUC calculations
- Concept-level trend visualization

This functionality follows methodological recommendations for improving the reliability of Google Ngram studies.

### Inflections

Explore:

- Inflected forms
- Derivational variants
- Related word forms
- Lemma-based expansions

### Cross-Corpus Analysis

Compare trajectories across multiple corpora.

**Supported analyses:**

- AUC comparison
- Pearson correlation
- Spearman correlation
- Shared-year overlap analysis
- Trajectory ranking
- Statistical testing

**Statistical tests:**

- Welch's t-test
- Mann–Whitney U test
- Shapiro–Wilk normality test

### Excel Export

Generate structured Excel reports containing:

- AUC tables
- Rankings
- Correlation matrices
- Statistical summaries
- Metadata
- Trajectory comparison results

---

## Data Format

Input files should be provided as Excel spreadsheets (`.xlsx`).

| word | 1900 | 1901 | 1902 |
|------|------|------|------|
| love | 12.3 | 12.1 | 11.8 |
| war  | 8.2  | 8.6  | 9.1  |

**Requirements**

- First column: word
- Remaining columns: years
- Values: word frequencies
- File format: `.xlsx`

---

## Technology Stack

### Core

- Python
- Shiny for Python
- Pandas
- NumPy
- SciPy
- Plotly
- OpenPyXL

### Additional Libraries

- Matplotlib
- shinywidgets
- requests
- urllib

---

## Statistical Methods

### Area Under the Curve (AUC)

NGRAM LAB estimates long-term word prevalence using trapezoidal integration:

```math
AUC = \int_{t_0}^{t_n} f(t)\,dt
```

### Correlation Analysis

- Pearson correlation
- Spearman correlation
- Trajectory similarity analysis

### Standardization

- Z-score normalization
- Indexed trajectories
- Shared-year filtering
- Exclusion of zero-overlap years

These procedures improve comparability between corpora with different scales and coverage.

---

## Research Motivation

Google Ngram data is widely used in:

- Digital humanities
- Psychology
- Linguistics
- Cultural analytics
- Computational social science

However, historical corpora present methodological challenges such as:

- Changing corpus sizes
- OCR artifacts
- Semantic ambiguity
- Dominance of high-frequency words
- Uneven historical coverage

NGRAM LAB provides a transparent and reproducible environment for addressing these issues through interactive analysis and standardized workflows.

---

## Related Research

- Michel et al. (2011), *Quantitative Analysis of Culture Using Millions of Digitized Books*
- Younes & Reips (2019), *Guideline for Improving the Reliability of Google Ngram Studies*
- Research on corpus validation and psychological trend analysis

---

## Example Workflow

1. Retrieve or upload trajectories
2. Select words, synonym groups, or inflections
3. Explore trends interactively
4. Compute AUC statistics
5. Compare corpora
6. Export results

---

## Project Status

🚧 Active development

NGRAM LAB is an ongoing research and educational project developed at the intersection of corpus linguistics, digital humanities, psychology, and computational social science.

---

## Author

**Dorota Siciak**  
Doctoral Researcher  
University of Konstanz – iScience Group
