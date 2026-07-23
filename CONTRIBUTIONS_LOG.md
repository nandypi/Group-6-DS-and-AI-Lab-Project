# Project Contribution Log

This document tracks the individual contributions of each team member throughout the project milestones.

## Team Consent

We, the undersigned team members, confirm that:

- We have actively contributed to the completion of the project milestones.
- We have reviewed the submitted work and verified its contents.
- We consent to the submission of the project milestones for evaluation.
- The contributions listed in this document accurately reflect our individual work.

| Name | Roll No. | Signature |
|------|----------|-----------|
| Shubhashish Biswas | *21f1001460* | *S.B* |
| Gurram Sai Sri Ram Hruthik | *22f3001648* | *G.H* |
| Shubham Gattani | *21f3002082* | *S.G* |
| Akbar Ali | *23f1002997* | *A.A* |
| NandanReddy Parnapalli | *22f3002857* | *N.P* |

---

## Milestone 1 – Problem Definition & Literature Review

| Team Member | Contribution |
|-------------|--------------|
| **Shubhashish Biswas** | Contributed to the problem definition, explored existing solutions, conducted the literature review, provided domain knowledge during discussions, and reviewed the final deliverables. |
| **Gurram Sai Sri Ram Hruthik** | Prepared the Milestone 1 presentation (PPT), explored existing solutions, proofread final document, contributed to the literature review and stakeholder. |
| **NandanReddy Parnapalli** | Created the project repository, configured the GitHub repository for Milestone 1, added collaborators, managed repository access, and completed the required project forms. |
| **Shubham Gattani** | Participated in problem definition discussions, explored existing solutions and analyzed their advantages and limitations, and proofread the project documentation and presentation. |
| **Akbar Ali** | Participated in problem definition discussions, prepared the Milestone 1 document and assited with presentation (PPT), explored existing solutions, and contributed to the literature review. |

---

## Milestone 2

| Team Member | Contribution |
|-------------|--------------|
| **Shubham Gattani** | Analyzed Infosys NSE filings and created metadata-based filtering rules that automated ~40% of document screening. Developed an LLM prompt to classify ambiguous documents into ACCEPT/REJECT categories. Extracted Yahoo Finance articles using the `yfinance` library and performed markdown file categorization, renaming, and preprocessing to support data collection and ingestion.|
| **Gurram Sai Sri Ram Hruthik** | Converted NSE filings, earnings call, and fact sheet PDFs to Markdown using the open-source Docling tool, and completed the Milestone 2 project report. |
| **Shubhashish Biswas** | Included data from Infosys IR, included scripts for data collection from Yt finance, reviewed data veracity and helped with chunking strategy formulation, reviewed readme and ppt |
| **NandanReddy Parnapalli** | Developed filtering logic for NSE documents based on description key words, including data extraction and Markdown conversion for Trendlyne and Yahoo Finance sources. |
| **Akbar Ali** | Explored news aggregation platforms such as Zerodha Pulse and data sources like GDELT to evaluate options for collecting financial news. Generated data-source links and prepared the Milestone 2 ppt. |

---

## Milestone 3

| Team Member | Contribution |
|-------------|--------------|
| **Shubham Gattani** | Led Milestone 3 by preprocessing the complete NSE dataset and categorizing files into keep, reject, and review buckets. Conducted an LLM-assisted review using refined prompts, further classifying documents by length (≤10 pages and >10 pages). Designed prompts for sectioning longer documents, merged adjacent sections using Python scripts, and developed dedicated cleanup prompts to preserve critical facts, tables, and numerical data while improving document quality. |
| **Gurram Sai Sri Ram Hruthik** | Completed knowledge extraction for Infosys IR, earnings calls, and quarterly reports, producing clean, structured Markdown files. Developed knowledge extraction prompts for Yahoo Finance news articles and Trendlyne brokerage reports, generating standardized Markdown outputs. Prepared the Milestone 3 report and presentation. |
| **Shubhashish Biswas** |Collaborated with Shubham and Hruthik on prompt engineering to reduce information loss and improve the reliability of LLM responses. Also explored and evaluated techniques for preserving the structure and context of tabular data within RAG pipelines. |
| **NandanReddy Parnapalli** | Explored local embedding generation using the BGE model with ChromaDB by building a pipeline to create embeddings for the demo documents provided by Shubham, store them in a vector database, and retrieve the top-3 relevant chunks for user queries. Later, migrated to OpenAI embeddings to reduce processing time, simplify the pipeline, and improve collaboration across the team. |
| **Akbar Ali** | Explored vector databases such as Qdrant and ChromaDB for efficient embedding storage and retrieval. Built a pipeline to generate OpenAI text-embedding-3-small embeddings and store them in a vector database. Implemented top-3 chunk retrieval to support the project demo. |


---

## Milestone 4

*To be updated.*

---

## Milestone 5

*To be updated.*

---

## Milestone 6

*To be updated.*
