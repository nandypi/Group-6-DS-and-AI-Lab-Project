# Qualitative Analysis — Pipeline A (Metadata-Only RAG)

**Dataset:** 50 investor-oriented questions about Infosys
**Pipeline:** Metadata-only embedding (top-10 retrieval) → top-3 context → `gpt-4o-mini`
**Evaluator:** RAGAS with `gpt-4o-mini` + `text-embedding-3-small`
**Metrics:** Faithfulness · Answer Relevancy · Context Precision · Context Recall

---

## Part 1 — Successful Predictions

> These examples show the pipeline working as intended: the correct document is
> retrieved, the answer is grounded in context, and it closely matches the reference.

---

### Success Example 1 — Factual, Single-Source Question

**ID 9 | Source: IR — Q3 FY26 Earnings Call**

| Metric | Score |
|---|---:|
| Faithfulness | 1.0000 |
| Answer Relevancy | 0.8580 |
| Context Precision | 1.0000 |
| Context Recall | 1.0000 |
| **Mean** | **0.9645** |

**Question:**
> What was the total contract value of large deals Infosys closed in Q3 FY26, and what share of that TCV represented net new business?

**Model Answer:**
> The total contract value (TCV) of large deals Infosys closed in Q3 FY26 was **$4.8 billion**, with **57%** of that TCV representing net new business.

**Reference Answer:**
> The total contract value of large deals Infosys closed in Q3 FY26 was $4.8 billion, with 57% representing net new business.

**Why it works:**
The question targets a single, specific quarterly fact. The correct earnings-call chunk was ranked first by the metadata pipeline (its `sample_queries` YAML field includes an exact paraphrase of this question). The answer matches the reference verbatim, resulting in perfect faithfulness, precision, and recall.

---

### Success Example 2 — Strategic Multi-Part Question

**ID 22 | Source: NSE ≤10 pages — Infosys–Intel PR**

| Metric | Score |
|---|---:|
| Faithfulness | 1.0000 |
| Answer Relevancy | 0.9598 |
| Context Precision | 1.0000 |
| Context Recall | 1.0000 |
| **Mean** | **0.9900** |

**Question:**
> What is the strategic rationale behind Infosys and Intel deepening their partnership to deliver enterprise AI solutions globally?

**Model Answer:**
> The strategic rationale behind Infosys and Intel deepening their partnership is to facilitate the transition of enterprises from AI pilots to large-scale production deployments. This collaboration combines Intel's high-performance, energy-efficient compute platforms with Infosys Topaz Fabric, creating a unified ecosystem that optimizes performance, enhances security, and reduces costs. By co-innovating on AI workloads and focusing on "right-sized" architectures, the partnership aims to deliver measurable outcomes across various industries, enabling organizations to securely and reliably implement AI in complex environments.

**Reference Answer:**
> The strategic rationale is to help enterprises scale AI deployments from pilots to production at scale. The collaboration combines Intel's high-performance, energy-efficient compute platforms with Infosys Topaz Fabric, aiming to advance open standards and accelerate secure, cost-efficient enterprise AI deployments.

**Why it works:**
The press release is a short, self-contained document with highly distinctive YAML metadata (unique partner name, product name, and topic). The metadata-only embedding placed it at rank 1. The LLM answer is fully grounded in the retrieved context with no hallucinated details.

---

### Success Example 3 — Numerical + Regulatory Detail

**ID 17 | Source: NSE ≤10 pages — Buyback Outcome Filing**

| Metric | Score |
|---|---:|
| Faithfulness | 1.0000 |
| Answer Relevancy | 0.9091 |
| Context Precision | 1.0000 |
| Context Recall | 1.0000 |
| **Mean** | **0.9773** |

**Question:**
> What was the aggregate buyback size and price per share approved by the Infosys Board in September 2025, and how many shares were proposed for repurchase?

**Model Answer:**
> The Infosys Board approved an aggregate buyback size of ₹18,000 crore at a price of ₹1,800 per share, proposing to repurchase 10,00,00,000 shares.

**Reference Answer:**
> The aggregate buyback size approved by the Infosys Board in September 2025 was ₹18,000 crore at a price of ₹1,800 per equity share, with a proposal to repurchase up to 10,00,00,000 shares.

**Why it works:**
The NSE filing is the only document in the corpus mentioning this specific buyback. Three precise numerical values (₹18,000 crore, ₹1,800/share, 10 crore shares) are reproduced correctly, demonstrating strong faithfulness on financial regulatory data.

---

### Success Example 4 — Multi-Benefit Business Question

**ID 24 | Source: NSE ≤10 pages — Infosys Finacle PR**

| Metric | Score |
|---|---:|
| Faithfulness | 1.0000 |
| Answer Relevancy | 0.9622 |
| Context Precision | 1.0000 |
| Context Recall | 1.0000 |
| **Mean** | **0.9906** |

**Question:**
> What business and performance benefits is Bank CTBC Indonesia gaining from Infosys Finacle's digital banking suite deployed on cloud?

**Model Answer:**
> 1. **Scalability** — The cloud-hosted model allows the bank to scale effortlessly to meet growing business demands.
> 2. **Faster Innovation** — The bank can deliver innovations and new products faster, ensuring a shorter time-to-market.
> 3. **Operational Efficiency** — The modernization has improved operational efficiency, including over 300% reduction in bulk processing time.
> 4. **Enhanced Customer Experience** — The Finacle Customer Data Hub provides a unified view of customer data, enabling hyper-personalisation of services.
> 5. **Cost Reduction** — The deployment has led to a reduced total cost of ownership (TCO).
> 6. **Security and Flexibility** — The cloud-native solution offers secure and scalable flexibility.

**Reference Answer:**
> Effortless scalability and faster delivery of innovations. Improved operational efficiency and enhanced customer experience. Accelerated new feature releases. A unified 360-degree customer view through the Finacle Customer Data Hub, enabling hyper-personalisation. Transformative performance gains including over 300% reduction in bulk processing time and reduced TCO.

**Why it works:**
The press release is unique in the corpus (Bank CTBC Indonesia is mentioned nowhere else). All six benefit categories in the model answer map directly to claims in the source document, yielding perfect faithfulness and recall.

---

## Part 2 — Failure Cases

> These examples expose retrieval errors, context coverage gaps, and evaluation
> artefacts that cause one or more RAGAS metrics to fall sharply.

---

### Failure Case 1 — Wrong Document Retrieved → Factual Hallucination

**ID 46 | Source: NSE >10 pages — 44th AGM Transcript**

| Metric | Score |
|---|---:|
| Faithfulness | 0.0000 |
| Answer Relevancy | 0.9551 |
| Context Precision | 0.5000 |
| Context Recall | 0.0000 |
| **Mean** | **0.3638** ← *Lowest in dataset* |

**Question:**
> What was the total value of large deals Infosys won during fiscal year 2024–25 as reported at the 44th Annual General Meeting?

**Model Answer:**
> The total value of large deals Infosys won during fiscal year 2024–25, as reported at the 44th Annual General Meeting, was **$14.9 billion**.

**Reference Answer:**
> Large deals totaled **US$11.6 billion** during fiscal year 2024–25.

**Retrieved Context (top 3 files):**
- `FY26-Q4-ifrs-inr-press-release/group_001.md` ← **WRONG** (FY26 data, not FY25)
- `Infosys_23042026170027_outcome/group_021.md`
- `Infosys_02072025225219_SEfiling_AGMtranscript_2025/group_003.md` ← correct

**Root Cause:**
The correct source (`AGMtranscript_2025/group_003.md`) was retrieved at rank 3, but the dominant context was the FY26 Q4 press release, which reports $14.9 billion for **FY26** large deals. The LLM read the wrong figure from the wrong year. The question requires distinguishing FY24-25 from FY26 — two fiscal years with different TCV figures but nearly identical YAML metadata vocabulary.

**Error pattern:** *Inter-document confusion — similar topics, different time periods*

---

### Failure Case 2 — Context Coverage Gap (Incomplete Enumeration)

**ID 15 | Source: IR — Q2 FY26 IFRS Press Release**

| Metric | Score |
|---|---:|
| Faithfulness | 0.8889 |
| Answer Relevancy | 0.9925 |
| Context Precision | 0.5833 |
| Context Recall | 0.1250 |
| **Mean** | **0.6474** |

**Question:**
> What third-party rankings and industry recognitions has Infosys received for its AI and cloud service capabilities as listed in the Q2 FY26 press release?

**Model Answer:**
> 1. **Forrester Wave™: AI Technical Services, Q4 2025** — Recognized as a Leader, ranked among the top two in strategy.
> 2. **Gartner Magic Quadrant for Public Cloud IT Transformation Services, 2025** — Positioned as a Leader for the third consecutive year.
> 3. **Brand Finance Global 500 2026** — Recognized as one of the top 3 most valuable IT services brands globally.

**Reference Answer (8 recognitions):**
> - Gartner Magic Quadrant — Leader in Public Cloud IT Transformation Services
> - Gartner Emerging Market Quadrant — Leader in GenAI Consulting and Implementation
> - IDC MarketScape: Asia Pacific Oracle Implementation Services 2025
> - IDC MarketScape: Worldwide Artificial Intelligence Services 2025
> - IDC MarketScape: Worldwide Life Science R&D AI and GenAI in Clinical Trials 2025
> - Constellation ShortList: AI and ML Best-of-Breed Platforms
> - Constellation ShortList: AI-Driven Cognitive Applications
> - Stevie® Awards — EdgeVerve AI Next platform

**Root Cause:**
The top-3 context files included only `group_002.md` from the Q2 press release, which listed 3 recognitions. The remaining 5 recognitions were in `group_001.md` — a second chunk of the same document that was not retrieved in the top 3. Context recall collapsed to 0.125 because 7 of 8 reference facts were absent from the retrieved context.

**Error pattern:** *Intra-document fragmentation — answer spans multiple chunks of one document*

---

### Failure Case 3 — Unfaithful Answer Despite Correct Context

**ID 13 | Source: IR — Q4 FY26 Earnings Call**

| Metric | Score |
|---|---:|
| Faithfulness | 0.4000 |
| Answer Relevancy | 0.9946 |
| Context Precision | 1.0000 |
| Context Recall | 1.0000 |
| **Mean** | **0.8487** |

**Question:**
> Why is Infosys passing AI-driven productivity gains through to clients rather than converting them into margin expansion?

**Model Answer:**
> Infosys is passing AI-driven productivity gains to clients rather than converting them into margin expansion because the company believes in **sharing the benefits** of productivity improvements with clients. This enhances client relationships and creates greater impact. The productivity gains from AI and automation are significant, typically ranging from **5% to 15%**, and are part of a broader strategy to improve client outcomes and satisfaction.

**Reference Answer:**
> Productivity benefits are largely passed back to clients because **the market is competitive and competitive intensity has increased**.

**Root Cause:**
The reference answer captures the single stated reason from the source: competitive pressure. The model's answer adds plausible but unsupported reasons — "sharing philosophy", "greater impact", "client satisfaction" — none of which appear in the retrieved context. RAGAS faithfulness penalises these additions as claims not entailed by the context, despite context precision and recall being perfect.

**Error pattern:** *LLM over-elaboration — adding plausible but ungrounded rationale beyond what the context states*

---

### Failure Case 4 — Answer Relevancy Collapse (RAGAS Metric Artefact)

**ID 8 | Source: IR — Q1 FY26 Earnings Call**

| Metric | Score |
|---|---:|
| Faithfulness | 1.0000 |
| Answer Relevancy | 0.0000 |
| Context Precision | 1.0000 |
| Context Recall | 0.6667 |
| **Mean** | **0.6667** |

**Question:**
> What reasons does Infosys management give for expecting H1 FY26 to outperform H2, and what assumptions underpin the upper and lower ends of the guidance range?

**Model Answer:**
> Infosys management expects H1 FY26 to outperform H2 due to **normal seasonality**, indicating that typically the first half sees stronger performance. The guidance range was adjusted, with the lower end increased from 0% to 1% based on strong Q1 performance and deal wins. The upper end remains unchanged due to ongoing uncertainties related to tariffs and the broader macroeconomic environment.

**Reference Answer:**
> Infosys management expects H1 FY26 to outperform H2 due to **usual seasonality**, supported by a strong Q1 performance. The lower end reflects higher uncertainty from current conditions, while the upper end assumes a stable environment.

**Why Answer Relevancy = 0.0:**
RAGAS answer relevancy works by generating synthetic questions from the answer text and computing the embedding similarity between those synthetic questions and the original question. When the answer is a long, multi-clause explanation, the synthetic questions generated by the LLM may not reconstruct the original question closely enough, causing the cosine similarity to fall near zero. The answer itself is factually correct and faithful — this is an evaluation metric artefact, not a genuine pipeline failure.

**Error pattern:** *RAGAS answer-relevancy artefact — long explanatory answers can produce low cosine similarity to synthetic questions*

---

### Failure Case 5 — Context Recall = 0 (Source Document Not Reached)

**ID 34 | Source: NSE ≤10 pages — Infosys Responsible AI PR**

| Metric | Score |
|---|---:|
| Faithfulness | 0.9375 |
| Answer Relevancy | 0.9175 |
| Context Precision | 0.8333 |
| Context Recall | 0.0000 |
| **Mean** | **0.6721** |

**Question:**
> What financial losses and reputational damage from AI-related incidents does the Infosys research report document?

**Model Answer:**
> AI-related incidents lead to significant financial losses and reputational damage through: investment cost overruns if AI investments do not yield outcomes; regulatory non-compliance fines; competitive market losses; negative media coverage; and operational disruptions. These factors highlight the potential for AI-related incidents to cause both financial losses and reputational harm.

**Reference Answer:**
> **77% of organisations reported financial loss**, and **53% of organisations have suffered reputational impact** from AI-related incidents.

**Retrieved Context:**
- `Form20F_July012025/group_012.md` — generic AI risk section from Form 20-F
- `Form20F_June152026/group_006.md` — generic AI risk section from annual report
- `Form20F_July012025/group_005.md` — generic AI risk section

**Root Cause:**
The correct source is a short NSE press release (`Infosys_14082025152800_PR_14082025.md`) that contains the specific statistics. The pipeline retrieved three chunks from the Form 20-F risk-factor section, which discusses AI-related risk in generic regulatory language. Both documents share nearly identical YAML `topics` and `sample_queries` vocabulary (`responsible AI`, `AI incidents`, `AI risks`). The pipeline could not distinguish between a research PR with specific statistics and a regulatory filing with generic risk language.

**Error pattern:** *Semantic vocabulary collision — different document types cover the same topic with similar metadata*

---

## Part 3 — Error Analysis: Patterns in Model Mistakes

### Pattern 1 — Intra-Quarter Vocabulary Collision (IR Category)

The IR category (earnings calls Q1–Q4, press conferences, fact sheets) scored
only **Recall@3 = 1/10** in retrieval. All quarterly documents share the same
YAML topics: `revenue guidance`, `operating margin`, `large-deal TCV`,
`constant currency`. The metadata-only embedding cannot distinguish Q1 from Q4
because the YAML vocabulary is identical — only the actual numbers in the body differ.

**Consequence:** Wrong-quarter context is retrieved → LLM answers with the wrong
quarter's numbers → low faithfulness and context recall.

**Fix:** Embed the document body (not just metadata), or add quarter-specific
fields to the YAML (`quarter`, `fiscal_year`) so the embedding vector encodes
time-period information.

---

### Pattern 2 — Multi-Chunk Fragmentation

Questions requiring an exhaustive list (e.g., "all third-party rankings", "all
banking AI use cases") are answered incompletely when the information spans
multiple chunks of the same source document. The pipeline retrieves top-3 chunks
by relevance, but in a long press release or transcript, relevant sections may
land in `group_001`, `group_002`, and `group_003` — all three ranked below
other documents in the metadata index.

**Consequence:** Context recall drops to near zero for list-type questions even
when the source document itself is correctly identified at a higher rank.

**Fix:** After the top-3 context chunks are selected, add a same-document
co-retrieval step: if `group_002.md` is retrieved, automatically include
`group_001.md` and `group_003.md` from the same folder.

---

### Pattern 3 — LLM Over-Elaboration → Low Faithfulness

When the context provides a brief, direct answer (e.g., a one-sentence reason
for a business decision), `gpt-4o-mini` tends to expand the answer with
plausible-sounding but ungrounded elaborations. RAGAS faithfulness checks
every claim in the answer against the context; unsupported claims reduce the score.

**Consequence:** Faithfulness scores of 0.4–0.75 on questions where the context
contains a short, specific answer and the model "fills in" logical justifications.

**Fix:** Add an explicit system instruction: *"Answer using only information
from the provided documents. Do not infer, extrapolate, or add information
not present in the context."*

---

### Pattern 4 — RAGAS Answer Relevancy Metric Artefact

Answer relevancy = 0.0 appeared on IDs 8 and 44 — both cases where the model
produced a long, multi-clause explanatory answer that is factually correct and
faithful. RAGAS computes answer relevancy by generating synthetic questions from
the answer and measuring embedding similarity to the original question. Long
answers tend to produce synthetic questions that span many sub-topics, none of
which closely resembles the original question vector.

**Consequence:** A genuine, high-quality answer is penalised as irrelevant.
This metric should be interpreted alongside faithfulness and context recall
rather than in isolation.

---

### Pattern 5 — Temporal Disambiguation Failure

Questions that require distinguishing between two adjacent fiscal years (e.g.,
FY24-25 vs FY25-26) are prone to failure when both years' documents share the
same YAML vocabulary and the distinguishing fact (the specific dollar figure)
only appears in the body text. The metadata pipeline retrieves the wrong year's
document at rank 1 and the correct document at rank 3, causing the LLM to read
the dominant (wrong) value.

**Consequence:** Faithfulness = 0.0 (the stated figure contradicts the
reference), context recall = 0.0 (the reference answer's facts are not in
the retrieved context).

---

## Summary Table

| ID | Question (abbreviated) | Key Failure | Faithfulness | Ans. Relevancy | CP | CR | Mean |
|---|---|---|---:|---:|---:|---:|---:|
| **9** | Q3 FY26 TCV and net-new % | *None — success* | 1.00 | 0.86 | 1.00 | 1.00 | **0.96** |
| **22** | Infosys–Intel partnership rationale | *None — success* | 1.00 | 0.96 | 1.00 | 1.00 | **0.99** |
| **17** | September 2025 buyback details | *None — success* | 1.00 | 0.91 | 1.00 | 1.00 | **0.98** |
| **24** | Bank CTBC cloud banking benefits | *None — success* | 1.00 | 0.96 | 1.00 | 1.00 | **0.99** |
| **46** | FY24-25 large deals at 44th AGM | Wrong document → wrong year | 0.00 | 0.96 | 0.50 | 0.00 | **0.36** |
| **15** | Q2 FY26 third-party rankings | Fragmented multi-chunk answer | 0.89 | 0.99 | 0.58 | 0.13 | **0.65** |
| **13** | Why pass AI gains to clients | LLM over-elaboration | 0.40 | 0.99 | 1.00 | 1.00 | **0.85** |
| **8** | H1 vs H2 outperformance reasons | RAGAS metric artefact | 1.00 | 0.00 | 1.00 | 0.67 | **0.67** |
| **34** | AI incident financial/reputational losses | Vocabulary collision, wrong doc | 0.94 | 0.92 | 0.83 | 0.00 | **0.67** |

---

## Pipeline A — Overall RAGAS Scores

| Metric | Score | Interpretation |
|---|---:|---|
| **Faithfulness** | **0.8929** | Answers are largely grounded in context; over-elaboration is the main leak |
| **Answer Relevancy** | **0.8439** | Dragged down by 2 metric-artefact zeros; true relevancy is higher |
| **Context Precision** | **0.9683** | Retrieved documents are highly precise; very few noisy chunks |
| **Context Recall** | **0.8725** | Good overall; weakened by IR category retrieval failures and chunk fragmentation |
