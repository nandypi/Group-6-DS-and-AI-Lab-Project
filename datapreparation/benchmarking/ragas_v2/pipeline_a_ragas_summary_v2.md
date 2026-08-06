# Pipeline A (no reranking) RAGAS Evaluation Summary

- Evaluator model: `gpt-4o-mini`
- Embedding model: `text-embedding-3-small`
- Pipeline results: `datapreparation/benchmarking/ragas_v2/pipeline_a_answers_v2.csv`
- Reference answers: `datapreparation/benchmarking/ragas_v2/reference_answers_v2_template.csv`
- Successful rows: 50
- Failed rows: 0

## Average scores

- faithfulness: 0.8929
- answer_relevancy: 0.8439
- context_precision: 0.9683
- context_recall: 0.8725

## Lowest average-score questions

- ID 46 (0.3638): What was the total value of large deals Infosys won during fiscal year 2024–25 as reported at the 44th Annual General Meeting?
- ID 15 (0.6474): What third-party rankings and industry recognitions has Infosys received for its AI and cloud service capabilities as listed in the Q2 FY26 press release?
- ID 8 (0.6667): What reasons does Infosys management give for expecting H1 FY26 to outperform H2, and what assumptions underpin the upper and lower ends of the guidance range?
- ID 34 (0.6721): What financial losses and reputational damage from AI-related incidents does the Infosys research report document?
- ID 44 (0.7333): What factors have driven Infosys's stronger growth in Europe, and how sustainable does management consider that momentum to be?
