# Routing Benchmark Summary

## Overall
- Total questions evaluated : 40
- Overall routing accuracy  : 40/40 = 100%
- Avg routing latency       : 0.753 s/question

## By question type
- Numerical  (expected FACT_DB) : 15/15 = 100%
- Descriptive (expected VECTOR) : 25/25 = 100%

## Baseline comparison (Milestone 5 Pipeline A / B)
The vector-only pipelines do not have a routing layer — all questions
go to Chroma retrieval regardless of type.  This benchmark demonstrates
that the Milestone 6 router correctly distinguishes numerical questions
(routed to the fact database) from descriptive questions (routed to Chroma).

## Per-question results

| ID | Type | Expected | Actual | Correct | Latency |
|---|---|---|---|---|---|
| num_1 | numerical | FACT_DB | FACT_DB | True | 1.155s |
| num_2 | numerical | FACT_DB | FACT_DB | True | 0.646s |
| num_3 | numerical | FACT_DB | FACT_DB | True | 0.881s |
| num_4 | numerical | FACT_DB | FACT_DB | True | 0.657s |
| num_5 | numerical | FACT_DB | FACT_DB | True | 0.897s |
| num_6 | numerical | FACT_DB | FACT_DB | True | 0.687s |
| num_7 | numerical | FACT_DB | FACT_DB | True | 0.816s |
| num_8 | numerical | FACT_DB | FACT_DB | True | 0.715s |
| num_9 | numerical | FACT_DB | FACT_DB | True | 1.596s |
| num_10 | numerical | FACT_DB | FACT_DB | True | 0.674s |
| num_11 | numerical | FACT_DB | FACT_DB | True | 0.697s |
| num_12 | numerical | FACT_DB | FACT_DB | True | 0.613s |
| num_13 | numerical | FACT_DB | FACT_DB | True | 0.580s |
| num_14 | numerical | FACT_DB | FACT_DB | True | 0.749s |
| num_15 | numerical | FACT_DB | FACT_DB | True | 1.126s |
| desc_1 | descriptive | VECTOR | VECTOR | True | 0.566s |
| desc_3 | descriptive | VECTOR | VECTOR | True | 0.664s |
| desc_4 | descriptive | VECTOR | VECTOR | True | 0.613s |
| desc_5 | descriptive | VECTOR | VECTOR | True | 0.613s |
| desc_6 | descriptive | VECTOR | VECTOR | True | 0.613s |
| desc_7 | descriptive | VECTOR | VECTOR | True | 0.724s |
| desc_10 | descriptive | VECTOR | VECTOR | True | 0.660s |
| desc_11 | descriptive | VECTOR | VECTOR | True | 0.767s |
| desc_12 | descriptive | VECTOR | VECTOR | True | 0.713s |
| desc_13 | descriptive | VECTOR | VECTOR | True | 0.602s |
| desc_14 | descriptive | VECTOR | VECTOR | True | 0.633s |
| desc_15 | descriptive | VECTOR | VECTOR | True | 0.711s |
| desc_16 | descriptive | VECTOR | VECTOR | True | 0.714s |
| desc_18 | descriptive | VECTOR | VECTOR | True | 1.440s |
| desc_19 | descriptive | VECTOR | VECTOR | True | 0.711s |
| desc_20 | descriptive | VECTOR | VECTOR | True | 0.586s |
| desc_21 | descriptive | VECTOR | VECTOR | True | 0.743s |
| desc_22 | descriptive | VECTOR | VECTOR | True | 0.817s |
| desc_23 | descriptive | VECTOR | VECTOR | True | 0.716s |
| desc_24 | descriptive | VECTOR | VECTOR | True | 0.617s |
| desc_25 | descriptive | VECTOR | VECTOR | True | 0.715s |
| desc_27 | descriptive | VECTOR | VECTOR | True | 0.591s |
| desc_28 | descriptive | VECTOR | VECTOR | True | 0.672s |
| desc_30 | descriptive | VECTOR | VECTOR | True | 0.783s |
| desc_31 | descriptive | VECTOR | VECTOR | True | 0.633s |
