"""Simple test runner that uses golden datasets and Langfuse evaluator for scoring."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import after adding src to path
from querying.agents import Orchestrator  # type: ignore
from config import MIN_SIMILARITY


def load_golden_dataset(dataset_file: str) -> list[dict]:
    """Load a golden dataset from JSONL file."""
    dataset_path = Path(__file__).parent.parent / "data" / "golden_datasets" / dataset_file
    
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")
    
    test_cases = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                test_cases.append(json.loads(line))
    
    return test_cases


async def run_tests(
    dataset_file: Optional[str] = None,
    min_similarity: float = MIN_SIMILARITY,
    max_tests: Optional[int] = None,
):
    """
    Run tests from golden datasets.
    
    Uses Langfuse evaluator for automatic quality scoring.
    """
    print("=" * 60)
    print("Golden Dataset Test Runner")
    print("=" * 60)
    
    # Initialize orchestrator
    print("\nInitializing orchestrator...")
    orchestrator = Orchestrator()
    print("✓ Orchestrator initialized")
    
    # Load datasets
    if dataset_file:
        datasets = {dataset_file.replace(".jsonl", ""): load_golden_dataset(dataset_file)}
    else:
        # Load all datasets
        datasets_dir = Path(__file__).parent.parent / "data" / "golden_datasets"
        datasets = {}
        for jsonl_file in datasets_dir.glob("*.jsonl"):
            dataset_name = jsonl_file.stem
            datasets[dataset_name] = load_golden_dataset(jsonl_file.name)
    
    print(f"\nLoaded {len(datasets)} dataset(s)")
    
    # Run tests
    total_tests = 0
    total_passed = 0
    
    for dataset_name, test_cases in datasets.items():
        print(f"\n{'=' * 60}")
        print(f"Testing: {dataset_name}")
        print(f"{'=' * 60}")
        
        if max_tests:
            test_cases = test_cases[:max_tests]
        
        passed = 0
        for i, test_case in enumerate(test_cases, 1):
            query = test_case.get("query", "")
            test_id = test_case.get("id", f"{dataset_name}_{i}")
            
            print(f"\n[{i}/{len(test_cases)}] {test_id}")
            print(f"Query: {query[:60]}...")
            
            try:
                # Process query
                response = await orchestrator.process_query_async(
                    query=query,
                    session_id=f"test_{test_id}",
                    min_similarity=min_similarity,
                )
                
                # Quality score is automatically assigned by Langfuse evaluator
                quality_score = response.metadata.get("quality_score")
                quality_reasoning = response.metadata.get("quality_reasoning", "")
                
                if quality_score:
                    print(f"Quality Score: {quality_score}/10")
                    if quality_score >= 7.0:
                        print("✓ PASS (score >= 7.0)")
                        passed += 1
                    else:
                        print(f"✗ FAIL (score < 7.0)")
                        if quality_reasoning:
                            print(f"  Reasoning: {quality_reasoning[:100]}...")
                else:
                    print("⚠ No quality score available")
                
            except Exception as e:
                print(f"✗ ERROR: {e}")
        
        print(f"\n{dataset_name} Results: {passed}/{len(test_cases)} passed")
        total_tests += len(test_cases)
        total_passed += passed
    
    print(f"\n{'=' * 60}")
    print(f"Overall Results: {total_passed}/{total_tests} passed")
    print(f"{'=' * 60}")
    
    return total_passed == total_tests


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run golden dataset tests")
    parser.add_argument("--dataset", type=str, help="Specific dataset file (e.g., finance.jsonl)")
    parser.add_argument("--min-similarity", type=float, default=MIN_SIMILARITY, help="Minimum similarity threshold")
    parser.add_argument("--max-tests", type=int, help="Maximum tests to run")
    
    args = parser.parse_args()
    
    success = asyncio.run(run_tests(
        dataset_file=args.dataset,
        min_similarity=args.min_similarity,
        max_tests=args.max_tests,
    ))
    
    sys.exit(0 if success else 1)

