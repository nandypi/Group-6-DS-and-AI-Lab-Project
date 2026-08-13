"""Quick setup script for hybrid retrieval (Chroma + BM25 + RRF).

Run this script to:
1. Install missing dependencies
2. Build BM25 index
3. Test the hybrid retriever
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EMBEDDINGS_FOLDER = PROJECT_ROOT / "embeddings_script"


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(text.center(80))
    print("=" * 80)


def run_command(cmd, description):
    """Run a shell command and report status."""
    print(f"\n▶ {description}...")
    try:
        result = subprocess.run(cmd, shell=True, cwd=str(EMBEDDINGS_FOLDER))
        if result.returncode == 0:
            print(f"✓ {description} completed successfully.")
            return True
        else:
            print(f"✗ {description} failed (exit code: {result.returncode})")
            return False
    except Exception as exc:
        print(f"✗ {description} encountered an error: {exc}")
        return False


def main():
    """Execute the setup workflow."""
    print_header("HYBRID RETRIEVAL SETUP")

    # Step 1: Check Chroma index
    print_header("Step 1: Verify Chroma Index")
    chroma_db = EMBEDDINGS_FOLDER / "chroma_db"
    if chroma_db.exists():
        print("✓ Chroma database found at chroma_db/")
    else:
        print("⚠ Chroma database not found.")
        print("You may need to run: python index_documents.py")

    # Step 2: Build BM25 index
    print_header("Step 2: Build BM25 Index")
    bm25_index = EMBEDDINGS_FOLDER / "bm25_index.pkl"
    bm25_docs = EMBEDDINGS_FOLDER / "bm25_docs.pkl"

    if bm25_index.exists() and bm25_docs.exists():
        print("✓ BM25 index already exists.")
        rebuild = input("Rebuild index? (y/n): ").lower()
        if rebuild == "y":
            success = run_command(
                f"{sys.executable} bm25_indexer.py --force",
                "Building BM25 index with --force"
            )
        else:
            success = True
    else:
        print("✗ BM25 index not found. Building now...")
        success = run_command(
            f"{sys.executable} bm25_indexer.py",
            "Building BM25 index"
        )

    if not success:
        print("\nSetup incomplete. Fix the error above and try again.")
        sys.exit(1)

    # Step 3: Test retriever
    print_header("Step 3: Test Hybrid Retriever")
    print("\nTesting retrieve1.py with a sample question...")
    test_code = """
import sys
sys.path.insert(0, '.')
from retrieve1 import answer_question

try:
    print("Testing with: 'What are the key financial metrics?'")
    result = answer_question('What are the key financial metrics?')
    print(f"✓ Retrieval successful!")
    print(f"  Answer preview: {result['answer'][:100]}...")
    print(f"  Citations: {len(result['citations'])} documents")
    print(f"  Total latency: {result['timings'].get('total', 0):.2f}s")
except Exception as e:
    print(f"✗ Retrieval failed: {e}")
    import traceback
    traceback.print_exc()
"""

    result = subprocess.run(
        [sys.executable, "-c", test_code],
        cwd=str(EMBEDDINGS_FOLDER),
        capture_output=False
    )

    if result.returncode == 0:
        print("\n✓ All setup steps completed successfully!")
        print("\nNext steps:")
        print("1. Run: python retrieve1.py (interactive mode)")
        print("2. Or update backend/app.py to use retrieve1.answer_question")
        print("3. See HYBRID_RETRIEVAL_SETUP.md for full documentation")
    else:
        print("\n⚠ Test encountered issues. Check the output above.")

    print_header("Setup Complete")


if __name__ == "__main__":
    os.chdir(PROJECT_ROOT)
    main()
