# ADD A QUESTION-GENERATOR IN THE PROMPT

Yes. This is a useful retrieval technique: generate likely user questions from each document or section and embed them as additional retrieval representations.

I recommend adding:

```json
"answerable_questions": [
  {
    "question": "What acquisition did Infosys announce in April 2026?",
    "supporting_pages": [1, 2]
  }
]
```

Prompt rules should require that each question:

- Can be answered completely from the supplied document or section.
- Represents materially useful investor information.
- Is written as a natural user question.
- Is specific about entities, periods, and metrics when available.
- Does not introduce unsupported facts.
- Is not merely a rewording of another generated question.
- Includes the page or pages containing the supporting information.
- Returns `[]` when there are no useful answerable questions.

For section processing, questions must only be answerable from that section. For whole-document processing, they can use evidence from anywhere in the document.

For retrieval, do **not** concatenate all generated questions into the content and create one embedding. Instead:

1. Keep the original content embedding.
2. Embed every generated question separately.
3. Link each question embedding back to its source document or section.
4. Search both content and question embeddings.
5. Merge and rerank the matched source sections.

This gives each section multiple retrieval entry points without weakening its primary content embedding.

I would avoid vague generated questions such as “What recent acquisitions did Infosys make?” when the document provides a date. Prefer “What acquisition did Infosys announce in April 2026?” The user can still search with “recently,” while the stored question remains precise and does not become stale.