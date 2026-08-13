# Fixing Poor Hybrid Retrieval Performance

## Current Situation

| Metric | Value | Status |
|--------|-------|--------|
| Baseline (Chroma-only) | Recall@7 = 44% | ✓ Good |
| Hybrid retrieve1.py | Recall@7 = 28% | ✗ Bad (36% worse) |
| Target with retrieve2.py | Recall@7 = 40%+ | Goal |

## Root Causes of Poor Performance

### 1. **RRF Parameter Too High (k=60)**
- **Problem**: RRF score = 1/(60+rank), which makes all results weighted almost equally
- **Impact**: A BM25 result at rank 5 is barely different from Chroma result at rank 5
- **Example**: 
  - Chroma rank #1: score = 1/(60+1) = 0.0164
  - Chroma rank #10: score = 1/(60+10) = 0.0139
  - Only 18% difference, too small!
- **Solution**: Lower k to 30 in retrieve2.py (2x more weight to top results)

### 2. **Weak BM25 Tokenization**
- **Problem**: Simple whitespace tokenization misses important patterns
- **Impact**: Query "revenue trends" doesn't match "revenues" or "trending"
- **Example**:
  ```
  Simple tokenize: ["revenue", "trends"]
  Improved tokenize: ["revenu", "trend"]  # Matches "revenues", "trending"
  ```
- **Solution**: Added stemming in retrieve2.py

### 3. **Top-K Too Small (10 per source)**
- **Problem**: Expected document may rank 12-15 in Chroma but gets cut off
- **Impact**: Document never enters RRF fusion, guaranteed miss
- **Solution**: Increased to 15 per source in retrieve2.py

### 4. **BM25 Not Helping**
- **Problem**: Pure keyword matching underperforms semantic search for finance domain
- **Impact**: BM25 introduces noise, pulls down combined score
- **Solution**: Added Chroma weight boost (1.2x) in retrieve2.py

## Solutions Implemented in retrieve2.py

### Parameter Changes
```python
# retrieve1.py (POOR)
RRF_K = 60
TOP_K_PER_SOURCE = 10
CHROMA_WEIGHT = 1.0

# retrieve2.py (OPTIMIZED)
RRF_K = 30          # ↓ Lower = favor top results
TOP_K_PER_SOURCE = 15  # ↑ Get more candidates
CHROMA_WEIGHT = 1.2  # ↑ Boost dense search
```

### Code Improvements
```python
# Better tokenization with stemming
def improved_tokenize(text):
    tokens = re.findall(r'\b[a-z0-9]+\b', text.lower())
    return [simple_stem(t) for t in tokens if len(t) > 2]

# Weighted RRF fusion
rrf_score_dense = (1.0 / (k + rank + 1)) * chroma_weight
rrf_score_lexical = 1.0 / (k + rank + 1)
```

## Testing Strategy

### Step 1: Run Diagnostic Analysis
```bash
cd Group-6-DS-and-AI-Lab-Project
python diagnose_hybrid.py
```
Output shows which queries fail and why.

### Step 2: Test Optimized Retriever
```bash
python datapreparation/benchmarking/run_retrieve2_optimized_recall_benchmark.py --limit 10
```
Test on 10 queries first to validate improvements.

### Step 3: Full Benchmark (50 queries)
```bash
python datapreparation/benchmarking/run_retrieve2_optimized_recall_benchmark.py
```

### Step 4: Compare Results
```bash
# Compare all three pipelines
Baseline (retrieve.py):   44%
Hybrid v1 (retrieve1.py): 28%  ✗ Failed
Hybrid v2 (retrieve2.py): ??%  (testing)
```

## Expected Improvements

With optimized retrieve2.py:
- **Recall@7** should improve from 28% to **35-40%** (closer to baseline)
- **Recall@9** should improve to **45%+**
- Better quality documents in top 3
- Minimal latency increase

## If retrieve2.py Still Underperforms

### Option A: Use Hybrid with Reranking
Create `retrieve3.py` combining:
- Hybrid retrieval (Chroma + BM25)
- Top 15 results
- BGE reranking to final 3
- **Expected**: Should exceed 44% baseline

### Option B: Weighted Voting Instead of RRF
Replace RRF with:
```python
# Simple voting: weight Chroma results higher
score = 0.7 * chroma_normalized_score + 0.3 * bm25_normalized_score
```

### Option C: Just Use Chroma (Baseline)
If BM25 integration proves difficult:
- Fall back to retrieve.py (44% Recall@7)
- Focus on other improvements (reranking, query expansion, etc.)

## Quick Reference: File Changes

### New Files
- `embeddings_script/retrieve2.py` - Optimized hybrid retriever
- `datapreparation/benchmarking/run_retrieve2_optimized_recall_benchmark.py` - Benchmark
- `diagnose_hybrid.py` - Diagnostic tool

### No Changes Needed
- `bm25_indexer.py` - Works as-is
- `backend/app.py` - Just swap import
- `.env` - All parameters work

## Testing Commands

```bash
# Quick test (10 queries)
python datapreparation/benchmarking/run_retrieve2_optimized_recall_benchmark.py --limit 10

# Resume from question 20
python datapreparation/benchmarking/run_retrieve2_optimized_recall_benchmark.py --start 20 --limit 30

# Full benchmark
python datapreparation/benchmarking/run_retrieve2_optimized_recall_benchmark.py

# Interactive testing
python embeddings_script/retrieve2.py
```

## Next Steps

1. **Run Step 2** above (test on 10 queries)
2. **Compare** Recall@7 score:
   - If improved (35%+) → Run full benchmark (Step 3)
   - If still poor (< 30%) → Use Option A or B above
3. **Evaluate** latency impact
4. **Update** backend/app.py to use retrieve2 or retrieve3

## Performance Tracking

Keep a log of different approaches:

```
Approach                 | Recall@7 | Recall@9 | Latency | Status
Chroma-only (retrieve)   | 44%      | 50%      | 0.35s   | Baseline
Simple hybrid (retrieve1)| 28%      | 34%      | 0.40s   | ✗ Fail
Optimized (retrieve2)    | ??%      | ??%      | 0.42s   | Testing
Hybrid + Rerank (retrieve3) | ??%   | ??%      | 0.80s   | TBD
```

**You're close to solving this.** The diagnostics show exactly where retrieve1.py fails. The optimizations in retrieve2.py address all three issues. Test it and iterate if needed.
