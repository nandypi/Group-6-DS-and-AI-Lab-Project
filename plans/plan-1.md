If the specification contains minor ambiguities, do not stop for clarification. Choose the most reasonable implementation consistent with the rest of the specification.

# Objective

Implement a Python module that converts large Infosys Markdown documents into logical extraction units for downstream LLM-based knowledge extraction.

The implementation should prioritize **semantic coherence** over fixed page counts or fixed chunk sizes.

The output of this module will be consumed by another pipeline that performs knowledge extraction using an LLM.

This module **must not** call any LLM.

---

# Input

The module receives

```text
Markdown file
```

generated from Docling.

Example

```text
data\nse_files_final\categorisation_by_pages\more_than_10_pages\Infosys_01072025210240_Form20F_July012025_1__1_.md
```

Markdown may contain

* headings
* paragraphs
* tables
* lists
* page markers
* images
* formatting artifacts

---

# Output

For every Markdown document generate

```text
working/sections/<document_name>.json
```

Example

```json
{
  "document_name": "annual_report_2025.md",
  "total_sections": 47,
  "sections": [
    {
      "section_id": "annual_report_2025__001",
      "heading_path": [
        "Board's Report",
        "Financial Performance"
      ],
      "page_start": 31,
      "page_end": 35,
      "estimated_tokens": 4312,
      "text": "..."
    }
  ]
}
```

No LLM output should be generated.

---

# High-level algorithm

The pipeline should perform the following stages:

```text
Markdown

↓

Parse structure

↓

Remove boilerplate

↓

Build heading tree

↓

Estimate token counts

↓

Merge tiny sibling sections

↓

Split oversized sections recursively

↓

Generate extraction units

↓

Save JSON manifest
```

---

# Stage 1 — Parse Markdown

Parse the Markdown into blocks.

Supported block types:

* Heading
* Paragraph
* Table
* List
* Image placeholder
* Horizontal rule
* Blank line
* Page marker

Preserve document order.

---

# Stage 2 — Preserve page mapping

Every block should know which original page it belongs to.

Every generated extraction unit must contain

```text
page_start

page_end
```

These must refer to original PDF pages.

---

# Stage 3 — Build heading hierarchy

Construct a tree using Markdown heading levels.

Example

```markdown
# Annual Report

## Board's Report

### Financial Performance

### Dividend

## Corporate Governance
```

becomes

```text
Annual Report

├── Board's Report

│   ├── Financial Performance

│   └── Dividend

└── Corporate Governance
```

Each node should contain

* heading text
* heading level
* direct content
* child nodes
* page range

---

# Stage 4 — Boilerplate removal

Before calculating section sizes, identify sections that are purely boilerplate.

Examples include

* Safe Harbor
* Media Contacts
* Contact Details
* Signatures
* Exchange submission wrapper
* Table of Contents
* Repeated headers
* Repeated footers
* Blank image-only sections

Do **not** permanently delete them.

Instead

```python
excluded = True
```

These blocks should not participate in section sizing.

---

# Stage 5 — Token estimation

Estimate tokens.

A rough approximation is acceptable.

The estimate only guides section sizing.

---

# Target section size

Preferred

```
2000–6000 tokens
```

Soft maximum

```
8000 tokens
```

Hard maximum

```
10000 tokens
```

---

# Stage 6 — Recursive splitting

Recursively process the heading tree.

Rules

If a node

```
<= 8000 tokens
```

keep it intact.

If

```
>8000
```

split using child headings.

Repeat recursively.

---

# Stage 7 — Merge tiny sections

Very small sibling sections create noisy LLM calls.

If a section is

```
<2000 tokens
```

attempt to merge it with adjacent siblings.

Rules

Merge only

* adjacent siblings
* same parent
* preserve document order

Never merge across top-level sections.

---

# Stage 8 — Oversized leaves

Sometimes a leaf section still exceeds

```
8000 tokens
```

because no child headings exist.

Split using the following priority.

1.

Numbered subsection patterns

Examples

```
Note 1

Note 2

1.

2.

3.

```

2.

Table boundaries

3.

Page boundaries

4.

Paragraph boundaries

Never split inside a table.

---

# Stage 9 — Tables

Tables are atomic.

Never split a table because a token limit is reached.

If an individual table exceeds limits

split only at logical row groups while repeating

* title
* headers
* units

---

# Stage 10 — Heading path

Every extraction unit must preserve

```json
[
  "Board's Report",
  "Financial Performance"
]
```

Never keep only the leaf heading.

---

# Stage 11 — Extraction unit

Every unit should contain

```json
{
  "section_id": "",
  "heading_path": [],
  "page_start": 0,
  "page_end": 0,
  "estimated_tokens": 0,
  "text": ""
}
```

Nothing else.

---

# Stage 12 — Determinism

The algorithm should be deterministic.

Given the same Markdown

the generated sections must always be identical.

Do not use

* randomization
* heuristics depending on runtime state
* LLMs

---

# Stage 13 — Preserve document order

Generated extraction units must appear in the same order as the document.

Never reorder sections.

---

# Stage 14 — Things that must never happen

Never

* split a heading from its content
* split a table arbitrarily
* merge unrelated top-level sections
* merge sections from different page ranges unless they are adjacent siblings
* lose page information
* modify document text
* summarize
* remove numbers
* normalize wording

The text must remain exactly as it appears in Markdown.

---

# Stage 15 — CLI

Provide a CLI.

Example

```bash
python -m sectioner.cli \
    --input data/large_docs \
    --output working/sections
```

The CLI should process every Markdown file.

---

# Stage 16 — Logging

For every processed document print

```
Document:
Annual_Report_2025.md

Sections generated:
47

Average tokens:
4180

Largest section:
7712

Smallest section:
2310
```

---

# Stage 17 — Validation report

Generate

```
working/reports/
```

Example

```
001

Pages 31-35

4312 tokens

Board's Report

>

Financial Performance

--------------------------------------------------

002

Pages 36-38

2876 tokens

Board's Report

>

Dividend

>

Share Capital
```

This report is intended for human inspection before running LLM extraction.

---

# Stage 18 — Code quality

Organize the code into multiple modules.

Avoid one large script.

Prefer dataclasses where appropriate.

Add type hints.

Write clear docstrings.

Avoid premature optimization.

Prioritize readability.

---

# Stage 19 — Acceptance criteria

The implementation should satisfy the following expectations.

### 20-page press release

Expected

```
2–5 extraction units
```

---

### Quarterly results

Expected

```
6–15 extraction units
```

---

### Annual report (200+ pages)

Expected

```
40–80 extraction units
```

depending on document structure.

---

### Every extraction unit

Must

* represent one coherent topic
* preserve page range
* preserve heading hierarchy
* stay within target token limits whenever reasonably possible
