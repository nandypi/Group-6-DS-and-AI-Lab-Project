#!/usr/bin/env python
"""Compare retrieve1 vs retrieve2 behavior."""

from embeddings_script.retrieve1 import retrieve as retrieve1
from embeddings_script.retrieve2 import retrieve as retrieve2
from embeddings_script.retrieve2 import RRF_K as K2, TOP_K_PER_SOURCE as TOP2, CHROMA_WEIGHT
from embeddings_script.retrieve1 import RRF_K as K1

test_q = "What are Infosys revenue and earnings?"

print("="*70)
print("RETRIEVE1 (Baseline 28% Recall@7)")
print(f"Parameters: RRF_K={K1}, TOP_K=10, CHROMA_WEIGHT=1.0")
print("="*70)
try:
    r1 = retrieve1(test_q)
    print(f"Retrieved {len(r1)} results\n")
    print("Top 5 Results:")
    for i, doc in enumerate(r1[:5]):
        filename = doc.get("filename", "unknown")
        score = doc.get("fusion_score", 0)
        sources = doc.get("sources", [])
        print(f"{i+1}. {filename}")
        print(f"   Fusion Score: {score:.6f}")
        print(f"   Sources: {sources}\n")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

print("\n" + "="*70)
print("RETRIEVE2 (Optimized - Got 2% Recall@7!!)")
print(f"Parameters: RRF_K={K2}, TOP_K={TOP2}, CHROMA_WEIGHT={CHROMA_WEIGHT}")
print("="*70)
try:
    r2 = retrieve2(test_q)
    print(f"Retrieved {len(r2)} results\n")
    print("Top 5 Results:")
    for i, doc in enumerate(r2[:5]):
        filename = doc.get("filename", "unknown")
        score = doc.get("fusion_score", 0)
        sources = doc.get("sources", [])
        print(f"{i+1}. {filename}")
        print(f"   Fusion Score: {score:.6f}")
        print(f"   Sources: {sources}\n")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

print("\n" + "="*70)
print("DIAGNOSTIC SUMMARY")
print("="*70)
print("If retrieve2 is getting different results, likely issues:")
print("1. RRF fusion is reordering incorrectly")
print("2. TOP_K=15 is pulling in low-quality candidates")
print("3. CHROMA_WEIGHT boost is having unintended side effects")
print("4. SIMPLE ISSUE: Maybe the parameter didn't get passed correctly?")
