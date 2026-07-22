You are an expert equity research analyst.

Your task is to extract ONLY the information genuinely useful for answering future investor questions about Infosys Limited.

The input is the COMPLETE official Infosys document. The complete document is provided in one request because it is 10 pages or fewer.

Document metadata:

* Company: Infosys Limited
* Source: NSE Corporate Announcements
* Document Name: {DOCUMENT_NAME}
* Document URL: {DOCUMENT_URL}
* Document Type: {DOCUMENT_TYPE}
* Primary Category: {PRIMARY_CATEGORY}
* Announcement Date: {ANNOUNCEMENT_DATE}

---

## DOCUMENT TEXT

{DOCUMENT_TEXT}

---

Instructions:

1. Extract factual information only.

2. Ignore repetitive legal language, signatures, safe harbor statements, addresses, media contacts, disclaimers, table of contents, page headers and footers, and formatting artifacts.

3. NEVER invent facts, amounts, dates, relationships, impacts, classifications, or section headings.

4. When an array has no applicable information, return `[]`.

5. Never return placeholder objects containing empty strings or null-only values.

6. Preserve all financial numbers, percentages, dates, currencies, ratios, deal values, guidance ranges, and other important quantitative information exactly as written.

7. Do not summarize away important numerical information.

8. Keep `important_text_spans` verbatim.

9. Every extracted fact must correspond to information explicitly present in this document.

10. Extract a compressed investor knowledge record, not a comprehensive inventory of every fact in the document.

Include only information likely to be useful for answering future questions about Infosys as a business or investment.

Do not extract:

* stock-exchange submission details
* recipient exchanges
* signatures or company-secretary details
* addresses, contact details, or media contacts
* generic “About Infosys” or “About the organization” boilerplate
* standard company descriptions, employee counts, or geographic footprint unless the document specifically reports them as a new result or material change
* background facts about third-party organizations unless necessary to understand the main event
* quotations unless they contain unique material information
* minor operational details that do not affect the meaning, scale, financial impact, strategic significance, or investor relevance of the event
* the same fact in multiple category-specific fields
* facts included only in generic company descriptions, safe harbor statements, or historical boilerplate

11. Determine whether the complete document is MATERIAL for a long-term investor.

Set `"is_material": true` if the document contains information that could reasonably affect an investor’s understanding of Infosys’s:

* business operations
* financial performance
* operating performance
* risks
* leadership or governance
* strategy
* acquisitions or divestitures
* material commercial partnerships or client deals
* products, platforms, or major service offerings
* litigation or regulatory matters
* major corporate actions
* capital allocation
* workforce changes
* guidance
* future outlook

Set `"is_material": false` if the document is primarily about:

* administrative or procedural matters
* CSR or philanthropy
* awards or recognitions
* sponsorships
* conference or meeting schedules
* greetings or commemorative announcements
* media contacts
* routine legal boilerplate
* safe harbor statements
* routine compliance notices
* other information unlikely to influence a long-term investment decision

12. For documents marked `"is_material": false`, keep the extraction especially concise:

* `detailed_summary`: approximately 40–80 words and never more than 100 words
* `key_facts`: maximum 3 items
* `important_text_spans`: maximum 2 items
* `search_keywords`: maximum 8 items
* mention only organizations, people, products, or locations necessary to understand the event
* populate only the category-specific field that best represents the event
* avoid minor implementation details

13. For documents marked `"is_material": true`:

- include all genuinely material facts
- avoid arbitrary repetition
- prefer fewer complete facts over many minor facts
- normally limit `key_facts` to 5-7 items
- exceed 7 `key_facts` only when the document contains multiple distinct material events or several independently important disclosures
- retain all material financial, operational, strategic, regulatory, leadership, and risk information

14. The `title` and `detailed_summary` must describe the complete document rather than the stock-exchange submission wrapper.

15. Place each event in the single most appropriate category-specific field.

Examples:

* A CSR collaboration belongs in `esg_or_csr_items`, not in `partnerships_or_deals`, unless it is also a material commercial partnership.
* A client contract belongs in `partnerships_or_deals`, not in `corporate_actions`.
* A CEO resignation belongs in `leadership_changes`.
* A regulatory penalty belongs in `litigation_or_regulatory_matters`.

16. Populate a category-specific field only when the document contains a distinct event or disclosure that independently belongs in that category.

Do not populate a field merely because a product, regulator, approval, workforce figure, technology, or risk is mentioned as supporting context for another main event.

Examples:

- Mentioning Infosys Topaz or Infosys Cobalt in an acquisition announcement does not by itself require a `products_or_platforms` item.
- A regulatory approval required to complete an acquisition normally belongs in the acquisition description or `risk_factors`; do not create a `litigation_or_regulatory_matters` item unless the document describes a distinct regulatory proceeding, order, investigation, penalty, dispute, or compliance matter.
- A closing condition is not automatically a separate risk factor unless it represents an investor-relevant uncertainty worth retrieving independently.
- A workforce figure for an acquisition target is not Infosys headcount.

17. For every category-specific array, follow the exact object structure defined below.

18. Do not add new top-level keys or new keys inside defined objects.

19. Do not omit any top-level key from the output schema.

20. Use `null` for an optional scalar value that is not explicitly stated.

21. Use the exact document section heading when one exists.

22. If no clear section heading exists, return `null` for `section_heading`.

23. Do not invent, shorten, normalize, or paraphrase section headings.

24. Output ONLY valid JSON.

Return the following JSON structure:

{
"document_name": "",

"is_material": true,

"title": "",

"detailed_summary": "",

"key_facts": [],

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

"important_text_spans": [],

"search_keywords": [],

"processing_notes": ""
}

Field guidelines:

## title

Write a concise title describing the main event or information in the document.

Do not include:

* stock-exchange submission wording
* phrases such as “Infosys Limited has informed the Exchange”
* administrative filing language
* generic document labels when a more informative title is available

## detailed_summary

Summarize only the main investor-relevant event or information in the complete document.

Include, when relevant:

* what happened
* the parties directly involved
* the financial or strategic scale
* important numerical information
* the expected or stated business impact
* the expected or stated investor significance
* important risks or limitations explicitly stated in the document

Exclude:

* implementation details that do not affect investor understanding
* long lists of facilities, features, services, or activities
* generic company background
* third-party background that is not necessary
* quotations
* administrative submission details
* opinions or speculation
* information found only in boilerplate

Length:

* If `is_material` is false: approximately 40–80 words and never more than 100 words.
* If `is_material` is true: normally 100–250 words, but use fewer words when the document can be accurately summarized more concisely.

## key_facts

Include atomic factual statements necessary to understand the main event, financial performance, business impact, risk, or strategic significance.

Each `key_facts` item must follow this exact structure:

{
"fact": "string",
"section_heading": "string or null"
}

Guidelines:

* each item should contain one clear factual statement
* include the exact section heading when one exists
* otherwise return `null` for `section_heading`
* do not invent section headings
* do not include document submission dates unless the date itself is relevant to the event
* do not include exchange recipients
* do not include signatures
* do not include generic company background
* do not include boilerplate headcount or geographic footprint
* do not include minor operational details unless directly relevant
* if `is_material` is false, include no more than 3 facts
* if `is_material` is true, include only genuinely important facts

## financial_metrics

Extract a metric only when it is part of the document’s main subject, reported result, transaction, guidance, workforce change, or another material event.

Do not extract financial or operating figures from:

* generic “About Infosys” sections
* standard company profiles
* repeated historical background
* safe harbor language
* unrelated contextual descriptions
* boilerplate company statistics

If the document does not specifically report financial performance, operating performance, guidance, workforce changes, transaction values, dividends, or another material quantitative event, return every field in `financial_metrics` as `null`.

Field guidance:

* `currency`: Report the currency explicitly used for the extracted financial metrics. Return `null` if no applicable financial metric is present.
* `period`: Preserve the reporting period exactly as written.
* `revenue`: Preserve the reported revenue exactly as written.
* `revenue_growth_yoy`: Preserve the year-over-year revenue growth exactly as written.
* `revenue_growth_qoq`: Preserve the quarter-over-quarter revenue growth exactly as written.
* `operating_margin`: Preserve the reported operating margin exactly as written.
* `net_profit`: Preserve the reported net profit exactly as written.
* `eps`: Preserve reported earnings per share exactly as written.
* `free_cash_flow`: Preserve reported free cash flow exactly as written.
* `large_deal_tcv`: Preserve reported large-deal total contract value exactly as written.
* `headcount`: Extract only when the document specifically reports Infosys Limited's or a consolidated Infosys group's current workforce, workforce change, hiring target, restructuring impact, or another material workforce update.

  Do not place the workforce size of an acquisition target, client, partner, subsidiary being described separately, or third-party organization in this field.

  When a third-party or acquisition-target workforce figure is important, include it only in the relevant `corporate_actions`, `partnerships_or_deals`, `key_facts`, or `detailed_summary`.
* `attrition`: Preserve the reported attrition figure exactly as written.
* `guidance`: Preserve guidance ranges and accompanying units exactly as written.
* `dividend`: Preserve the dividend amount, type, and relevant period exactly as written when available.

Do not calculate missing values.

Do not combine figures from unrelated reporting periods.

## corporate_actions

Include material corporate actions such as:

* acquisitions
* mergers
* divestitures
* buybacks
* dividends
* stock splits
* capital reductions
* material share allotments
* major investments
* changes to capital structure

Each `corporate_actions` item must follow this exact structure:

{
"action_type": "string",
"description": "string",
"amount_or_ratio": "string or null",
"effective_date": "string or null",
"section_heading": "string or null"
}

Guidelines:

* use a concise `action_type`, such as `"acquisition"`, `"buyback"`, `"dividend"`, `"share allotment"`, or `"divestiture"`
* describe the action factually and concisely
* preserve amounts, ratios, and dates exactly as written
* include only actions relevant to investors
* do not include routine administrative filings
* return `null` when an optional value is not explicitly stated
* do not infer an effective date, amount, or ratio

## partnerships_or_deals

Include material:

* commercial partnerships
* client contracts
* strategic alliances
* joint ventures
* outsourcing agreements
* transformation deals
* major business agreements

Each `partnerships_or_deals` item must follow this exact structure:

{
"deal_type": "string",
"counterparty": "string or null",
"description": "string",
"value": "string or null",
"duration": "string or null",
"section_heading": "string or null"
}

Guidelines:

* distinguish commercial or strategic deals from CSR collaborations
* use a concise `deal_type`, such as `"client contract"`, `"strategic partnership"`, `"joint venture"`, or `"outsourcing agreement"`
* include the counterparty only when explicitly identified
* preserve deal value and duration exactly as written
* do not infer an undisclosed contract value
* do not estimate deal size
* exclude routine vendor relationships
* exclude non-material collaborations
* exclude CSR or philanthropic collaborations unless they are also material commercial arrangements

## leadership_changes

Include appointments, resignations, retirements, terminations, or changes involving:

* directors
* chief executive officers
* chief financial officers
* key managerial personnel
* senior executives
* other materially important leadership positions

Each `leadership_changes` item must follow this exact structure:

{
"person": "string",
"role": "string",
"change_type": "string",
"effective_date": "string or null",
"predecessor_or_successor": "string or null",
"section_heading": "string or null"
}

Guidelines:

* use a concise `change_type`, such as `"appointed"`, `"resigned"`, `"retired"`, `"terminated"`, or `"ceased"`
* include only leadership changes relevant to governance or management
* do not include people merely quoted in a press release
* do not include document signatories
* do not infer predecessor or successor relationships
* preserve effective dates exactly as written

## litigation_or_regulatory_matters

Include material:

* litigation
* regulatory investigations
* regulatory orders
* penalties
* settlements
* tax disputes
* compliance matters
* government or regulatory proceedings

Each `litigation_or_regulatory_matters` item must follow this exact structure:

{
"matter_type": "string",
"authority_or_counterparty": "string or null",
"description": "string",
"amount": "string or null",
"status": "string or null",
"section_heading": "string or null"
}

Guidelines:

* use a concise `matter_type`, such as `"litigation"`, `"regulatory investigation"`, `"penalty"`, `"tax dispute"`, or `"settlement"`
* describe the matter factually
* preserve monetary amounts exactly as written
* include the current status only when explicitly stated
* do not infer liability
* do not infer guilt
* do not infer probability of loss
* do not speculate about likely outcomes
* exclude generic regulatory language
* exclude routine compliance disclosures

## risk_factors

Include only risks that are:

* newly disclosed
* materially updated
* specifically connected to the document’s main event
* directly relevant to understanding potential business or investor impact

Each `risk_factors` item must follow this exact structure:

{
"risk": "string",
"potential_impact": "string or null",
"section_heading": "string or null"
}

Guidelines:

* describe each risk concisely and factually
* include `potential_impact` only when explicitly stated or directly explained in the document
* do not extract generic safe harbor risks
* do not speculate about likelihood or severity
* do not convert ordinary implementation details into risk factors
* do not create risks from your own analysis

## esg_or_csr_items

Include only the main ESG, sustainability, or CSR event necessary to understand the document.

Each `esg_or_csr_items` item must follow this exact structure:

{
"item": "string",
"amount": "string or null",
"section_heading": "string or null"
}

Guidelines:

* keep this field concise because ESG and CSR items are generally lower priority for this investor-focused application
* preserve a reported amount exactly as written
* do not include detailed implementation activities
* do not include long beneficiary-category lists
* do not include facility or equipment lists unless essential to understanding the scale of the event
* do not duplicate the event under `partnerships_or_deals` unless it is also a material commercial partnership
* for a non-material CSR document, normally include no more than one item

## products_or_platforms

Include material launches, upgrades, expansions, integrations, discontinuations, or strategic announcements involving Infosys:

* products
* platforms
* solutions
* major service offerings
* proprietary technologies

Each `products_or_platforms` item must follow this exact structure:

{
"name": "string",
"event_type": "string",
"description": "string",
"target_market_or_use_case": "string or null",
"section_heading": "string or null"
}

Guidelines:

* use a concise `event_type`, such as `"launched"`, `"expanded"`, `"upgraded"`, `"integrated"`, or `"discontinued"`
* include only products or platforms relevant to Infosys’s business, strategy, revenue potential, or competitive position
* do not include technologies mentioned only in generic company descriptions
* do not list every feature
* include the target market or use case only when explicitly stated
* do not treat a client’s product as an Infosys product unless the document clearly identifies Infosys ownership or offering responsibility

## important_text_spans

Copy only short verbatim excerpts that directly support the most important claims.

Each `important_text_spans` item must follow this exact structure:

{
"text": "string",
"section_heading": "string or null",
"reason": "string"
}

Guidelines:

* keep `text` exactly as written in the document
* do not paraphrase the excerpt
* include the exact section heading when one exists
* otherwise return `null` for `section_heading`
* do not invent section headings
* explain briefly what important claim the excerpt supports
* do not copy long paragraphs
* avoid titles unless the title itself is necessary evidence
* avoid boilerplate
* avoid generic descriptions
* avoid repeated evidence
* if `is_material` is false, include no more than 2 spans

## search_keywords

Include only terms likely to improve retrieval.

Include, when relevant:

- important counterparties
- important products or platforms
- strategic initiatives
- deal names
- financial terms
- litigation or regulatory topics
- distinctive business concepts
- important technologies

Guidelines:

- return a maximum of 8 keywords for every document
- prefer the fewest keywords necessary for reliable retrieval
- prioritize distinctive entities, transaction names, products, regulatory matters, and investor-relevant concepts
- do not include generic terms that occur in most Infosys documents
- do not include administrative terms
- do not include document dates unless the date is itself likely to be searched
- do not include narrow operational details unlikely to appear in an investor question
- avoid synonyms, minor variations, and keywords already covered by a broader distinctive phrase

## processing_notes

Briefly explain only:

* unusual extraction decisions
* important exclusions
* genuine ambiguities
* missing or corrupted document content
* formatting or document-quality problems
* reasons a potentially relevant field could not be populated

Return an empty string if no note is necessary.

Do not restate the detailed summary.

Do not use `processing_notes` to explain ordinary decisions already covered by these instructions.
