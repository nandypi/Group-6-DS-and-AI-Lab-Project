# What is reranking?

Chroma and the reranker answer slightly different questions, so their rankings can differ a lot.

Chroma is the fast first-pass retriever. It converts the question and every indexed document/chunk into embeddings, then finds the closest vectors.

```text
Question embedding  ── similarity search ──> top 25 Chroma candidates
```

This is efficient because document embeddings are created once during indexing. But the comparison is broad: it asks, “Which documents are semantically similar to this question?”

The BGE reranker is a cross-encoder. For each of those 25 candidates, it reads the question and candidate text together:

```text
[question] + [one candidate body] ── BGE cross-encoder ──> relevance score
```

It can therefore judge the exact relationship between the question and the text: numbers, entities, negation, time periods, and whether the candidate actually answers the question rather than merely discussing a related topic.

In this project, each candidate gets two independent BGE scores:

```text
body_score     = BGE(question, document body)
metadata_score = BGE(question, YAML metadata)

final_score = 0.8 × body_score + 0.2 × metadata_score
```

Then we sort the 25 Chroma candidates by `final_score` and calculate Recall@3, Recall@5, and Recall@7 from that new order.

Why rankings change in practice:

- Chroma may rank a document high because it broadly discusses “revenue growth,” while the question specifically asks about “Q1 FY26 operating margin.”
- The reranker sees both texts together and can promote the document containing the exact Q1 FY26 figures.
- Metadata may help distinguish otherwise similar documents—for example, a filing’s date, title, quarter, or source category.
- Embedding similarity is compressed into vectors; some exact details can be weakened. A cross-encoder reads the actual tokens directly.

A useful analogy:

```text
Chroma = quickly shortlist 25 books based on the title and general subject.
Reranker = read the question alongside relevant parts of each shortlisted book
           and decide which books answer it most precisely.
```

The reranker cannot recover a correct source that Chroma did not place in the initial top 25. It only improves the order of those 25 candidates.

# Why call it "cross-encoder"?

It is called a cross-encoder because it encodes the question and document together in one model pass.

```text
Cross-encoder input:
[Question] What was Q1 FY26 revenue growth?
[Document] Infosys reported revenue growth of ...
             ↓
      one relevance score
```

The attention layers can directly compare every question token with every document token. For example, “Q1,” “FY26,” “revenue,” and “growth” can interact with the exact matching words and figures in the document.

By contrast, Chroma uses a bi-encoder:

```text
Question ──> question embedding
Document ──> document embedding
               ↓
       compare the two vectors
```

Each side is encoded separately, so it is very fast for searching thousands of documents. But it cannot make detailed token-by-token comparisons at search time.

“Cross” refers to these cross-attention interactions between the query and document tokens. It is more accurate, but too expensive to run across the entire database—hence the two-stage approach: Chroma retrieves a small candidate set, then the cross-encoder reranks it.

# What influences "cross-encoding"?

A cross-encoder’s relevance score depends on the full question–document pair, not on one fixed similarity metric.

In practice it weighs signals such as:

- Exact term matches: “Q1 FY26,” “operating margin,” “Versent Group.”
- Meaning and paraphrases: “shareholder return” can match “buyback payout.”
- Context and relationships: whether the number is actually tied to the requested company, period, and metric.
- Entities: company names, subsidiaries, people, deal names, and products.
- Numbers and units: percentages, revenue figures, currency, dates, fiscal quarters.
- Intent: whether the text answers “why,” “how much,” “who,” or “when.”
- Negation and qualifiers: “expected,” “not,” “up to,” “excluding,” “subject to.”
- Position and surrounding context: a phrase may be relevant only when nearby sentences establish what it refers to.
- Metadata, separately in this project: document title/date/source can contribute through the 20% metadata score.

The model learns how strongly to weigh these from its training data. It does not expose a simple human-readable formula such as “30% keyword match + 20% date match.” Its output is a learned relevance score based on attention across all tokens in the question and candidate text.

Our final ranking does add one explicit rule on top:

```text
final_score = 0.8 × body relevance + 0.2 × YAML metadata relevance
```

So a document needs a strong body match first; metadata can help break or improve close cases.

# In our case:

  For every one of the 25 Chroma candidates, we make two separate cross-encoder inputs:

  (question, complete document body)  → body_score
  (question, YAML metadata)           → metadata_score

  Then we calculate:

  final_score = 0.8 × body_score + 0.2 × metadata_score

  We sort the 25 candidates by final_score. **The YAML metadata is not appended to the body for either BGE scoring or the final LLM context.**

## Why so much latency?

For each question, we rerank 25 candidates with:

```text
25 × (question, body) comparisons
25 × (question, YAML metadata) comparisons
= 50 cross-encoder comparisons
```

The body comparisons are especially expensive because BGE reads the question and document tokens together. For long documents, each comparison can be close to the configured 8,190-token limit. Cross-attention cost also grows sharply as the combined sequence gets longer.

So compared with Chroma’s quick vector lookup, reranking is doing much heavier work:

```text
Chroma:     one question embedding + vector search
Reranker:   50 detailed question–text evaluations
```

That matches the several-minute latency per question we are seeing. The metadata comparisons are usually cheap because YAML is short; the 25 long-body comparisons dominate the time.