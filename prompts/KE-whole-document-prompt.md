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
9. Determine whether the complete document is MATERIAL for a long-term investor.

Mark "is_material" as:

true  -> if this document contains information that could reasonably affect an investor's understanding of the company's business, financial performance, risks, management, strategy, acquisitions, partnerships, products, litigation, regulatory matters, major corporate actions, or future outlook.

false -> if this document is primarily administrative, CSR, awards, sponsorships, conference schedules, greetings, media contacts, legal boilerplate, safe harbor statements, procedural notices, or other information that is unlikely to influence a long-term investment decision.

10. The title and summaries should describe the complete document.
11. Output ONLY valid JSON.

Return the following JSON:

{
  "document_name": "",
  "page_start": 0,
  "page_end": 0,

  "is_material": true,

  "title": "",

  "one_line_summary": "",

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

- detailed_summary:
  A concise factual summary (100-250 words) describing the important information contained in this complete document. Do not include opinions or speculation.

- key_facts:
  List atomic factual statements. Each fact should contain only one piece of information and include the page number where it appears.

- financial_metrics:
  Extract only metrics explicitly present in this document. Do not calculate missing values.

- important_text_spans:
  Copy only short verbatim excerpts that would serve as strong supporting evidence for important facts. Do not copy long paragraphs.

- search_keywords:
  Include important names, products, initiatives, technologies, financial terms and topics that would improve retrieval.
