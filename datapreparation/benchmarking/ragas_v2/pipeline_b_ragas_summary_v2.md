# Pipeline B (with reranking) RAGAS Evaluation Summary

- Evaluator model: `gpt-4o-mini`
- Embedding model: `text-embedding-3-small`
- Pipeline results: `datapreparation/benchmarking/ragas_v2/pipeline_b_answers_v2.csv`
- Reference answers: `datapreparation/benchmarking/ragas_v2/reference_answers_v2_template.csv`
- Successful rows: 49
- Failed rows: 1

## Average scores

- faithfulness: 0.9210
- answer_relevancy: 0.8146
- context_precision: 0.9507
- context_recall: 0.9277

## Lowest average-score questions

- ID 46 (0.2367): What was the total value of large deals Infosys won during fiscal year 2024–25 as reported at the 44th Annual General Meeting?
- ID 4 (0.6555): What FY27 revenue growth guidance has Infosys provided and what structural or macro headwinds are already baked into that outlook?
- ID 8 (0.6667): What reasons does Infosys management give for expecting H1 FY26 to outperform H2, and what assumptions underpin the upper and lower ends of the guidance range?
- ID 5 (0.7046): How does Infosys's valuation compare with peers such as TCS and HCL Technologies on earnings and enterprise value multiples like P/E, PEG, and EV/EBITDA?
- ID 15 (0.7201): What third-party rankings and industry recognitions has Infosys received for its AI and cloud service capabilities as listed in the Q2 FY26 press release?

## Failed rows

- ID 1: 'choices'
