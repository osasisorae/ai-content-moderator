"""
Feature 1: LangChain Integration
Demonstrates PrysmCallbackHandler capturing chain executions, LLM calls, and tool usage.
"""
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from prysmai.integrations.langchain import PrysmCallbackHandler
from prysmai import prysm_context

# Initialize the Prysm callback handler
handler = PrysmCallbackHandler(
    api_key=os.environ["PRYSM_API_KEY"],
    base_url=os.environ.get("PRYSM_BASE_URL", "https://prysmai.io/api/v1"),
    session_id=None,   # auto-generated per invocation
    user_id=None,       # set per-request via prysm_context
    metadata={"pipeline": "langchain", "app": "content-moderator"},
    batch_size=10,      # buffer 10 events before flushing
    flush_interval=5.0, # flush every 5 seconds max
)

# Build a content moderation chain
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a content moderation assistant. Analyze the following text 
    and provide a moderation assessment. Include:
    1. A safety rating (safe/warning/unsafe)
    2. Categories of concern (if any)
    3. A brief explanation
    
    Be thorough but fair. Do not over-flag benign content."""),
    ("human", "{text}"),
])

# IMPORTANT: Point ChatOpenAI at the Prysm proxy, NOT directly at OpenAI.
# The Prysm proxy holds the upstream provider key — you only need PRYSM_API_KEY.
model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    openai_api_key=os.environ["PRYSM_API_KEY"],
    openai_api_base=os.environ.get("PRYSM_BASE_URL", "https://prysmai.io/api/v1"),
)
chain = prompt | model | StrOutputParser()


async def run_langchain_moderation(text: str, user_id: str) -> dict:
    """
    Run the LangChain moderation pipeline with Prysm monitoring.
    
    The PrysmCallbackHandler captures:
    - on_chat_model_start: model name, messages
    - on_llm_end: completion text, token usage, latency
    - on_chain_start/end: chain type, inputs, outputs
    
    All events are batched and sent to /telemetry/events with source="langchain".
    """
    with prysm_context(user_id=user_id, metadata={"pipeline": "langchain"}):
        result = await chain.ainvoke(
            {"text": text},
            config={"callbacks": [handler]},
        )
    
    # Flush remaining events
    handler.flush()
    
    return {
        "pipeline": "langchain",
        "result": result,
        "events_captured": [
            "chat_model_start",
            "llm_end (completion + tokens)",
            "chain_start",
            "chain_end",
        ],
    }
