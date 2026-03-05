"""
Feature 2: CrewAI Integration
Demonstrates PrysmCrewMonitor capturing agent executions, task completions, and tool usage.

The PrysmCrewMonitor captures via the CrewAI event bus:
- CrewKickoffStartedEvent / CompletedEvent
- AgentExecutionStartedEvent / CompletedEvent (per agent)
- TaskExecutionStartedEvent / CompletedEvent (per task)
- ToolUsageStartedEvent / FinishedEvent / ErrorEvent

All events are sent to /telemetry/events with source="crewai".
"""
import os
from crewai import Agent, Task, Crew, Process
from prysmai.integrations.crewai import PrysmCrewMonitor
from prysmai import prysm_context

# Initialize the Prysm crew monitor
monitor = PrysmCrewMonitor(
    api_key=os.environ["PRYSM_API_KEY"],
    base_url=os.environ.get("PRYSM_BASE_URL", "https://prysmai.io/api/v1"),
    session_id=None,   # auto-generated
    user_id=None,       # set per-request
    metadata={"pipeline": "crewai", "app": "content-moderator"},
)

# Define agents for a content moderation crew
safety_analyst = Agent(
    role="Safety Analyst",
    goal="Analyze text for safety concerns including toxicity, hate speech, and harmful content",
    backstory="""You are an expert content safety analyst with years of experience 
    in trust & safety at major tech companies. You identify harmful content patterns 
    with precision and nuance.""",
    verbose=True,
    allow_delegation=False,
)

pii_inspector = Agent(
    role="PII Inspector",
    goal="Identify all personally identifiable information in the text",
    backstory="""You are a data privacy specialist trained in GDPR, CCPA, and HIPAA 
    compliance. You detect PII that automated regex patterns miss — names, addresses, 
    medical information, financial data.""",
    verbose=True,
    allow_delegation=False,
)

policy_reviewer = Agent(
    role="Policy Reviewer",
    goal="Check content against organizational content policies",
    backstory="""You are a content policy expert who ensures all AI outputs comply 
    with organizational guidelines. You check for competitor mentions, unauthorized 
    claims, and policy violations.""",
    verbose=True,
    allow_delegation=True,  # Can delegate back to safety_analyst
)


async def run_crewai_moderation(text: str, user_id: str) -> dict:
    """
    Run the CrewAI moderation crew with Prysm monitoring.

    The PrysmCrewMonitor captures via the CrewAI event bus:
    - CrewKickoffStartedEvent / CompletedEvent
    - AgentExecutionStartedEvent / CompletedEvent (per agent)
    - TaskExecutionStartedEvent / CompletedEvent (per task)
    - ToolUsageStartedEvent / FinishedEvent / ErrorEvent

    All events are sent to /telemetry/events with source="crewai".
    """
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

    with prysm_context(user_id=user_id, metadata={"pipeline": "crewai"}):
        # The monitor auto-subscribes to the event bus on first __call__
        result = crew.kickoff()

    monitor.flush()

    return {
        "pipeline": "crewai",
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
