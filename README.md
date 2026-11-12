# Detection and Temporal Evolution of AI-Generated Scientific Text (2015-2025)

## 1. Scientific Paper Collection

In this first stage, we collected and validated a corpus of **13,325 scientific papers** spanning 11 publication years (2015 to 2025) across 4 premier conferences in Artificial Intelligence and Natural Language Processing.

### Official Collection Sources

Papers were obtained exclusively from official open-access repositories:
* **NeurIPS:** Harvested from the official [NeurIPS Proceedings](https://proceedings.neurips.cc/) repository (2015 to 2024) and [OpenReview](https://openreview.net/) for recent years.
* **ACL:** Extracted from the [ACL Anthology](https://aclanthology.org/), the official digital library for natural language processing research.
* **ICML:** Gathered from the annual volumes of the [Proceedings of Machine Learning Research (PMLR)](https://proceedings.mlr.press/).
* **ICLR:** Collected via the [OpenReview API](https://openreview.net/) (2018 to 2025) and [arXiv](https://arxiv.org/) filtered by submission date for inaugural editions (2015 to 2017).

### Sampling and Balancing Strategy

Sampling was structured across 44 strata (4 conferences $\times$ 11 years) divided into two temporal horizons:

1. **Pre-2020 Period ($\le 2019$):** Represents the historical human baseline prior to modern conversational LLMs.
   * **AI Seeds (`seed_discarded`):** 1,500 human abstracts used to condition synthetic generation in the downstream phase. Original texts are strictly excluded from classifier training to prevent information leakage.
   * **Human Ground Truth (`human_ground_truth`):** 1,500 human papers reserved for the supervised modeling split (label 0). Within each individual stratum, the number of seeds strictly equals the number of training papers ($N_{\text{seed}} = N_{\text{human}}$), shielding the classifier against spurious publication year or venue correlations.
   * **Temporal Blind Control (`human_temporal_blind`):** 2,462 additional historical human papers reserved to audit false positive rates during a timeframe with zero expected AI incidence.
2. **Post-2020 Period ($\ge 2020$):** A total of **7,863 unlabeled papers** (`longitudinal_unlabeled`), preserved in full to maximize sample density and statistical power when measuring year-over-year AI adoption.

### Collection Engineering

* **In-Memory Stream Processing:** PDF downloads run in memory buffers (`io.BytesIO`) and are parsed directly using PyMuPDF, extracting exclusively Abstract, Introduction, and Conclusion without persisting heavy PDF binaries to disk.
* **Text Quality Filtering:** English language validation and minimum word count enforcement (Abstract $\ge 50$, Introduction $\ge 200$, Conclusion $\ge 50$).
* **Resilience:** Requests guarded by exponential backoff with jitter and atomic line-by-line JSONL streaming, allowing immediate resumption without redownloading.
* **Deduplication:** SHA-256 hash validation over paper identifiers and URLs, ensuring 100% unique records.

### Quantitative Summary Tables

#### Collected Papers by Conference and Year

| Conference | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | $\le 2019$ | $\ge 2020$ | Total |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **NeurIPS** | 293 | 380 | 419 | 466 | 480 | 379 | 379 | 381 | 386 | 388 | 48 | **2,038** | **1,961** | **3,999** |
| **ACL** | 160 | 209 | 175 | 223 | 426 | 340 | 323 | 321 | 352 | 347 | 370 | **1,193** | **2,053** | **3,246** |
| **ICML** | 211 | 248 | 335 | 410 | 440 | 362 | 365 | 361 | 373 | 378 | 106 | **1,644** | **1,945** | **3,589** |
| **ICLR** | 40 | 69 | 105 | 168 | 205 | 200 | 317 | 320 | 346 | 357 | 364 | **587** | **1,904** | **2,491** |
| **TOTAL** | **704** | **906** | **1,034** | **1,267** | **1,551** | **1,281** | **1,384** | **1,383** | **1,457** | **1,470** | **888** | **5,462** | **7,863** | **13,325** |

#### Distribution by Timeframe and Provenance Type

| Timeframe | Provenance Group (`provenance_type`) | Supervised Label | Count | Purpose in Study |
| :--- | :--- | :---: | :---: | :--- |
| **Pre-2020 ($\le 2019$)** | `seed_discarded` | `None` | 1,500 | Real human abstracts used to condition LLM synthetic generation; discarded from training. |
| **Pre-2020 ($\le 2019$)** | `human_ground_truth` | `0` (Human) | 1,500 | Balanced human component for supervised classifier training and validation. |
| **Pre-2020 ($\le 2019$)** | `human_temporal_blind` | `0` (Human) | 2,462 | Historical blind control group to audit false positive rates prior to public LLM availability. |
| **Post-2020 ($\ge 2020$)** | `longitudinal_unlabeled` | `None` (Unlabeled) | 7,863 | Contemporary longitudinal time series for inference and yearly AI prevalence tracking. |
| **Pre-2020 ($\le 2019$)** (AI Mirror) | `synthetic_ai` | `1` (AI) | 1,461 | Synthetic papers generated via `Qwen/Qwen2.5-7B-Instruct` from seeds; positive class in supervised modeling. |
| **Global Total** | | | **14,786** | Consolidated corpus (13,325 collected papers + 1,461 AI-generated synthetic papers). |

---

## 2. Specialized Text Preprocessing

When detecting machine-generated scientific text using neural models, non-linguistic structural tokens introduce shortcut learning vulnerabilities, causing classifiers to memorize superficial layout patterns instead of genuine prose style [1, 2, 4]. Stage 2 runs a deterministic sanitation and masking pipeline over all extracted sections.

### Processing Steps

1. **Comprehensive Dehyphenation:** Reconstructs hyphenated line-wrap breaks across columns and ASCII or Unicode hyphens (`\b(\w+)\s*[-‐‑⁃]\s*\n\s*(\w+)\b`).
2. **Unicode Normalization (NFKD + NFKC) and Diacritic Stripping:** Canonical decomposition to dismantle typographic ligatures (`fi`, `fl`, `ff`, `ffi`), ASCII control character purging (`\x00-\x1f`), and isolated accent stripping (`´`, `` ` ``, `ˇ`) for clean reconstruction of author names [2].
3. **Section Boundary Truncation and Leaked Text Purging:** Automated detection and removal of reference lists (`References`, `Bibliography`, `Works Cited`), appendices and proofs (`Appendix`, `Supplementary Material`, `Proofs`), and institutional disclosures (`Impact Statement`, `Broader Impacts`, `Checklist`). In introductions, text is truncated strictly at the boundary of Section 2 or subsequent headers (e.g., `2. Informal statement of the result`, `Related Work`, `Background`).
4. **Pseudocode and Structured Algorithm Removal:** Removal of floating pseudocode algorithm blocks (`Algorithm 1: ... 1: Input: ... 7: until meet stopping criterion`), while preserving in-line prose discussions.
5. **Purging Affiliations, Author Emails, and Footnote URLs:** Complete removal of authorship footnotes (`equal contribution`, `work done while`, `corresponding author`), author email listings, and footnote lines containing numbered hyperlinks to prevent human contact shortcuts.
6. **Multiline Caption Purging:** Complete excision of figure and table caption blocks (`Figure X:`, `Table X:`) swept into column extraction streams.
7. **Editorial Metadata and Running Header Removal:** Purging of proceeding and conference footers (`JMLR: W&CP`, `PMLR`, copyright notices), lone page numbers, and running paper titles repeated at the top of pages.
8. **Footnote Index Detachment:** Stripping superscript numeric footnote indices attached to word endings before punctuation (`available3` $\rightarrow$ `available`, `toolkit1` $\rightarrow$ `toolkit`) without corrupting valid technical tokens such as `arg1` or `arg2`.
9. **Multi-Stage Canonical Shortcut Masking:** Replacement of narrative textual citations (e.g., "Cunha et al. (2020)", "Chen and Manning (2014)"), typographic and punctuation variants (`et. al`, `et.al.`, `etal.`), authors with attached superscript digits (`4Nallapati et al.`), OCR-fragmented names (`Saatc i et al.`, `Heikkil a et al.`), orphan opening-bracket citations caused by footnote cutoffs (`et al., 2006; ...)`), parenthetical citations (e.g., "(Devlin et al., 2019)"), numeric citations, and alphanumeric bracket keys with the canonical `[CITE]` token [4] (preserving continuous mathematical intervals such as `[0, 1]`), collapsing adjacent citations separated by semicolons (`[CITE] ; [CITE]` $\rightarrow$ `[CITE]`).
10. **Advanced Math and Optimization Masking:** Replacement of LaTeX display blocks, inline expressions (`$...$`), optimization operators (`arg min`, `arg max`), plain text equations (`Ax + Bz = c`, `ρ > 0`), Greek letters, and Unicode mathematical symbols with the canonical `[MATH]` token.
11. **Case-Insensitive Masking of URLs, DOIs, Naked Domains, and Broken Protocol Reconciliation:** Pre-separation of word or digit prefixes attached to protocols (`start1https://` $\rightarrow$ `start1 https://`), reconciliation of protocols split by column wrapping (`https: //`, `http : //`, `https : / /` $\rightarrow$ `https://`), comprehensive link and DOI identifier detection (`10.\d{4,9}/\S+`), naked repository and database domains (`github.com/...`, `en.wikipedia.org/...`, `wordnet.princeton.edu`), orphan scheme purging (`http:`, `https:`, `(https:`, `'http(s)://...'`) while preserving legitimate technical prose tokens (e.g., "HTTP traffic"), elimination of preceding numeric footnote anchors, and collapsing consecutive `[URL]` tokens into a single marker.
12. **Bullet Point Standardization:** Normalization of bullet glyphs (`•`, `*`, `▪`) into uniform hyphens `- `.
13. **Intra-Paragraph Line Unwrapping and Structural Preservation:** Conversion of physical column line breaks into continuous spaces within paragraphs, with strict preservation of double paragraph breaks (`\n\n`) and bulleted list items (`- `).

### Command Line Execution

The pipeline operates via a parameterized CLI (`src.preprocessing`), supporting both standard human corpus processing and scientific parity preprocessing for AI-generated articles:

```bash
# Standard execution (Stage 2: collected corpus preprocessing)
python3 -m src.preprocessing

# Parity execution (Stage 3.5: synthetic corpus preprocessing)
python3 -m src.preprocessing -i data/raw/synthetic_ai.jsonl -o data/processed/synthetic_corpus.jsonl
```

### Algorithms and Libraries

* **`unicodedata` (Python Standard Library):** Canonical NFKC Normalization (Unicode Standard Annex #15), executing compatibility decomposition followed by canonical composition to remove typographic font artifacts.
* **`re` (Python Standard Library):** Deterministic finite automaton of compiled regular expressions running single-pass $O(N)$ document scanning and substitution.
* **`json` (Python Standard Library):** Atomic line-by-line streaming without RAM overhead.

---

## 3. Synthetic Generation and Scientific Parity Preprocessing

To enable supervised detector training, pre-2020 human papers are paired with synthetic scientific papers generated by state-of-the-art open language models.

### Two-Stage Generation Architecture

1. **Technical Fact Extraction (Prompt 1):** From the 1,500 raw discarded human seeds in `data/raw/collected_corpus.jsonl` (`provenance_type: 'seed_discarded'`), the open-source model `Qwen/Qwen2.5-7B-Instruct` extracts the core technical challenge, formal mathematical formulations (when present), prior literature with exact citation markers paired with paraphrased summaries, and empirical findings, ignoring PDF extraction artifacts.
2. **Synthetic Scientific Drafting (Prompt 2):** Based exclusively on the factual summary, the model drafts three complete sections (Abstract, Introduction, and Conclusion) in natural academic prose, matching human word-count targets and replicating extracted citations (author-year or numeric) without verbatim source copying.
3. **Discarding Human Seed Text:** Original texts of the seeds are permanently excluded from classifier training to prevent topic or lexical leakage.

### Official Generation Prompts

#### Prompt 1: Technical Fact Extraction

* **System Prompt:**
  ```text
  You are an expert scientific analyst specializing in machine learning and computational linguistics. Your task is to analyze the provided raw paper sections and extract their core technical facts into a concise, factual JSON structure. Silently normalize PDF extraction artifacts (such as broken line-wrap hyphens or ligatures) and ignore non-prose noise (figure/table captions, conference headers or years, author emails, footnote markers, pseudocode listings, and any leaked reference lists or downstream sections). Do not include introductory filler, conversational pleasantries, or stylistic evaluations.
  ```

* **User Prompt Template:**
  ```text
  Extract the core technical substance from the raw scientific paper sections below into a structured JSON object.

  [INPUT SECTIONS]
  Title: {title}
  Abstract: {abstract}
  Introduction: {introduction}
  Conclusion: {conclusion}

  [OUTPUT FORMAT]
  Output strictly a valid JSON object matching this schema (exclude paper-level metadata such as venue names, publication years of this paper, author affiliations, or figure/table numbers):
  {
    "problem_statement": "The core research question and technical challenge addressed.",
    "core_methodology": "The key proposed model, theoretical framework, and formal mechanisms (include equations and variable notations in LaTeX $...$ only if mathematical expressions or formal symbols appear in the source text).",
    "empirical_findings": "The quantitative benchmarks, experimental evidence, datasets, and verified results.",
    "related_work_and_baselines": "All cited prior works, foundational claims, and baseline methods from the text, pairing each exact citation marker as written (whether author-year such as Author et al. (Year) / (Author and Author, Year), or numeric brackets such as [1], [2, 5]) with a concise paraphrased summary (in your own words, not verbatim prose) of the specific claim, method, or finding that citation supports.",
    "resources_and_urls": "Any public code repository links, dataset URLs, or project artifacts explicitly mentioned in the prose (excluding author emails or publisher footers).",
    "main_conclusions": "The concluding takeaways, practical implications, and future research avenues."
  }
  ```

#### Prompt 2: Synthetic Scientific Drafting

* **System Prompt:**
  ```text
  You are an expert AI researcher drafting a peer-reviewed academic conference paper in machine learning or computational linguistics. Using strictly the provided technical facts, write three complete, formal, and authoritative scientific paper sections: Abstract, Introduction, and Conclusion.
  Maintain natural academic prose, clear paragraph transitions, and varied sentence structure typical of published peer-reviewed papers. Strictly respect the requested word-count target for each section without padding or truncating prematurely. Never include venue names, author details, figure/table numbers (e.g., Figure 1, Table 2), or PDF formatting artifacts. Output strictly a valid JSON object containing the exact keys "abstract", "introduction", and "conclusion".
  ```

* **User Prompt Template:**
  ```text
  Using exclusively the technical facts provided below, write a new, complete, and formal academic paper comprising an Abstract, Introduction, and Conclusion.

  [TECHNICAL FACTS]
  Problem: {problem_statement}
  Methodology & Math: {core_methodology}
  Prior Literature & Baselines: {related_work_and_baselines}
  Findings: {empirical_findings}
  Resources & URLs: {resources_and_urls}
  Conclusions: {main_conclusions}

  [SECTION REQUIREMENTS]
  1. abstract: A dense, self-contained summary strictly within 130 to 170 words (target ~145 words) framing the problem, the proposed approach, key technical mechanisms, and principal empirical findings.
  2. introduction: A comprehensive introduction strictly within 550 to 750 words (target ~600 words, developed across 4 to 6 substantial paragraphs) contextualizing the domain, motivating and formalizing the problem, and actively grounding background claims in Prior Literature & Baselines. Replicate the exact citation markers provided in Prior Literature & Baselines alongside the paraphrased claims they support: preserve nominal author-year style when provided (mixing narrative, e.g., Author et al. (Year), and parenthetical, e.g., (Author et al., Year)), and replicate the exact numeric bracket citations (e.g., [1], [2, 5]) when numeric citations are provided. Never invent author names, years, or citation numbers not present in the facts. Explain the proposed methodology clearly (using inline LaTeX $...$ only when mathematical formulations are present in the facts), mention resource or repository links if provided, and conclude the introduction in cohesive academic prose synthesizing the paper's main findings and contributions without forcing a templated bulleted list.
  3. conclusion: A formal closing section strictly within 180 to 250 words (target ~210 words, 1 to 2 substantial paragraphs) synthesizing the main findings, noting limitations or scope boundaries, and outlining future directions.

  [OUTPUT FORMAT]
  Output strictly a valid JSON object:
  {
    "abstract": "...",
    "introduction": "...",
    "conclusion": "..."
  }
  ```

### Scientific Parity Preprocessing

The raw generated file (`data/raw/synthetic_ai.jsonl`) passes locally through the exact same deterministic preprocessing pipeline applied to human papers (`src.preprocessing`), producing the corpus `data/processed/synthetic_corpus.jsonl` with 1,461 articles labeled as class 1 (AI).

* **Identical Shielding:** Complete neutralization of formulas (`[MATH]`), citations (`[CITE]`), and links (`[URL]`), preventing classifiers from learning spurious layout shortcuts.
* **Metadata Recovery:** Reconstitution of conference venue, publication year, and authors from the original seed to enable balanced stratified cross-validation.

---

## 4. Execution and Experimentation Notebooks

Interactive experiments, large-scale hardware-accelerated generation, and the end-to-end modeling and inference pipeline are organized in [`src/notebooks/`](src/notebooks/):

1. **[`qwen_synthetic_generation.ipynb`](src/notebooks/qwen_synthetic_generation.ipynb):**  
   Parameterized notebook for batch generation of mirrored synthetic scientific papers. Designed for dual Nvidia Tesla T4 GPU clusters (Kaggle or Google Colab), orchestrating `Qwen/Qwen2.5-7B-Instruct` via `vLLM` with 4-bit AWQ quantization to fit within VRAM constraints. Executes two-stage factual extraction and stores raw records in `data/raw/synthetic_ai.jsonl`.

2. **[`end_to_end_pipeline.ipynb`](src/notebooks/end_to_end_pipeline.ipynb):**  
   Core notebook and primary project deliverable. Unifies all empirical stages into a single executable workflow:
   * **Section 1 (Setup & Environment):** Dependency installation, deterministic random seeds (`seed = 42`), and GPU hardware accelerator inspection.
   * **Section 2 (Data Acquisition & Corpus Overview):** Dynamic path resolution (supporting local execution or automated download of compressed `.jsonl.gz` releases directly from GitHub when running on Google Colab), partition loading, and construction of the 2,961-paper modeling split (1,500 human ground truth and 1,461 synthetic papers).
   * **Section 3 (Linguistic Characterization):** Contrastive quantitative analysis between human and AI writing (distribution table across conferences and years, section length boxplots for Abstract, Introduction, and Conclusion with statistical hypothesis tests, density curves for sentential burstiness, lexical density, and syntactic complexity, part-of-speech POS tagging with acronym glossaries, syntactic structures, document incidence n-grams, and longitudinal diachronic evolution of excess vocabulary across all 13,325 collected papers).
   * **Section 4 (Supervised Modeling & Optuna Tuning):** Supervised classification with 5-fold cross-validation grouped by paper identifier and Bayesian hyperparameter optimization with Optuna.
   * **Section 5 (Longitudinal Temporal Analysis):** Infiltration evaluation across the 2015-2025 historical timeline using Rogan-Gladen statistical prevalence adjustment and bootstrap confidence intervals.

---

## 5. Repository Structure

```text
Projeto-Final-APPNL/
├── data/
│   ├── processed/          # Processed datasets and compressed releases (.jsonl.gz)
│   └── raw/                # Raw collected data and raw LLM generation outputs
├── src/
│   ├── coleta/             # Modular web scraping and API collection scripts
│   │   ├── collector.py
│   │   └── utils.py
│   ├── notebooks/          # Interactive Jupyter experiment and modeling notebooks
│   │   ├── end_to_end_pipeline.ipynb
│   │   └── qwen_synthetic_generation.ipynb
│   └── preprocessing/      # 13-stage deterministic text sanitization pipeline
│       ├── __init__.py
│       ├── __main__.py
│       └── preprocessor.py
├── .gitignore              # Exclusion rules for heavy binaries, artifacts, and caches
├── AGENTS.md               # Engineering manual and governance operational guide
└── README.md               # Project overview and reproduction guide
```

---

## References

[1] Kobak, D., González-Márquez, R., Horvát, E. A., & Kapoor, S. (2024). Delving into ChatGPT usage in academic writing through excess vocabulary. *arXiv preprint arXiv:2406.07016*.

[2] Liang, W., Izzo, M. A., Zhang, Y., Leppert, H., Hou, H., Cheng, X., Zou, J., et al. (2024). Monitoring AI-modified text in the scientific literature. *arXiv preprint arXiv:2403.07183*.

[3] Sadasivan, V. S., Kumar, A., Balasubramanian, S., Wang, W., & Feizi, S. (2023). Can AI-Generated Text be Reliably Detected? *arXiv preprint arXiv:2303.11156*.

[4] Tang, X., et al. (2024). AIGT-SignalBench: Disentangling Shortcut Cues from Generalizable Signals in AI-Generated Text Detection. *Findings of the Association for Computational Linguistics (ACL)*.
