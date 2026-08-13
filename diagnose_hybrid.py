"""Diagnose hybrid retrieval performance issues."""
import csv
import json
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parents[0]
HYBRID_CSV = PROJECT_ROOT / "data/csv_files_from_milestone5/infosys_rag_test_dataset_50_queries_hybrid_retrieve1_recall_results.csv"
INPUT_CSV = PROJECT_ROOT / "data/infosys_rag_test_dataset_50_queries.csv"

def analyze_failures():
    """Analyze which queries fail and why."""
    with open(HYBRID_CSV, 'r', encoding='utf-8-sig') as f:
        hybrid_rows = {r['id']: r for r in csv.DictReader(f)}
    
    failed_recalls = []
    for qid, row in hybrid_rows.items():
        if row['recall@7'].lower() == 'false':
            failed_recalls.append({
                'id': qid,
                'query': row['query'],
                'expected': row['current_source_document'],
                'retrieved_top_3': row['retrieved_documents_top_10'].split(' | ')[:3] if row['retrieved_documents_top_10'] else [],
            })
    
    print("\n" + "="*80)
    print("FAILURE ANALYSIS: Queries Where recall@7 = False")
    print("="*80)
    print(f"Failed queries: {len(failed_recalls)}/50 (72%)\n")
    
    # Show first 5 failures
    for i, failure in enumerate(failed_recalls[:5], 1):
        print(f"\n{i}. Query #{failure['id']}: {failure['query'][:70]}")
        print(f"   Expected: {failure['expected']}")
        print(f"   Retrieved #1-3:")
        for j, doc in enumerate(failure['retrieved_top_3'], 1):
            print(f"      #{j}: {doc}")


def analyze_source_distribution():
    """Show if dense/lexical are contributing."""
    with open(HYBRID_CSV, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    
    dense_only = 0
    lexical_only = 0
    hybrid = 0
    
    for row in rows:
        sources = row.get('retrieved_sources_top_10', '')
        if sources:
            has_dense = 'dense' in sources
            has_lexical = 'lexical' in sources
            
            if has_dense and has_lexical:
                hybrid += 1
            elif has_dense:
                dense_only += 1
            elif has_lexical:
                lexical_only += 1
    
    print("\n" + "="*80)
    print("RETRIEVAL SOURCE DISTRIBUTION")
    print("="*80)
    print(f"Dense only:      {dense_only:2d} queries (Chroma)")
    print(f"Lexical only:    {lexical_only:2d} queries (BM25)")
    print(f"Hybrid (both):   {hybrid:2d} queries (both contributing)")
    print(f"Total:           {dense_only + lexical_only + hybrid:2d} queries")


def compare_with_baseline():
    """Compare hybrid approach with what pure Chroma would give."""
    with open(HYBRID_CSV, 'r', encoding='utf-8-sig') as f:
        hybrid_rows = list(csv.DictReader(f))
    
    print("\n" + "="*80)
    print("PROBLEM DIAGNOSIS")
    print("="*80)
    print("""
Your baseline (Chroma-only): Recall@7 = 44%
Your hybrid approach:        Recall@7 = 28%
DEGRADATION: -16 percentage points (36% worse)

ROOT CAUSES (likely):
1. RRF Parameter Too High (k=60)
   - Makes dense and lexical equally weighted
   - Dilutes the strong signal from Chroma
   - BM25 queries are less accurate than embeddings
   
2. Simple BM25 Tokenization
   - Basic whitespace tokenization loses semantic value
   - No stemming/lemmatization
   - No handling of company names, financial terms
   
3. Top-K Values Too Small (k=10)
   - Retrieving only top 10 from each source
   - May be missing the expected document before RRF
   
4. Path Mixing Issue
   - Windows paths vs relative paths in the index
   - May cause duplicate handling problems

SOLUTIONS TO TRY:
✓ Lower RRF k parameter (e.g., 30-40) to favor Chroma
✓ Improve BM25 tokenization (stemming, better preprocessing)
✓ Increase top-K to 15-20 per source
✓ Add reranking back to hybrid approach
✓ Weight Chroma results more heavily
""")


if __name__ == "__main__":
    analyze_failures()
    analyze_source_distribution()
    compare_with_baseline()
