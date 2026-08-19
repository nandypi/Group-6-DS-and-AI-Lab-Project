# FinQuery: An AI-powered, Stock-Specific Public Update Analyzer (PUA) for Indian Capital Markets

**Non-Technical Report — Group 6**
*Data Science and AI Lab (T2 - 2026)*

---

## 1. The Problem: Navigating Financial Disclosures Is Not Easy

Every publicly listed company in India is required by law to regularly publish documents that inform investors about its financial health and business activities. These include quarterly earnings reports, analyst transcripts, regulatory filings submitted to the National Stock Exchange (NSE), press releases, and brokerage research reports. For a major company such as Infosys Limited — one of India's largest technology firms — a single financial quarter can generate dozens of such documents, each running to several pages.

In theory, all of this information is freely accessible to anyone who wishes to use it. In practice, the sheer volume and complexity of these disclosures creates a significant barrier for the very audience they are meant to serve: retail investors, students, independent researchers, and financial analysts who may not have the time, resources, or specialist vocabulary to sift through hundreds of pages of corporate documents to find a specific fact or understand a trend.

Existing digital tools address parts of this problem but not all of it. Financial portals and trading applications display standardised financial ratios and price charts. Research aggregators surface analyst ratings and consensus forecasts. Search engines return keyword-matched results that may or may not contain the answer being sought. None of these tools can answer a question such as *"Why is Infosys passing AI-driven productivity gains to clients rather than converting them into margin expansion?"* with a direct, evidence-backed response drawn from the company's own published documents.

This is the gap that FinQuery was designed to address.

---

## 2. What FinQuery Does

FinQuery is an intelligent question-answering system that allows users to ask natural-language questions about a company's financial disclosures and receive precise, evidence-backed answers — as if consulting a research assistant who has read every relevant document and can quote directly from the source.

A user interacting with FinQuery types a question into a web interface. The system reads the question, understands what kind of answer is required, searches across hundreds of documents to locate the most relevant passages, and synthesises a clear, concise response. Every answer is accompanied by citations — references to the exact documents from which the information was drawn — so the user can verify the response or read further.

FinQuery handles two broad categories of questions:

**Numerical questions** ask for specific financial figures. Examples include the company's operating profit margin for a given quarter, the total value of large contracts signed during a specific period, or the rate at which employees voluntarily leave the organisation. For these questions, the system consults a structured database of financial facts extracted directly from company-published quarterly documents. The response is precise and traceable to an exact data point in an official report.

**Descriptive questions** ask for explanations, context, or strategy. Examples include why a company's margins declined in a particular quarter, how it plans to expand in a new market, or what analysts believe about its long-term growth prospects. For these questions, the system searches across the full document corpus — earnings call transcripts, press releases, analyst reports, and regulatory filings — to identify the most relevant passages and compose a coherent, grounded response.

The distinction between these two question types is handled automatically, without any input from the user.

---

## 3. Who It Is For

FinQuery was designed with three primary user groups in mind.

**Retail investors** who hold or are considering holding shares in a company require up-to-date, accurate information to make informed decisions. They may wish to understand what management said about future revenue guidance, whether a recent contract win is material, or how the company performed relative to its own stated targets. FinQuery allows such users to obtain this information directly, without needing to read full earnings call transcripts or navigate dense regulatory filings.

**Students and academic researchers** studying corporate finance, financial reporting, or the application of artificial intelligence to financial analysis may use FinQuery as a research tool. The system's citation mechanism ensures that all retrieved information is traceable to original sources, supporting rigorous academic inquiry.

**Financial analysts and market professionals** who routinely review quarterly disclosures for multiple companies may use FinQuery to accelerate research. The ability to ask precise questions and receive immediate answers with source citations reduces the time required to locate specific data points within large document sets.

---

## 4. How the System Was Built: The Project Journey

FinQuery was developed over six milestones spanning the academic year. Each milestone built upon the previous one, progressively transforming an initial concept into a deployed, functional application.

### Milestone 1 — Defining the Problem

The project began with a structured review of the existing landscape of financial information tools and academic research on intelligent document systems. The team identified the specific gap — the absence of an evidence-grounded question-answering capability over curated corporate disclosures — and established the evaluation criteria that would be used to measure success throughout the project.

### Milestone 2 — Collecting and Curating the Document Corpus

Infosys Limited was selected as the pilot company for the project, given its comprehensive public disclosure record and active investor relations programme. The team collected 492 NSE filings, 16 Infosys investor relations documents, 6 news articles, and 5 brokerage research reports published between July 2025 and July 2026. A substantial proportion of the NSE filings were routine administrative documents with no substantive financial content. A three-stage filtering process — combining rule-based category classification, keyword screening, and AI-assisted content review — reduced the collection to 207 high-quality, information-rich documents. This curated corpus forms the foundation of the system.

### Milestone 3 — Building the Initial System

The team converted all 207 documents from their original PDF format into structured text, preserving tables, headings, and paragraph structure. Each document was further processed by an AI model to remove formatting noise and produce a clean, machine-readable version alongside a concise summary of the document's key topics and likely user questions. An initial version of the question-answering system was assembled and verified end-to-end: a question was submitted, relevant documents were located and retrieved, and an answer was generated.

### Milestone 4 — Improving How the System Finds Relevant Documents

A core challenge in any document question-answering system is *retrieval*: given hundreds of documents, which ones actually contain the answer to a specific question? The team evaluated three different retrieval approaches. The first was a basic similarity search that returned the documents most mathematically similar to the question. The second attempted to improve retrieval by first generating a hypothetical answer and searching for documents similar to that answer. The third applied a more sophisticated relevance-scoring model to re-order results after initial retrieval. While the third approach produced the most accurate results, it was approximately forty times slower than the others — a practical limitation for an interactive system.

### Milestone 5 — A Breakthrough in Retrieval Quality

A significant improvement was achieved by changing what the system searches. Rather than searching the full text of each document, the system was redesigned to search only the structured summaries — the concise topic lists and sample questions generated for each document in Milestone 3. This approach proved far more effective: the proportion of questions for which the correct document was retrieved within the top three results rose from 40% to 74%, while retrieval speed improved by a factor of over ten compared to the most accurate Milestone 4 approach. A detailed analysis revealed that documents from Infosys's own investor relations library — quarterly earnings calls — were the most difficult to retrieve correctly, because four consecutive quarters discuss the same metrics using nearly identical language.

### Milestone 6 — Deployment and the Numeric Fidelity Layer

The final milestone addressed two remaining challenges. The first was the retrieval difficulty for numerical queries. Rather than searching documents for a specific financial figure — a process prone to confusion when the same metric appears across multiple quarters — the system now maintains a separate structured database of over 2,500 individual financial facts extracted from official Infosys quarterly documents. Numerical questions are answered by querying this database directly, delivering exact, verified figures rather than synthesised estimates.

The second development was the deployment of the application as a publicly accessible web service, with a web interface for end users, a secure backend that manages authentication and access control, and a containerised packaging format that allows the system to be launched on any compatible server without manual software installation.

Additionally, the retrieval approach for descriptive questions was further refined by combining two complementary search methods — one that understands the meaning behind a question, and one that matches exact words and phrases — and merging their results. This combination improved the proportion of questions for which the correct document was found within the top three results to 76%, with markedly better performance at broader retrieval windows.

---

## 5. What the System Can Do

The deployed FinQuery system provides the following capabilities:

**Evidence-grounded answers to numerical questions.** Users may ask about any financial metric that Infosys has reported in its official quarterly documents for FY26 — including revenue, operating margin, net profit, earnings per share, headcount, attrition rate, and large-deal contract values. The system returns the precise figure along with the source document from which it was extracted.

**Contextual answers to descriptive questions.** Users may ask open-ended questions about strategy, performance, management commentary, partnerships, market conditions, and analyst assessments. The system retrieves the most relevant passages from across the full document corpus and synthesises a coherent, cited response.

**Automatic question classification.** Users do not need to specify whether their question is numerical or descriptive. The system classifies the question automatically and routes it to the appropriate retrieval and answer-generation process.

**Source citations for every answer.** Every response includes references to the specific documents from which information was drawn, allowing users to verify claims and read the original source.

**Secure, rate-limited access.** The system requires user authentication and enforces a limit on the number of questions that can be submitted per hour, ensuring fair and responsible use.

**Web-based interface.** The application is accessible via any standard web browser. No software installation is required on the user's device.

---

## 6. How Well the System Performs

The system's performance was evaluated across three dimensions using structured benchmark tests.

**Routing accuracy** measures whether the system correctly identifies whether a question is numerical or descriptive and routes it to the appropriate processing pipeline. On a test set of 40 questions, the system achieved perfect routing accuracy — every question was directed to the correct pipeline.

**Numeric accuracy** measures whether the system returns the correct financial figure for questions about specific metrics. On a benchmark of 15 representative numerical questions, the system returned accurate answers — within a 5% margin of the expected value — in every case.

**Retrieval quality** measures whether the correct source document is among the top results returned for descriptive questions, since the accuracy of the final answer depends on whether the relevant passage was retrieved. On a benchmark of 50 descriptive questions, the system retrieved the correct document within the top 3 results for 76% of questions, and within the top 5 results for 86% of questions.

**Answer quality**, assessed independently using an established evaluation framework, showed that generated answers are highly faithful to the source material (approximately 89% of claims in generated answers are directly supported by retrieved documents) and contextually precise (approximately 97% of retrieved passages are relevant to the question asked).

In terms of speed, the system responds to a typical question within approximately 4 to 5 seconds from submission to answer delivery.

---

## 7. Challenges Encountered and How They Were Resolved

The development of FinQuery was not without significant challenges. The following describes the most consequential difficulties and the solutions that were found.

**Distinguishing between quarterly documents.** Infosys publishes four sets of quarterly financial documents each year, all discussing the same metrics — revenue, margin, headcount — in similar language. The initial retrieval system struggled to distinguish between, for example, a Q1 document and a Q3 document when answering a quarter-specific question. This was resolved by creating a structured financial facts database specifically for numerical queries, in which each data point is tagged with the exact reporting period. Numerical queries now bypass open-ended document search entirely and consult this structured record directly.

**Balancing accuracy and speed.** The most accurate retrieval approach evaluated during the project was also the slowest, taking over four minutes per question — entirely impractical for interactive use. The insight that searching structured document summaries rather than full document text could simultaneously improve accuracy and dramatically reduce retrieval time was a pivotal finding that enabled the project to meet both quality and performance requirements.

**Avoiding incorrect financial figures.** In one tested configuration, the system returned a regional financial figure in response to a question about a company-wide metric. The company-wide and regional values for the same metric appeared in the same data source, and the system could not reliably distinguish between them. This was resolved by introducing explicit data quality rules that constrain numerical queries to values within the expected range for each metric, with different range limits applied for company-wide versus segment-level data.

**Reliable deployment.** Deploying the system as a containerised application exposed a technical incompatibility between the software library used for document search and the access restrictions applied to the storage volume. The system attempted to write internal state information even when performing read-only queries — a requirement not evident from the library's documentation. The resolution was to grant write access to the relevant storage volume, which had no effect on data security but allowed the library to function as designed.

---

## 8. Limitations

While the system performs well within its defined scope, several limitations are acknowledged.

**Single company coverage.** FinQuery currently supports queries about Infosys Limited only. The data collection, processing, and indexing pipeline would need to be re-executed to support any other company.

**Fixed document corpus.** The corpus covers July 2025 through July 2026. Questions about events outside this window cannot be answered. Regular updates to the corpus would be required to keep the system current.

**Questions requiring evidence from multiple sources.** The system presents up to three document passages to the answer-generation model for any given question. Questions that can only be answered by combining evidence from four or more distinct documents may receive incomplete answers.

**No user-defined filters.** The current system does not allow users to restrict search to a specific document type (e.g., "search only in earnings call transcripts") or time period. All documents in the corpus are considered for every query.

---

## 9. Future Directions

The current system demonstrates that the core approach — combining structured financial fact retrieval with intelligent document search — is effective for single-company financial Q&A. Several extensions are planned or under consideration.

**Multi-company support** would allow users to query disclosures for any NSE-listed company by parameterising the data collection and processing pipeline. This would significantly expand the system's utility for comparative analysis across companies and sectors.

**Real-time document updates** would enable the system to incorporate new quarterly filings, press releases, and regulatory announcements as they are published, keeping the knowledge base current without manual intervention.

**User-controlled filters** would allow users to constrain queries to specific time periods, document types, or reporting segments, improving precision for targeted research tasks.

**Expanded coverage of document types** could include shareholder letters, sustainability reports, and conference presentations, broadening the scope of questions the system can address.

---

## 10. Conclusion

FinQuery demonstrates that artificial intelligence can be applied to the practical challenge of making corporate financial disclosures more accessible and useful. By combining intelligent document search with a structured financial facts database and a natural-language interface, the system enables users to ask precise questions about a company's financial performance and strategy and receive grounded, cited answers within seconds.

The project progressed from an initial problem definition through data collection, system construction, retrieval optimisation, and production deployment across six milestones. The final system achieves high accuracy on both numerical and descriptive questions, operates within practical speed constraints, and is accessible through a standard web browser without requiring any technical expertise from the user.

The broader ambition of the project is to reduce the information asymmetry between sophisticated institutional investors, who employ dedicated research teams to process corporate disclosures, and retail investors and students, who typically lack such resources. FinQuery represents a step toward that goal: a tool that makes authoritative, source-cited financial information equally accessible to anyone who wishes to use it.
