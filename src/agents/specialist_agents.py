"""Specialist agent implementations."""

from .base_agent import BaseAgent


class FinanceAgent(BaseAgent):
    """Finance specialist agent for billing, payments, and financial queries."""
    
    def __init__(self, llm_model: str = None):
        super().__init__(
            name="finance",
            handbook_name="finance_handbook",
            description="Handles queries about billing, payments, invoices, pricing, refunds, and financial matters",
            llm_model=llm_model,
        )


class HRAgent(BaseAgent):
    """HR specialist agent for account management and user support."""
    
    def __init__(self, llm_model: str = None):
        super().__init__(
            name="hr",
            handbook_name="hr_handbook",
            description="Handles queries about account management, user support, subscriptions, account settings, and user-related issues",
            llm_model=llm_model,
        )


class LegalAgent(BaseAgent):
    """Legal specialist agent for compliance and legal matters."""
    
    def __init__(self, llm_model: str = None):
        super().__init__(
            name="legal",
            handbook_name="legal_handbook",
            description="Handles queries about terms of service, privacy policies, compliance, legal agreements, and regulatory matters",
            llm_model=llm_model,
        )


class TechAgent(BaseAgent):
    """Tech specialist agent for technical support and integrations."""
    
    def __init__(self, llm_model: str = None):
        super().__init__(
            name="tech",
            handbook_name="tech_handbook",
            description="Handles queries about API documentation, integrations, technical support, troubleshooting, and technical implementation",
            llm_model=llm_model,
        )


class GeneralKnowledgeAgent(BaseAgent):
    """General knowledge agent for company information and fallback queries."""
    
    def __init__(self, llm_model: str = None):
        super().__init__(
            name="general_knowledge",
            handbook_name="general_handbook",
            description="Handles general company information, product overview, company policies, and serves as a fallback for queries that don't fit other categories",
            llm_model=llm_model,
        )


def create_agent(agent_name: str, llm_model: str = None) -> BaseAgent:
    """
    Factory function to create an agent by name.
    
    Args:
        agent_name: Name of the agent (finance, hr, legal, tech, general_knowledge)
        llm_model: Optional LLM model override
        
    Returns:
        Initialized agent instance
        
    Raises:
        ValueError: If agent name is not recognized
    """
    agents = {
        "finance": FinanceAgent,
        "hr": HRAgent,
        "legal": LegalAgent,
        "tech": TechAgent,
        "general_knowledge": GeneralKnowledgeAgent,
        "general": GeneralKnowledgeAgent,  # Alias
    }
    
    agent_class = agents.get(agent_name.lower())
    if not agent_class:
        raise ValueError(
            f"Unknown agent: {agent_name}. Available agents: {list(agents.keys())}"
        )
    
    return agent_class(llm_model=llm_model)

