"""
Feature 2: CrewAI Integration
Demonstrates PrysmCrewMonitor capturing agent executions, task completions, and tool usage.

The PrysmCrewMonitor captures via the CrewAI event bus:
- CrewKickoffStartedEvent / CompletedEvent
- AgentExecutionStartedEvent / CompletedEvent (per agent)
- TaskExecutionStartedEvent / CompletedEvent (per task)
- ToolUsageStartedEvent / FinishedEvent / ErrorEvent

All events are sent to /telemetry/events with source="crewai".

All LLM calls route through the Prysm proxy — no separate OPENAI_API_KEY needed.
"""
import os
from crewai import Agent, Task, Crew, Process, LLM
from prysmai.integrations.crewai import PrysmCrewMonitor
from prysmai import prysm_context

# ─── Prysm proxy configuration ───
PRYSM_API_KEY = os.environ["PRYSM_API_KEY"]
PRYSM_BASE_URL = os.environ.get("PRYSM_BASE_URL", "https://prysmai.io/api/v1")

# Initialize the Prysm crew monitor
monitor = PrysmCrewMonitor(
    api_key=PRYSM_API_KEY,
    base_url=PRYSM_BASE_URL,
    session_id=None,   # auto-generated
    user_id=None,       # set per-request
    metadata={"pipeline": "crewai", "app": "content-moderator"},
)


def _create_llm(model_name: str = "gpt-4.1-mini") -> LLM:
    """Create a CrewAI LLM routed through the Prysm proxy.
    
    All models (including Claude, Gemini, DeepSeek) are accessed via the
    Prysm proxy which exposes an OpenAI-compatible API. We use provider='openai'
    to ensure CrewAI uses its native OpenAI adapter rather than LiteLLM.
    """
    return LLM(
        model=model_name,
        provider="openai",
        api_key=PRYSM_API_KEY,
        base_url=PRYSM_BASE_URL,
    )


def _create_agents(model_name: str = "gpt-4.1-mini"):
    """Create the moderation crew agents with the specified model."""
    llm = _create_llm(model_name)

    safety_analyst = Agent(
        role="Safety Analyst",
        goal="Analyze text for safety concerns including toxicity, hate speech, and harmful content",
        backstory="""You are an expert content safety analyst with years of experience 
        in trust & safety at major tech companies. You identify harmful content patterns 
        with precision and nuance.""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
    )

    pii_inspector = Agent(
        role="PII Inspector",
        goal="Identify all personally identifiable information in the text",
        backstory="""You are a data privacy specialist trained in GDPR, CCPA, and HIPAA 
        compliance. You detect PII that automated regex patterns miss — names, addresses, 
        medical information, financial data.""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
    )

    policy_reviewer = Agent(
        role="Policy Reviewer",
        goal="Check content against organizational content policies",
        backstory="""You are a content policy expert who ensures all AI outputs comply 
        with organizational guidelines. You check for competitor mentions, unauthorized 
        claims, and policy violations.""",
        verbose=True,
        allow_delegation=True,
        llm=llm,
    )

    return safety_analyst, pii_inspector, policy_reviewer


async def run_crewai_moderation(text: str, user_id: str, model_name: str = "gpt-4.1-mini") -> dict:
    """
    Run the CrewAI moderation crew with Prysm monitoring.

    All LLM calls are routed through the Prysm proxy (PRYSM_BASE_URL).
    No separate OPENAI_API_KEY is needed — Prysm injects the provider key.

    The PrysmCrewMonitor captures via the CrewAI event bus:
    - CrewKickoffStartedEvent / CompletedEvent
    - AgentExecutionStartedEvent / CompletedEvent (per agent)
    - TaskExecutionStartedEvent / CompletedEvent (per task)
    - ToolUsageStartedEvent / FinishedEvent / ErrorEvent

    All events are sent to /telemetry/events with source="crewai".
    """
    safety_analyst, pii_inspector, policy_reviewer = _create_agents(model_name)

    # Define tasks
    safety_task = Task(
        description=f"Analyze this text for safety concerns: {text}",
        expected_output="Safety assessment with rating and categories",
        agent=safety_analyst,
    )

    pii_task = Task(
        description=f"Identify all PII in this text: {text}",
        expected_output="List of PII entities with types and risk levels",
        agent=pii_inspector,
    )

    policy_task = Task(
        description=f"Review this text against content policies: {text}",
        expected_output="Policy compliance report with any violations",
        agent=policy_reviewer,
    )

    crew = Crew(
        agents=[safety_analyst, pii_inspector, policy_reviewer],
        tasks=[safety_task, pii_task, policy_task],
        process=Process.sequential,
        verbose=True,
        callbacks=[monitor],  # Attach the Prysm monitor
    )

    with prysm_context(user_id=user_id, metadata={"pipeline": "crewai", "model": model_name}):
        result = crew.kickoff()

    monitor.flush()

    return {
        "pipeline": "crewai",
        "model": model_name,
        "result": str(result),
        "agents_used": ["Safety Analyst", "PII Inspector", "Policy Reviewer"],
        "events_captured": [
            "crew_kickoff_started",
            "crew_kickoff_completed",
            "agent_execution_started (x3)",
            "agent_execution_completed (x3)",
            "task_execution_started (x3)",
            "task_execution_completed (x3)",
            "tool_usage_started/completed (if tools used)",
        ],
    }
