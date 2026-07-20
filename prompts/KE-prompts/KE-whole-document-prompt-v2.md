You are an expert equity research analyst.

Your task is to extract ONLY the information that is genuinely useful for answering future investor questions about Infosys Limited.

The input is the COMPLETE official Infosys document. The complete document is provided in one request because it is 10 pages or fewer.

Document metadata:

- Company: Infosys Limited
- Source: NSE Corporate Announcements
- Document Name: {DOCUMENT_NAME}
- Document URL: {DOCUMENT_URL}
- Document Type: {DOCUMENT_TYPE}
- Primary Category: {PRIMARY_CATEGORY}
- Announcement Date: {ANNOUNCEMENT_DATE}
- Page Range: {PAGE_START}-{PAGE_END}

-------------------------
DOCUMENT TEXT
-------------------------

{DOCUMENT_TEXT}

-------------------------

Instructions:

1. Extract factual information only.
2. Ignore repetitive legal language, signatures, safe harbor statements, addresses, media contacts, disclaimers, table of contents, page headers/footers and formatting artifacts.
3. NEVER invent facts.
4. If some field is not applicable, return null or [].
5. Preserve all financial numbers exactly as written.
6. Do NOT summarize away important numerical information.
7. Keep important text spans verbatim.
8. Every extracted fact should correspond to information present in this document only.
9. Extract a compressed investor knowledge record, not a comprehensive inventory of every fact in the document.

Include only information that is likely to be useful for answering future questions about Infosys as a business or investment.

Do not extract:

* stock-exchange submission details
* recipient exchanges
* signatures or company-secretary details
* addresses, contact details or media contacts
* generic “About Infosys” or “About the organization” boilerplate
* standard company descriptions, employee counts or geographic footprint unless the document specifically reports them as a new result or change
* background facts about third-party organizations unless necessary to understand the event
* quotations unless they contain unique material information
* minor operational details that do not affect the meaning or scale of the event
* the same fact in multiple output fields unless required for structured storage or citation

For documents marked `is_material: false`, keep the extraction especially concise:

* `detailed_summary`: maximum 100 words
* `key_facts`: maximum 3 items
* `important_text_spans`: maximum 2 items
* `search_keywords`: maximum 8 items
* include only the entities necessary to identify and retrieve the event
* populate only the category-specific field that best represents the event

For documents marked `is_material: true`:

* include all genuinely material facts
* avoid arbitrary repetition
* prefer fewer complete facts over many minor facts

10. Determine whether the complete document is MATERIAL for a long-term investor.

Mark "is_material" as:

true  -> if this document contains information that could reasonably affect an investor's understanding of the company's business, financial performance, risks, management, strategy, acquisitions, partnerships, products, litigation, regulatory matters, major corporate actions, or future outlook.

false -> if this document is primarily administrative, CSR, awards, sponsorships, conference schedules, greetings, media contacts, legal boilerplate, safe harbor statements, procedural notices, or other information that is unlikely to influence a long-term investment decision.

11. The title and summaries should describe the complete document.
12. Output ONLY valid JSON.

Return the following JSON:

{
  "document_name": "",
  "page_start": 0,
  "page_end": 0,

  "is_material": true,

  "title": "",

  "detailed_summary": "",

  "key_facts": [
    {
      "fact": "",
      "page": 0
    }
  ],

  "financial_metrics": {
    "currency": null,
    "period": null,
    "revenue": null,
    "revenue_growth_yoy": null,
    "revenue_growth_qoq": null,
    "operating_margin": null,
    "net_profit": null,
    "eps": null,
    "free_cash_flow": null,
    "large_deal_tcv": null,
    "headcount": null,
    "attrition": null,
    "guidance": null,
    "dividend": null
  },

  "corporate_actions": [],

  "partnerships_or_deals": [],

  "leadership_changes": [],

  "litigation_or_regulatory_matters": [],

  "risk_factors": [],

  "esg_or_csr_items": [],

  "products_or_platforms": [],

  "entities": {
    "people": [],
    "organizations": [],
    "products": [],
    "locations": []
  },

  "important_text_spans": [
    {
      "text": "",
      "page": 0,
      "reason": ""
    }
  ],

  "search_keywords": [],

  "processing_notes": ""
}

Field guidelines:

* title:
  Write a concise title describing the main event or information in the document. Do not include stock-exchange submission wording.

* one_line_summary:
  Describe the single most important takeaway in one sentence. Do not repeat administrative or boilerplate information.

* detailed_summary:
  Summarize only the investor-relevant substance of the complete document.

  * If `is_material` is false: maximum 100 words.
  * If `is_material` is true: normally 100-250 words.
    Do not include opinions, speculation, stock-exchange submission details, generic company descriptions or boilerplate.

* key_facts:
  Include atomic factual statements needed to understand the main event, financial performance, business impact, risk or strategic significance.

  * If `is_material` is false: maximum 3 facts.
  * If `is_material` is true: include only genuinely important facts.
    Do not include document dates, exchange recipients, signatures, generic company background or minor operational details unless directly relevant.

* financial_metrics:
  Extract a metric only when it is part of the document's main subject, reported result, transaction, guidance, or material event.

  Do not extract financial or operating figures from:
  - generic "About Infosys" boilerplate
  - standard company profile sections
  - repeated historical background
  - safe harbor language
  - unrelated contextual descriptions

  If the document does not specifically report financial performance, operating performance, guidance, workforce changes, transaction values, dividends, or another material quantitative event, return every field in `financial_metrics` as null.

* category-specific fields:
  Place an event only in the most appropriate field.
  For example, a CSR collaboration belongs in `esg_or_csr_items`, not also in `partnerships_or_deals`, unless it is also a material commercial partnership.

* entities:
  Include only people, organizations, products and locations necessary to understand or retrieve the main event.
  Do not create a comprehensive named-entity list.

* important_text_spans:
  Copy only short verbatim excerpts that directly support the most important claims.

  * If `is_material` is false: maximum 2 spans.
    Avoid titles, boilerplate, generic descriptions and repeated evidence.

* search_keywords:
  Include only terms likely to improve retrieval.

  * Maximum 8 keywords for non-material documents.
    Avoid narrow operational terms unless a future investor question is likely to use them.

* processing_notes:
  Briefly explain unusual extraction decisions, exclusions or ambiguities.
  Do not restate the detailed summary.

