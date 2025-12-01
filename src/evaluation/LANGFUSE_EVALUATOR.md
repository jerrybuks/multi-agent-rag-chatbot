# Langfuse Automatic Evaluator

This document describes the automatic quality evaluation system integrated with Langfuse.

## Overview

The system automatically evaluates every RAG response using an LLM-as-a-Judge approach, assigning a quality score from 1-10 and storing it in Langfuse for monitoring and analysis.

## How It Works

1. **Automatic Evaluation**: After each query is processed, the `LangfuseEvaluator` automatically scores the response
2. **LLM-as-a-Judge**: Uses GPT-4o-mini (or configured model) to evaluate response quality
3. **Multi-Dimensional Scoring**: Evaluates on 5 dimensions:
   - **Relevance** (30%): Does it address the query?
   - **Accuracy** (25%): Is it factually correct?
   - **Completeness** (20%): Does it fully answer the query?
   - **Clarity** (15%): Is it clear and well-structured?
   - **Helpfulness** (10%): Is it actionable and useful?

4. **Langfuse Integration**: Scores are automatically stored in Langfuse and attached to traces

## Score Scale

- **9-10**: Excellent quality
- **7-8**: Good quality
- **5-6**: Acceptable but has issues
- **Below 5**: Significant problems

## API Response

The quality score is included in the API response:

```json
{
  "content": "...",
  "quality_score": 8.5,
  "quality_reasoning": "The response directly addresses the query with accurate information...",
  "metadata": {
    "quality_dimensions": {
      "relevance": 9.0,
      "accuracy": 8.5,
      "completeness": 8.0,
      "clarity": 8.5,
      "helpfulness": 8.0
    }
  }
}
```

## Viewing Scores in Langfuse

1. Navigate to your Langfuse dashboard
2. Go to "Scores" section
3. Filter by score name: `rag_quality_score`
4. View scores attached to traces and observations
5. Analyze trends and identify low-quality responses

## Configuration

The evaluator uses the same LLM model as the orchestrator (default: `gpt-4o-mini`). To change:

```python
# In orchestrator.py
self.evaluator = LangfuseEvaluator(llm_model="gpt-4")  # Use GPT-4 for more accurate scoring
```

## Benefits

1. **Automatic Monitoring**: Every response is automatically evaluated
2. **Quality Tracking**: Track quality trends over time in Langfuse
3. **Issue Detection**: Identify low-quality responses automatically
4. **No Manual Work**: Fully automated, no human annotation needed
5. **Multi-Dimensional**: Understand which aspects need improvement

## Performance

- Evaluation adds ~1-2 seconds per query (LLM call for scoring)
- Runs asynchronously and doesn't block the main response
- If evaluation fails, the response still returns (graceful degradation)

