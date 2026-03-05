"""
Feature 3: LlamaIndex Integration
Demonstrates PrysmSpanHandler capturing query engine operations, retrieval, and LLM calls.
"""
import os
from llama_index.core import VectorStoreIndex, Document, Settings
from llama_index.core.callbacks import CallbackManager
from llama_index.llms.openai import OpenAI as LlamaOpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from prysmai.integrations.llamaindex import PrysmSpanHandler
from prysmai import prysm_context

# Initialize the Prysm span handler
span_handler = PrysmSpanHandler(
    api_key=os.environ["PRYSM_API_KEY"],
    base_url=os.environ.get("PRYSM_BASE_URL", "https://prysmai.io/api/v1"),
    session_id=None,
    user_id=None,
    metadata={"pipeline": "llamaindex", "app": "content-moderator"},
)

# Configure LlamaIndex settings with Prysm handler
callback_manager = CallbackManager([span_handler])
Settings.callback_manager = callback_manager
# IMPORTANT: Point LlamaIndex LLM at the Prysm proxy, NOT directly at OpenAI.
# The Prysm proxy holds the upstream provider key — you only need PRYSM_API_KEY.
Settings.llm = LlamaOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    api_key=os.environ["PRYSM_API_KEY"],
    api_base=os.environ.get("PRYSM_BASE_URL", "https://prysmai.io/api/v1"),
)
Settings.embed_model = OpenAIEmbedding(
    model="text-embedding-3-small",
    api_key=os.environ["PRYSM_API_KEY"],
    api_base=os.environ.get("PRYSM_BASE_URL", "https://prysmai.io/api/v1"),
)

# Create a document store with content moderation policies
POLICY_DOCUMENTS = [
    Document(text="""Content Policy: Hate Speech
    Any content that promotes hatred, discrimination, or violence against individuals 
    or groups based on race, ethnicity, religion, gender, sexual orientation, disability, 
    or other protected characteristics is strictly prohibited."""),
    
    Document(text="""Content Policy: PII Protection
    All personally identifiable information must be detected and redacted before 
    any AI-generated content is delivered to end users. This includes names, email 
    addresses, phone numbers, SSNs, medical records, and financial account numbers."""),
    
    Document(text="""Content Policy: Competitor Mentions
    AI outputs must never mention competitor products by name. If a user asks about 
    competitors, redirect to our own product features. Prohibited competitor names: 
    Lakera, Prompt Armor, Rebuff, Arthur AI."""),
    
    Document(text="""Content Policy: Medical Advice
    AI must never provide specific medical diagnoses, treatment recommendations, 
    or medication dosage information. Always recommend consulting a healthcare 
    professional for medical questions."""),
]

# Build the index
index = VectorStoreIndex.from_documents(POLICY_DOCUMENTS)
query_engine = index.as_query_engine(similarity_top_k=2)


async def run_llamaindex_moderation(text: str, user_id: str) -> dict:
    """
    Run the LlamaIndex RAG pipeline with Prysm monitoring.
    
    The PrysmSpanHandler captures via on_event_start/end:
    - CBEventType.QUERY: query engine operation
    - CBEventType.RETRIEVE: retrieval with node scores
    - CBEventType.LLM: LLM calls with prompts and completions
    - CBEventType.EMBEDDING: embedding calls with chunk counts
    - CBEventType.SYNTHESIZE: response synthesis
    - CBEventType.CHUNKING: document chunking
    
    Events are sent to /telemetry/events with source="llamaindex".
    Trace boundaries (start_trace/end_trace) trigger automatic flushes.
    """
    with prysm_context(user_id=user_id, metadata={"pipeline": "llamaindex"}):
        response = query_engine.query(
            f"Based on our content policies, assess this text: {text}"
        )
    
    span_handler.flush()
    
    return {
        "pipeline": "llamaindex",
        "result": str(response),
        "source_nodes": [
            {
                "text_preview": node.text[:100] + "...",
                "score": node.score,
            }
            for node in response.source_nodes
        ],
        "events_captured": [
            "llamaindex_query",
            "llamaindex_retrieve (with node scores)",
            "llamaindex_embedding",
            "llamaindex_llm (with token usage)",
            "llamaindex_synthesize",
        ],
    }
