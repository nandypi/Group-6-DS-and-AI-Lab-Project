# **Data Science and AI Lab**

### **T2 - 2026**

# **FinQuery: An AI-powered, Stock-Specific Public Update Analyzer (PUA) for Indian Capital Markets**

## **Milestone-2**

**Submitted by:**

**Team 06**  
	Akbar Ali \- 23f1002997  
	Gurram Sai Sri Ram Hruthik \- 22f3001648  
	NandanReddy Parnapalli \- 22f3002857  
	Shubham Gattani \- 21f3002082  
	Shubhashish Biswas \- 21f1001460

---

# **1. Data Sources**

Pilot company: **Infosys Limited (NSE: INFY)**. Target window: **1 July 2025 – 1 July 2026**, subject to availability per source.

| Source | Collection method | Ownership | Format | Usage constraints |
| --- | --- | --- | --- | --- |
| **NSE corporate announcements** | Programmatic — NSE announcements API scraped per symbol/date range | NSE / Infosys Limited (SEBI LODR disclosures) | JSON metadata + linked PDFs | Public regulatory disclosures; used for non-commercial research; source URL retained for attribution |
| **Infosys IR website** (earnings calls, investor presentations, press conferences) | Manual — downloaded from Infosys investor relations site | Infosys Limited | PDF | Publicly published investor material; research use only |
| **Yahoo Finance news** | Hybrid — `yfinance` script used to discover/shortlist relevant articles; full articles downloaded manually as PDF (many are paywalled) | Respective publishers, aggregated by Yahoo | PDF → Markdown | Public news aggregation; research/demo use, source URL retained |
| **Trendlyne broker/stock reports** | Manual — downloaded from Trendlyne | Trendlyne / brokerage authors (e.g., ICICI Direct) | PDF → Markdown | Publicly available broker reports |

---

# **2. Dataset Description**

## 2.1 Size per source (current corpus)

| Source | Raw units collected | Converted / usable Markdown |
| --- | --- | --- |
| NSE announcement PDFs → Markdown | 492 PDFs converted (`data/nse_files/final/`) | 180 selected into RAG corpus (108 auto-kept + 72 LLM-accepted) |
| Infosys IR site (earnings calls, fact sheets, press releases, press conferences — FY26 Q1–Q4) | 16 PDFs | 16 (`data/infosys_earning_calls_press_conf_fact_sheets_results/`) |
| Yahoo Finance news articles | 6 PDFs | 6 (`data/yfinance/mds/`) |
| Trendlyne broker reports | 5 PDFs | 5 (`data/trendlyne/mds/`) |
| **Total curated Markdown corpus** | | **207 documents** |

## 2.2 Feature distribution — NSE announcement metadata (1-yr sample, n=240)

19 distinct `desc` disclosure categories; top ones:

| Category | Count |
| --- | --- |
| Updates | 134 |
| Disclosure under SEBI Takeover Regulations | 27 |
| Copy of Newspaper Publication | 26 |
| ESOP/ESOS/ESPS | 10 |
| General Updates | 10 |
| Shareholders meeting | 8 |
| Others (13 categories) | 25 |

Attachment size range: 124 KB – ~41 MB (avg ~1.96 MB per PDF). \
Total size ~405 MB (All Markdown Files)

---

# **3. Dataset Quality Assessment**

* **Missing values:** 4 of 20 metadata fields (`bflag`, `csvName`, `old_new`, `orgid`) are 100% null across all 240 records — API artifacts, dropped at ingestion. `desc`, `attchmntText`, `attchmntFile`, `sort_date` are fully populated.
* **Duplicates:** No duplicate `attchmntFile` URLs in the 240-record sample (240 unique). NSE occasionally re-issues the same filing with a hash-suffixed filename (e.g. `PR_02022026.md` vs `PR_02022026_434f4750.md`); these are treated as distinct filings, not deduped, since content can differ.
* **Noise/inconsistency:** `Updates` (134/240, 56%) is a catch-all category mixing transcripts, press releases, and routine notices — this is why classification uses a category rule + keyword rule + LLM content review (§7), not a single pass. Yahoo Finance news JSON has several top-level `null` fields (`title`, `publisher`, `summary`) that actually live under a nested `raw.content` payload — normalized during PDF export.

---

# **4. Dataset Adequacy & Expansion**

The current corpus (single company, ~1 year, 207 curated documents across 4 source types) is adequate to validate the **pipeline end-to-end** but is limited in temporal depth and company breadth for robust RAG evaluation. Planned expansion, since the pipeline is symbol-parameterized:

* Extend NSE history beyond 1 year (an initial multi-year pull is already scoped — 502 attachment links / ~9,235 pages tracked in `metadata/desc_attchmnt_pdf_dict_with_pages.json`).
* Add earnings calls/press material for earlier quarters (currently only FY26 Q1–Q4).
* Add 2–3 more NSE-listed companies to confirm the pipeline generalizes beyond INFY.
* No synthetic documents are used for the knowledge corpus — all sources are real, sourced filings/articles/reports.

---

# **5. Train / Validation / Test Strategy or RAG-specific Chunking Strategy**

This is a RAG knowledge corpus, not a labeled training set, so a conventional train/val/test split does not apply in the usual sense. Instead:

* **Corpus set:** all accepted documents are embedded/indexed — the retrieval knowledge base.
* **Evaluation query set (planned):** held-out question–answer pairs written against specific source documents, created only after the corpus is finalized.
* **Leakage check:** tracked at the **document level** (by `source_url`/filename) — a document used to seed an evaluation question is not also claimed as an "unseen" document in later generalization checks. Chunk-level splitting is avoided since chunks from the same document are highly correlated.
* **Temporal holdout:** once multi-year data is available (§4), the most recent reporting period will be held out from corpus construction to test recency-sensitive queries without those filings having tuned retrieval.
* Chunking Strategy:
* (a) For quarterly reports, structure-aware chunking will be used to benefit the most from its uniform and structured format as pu

---

# **6. Cross-Source Alignment**

Four heterogeneous sources (NSE filings, Infosys IR material, news, broker reports) feed one retrieval index. Alignment across them is established via shared metadata rather than a shared schema:

* **Company symbol** (`INFY`) — constant per corpus, will key multi-company expansion later.
* **Date** — filing/publication date normalized per document, enabling time-ranged and "as of" queries across sources.
* **Document type/family** — each document is tagged with its origin type (NSE filing category, earnings call, press release, news article, broker report) so retrieval can be filtered by type when a query needs it (e.g., "broker view" vs "company disclosure").

No further task-specific alignment (e.g., joint labels) is needed since all sources feed the same retrieval task.

---

# **7. Document Preparation for RAG**

## 7.1 Approach and Pipeline

```text
APPROACH:
We assessed the data for quality, relevance and sufficiency using the following:

	(A) Relevance: We first categorized a small set of the collected documents as HIGH / MID / LOW on relevance, based our domain knowledge and semantic understanding. Based 	on that, we extracted meta-data, designed a relevance-index and used it for classifying the rest of the data. Once done, we ran it on the entire document repository and 	finally used only the documents scoring HIGH / MID on the relevance-index.
	
	(B) Quality: We evaluated 10+ news sources and found many of them filled with noise, irrelevant and even misleading content, despite coming from credible news channels 	(e.g. moneycontrol.com ). We kept such data sources out to ensure quality, and eventually used more credible sources like Yahoo Finance.  
	
	(C) Sufficiency: We collected sufficient volume of reports and updates from NSE, but could get only a few reports from brokerages. Therefore, we widened our consideration 	set of brokerage reports while limiting the NSE updates strictly within one year.
	
Beyond these steps, we aim to improve our data further after looking at the RAG output. To evaluate that, we have selected the RAGAS framework.

PIPLELINE:
NSE metadata (240 records, 1-yr sample)
   -> category + keyword filter (datapreparation/pdf_seperate.py)   -> keep 67 / reject 95 / review 78
Full historical NSE PDFs
   -> Docling PDF->Markdown conversion                               -> 492 files (data/nse_files/final)
   -> same category/keyword rules applied at corpus scale            -> keep 108 / review 115 (data/nse_files/keep, /review)
   -> LLM content review of the review bucket (prompts/review-files-using-codex.txt) -> 72 ACCEPT / 43 REJECT (metadata/processed/review_decisions.json)
   => NSE RAG corpus = 108 (rule-kept) + 72 (LLM-accepted) = 180 documents

Infosys IR PDFs (manual download) -> Docling PDF->Markdown            -> 16 documents
Yahoo Finance articles (yfinance discovery + manual PDF download)     -> ChatGPT summarization to Markdown -> 6 documents
Trendlyne broker reports (manual download)                            -> ChatGPT summarization to Markdown -> 5 documents
```

The NSE keyword filter (`GOOD`/`BAD` word lists checked against `attchmntText`) is defined in `datapreparation/pdf_seperate.py`; documents in ambiguous categories (`Updates`, `General Updates`, `Shareholders meeting`, `Analysts/Institutional Investor Meet/Con. Call Updates`) that match neither list go to `review` for the LLM content pass.

## 7.2 Chunking strategy (planned and analysed)

The following decisions on chunking strategy have been taken:
```text
(A) Section/heading-aware chunking on Markdown structure, with recursive token-bounded sub-chunking (~500–800 tokens, overlap) for long sections, and financial tables chunked separately. Every chunk retains source metadata (URL, doc type, date, page) for citation.
(B) For NSE reports of varying length and context with sufficient volume (200+), semantic chunking will be used.
(C) For structured, uniform and tabulated number-heavy documemts like quarterly reports, structure-aware chunking will be used. 
(D) For earning call and investor presentation (meeting / interview transcripts), semantic chunking will be used, possibly with context enrichment, if possible. 
```
## 7.3 Vector database options (proposed, not yet implemented)

Local, metadata-filterable stores (**FAISS** or **Chroma**) are the leading candidates given the current corpus size and the Streamlit demo scope from Milestone-1; a hosted option (Qdrant/Pinecone) is a fallback if the corpus scales to many companies. Final choice to be validated in Milestone-3.

---

# **8. Preprocessing Steps (Reproducibility)**

| Step | Script / Notebook | Input | Output |
| --- | --- | --- | --- |
| Download NSE filings | `datapreparation/download_data/download_nse_filings.ipynb` | NSE symbol + date range | `data/announcements_metadata-last-year.json` |
| Classify announcements | `datapreparation/pdf_seperate.py` | Announcement metadata JSON | `keep.json` / `reject.json` / `review.json` (`metadata/processed/`) |
| Build reduced file lists | `datapreparation/create_keep_file_list.py` | `keep.json`, `review.json` | `keep-file-list.json`, `review-file-list.json` |
| Convert NSE PDFs to Markdown | `datapreparation/data-preprocessing/NSE_PDFs_Extraction_and_Conversion_to_MD.ipynb` (Docling) | NSE PDFs | `data/nse_files/final/*.md` |
| Rename / sort converted Markdown | `datapreparation/rename_markdown_from_source_url.py`, `datapreparation/copy_markdown_file_lists.py` | `data/nse_files/final/` | `data/nse_files/keep/`, `data/nse_files/review/` |
| LLM content review of review bucket | `prompts/review-files-using-codex.txt` | `data/nse_files/review/*.md` | `metadata/processed/review_decisions.json` |
| Parse Infosys IR material | `datapreparation/data-preprocessing/Earning_calls_and_quarterly_updates_parsing.ipynb` (Docling) | Manually downloaded Infosys IR PDFs | `data/infosys_earning_calls_press_conf_fact_sheets_results/*.md` |
| Collect Yahoo Finance news | `datapreparation/download_data/download_yfinance_articles.ipynb` + manual PDF download + ChatGPT summarization | `INFY.NS` ticker | `data/yfinance/pdfs/`, `data/yfinance/mds/` |
| Collect Trendlyne reports | Manual download + ChatGPT summarization | Trendlyne report pages | `data/trendlyne/pdfs/`, `data/trendlyne/mds/` |

All scripts/notebooks are committed under `datapreparation/`; raw PDFs and their Markdown conversions are committed under `data/`, so the corpus is reproducible without re-scraping.
