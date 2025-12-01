# Golden Dataset

This directory contains golden (ground truth) datasets for evaluating the multi-agent RAG chatbot.

## Dataset Structure

Each golden dataset file is a JSONL (JSON Lines) file where each line is a JSON object representing a test case:

```json
{
  "id": "unique_test_id",
  "query": "User's question",
  "expected_agent": "finance|hr|legal|tech|general_knowledge",
  "expected_agents": ["finance", "tech"],  // For multi-agent queries
  "expected_routing_mode": "single|multi_parallel|multi_sequential",
  "expected_sources": [
    {
      "handbook": "finance_handbook",
      "content_snippet": "Expected content snippet from source",
      "min_similarity": 0.78
    }
  ],
  "expected_response_keywords": ["payment", "invoice", "billing"],  // Keywords that should appear in response
  "metadata": {
    "category": "billing",
    "difficulty": "easy|medium|hard",
    "description": "What this test case validates"
  }
}
```

## Dataset Files

- `finance.jsonl` - Finance agent test cases
- `hr.jsonl` - HR agent test cases
- `legal.jsonl` - Legal agent test cases
- `tech.jsonl` - Tech agent test cases
- `general_knowledge.jsonl` - General knowledge agent test cases
- `multi_agent.jsonl` - Multi-agent routing test cases
- `routing.jsonl` - Routing accuracy test cases

## Usage

See `src/evaluation/` for evaluation framework and tools.

