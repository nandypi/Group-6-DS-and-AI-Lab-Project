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
| **Akbar Ali** | Explored vector databases such as Qdrant and ChromaDB and models for efficient embedding storage and retrieval. Built a pipeline to generate OpenAI text-embedding-3-small embeddings and store them in a vector database. Implemented top-3 chunk retrieval to support the project demo. Designed and implemented the retrieval layer of a finance RAG chatbot by evaluating vector databases, implementing semantic top-k retrieval and context construction, and validating the complete retrieval pipeline for accurate LLM-powered question answering. |


---

## Milestone 4

| Team Member | Contribution |
|-------------|--------------|
| **Shubham Gattani** | I improved the RAG system by adding an optional BGE cross-encoder reranking feature with separate scoring for metadata and document content. Also made both retrieval modes work independently, with or without reranking. I also added detailed latency logging to measure the time taken by each pipeline stage. I created benchmark workflows to compare retrieval performance and saved the results in separate CSV files. In addition, we set up a RAGAS evaluation workspace, generated reference answers, prepared evaluation files, and completed RAGAS scoring for all 50 no-reranking questions to measure the system's answer quality and retrieval performance. |
| **Gurram Sai Sri Ram Hruthik** | Prepared a benchmark dataset comprising 50 evaluation questions for assessing the RAG system. Explored and implemented HyDE (Hypothetical Document Embeddings) as an alternative retrieval strategy for the RAG system. Prepared the Milestone 4 presentation in accordance with the specified project requirements. |
| **Shubhashish Biswas** |Made a version / alternative on the evaluation module (using RAGAS) with 30 eval questions.⁠Reviewed the overall application for code stability and structure alignment to usage of suggested parts (e.g. RAGAS, hyde, re-ranking) |
| **NandanReddy Parnapalli** | Contributed to deployment planning by exploring application deployment strategies and preparing the project for deployment. Reviewed the project documentation and implementation, provided feedback during discussions, and verified the Milestone 4 deliverables before submission. |
| **Akbar Ali** | Explored BM25 lexical retrieval and evaluated its performance against the existing vector retrieval approach in ChromaDB. Investigated exact vector search as an alternative to HNSW for our relatively small document corpus, prioritizing retrieval accuracy over approximate nearest-neighbor search.Implemented a hybrid retrieval pipeline (BM25 + exact vector search) to combine lexical and semantic retrieval, aiming to improve answer quality and retrieval accuracy for finance-related queries. |



---

## Milestone 5

| Team Member | Contribution |
|-------------|--------------|
| **Shubham Gattani** | I led the Milestone 5 work on improving the RAG pipeline for long NSE and Infosys IR documents. I replaced estimated token counts with actual `text-embedding-3-small` tokenizer counts, created section-aware 1,500-2,500 token chunks with a 3,000-token hard cap, and built prompt v2 for cleaner investor-focused knowledge extraction. I also customized the Infosys IR prompt for table-heavy financial documents, regenerated embeddings for 1,877 updated Markdown files, and benchmarked retrieval using Chroma, BGE reranking, and GPU-based weight sweeps. This work made the corpus cleaner, retrieval units smaller, and evaluation more rigorous. |
| **Gurram Sai Sri Ram Hruthik** | Built a pipeline that retrieves relevant documents using only their metadata, and extended it with a re-ranking step to improve retrieval quality. Set up the RAGAS evaluation framework to measure how accurately and faithfully the system answers questions. Performed qualitative analysis to identify successful cases and failure patterns in the pipeline's outputs. Also created the Milestone 5 presentation. |
| **Shubhashish Biswas** | Provided an evaluation set of questions with expected answers, and drove actual evaluation of the obtained answers in comparison with them. ⁠Drove a part of the qualitative evaluation from the business user perspective. |
| **NandanReddy Parnapalli** | Supported deployment readiness by evaluating different deployment approaches and helping prepare the application for release. Examined the project's documentation and implementation, shared constructive input during team discussions, and validated the Milestone 5 deliverables to ensure they met requirements prior to submission. |
| **Akbar Ali** | Assisted in preparing the project for production by assessing suitable deployment methods and ensuring deployment readiness. Performed a thorough review of the application's implementation and supporting documentation, contributed recommendations during technical discussions, and completed a final quality check of the Milestone 5 deliverables before they were submitted. |

---

## Milestone 6

*To be updated.*
