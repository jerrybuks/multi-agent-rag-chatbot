"""
Orchestrator for routing queries to specialist agents.

The orchestrator uses an LLM to determine which specialist agent should handle
a given query, supports multi-agent processing, and manages context bundling
for continuous conversations.
"""

import os
import asyncio
from typing import Dict, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langfuse import Langfuse, observe, get_client
from langfuse.langchain import CallbackHandler

# Load environment variables
load_dotenv()

from config import LLM_MODEL
from querying.agents.specialist_agents import create_agent, BaseAgent
from querying.agents.base_agent import AgentResponse
from querying.tools.vector_store_manager import VectorStoreManager
from utils.llm import initialize_llm


class RoutingMode(Enum):
    """Routing mode for query processing."""
    SINGLE = "single"
    MULTI_PARALLEL = "multi_parallel"
    MULTI_SEQUENTIAL = "multi_sequential"


@dataclass
class ConversationContext:
    """Context for maintaining conversation continuity."""
    session_id: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    agent_history: List[str] = field(default_factory=list)  # Which agents handled queries
    last_agent: Optional[str] = None
    
    def add_message(self, role: str, content: str):
        """Add a message to conversation history."""
        self.messages.append({"role": role, "content": content})
        # Keep last 20 messages for context
        if len(self.messages) > 20:
            self.messages = self.messages[-20:]
    
    def get_recent_history(self, limit: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation history."""
        return self.messages[-limit:]


@dataclass
class AgentConfig:
    """Configuration for a specialist agent."""
    name: str
    description: str
    handbook_name: str  # Maps to the handbook/vector store name


class AgentRegistry:
    """
    Registry of available specialist agents.
    
    To add a new agent, simply add it to the AGENTS dictionary.
    To remove an agent, remove it from the AGENTS dictionary.
    """
    
    AGENTS: Dict[str, AgentConfig] = {
        "finance": AgentConfig(
            name="finance",
            description="Handles queries about billing, payments, invoices, pricing, refunds, and financial matters",
            handbook_name="finance_handbook"
        ),
        "hr": AgentConfig(
            name="hr",
            description="Handles queries about account management, user support, subscriptions, account settings, and user-related issues",
            handbook_name="hr_handbook"
        ),
        "legal": AgentConfig(
            name="legal",
            description="Handles queries about terms of service, privacy policies, compliance, legal agreements, and regulatory matters",
            handbook_name="legal_handbook"
        ),
        "tech": AgentConfig(
            name="tech",
            description="Handles queries about API documentation, integrations, technical support, troubleshooting, and technical implementation",
            handbook_name="tech_handbook"
        ),
        "general_knowledge": AgentConfig(
            name="general_knowledge",
            description="Handles general company information, product overview, company policies, and serves as a fallback for queries that don't fit other categories",
            handbook_name="general_handbook"
        ),
    }
    
    @classmethod
    def get_agent(cls, agent_name: str) -> Optional[AgentConfig]:
        """Get agent configuration by name."""
        return cls.AGENTS.get(agent_name.lower())
    
    @classmethod
    def list_agents(cls) -> Dict[str, AgentConfig]:
        """List all registered agents."""
        return cls.AGENTS.copy()
    
    @classmethod
    def get_agent_descriptions(cls) -> str:
        """Get formatted descriptions of all agents for LLM prompts."""
        descriptions = []
        for agent_name, agent_config in cls.AGENTS.items():
            descriptions.append(
                f"- {agent_name.upper()}: {agent_config.description}"
            )
        return "\n".join(descriptions)


@dataclass
class OrchestratorResponse:
    """Response from the orchestrator."""
    content: str
    agents_used: List[str]
    responses: List[AgentResponse] = field(default_factory=list)
    routing_mode: RoutingMode = RoutingMode.SINGLE
    metadata: Dict = field(default_factory=dict)


class Orchestrator:
    """
    Orchestrator that routes queries to appropriate specialist agents.
    
    Features:
    - Single agent routing for simple queries
    - Multi-agent detection and parallel/sequential processing
    - Context bundling for continuous conversations
    - Error handling and fallback strategies
    - Langfuse instrumentation
    """
    
    def __init__(self, llm_model: str = None):
        """
        Initialize the orchestrator.
        
        Args:
            llm_model: LLM model to use for routing. Defaults to config LLM_MODEL.
        """
        self.llm_model = llm_model or LLM_MODEL
        self.agent_registry = AgentRegistry()
        
        # Initialize Langfuse from environment variables only
        self.langfuse = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
        
        # Initialize Langfuse callback handler for LangChain
        # CallbackHandler reads from environment variables automatically
        self.langfuse_handler = CallbackHandler()
        
        # Initialize LLM
        self._initialize_llm()
        
        # Create prompts
        self._create_prompts()
        
        # Create LCEL chains for routing and multi-agent detection
        self._create_chains()
        
        # Preload all vector stores at startup
        handbook_names = [
            config.handbook_name 
            for config in self.agent_registry.AGENTS.values()
        ]
        self.vector_store_manager = VectorStoreManager(handbook_names)
        
        # Agent instances cache (lazy loading)
        self._agent_instances: Dict[str, BaseAgent] = {}
        
        # Conversation contexts (session-based)
        self._conversation_contexts: Dict[str, ConversationContext] = {}
    
    def _initialize_llm(self):
        """Initialize the LLM with Langfuse instrumentation."""
        self.llm = initialize_llm(
                model=self.llm_model,
            langfuse_handler=self.langfuse_handler
        )
    
    def _create_prompts(self):
        """Create prompt templates for routing and multi-agent detection."""
        # Single agent routing prompt
        self.routing_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an intelligent query router for a multi-agent customer support system.

Your task is to analyze customer queries and determine which specialist agent should handle them.

Available agents:
{agent_descriptions}

IMPORTANT ROUTING RULE:
- **ALWAYS prefer a specialist agent (finance, hr, legal, tech) over general_knowledge when there is ANY ambiguity**
- Only route to "general_knowledge" if the query is clearly about general company information, company overview, or truly doesn't fit any specialist domain
- When in doubt between a specialist agent and general_knowledge, choose the specialist agent

Instructions:
1. Analyze the query carefully to understand its intent and subject matter
2. Match the query to the most appropriate specialist agent based on their descriptions
3. If there's any connection to a specialist domain (even if weak), route to that specialist agent
4. Only route to "general_knowledge" if the query is clearly general company information with no specialist domain connection
5. Respond with ONLY the agent name (lowercase) - one of: finance, hr, legal, tech, or general_knowledge
6. Do not include any explanation or additional text, just the agent name

Examples:
- "How do I update my payment method?" -> finance
- "I need help with API authentication" -> tech
- "What are the browser requirements?" -> tech (system requirements = tech domain)
- "What are your privacy policies?" -> legal
- "How do I add a new user to my account?" -> hr
- "Tell me about your company" -> general_knowledge (truly general, no specialist domain)"""),
            ("human", "Query: {query}\n\nAgent:"),
        ])
    
        # Multi-agent detection prompt
        self.multi_agent_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an intelligent query analyzer for a multi-agent customer support system.

Your task is to determine if a query requires multiple specialist agents to answer it, and whether those agents need to process sequentially (with context handoff) or can process in parallel (independently).

Available agents:
{agent_descriptions}

IMPORTANT ROUTING RULE:
- **ALWAYS prefer a specialist agent (finance, hr, legal, tech) over general_knowledge when there is ANY ambiguity**
- Only route to "general_knowledge" if the query is clearly about general company information with no specialist domain connection
- When in doubt between a specialist agent and general_knowledge, choose the specialist agent and then use general_knowledge as a fallback if the specialist agent doesn't have the information.

Analyze the query and determine:
1. Does this query have multiple distinct parts that require different agents?
2. If multiple agents are needed, do they need to see each other's responses (sequential) or can they work independently (parallel)?

Key considerations for sequential processing:
- One agent's answer is needed to answer another agent's part
- The query has dependencies between parts (e.g., "First check if I can upgrade, then tell me the pricing")
- One part builds on another (e.g., "What are the legal requirements for billing, and then what are the billing steps?")
- The query asks for a workflow that spans multiple domains

Key considerations for parallel processing:
- Multiple independent questions that don't depend on each other
- Questions about different topics that can be answered separately
- No dependencies between the parts (e.g., "Tell me about payment methods and API documentation")

Respond with a JSON object:
{{
    "requires_multiple_agents": true/false,
    "agents": ["agent1", "agent2", ...],  // List of agent names needed - prefer specialist agents over general_knowledge
    "requires_sequential": true/false,  // true if agents need to see previous responses, false if independent
    "reasoning": "Brief explanation of why sequential or parallel"
}}

If requires_multiple_agents is false, provide only one agent name and set requires_sequential to false. Prefer specialist agents over general_knowledge.
If requires_multiple_agents is true, determine if requires_sequential should be true or false based on dependencies.

Examples:
- "How do I update my payment method?" -> {{"requires_multiple_agents": false, "agents": ["finance"], "requires_sequential": false, "reasoning": "Single question about payment"}}
- "What are the browser requirements?" -> {{"requires_multiple_agents": false, "agents": ["tech"], "requires_sequential": false, "reasoning": "System requirements are technical domain"}}
- "I need to update my payment method and also want to know about your API authentication" -> {{"requires_multiple_agents": true, "agents": ["finance", "tech"], "requires_sequential": false, "reasoning": "Two independent questions that can be answered in parallel"}}
- "What are your billing policies and privacy terms?" -> {{"requires_multiple_agents": true, "agents": ["finance", "legal"], "requires_sequential": false, "reasoning": "Independent questions about different topics"}}
- "First, can I upgrade my account? If yes, what are the pricing options?" -> {{"requires_multiple_agents": true, "agents": ["hr", "finance"], "requires_sequential": true, "reasoning": "Finance agent needs to know if upgrade is possible before providing pricing"}}
- "What are the legal requirements for billing, and then what are the billing steps?" -> {{"requires_multiple_agents": true, "agents": ["legal", "finance"], "requires_sequential": true, "reasoning": "Billing steps may depend on legal requirements"}}"""),
            ("human", "Query: {query}\n\nAnalysis:"),
        ])
    
    def _create_chains(self):
        """Create LCEL chains for routing and multi-agent detection."""
        # LCEL chain for single agent routing
        self.routing_chain = (
            self.routing_prompt.partial(
                agent_descriptions=self.agent_registry.get_agent_descriptions()
            )
            | self.llm
            | StrOutputParser()
        )
        
        # LCEL chain for multi-agent detection (with JSON parser)
        self.multi_agent_chain = (
            self.multi_agent_prompt.partial(
                agent_descriptions=self.agent_registry.get_agent_descriptions()
            )
            | self.llm
            | JsonOutputParser()
        )
    
    def _get_agent_instance(self, agent_name: str) -> BaseAgent:
        """Get or create an agent instance (lazy loading)."""
        if agent_name not in self._agent_instances:
            # Get preloaded vector store for this agent
            agent_config = self.agent_registry.get_agent(agent_name)
            if agent_config:
                vector_store = self.vector_store_manager.get_store(agent_config.handbook_name)
            else:
                vector_store = None
            
            self._agent_instances[agent_name] = create_agent(
                agent_name, 
                self.llm_model,
                vector_store=vector_store
            )
        return self._agent_instances[agent_name]
    
    def _get_conversation_context(self, session_id: str) -> ConversationContext:
        """Get or create conversation context for a session."""
        if session_id not in self._conversation_contexts:
            self._conversation_contexts[session_id] = ConversationContext(session_id=session_id)
        return self._conversation_contexts[session_id]
    
    @observe(name="orchestrator_detect_multi_agent")
    def _detect_multi_agent(self, query: str) -> Dict:
        """
        Detect if a query requires multiple agents and whether they need sequential processing.
        
        Args:
            query: User query
            
        Returns:
            Dict with requires_multiple_agents, agents, requires_sequential, and reasoning
        """
        # Use multi-agent detection chain (with JSON parser)
        # @observe decorator automatically captures function inputs/outputs
        try:
            result = self.multi_agent_chain.invoke(
                {"query": query},
                config={"callbacks": [self.langfuse_handler]}
            )
            
            # Validate agent names
            valid_agents = []
            for agent_name in result.get("agents", []):
                agent_name = agent_name.lower()
                if agent_name in self.agent_registry.AGENTS:
                    valid_agents.append(agent_name)
                elif agent_name == "general":
                    valid_agents.append("general_knowledge")
            
            if not valid_agents:
                # Fallback to general_knowledge
                valid_agents = ["general_knowledge"]
            
            result["agents"] = valid_agents
            result["requires_multiple_agents"] = len(valid_agents) > 1
            
            # Ensure requires_sequential is set (default to False if not present)
            if "requires_sequential" not in result:
                result["requires_sequential"] = False
            
            # If single agent, sequential doesn't apply
            if not result["requires_multiple_agents"]:
                result["requires_sequential"] = False
            
            # @observe decorator automatically captures return value and errors
            return result
            
        except Exception as e:
            # @observe decorator automatically captures exceptions
            # Fallback to single agent routing
            return {
                "requires_multiple_agents": False,
                "agents": ["general_knowledge"],
                "requires_sequential": False,
                "reasoning": f"Error in detection: {str(e)}",
            }
    
    @observe(name="orchestrator_route_single")
    def _route_single_agent(self, query: str) -> str:
        """
        Route a query to a single agent.
        
        Args:
            query: The customer query to route.
        
        Returns:
            The name of the agent that should handle the query.
        """
        # @observe decorator automatically captures function inputs
        
        # Use LCEL chain for routing decision
        result = self.routing_chain.invoke(
            {"query": query},
            config={"callbacks": [self.langfuse_handler]}
        )
        
        # Extract agent name from chain output (StrOutputParser returns string)
        agent_name = str(result).strip().lower()
        
        # Normalize agent name
        if agent_name == "general":
            agent_name = "general_knowledge"
        
        # Validate agent name
        if agent_name not in self.agent_registry.AGENTS:
            agent_name = "general_knowledge"
        
        # @observe decorator automatically captures return value
        return agent_name
    
    async def _process_agent_async(
        self,
        agent_name: str,
        query: str,
        conversation_history: List[Dict[str, str]],
        min_similarity: float = None,
    ) -> AgentResponse:
        """Process a query with an agent asynchronously."""
        try:
            agent = self._get_agent_instance(agent_name)
            # Run in thread pool since process_query is synchronous
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                agent.process_query,
                query,
                conversation_history,
                4,  # k parameter
                min_similarity,  # min_similarity parameter
            )
            return response
        except Exception as e:
            # Error will be captured by parent @observe decorator
            return AgentResponse(
                content=f"I encountered an error while processing your query with the {agent_name} agent. Please try again.",
                agent_name=agent_name,
                sources=[],
                metadata={"error": str(e), "error_type": type(e).__name__},
            )
    
    async def _process_multi_agent_parallel(
        self,
        agent_names: List[str],
        query: str,
        conversation_history: List[Dict[str, str]],
        min_similarity: float = None,
    ) -> List[AgentResponse]:
        """Process query with multiple agents in parallel."""
        tasks = [
            self._process_agent_async(agent_name, query, conversation_history, min_similarity)
            for agent_name in agent_names
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                agent_name = agent_names[i]
                processed_responses.append(
                    AgentResponse(
                        content=f"Error processing with {agent_name} agent: {str(response)}",
                        agent_name=agent_name,
                        sources=[],
                        metadata={"error": str(response), "error_type": type(response).__name__},
                    )
                )
            else:
                processed_responses.append(response)
        
        return processed_responses
    
    async def _process_multi_agent_sequential(
        self,
        agent_names: List[str],
        query: str,
        conversation_history: List[Dict[str, str]],
        min_similarity: float = None,
    ) -> List[AgentResponse]:
        """Process query with multiple agents sequentially with context handoff."""
        responses = []
        current_history = conversation_history.copy()
        
        for agent_name in agent_names:
            try:
                agent = self._get_agent_instance(agent_name)
                response = agent.process_query(query, current_history, k=4, min_similarity=min_similarity)
                responses.append(response)
                
                # Add response to history for next agent
                current_history.append({
                    "role": "assistant",
                    "content": f"[{agent_name.upper()} Agent]: {response.content}",
                })
            except Exception as e:
                # Error will be captured by parent @observe decorator
                responses.append(
                    AgentResponse(
                        content=f"Error processing with {agent_name} agent: {str(e)}",
                        agent_name=agent_name,
                        sources=[],
                        metadata={"error": str(e), "error_type": type(e).__name__},
                    )
                )
        
        return responses
    
    def _bundle_responses(
        self,
        responses: List[AgentResponse],
        routing_mode: RoutingMode,
    ) -> str:
        """Bundle multiple agent responses into a coherent answer."""
        if len(responses) == 1:
            return responses[0].content
        
        # Multi-agent response bundling
        bundled_parts = []
        error_responses = []
        
        for response in responses:
            error_type = response.metadata.get("error")
            
            # Include "no_context_found" responses as they provide useful feedback
            if error_type and error_type != "no_context_found":
                error_responses.append(f"{response.agent_name}: {error_type}")
                continue
            
            agent_title = response.agent_name.upper().replace("_", " ")
            bundled_parts.append(f"[{agent_title}]\n{response.content}")
        
        if not bundled_parts:
            if error_responses:
                return f"I encountered errors while processing your query: {', '.join(error_responses)}. Please try again or contact support."
            return "I couldn't find relevant information to answer your query. Please try rephrasing or contact support for assistance."
        
        return "\n\n".join(bundled_parts)
    
    @observe(name="orchestrator_process_query")
    async def process_query_async(
        self,
        query: str,
        session_id: str = "default",
        min_similarity: float = None,
    ) -> OrchestratorResponse:
        """
        Process a query with appropriate routing and agent handling.
        
        The orchestrator automatically determines:
        - Whether single or multi-agent processing is needed
        - Whether multi-agent queries should be processed in parallel (independent) 
          or sequentially (with context handoff)
        
        Args:
            query: User query
            session_id: Session ID for conversation continuity
            min_similarity: Minimum similarity threshold (0.0 to 1.0) for retrieved context.
                          Defaults to config MIN_SIMILARITY if None.
            
        Returns:
            OrchestratorResponse with bundled answer
        """
        from config import MIN_SIMILARITY as DEFAULT_MIN_SIMILARITY
        
        # Use provided min_similarity or fall back to config default
        if min_similarity is None:
            min_similarity = DEFAULT_MIN_SIMILARITY
        # Get conversation context
        context = self._get_conversation_context(session_id)
        context.add_message("user", query)
        
        # @observe decorator automatically captures function inputs/outputs and errors
        try:
            # Step 1: Detect if multi-agent is needed and processing mode
            detection_result = self._detect_multi_agent(query)
            requires_multi = detection_result["requires_multiple_agents"]
            agent_names = detection_result["agents"]
            requires_sequential = detection_result.get("requires_sequential", False)
            
            # Get conversation history
            conversation_history = context.get_recent_history()
            
            # Step 2: Process with appropriate mode (automatically determined by LLM)
            if requires_multi and len(agent_names) > 1:
                # Multi-agent processing - use sequential if dependencies exist, parallel otherwise
                if requires_sequential:
                    routing_mode = RoutingMode.MULTI_SEQUENTIAL
                    responses = await self._process_multi_agent_sequential(
                        agent_names, query, conversation_history, min_similarity
                    )
                else:
                    routing_mode = RoutingMode.MULTI_PARALLEL
                    responses = await self._process_multi_agent_parallel(
                        agent_names, query, conversation_history, min_similarity
                    )
            else:
                # Single agent processing
                routing_mode = RoutingMode.SINGLE
                if not agent_names:
                    agent_name = self._route_single_agent(query)
                else:
                    agent_name = agent_names[0]
                
                agent = self._get_agent_instance(agent_name)
                response = agent.process_query(query, conversation_history, k=4, min_similarity=min_similarity)
                responses = [response]
                agent_names = [agent_name]
            
            # Step 3: Bundle responses
            bundled_content = self._bundle_responses(responses, routing_mode)
            
            # Step 4: Update conversation context
            context.add_message("assistant", bundled_content)
            context.agent_history.extend(agent_names)
            context.last_agent = agent_names[-1] if agent_names else None
            
            # Step 5: Create orchestrator response
            orchestrator_response = OrchestratorResponse(
                content=bundled_content,
                agents_used=agent_names,
                responses=responses,
                routing_mode=routing_mode,
                metadata={
                    "session_id": session_id,
                    "detection_result": detection_result,
                    "conversation_length": len(context.messages),
                    "processing_mode": "sequential" if requires_sequential else "parallel",
                }
            )
            
            # @observe decorator automatically captures return value
            return orchestrator_response
            
        except Exception as e:
            # @observe decorator automatically captures exceptions
            # Fallback response
            fallback_agent = self._get_agent_instance("general_knowledge")
            fallback_response = fallback_agent.process_query(
                query,
                context.get_recent_history(),
                k=4,
                min_similarity=min_similarity,
            )
            
            context.add_message("assistant", fallback_response.content)
            
            return OrchestratorResponse(
                content=fallback_response.content,
                agents_used=["general_knowledge"],
                responses=[fallback_response],
                routing_mode=RoutingMode.SINGLE,
                metadata={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "fallback_used": True,
                }
            )
    
    def process_query(
        self,
        query: str,
        session_id: str = "default",
        min_similarity: float = None,
    ) -> OrchestratorResponse:
        """
        Synchronous wrapper for process_query_async.
        
        The orchestrator automatically determines whether to use parallel or sequential
        processing based on query dependencies.
        
        Args:
            query: User query
            session_id: Session ID for conversation continuity
            min_similarity: Minimum similarity threshold (0.0 to 1.0) for retrieved context.
                          Defaults to config MIN_SIMILARITY if None.
        
        Returns:
            OrchestratorResponse with bundled answer
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.process_query_async(query, session_id, min_similarity)
        )
    
    def get_agent_config(self, agent_name: str) -> Optional[AgentConfig]:
        """Get the configuration for a specific agent."""
        return self.agent_registry.get_agent(agent_name)
    
    def list_available_agents(self) -> Dict[str, AgentConfig]:
        """List all available agents."""
        return self.agent_registry.list_agents()

    def get_conversation_context(self, session_id: str) -> Optional[ConversationContext]:
        """Get conversation context for a session."""
        return self._conversation_contexts.get(session_id)
    
    def clear_conversation_context(self, session_id: str):
        """Clear conversation context for a session."""
        if session_id in self._conversation_contexts:
            del self._conversation_contexts[session_id]
