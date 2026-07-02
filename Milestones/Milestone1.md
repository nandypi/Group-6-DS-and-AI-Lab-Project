# **Data Science and AI Lab**

### **T2 - 2026**

# **FinQuery: An AI-powered, Stock-Specific Public Update Analyzer (PUA) for Indian Capital Markets**

## **Milestone-1**

**Submitted by:**

**Team 06**  
	Akbar Ali \- 23f1002997  
	Gurram Sai Sri Ram Hruthik \- 22f3001648  
	NandanReddy Parnapalli \- 22f3002857  
	Shubham Gattani \- 21f3002082  
	Shubhashish Biswas \- 21f1001460

---

# **1. Introduction**

Indian listed companies regularly publish annual reports, quarterly results, exchange filings, investor presentations, regulatory disclosures, and earnings call transcripts through platforms such as the National Stock Exchange (NSE), Bombay Stock Exchange (BSE), and company investor relations portals. These documents contain valuable information regarding financial performance, business strategy, risks, corporate governance, and future outlook. Although publicly available, they are often lengthy, technical, and spread across multiple reporting periods, making them difficult for retail investors to interpret efficiently.

Existing brokerage and financial information platforms provide easy access to these disclosures but primarily function as repositories of information. Investors still need to manually navigate multiple reports to understand changes in business strategy, management priorities, or risk factors over time. This motivates the development of an intelligent document analysis system capable of retrieving relevant information from multiple disclosures and generating evidence-grounded responses to user queries for any selected listed company.

---

# **2. Problem Definition**

## **2.1 Problem Statement**

Retail investors have access to the same public financial disclosures as institutional investors; however, extracting meaningful insights from multiple reports remains a challenging and time-consuming task.

While existing platforms provide company filings, financial statements, and announcements, they generally do not support semantic search or reasoning across multiple documents. Consequently, users cannot easily answer questions that require information from several annual reports or identify how company strategies, risks, and management commentary have evolved over time.

This project proposes the development of a **Retrieval-Augmented Generation (RAG)** system capable of retrieving relevant information from multiple public disclosures of a **user-selected listed company** and generating evidence-grounded answers to user queries.

---

## **2.2 Scope and Boundaries**

### **In Scope**

* Analysis of publicly available financial disclosures of a user-selected listed company.
* Annual Reports & Quarterly Results.
* News Aggregators.
* Investor Presentations / Broker Reports.
* SEBI Circulars.
* Earnings Call Transcripts (where publicly available).
* Semantic document retrieval.
* Question answering and summarization using Retrieval-Augmented Generation.
* Streamlit-based demonstration interface.

### **Out of Scope**

* Simultaneous multi-company comparison or market-wide analysis.
* Stock price prediction.
* Investment recommendation or portfolio management.

---

## **2.3 Stakeholders**

The proposed system is expected to benefit the following stakeholders:

* Retail investors seeking quicker understanding of company disclosures.
* Students learning financial statement analysis.
* Academic researchers working on financial document intelligence.
* Financial analysts requiring efficient retrieval of information from historical reports.
* Developers and researchers exploring domain-specific RAG systems.

---

## **2.4 Project Objectives**

### **Primary Objectives**

* Develop a document processing pipeline for company financial disclosures.
* Build a semantic retrieval system using vector embeddings.
* Develop a Retrieval-Augmented Generation (RAG) pipeline for question answering and summarization.
* Enable multi-document queries across multiple reporting periods for a selected company.
* Evaluate retrieval effectiveness, answer faithfulness, and summarization quality.
* Deploy a functional web application using Streamlit.

### **Secondary Objectives**

* Integrate real-time financial news to provide context-aware responses alongside company disclosures.
* Investigate the impact of domain-specific fine-tuning on the retrieval and generation pipeline (subject to time and computational resources).

### **Research Objective**

To investigate whether a domain-specific Retrieval-Augmented Generation pipeline improves understanding of publicly available corporate disclosures by enabling evidence-grounded question answering and cross-document reasoning compared with conventional keyword-based document search.

---

# **3. Literature Review & Existing Solutions**

## **3.1 Existing Industry Solutions**

### **Trading Platforms (Zerodha, Groww, and Dhan)**

Trading platforms provide company announcements, exchange filings, financial statements, and corporate actions through their investment platforms.

**Strengths**

* Easy access to company disclosures.
* Well-organized financial information.
* Integrated with investment platforms.

**Limitations**

* No semantic search.
* No natural language question answering.
* No reasoning across multiple reports.
* Limited contextual analysis.

---

### **Screeners (Screener, Trendlyne, Tickertape)**

Financial screening platforms provide company financial statements, ratios, historical performance, and downloadable annual reports.

**Strengths**

* Comprehensive financial metrics.
* Historical company data.
* Easy report access.

**Limitations**

* Primarily keyword-based exploration.
* No semantic document retrieval.
* No AI-assisted analysis across reports.

---

### **Commercial LLMs (ChatGPT, Claude, Gemini)**

Modern Large Language Models (LLMs) can summarize uploaded reports and answer financial questions.

**Strengths**

* Strong language understanding.
* High-quality summarization.
* Conversational interaction.

**Limitations**

* Generic financial understanding.
* No persistent company-specific document repository.
* Limited support for querying multiple reports simultaneously.
* Responses depend on uploaded context and may not consistently provide evidence-backed answers.

---

## **3.2 Academic Literature Review**

Recent research demonstrates that Retrieval-Augmented Generation improves factual accuracy by grounding language model responses in retrieved documents instead of relying solely on model parameters. Dense embedding models and vector databases enable semantic retrieval, allowing documents to be searched based on meaning rather than exact keyword matches.

Document chunking strategies have also been shown to significantly influence retrieval quality by preserving contextual information while improving retrieval precision. In addition, modern embedding models such as BGE and E5 consistently outperform traditional keyword-based search techniques on semantic retrieval benchmarks.

Although these approaches have shown promising results across general document collections, relatively little work has focused on applying RAG systems to Indian corporate disclosures and evaluating their effectiveness for multi-document financial reasoning.

---

# **4. Gap Analysis**

## **4.1 Analysis of Current Approaches and Proposed Approach**

| Existing Solution                           | Strengths                                         | Limitations                                    | Proposed Approach                                                              |
| ------------------------------------------- | ------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------ |
| Trading Platforms (Zerodha, Groww, Dhan)    | Company filings and announcements                 | No semantic search or multi-document reasoning | Evidence-grounded question answering over multiple company reports             |
| Screeners (Screener, Trendlyne, Tickertape) | Financial ratios and historical statements        | Keyword-based exploration                      | Semantic retrieval using vector embeddings                                     |
| Commercial LLMs                             | Strong summarization and conversational abilities | Limited document persistence and grounding     | Dedicated RAG pipeline over a curated document corpus for the selected company |
| Traditional Search                          | Fast keyword matching                             | Cannot understand semantic similarity          | Context-aware retrieval based on embeddings                                    |

---

## **4.2 Identified Research Gap**

Existing financial platforms primarily focus on presenting financial data and individual reports, while commercial LLMs operate on user-provided context without maintaining a dedicated knowledge base of company disclosures.

None of these solutions specifically support:

* Cross-document reasoning across multiple annual reports.
* Longitudinal analysis of management commentary and business strategy.
* Evidence-grounded answers linked directly to source documents.
* Semantic retrieval over a curated corpus of disclosures for a user-selected listed company.

This project addresses these gaps by combining semantic retrieval with Retrieval-Augmented Generation to enable grounded question answering over multiple years of publicly available corporate reports.

---

# **5. Performance Benchmarks and Evaluation Criteria**

The proposed system will be evaluated using commonly accepted metrics for retrieval and text generation.

| Component          | Evaluation Metrics                                                |
| ------------------ | ----------------------------------------------------------------- |
| Retrieval          | Precision@k, Recall@k (Optional)                                  |
| Summarization      | ROUGE, BERTScore (Optional)                                       |
| Question Answering | Answer Relevance, Completeness (manual + LLM-assisted evaluation) |
| Faithfulness       | Hallucination Rate, Source Attribution                            |
| System Performance | Retrieval Latency, Response Time                                  |

The system will also be compared against a **keyword-based document search baseline** to evaluate whether semantic retrieval improves answer relevance, factual grounding, and overall user experience.
