# hyde_script

HyDE (Hypothetical Document Embeddings) retrieval for the existing RAG setup
in `embeddings_script/`. This directory adds a single, simple HyDE technique
on top of the same Chroma collection — it does not create or modify the
index.

## The technique

Standard retrieval embeds the user's question directly and searches Chroma
with that embedding. HyDE changes what gets embedded:

1. Ask an LLM (`gpt-4o-mini`) to write a short **hypothetical document** — a
   plausible passage that would answer the question, written as if it were
   an excerpt from a real financial disclosure.
2. Embed that hypothetical passage instead of the raw question
   (`text-embedding-3-small`, the same embedding model used to build the
   index).
3. Search the existing Chroma collection with the hypothetical document's
   embedding.
4. Answer the original question with `gpt-4o-mini`, grounded only in the
   real documents retrieved in step 3.

The idea: a hypothetical answer passage is written in the same style and
register as the documents being searched, so its embedding can land closer
to the real answer document than a short, differently-phrased question
would.

This is a single-pass approach — one hypothetical document is generated and
embedded per question, and it is used on its own (not combined with the raw
question's embedding).

### Generation prompt

`generate_hypothetical_document()` asks the model to pick whichever
register the question implies (press release, annual report section,
regulatory filing, earnings call transcript, or research note) rather than
defaulting to one style, and explicitly tells it not to invent specific
numbers, percentages, or dates — only the structure and language of a
plausible answer, since any fabricated figures are never shown to the user
and only exist to steer the embedding.

## What's in `hyde_retriever.py`

The module is self-contained: it duplicates the small pieces of
`embeddings_script/retriever.py` it needs (client setup, front-matter
stripping, context building, answering) instead of importing that package,
so every HyDE-specific change stays inside this directory.

| Function | Purpose |
|---|---|
| `get_clients()` | Creates the OpenAI client and opens the Chroma collection on first use, then reuses them. |
| `generate_hypothetical_document(question)` | Asks `gpt-4o-mini` to write the hypothetical answer passage. |
| `get_embedding(text)` | Creates an OpenAI embedding for any text (question or hypothetical document). |
| `retrieve(question, timings=None, candidate_count=3)` | Runs the full HyDE retrieval step: generate → embed → query Chroma. Returns the Chroma results and the generated hypothetical document. Optionally records per-stage timings. |
| `split_front_matter(document)` | Splits a Markdown document's YAML front matter from its body, mirroring `embeddings_script/reranker.py`. |
| `select_documents(results, limit=3)` | Deduplicates Chroma results by filepath and strips YAML front matter, keeping only the document body for the LLM context. |
| `build_context(selected_documents)` | Formats the selected document bodies into the final answer context. |
| `count_tokens(text)` | Estimates token count for the configured LLM using `tiktoken`. |
| `make_prompt(question, context)` | Builds the grounded answer prompt. |
| `ask_llm(question, context)` | Sends the prompt to `gpt-4o-mini` and returns the answer. |
| `main()` | Interactive question-and-answer loop: prints the generated hypothetical document, the selected documents, the answer, and per-stage latency. |

### Configuration

Read from the repository-root `.env` and environment variables:

| Setting | Default |
|---|---|
| `CHROMA_DB_PATH` | `<repo root>/chroma_db` (not configurable via env; hardcoded to the repo-root Chroma database) |
| `COLLECTION_NAME` | `finance_file_embeddings` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` |
| `LLM_MODEL` | `gpt-4o-mini` |
| `FINAL_DOCUMENT_COUNT` | `3` (number of documents sent to the answering LLM) |

## Usage

Install the dependencies scoped to this directory (deliberately excludes
the reranker's `torch`/`transformers`/`FlagEmbedding`, which this pipeline
doesn't use):

```bash
pip install -r hyde_script/requirements.txt
```

Make sure the repository-root `.env` has `OPENAI_API_KEY` set, and that
`chroma_db/` (the persistent Chroma database built by
`embeddings_script/index_documents.py`) exists at the repository root.

Run an interactive HyDE question-and-answer session:

```bash
cd hyde_script
python3 hyde_retriever.py
```

Type a question, and it will print the generated hypothetical document, the
documents retrieved with it, the final answer, and a per-stage latency
breakdown. Type `exit` to quit.

### Used by the benchmark

`datapreparation/benchmarking/run_hyde_benchmark.py` imports this module
(`import hyde_retriever`, via a `sys.path` insert of this directory) to run
the full 50-question test set from
`data/infosys_rag_test_dataset_50_queries.csv` and measure Recall@3/5/7
against the baseline (non-HyDE) and reranking pipelines. See
`datapreparation/benchmarking/results.md` for the results.
