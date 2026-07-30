That is the right basic idea. I’d use this slightly stronger prompt for creating reference answers:

```text
You are creating a concise, factual reference answer for a RAG evaluation dataset.

Question:
{question}

Source document:
<text-start>
{text}
<text-end>

Write the direct answer to the question using only the source document.

Rules:
- Include all important facts needed to answer the question.
- Do not add information that is not in the source document.
- Do not mention the source document, these instructions, or the text tags.
- Do not use phrases such as “based on the text”.
- If the source document does not contain the answer, return exactly:
  NOT_FOUND
- Return only the answer.
```

`NOT_FOUND` is useful because it clearly distinguishes an unsupported question from a weakly written answer. The generated answer should still be reviewed by a human before using it as the RAGAS `reference_answer`.