"""Langfuse-based evaluator for automatic RAG response quality scoring."""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langfuse import Langfuse
from langfuse import observe

# Load environment variables
load_dotenv()


@dataclass
class QualityScore:
    """Quality score result from evaluator."""
    score: float  # 1-10 scale
    reasoning: str
    dimensions: Dict[str, float]  # Breakdown by dimension


class LangfuseEvaluator:
    """
    Evaluator agent that uses LLM-as-a-Judge to automatically score RAG responses.
    
    Uses Langfuse's built-in evaluation capabilities to score responses on a 1-10 scale.
    """
    
    def __init__(self, llm_model: str = "gpt-4o-mini"):
        """
        Initialize the Langfuse evaluator.
        
        Args:
            llm_model: LLM model to use as judge (default: gpt-4o-mini)
        """
        self.llm_model = llm_model
        
        # Initialize Langfuse client
        self.langfuse = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
        
        # Initialize judge LLM
        self._initialize_judge_llm()
        
        # Create evaluation prompt
        self._create_evaluation_prompt()
    
    def _initialize_judge_llm(self):
        """Initialize the LLM that will act as judge."""
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_API_BASE")
        
        if base_url:
            self.judge_llm = ChatOpenAI(
                model=self.llm_model,
                openai_api_key=api_key,
                openai_api_base=base_url,
                temperature=0.0,  # Deterministic scoring
            )
        else:
            self.judge_llm = ChatOpenAI(
                model=self.llm_model,
                temperature=0.0,  # Deterministic scoring
            )
    
    def _create_evaluation_prompt(self):
        """Create the evaluation prompt for LLM-as-a-Judge."""
        self.evaluation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert evaluator for RAG (Retrieval Augmented Generation) chatbot responses.

Your task is to evaluate the quality of a chatbot response based on the original user query.

IMPORTANT: This is a RAG system that only answers based on its knowledge base. 

Evaluate the response on a scale of 1-10 based on these criteria:

1. **Relevance** (30%): Does the response directly address the user's query?
   - If the response directly answers the question with relevant information, score 8-10
   - If the response says "I don't know" or "I don't have information", it IS relevant because it addresses the query by explaining it cannot be answered - score 7-9
   - Score 1-3 only if the response is completely off-topic or doesn't address the query at all

2. **Accuracy** (25%): Is the information factually correct and reliable?
   - If the response provides accurate information that answers the question, score 8-10
   - "I don't have information" responses are HIGHLY ACCURATE when the knowledge base truly doesn't contain the information - score 8-10
   - Score 1-3 if the response makes up false information or provides incorrect details

3. **Completeness** (20%): Does the response fully answer the query or leave important gaps?
   - If the response fully answers the question with all relevant details, score 8-10
   - If the response answers the question but misses some details, score 6-7
   - "I don't know" responses don't answer the question, but that's expected when information isn't available - score 5-7
   - Score 1-3 if the response claims to answer but leaves critical gaps

4. **Clarity** (15%): Is the response clear, well-structured, and easy to understand?
   - If the response is well-organized, clear, and easy to follow, score 8-10
   - Score 5-7 if the response is somewhat unclear or poorly structured
   - Score 1-3 if the response is confusing or hard to understand

5. **Helpfulness** (10%): Is the response actionable and useful to the user?
   - If the response provides useful, actionable information that helps the user, score 8-10
   - "I don't know" responses that suggest alternatives (rephrasing, contacting support) are helpful - score 7-9
   - Score 1-3 if the response is unhelpful or misleading

CRITICAL RULES:
1. When a response directly answers the user's question with accurate information from the knowledge base, it should score HIGH (7-10 overall). Do NOT penalize it for not mentioning "platform" or "context" if the information is clearly relevant to the query.
2. When a response honestly states it doesn't have information about a topic that's outside the knowledge base scope, this is CORRECT behavior. Score it highly on accuracy (8-10) and relevance (7-9), moderately on completeness (5-7), and well on clarity and helpfulness (7-9).

Provide:
- An overall score (1-10, where 10 is excellent)
- Brief reasoning for the score
- Individual scores for each dimension (1-10)

Be strict but fair. A score of 7-8 indicates good quality, 9-10 is excellent, 5-6 is acceptable but has issues, and below 5 has significant problems."""),
            ("human", """User Query:
{query}

Chatbot Response:
{response}

Evaluate this response and provide a JSON object with:
- "score": overall score (1-10)
- "reasoning": brief explanation
- "dimensions": {{
    "relevance": score (1-10),
    "accuracy": score (1-10),
    "completeness": score (1-10),
    "clarity": score (1-10),
    "helpfulness": score (1-10)
}}

JSON:"""),
        ])
        
        self.parser = JsonOutputParser()
    
    @observe(name="langfuse_evaluator_score_response")
    def evaluate_response(
        self,
        query: str,
        response: str,
        trace_id: Optional[str] = None,
    ) -> QualityScore:
        """
        Evaluate a RAG response and assign a quality score.
        
        The @observe decorator automatically creates a trace for this evaluation.
        The score will be linked to the current trace context.
        
        Args:
            query: Original user query
            response: Chatbot response to evaluate
            trace_id: Optional Langfuse trace ID to attach score to (if not provided, uses current trace)
            
        Returns:
            QualityScore with score, reasoning, and dimension breakdown
        """
        try:
            # Create evaluation chain
            evaluation_chain = (
                self.evaluation_prompt
                | self.judge_llm
                | self.parser
            )
            
            # Run evaluation
            result = evaluation_chain.invoke({
                "query": query,
                "response": response,
            })
            
            # Parse result
            score = float(result.get("score", 5.0))
            reasoning = result.get("reasoning", "No reasoning provided")
            dimensions = result.get("dimensions", {})
            
            # Ensure score is in valid range
            score = max(1.0, min(10.0, score))
            
            quality_score = QualityScore(
                score=score,
                reasoning=reasoning,
                dimensions=dimensions,
            )
            
            # Store score in Langfuse
            # The @observe decorator creates a trace, and we can get the trace ID from it
            self._store_score_in_langfuse(
                score=score,
                reasoning=reasoning,
                dimensions=dimensions,
                query=query,
                response=response,
                trace_id=trace_id,
            )
            
            return quality_score
            
        except Exception as e:
            # Fallback to default score on error
            print(f"Warning: Evaluation failed: {e}")
            return QualityScore(
                score=5.0,
                reasoning=f"Evaluation error: {str(e)}",
                dimensions={},
            )
    
    def _store_score_in_langfuse(
        self,
        score: float,
        reasoning: str,
        dimensions: Dict[str, float],
        query: str,
        response: str,
        trace_id: Optional[str] = None,
    ):
        """
        Store the evaluation score in Langfuse.
        
        Uses Langfuse's score API. If trace_id is not provided, the score
        will be linked to the current trace created by @observe decorator.
        
        Args:
            score: Overall quality score (1-10)
            reasoning: Reasoning for the score
            dimensions: Dimension breakdown
            query: Original query
            response: Response that was evaluated
            trace_id: Optional trace ID to attach to
        """
        try:
            # Use Langfuse's score_current_trace to score the current trace
            # created by the @observe decorator
            if trace_id:
                # If trace_id is provided, use create_score
                self.langfuse.create_score(
                    name="rag_quality_score",
                    value=score,
                    trace_id=trace_id,
                    comment=reasoning,
                )
            else:
                # Score the current trace (created by @observe decorator)
                self.langfuse.score_current_trace(
                    name="rag_quality_score",
                    value=score,
                    comment=reasoning,
                )
            
        except Exception as e:
            print(f"Warning: Failed to store score in Langfuse: {e}")
    
    def evaluate_batch(
        self,
        queries_and_responses: list[tuple[str, str]],
    ) -> list[QualityScore]:
        """
        Evaluate multiple responses in batch.
        
        Args:
            queries_and_responses: List of (query, response) tuples
            
        Returns:
            List of QualityScore objects
        """
        results = []
        for query, response in queries_and_responses:
            score = self.evaluate_response(query, response)
            results.append(score)
        return results

