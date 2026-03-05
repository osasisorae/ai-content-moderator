"""
Feature 3: LlamaIndex Integration
Demonstrates PrysmSpanHandler capturing query engine operations, retrieval, and LLM calls.

The PrysmSpanHandler captures via on_event_start/end:
- CBEventType.QUERY: query engine operation
- CBEventType.RETRIEVE: retrieval with node scores
- CBEventType.LLM: LLM calls with prompts and completions
- CBEventType.EMBEDDING: embedding calls with chunk counts
- CBEventType.SYNTHESIZE: response synthesis
- CBEventType.CHUNKING: document chunking

Events are sent to /telemetry/events with source="llamaindex".
Trace boundaries (start_trace/end_trace) trigger automatic flushes.

All LLM and embedding calls route through the Prysm proxy — no separate OPENAI_API_KEY needed.
"""
import os
from llama_index.core import VectorStoreIndex, Document, Settings
from llama_index.core.callbacks import CallbackManager
from llama_index.core.llms import LLMMetadata, MessageRole
from llama_index.llms.openai import OpenAI as LlamaOpenAI
from llama_index.llms.openai.utils import (
    openai_modelname_to_contextsize,
    is_chat_model,
    is_function_calling_model,
    O1_MODELS,
)
from llama_index.embeddings.openai import OpenAIEmbedding
from prysmai.integrations.llamaindex import PrysmSpanHandler
from prysmai import prysm_context

# ─── Prysm proxy configuration ───
PRYSM_API_KEY = os.environ["PRYSM_API_KEY"]
PRYSM_BASE_URL = os.environ.get("PRYSM_BASE_URL", "https://prysmai.io/api/v1")

# ─── Patch LlamaIndex's OpenAI LLM to support non-OpenAI models via Prysm proxy ───
# LlamaIndex's metadata property calls openai_modelname_to_contextsize() which
# raises ValueError for non-OpenAI model names (e.g. claude-sonnet-4-20250514).
# We patch the metadata property to gracefully handle these models.
_original_metadata = LlamaOpenAI.metadata.fget


def _patched_metadata(self) -> LLMMetadata:
    """Return LLM metadata, falling back to safe defaults for non-OpenAI models."""
    try:
        return _original_metadata(self)
    except ValueError:
        # Non-OpenAI model routed through Prysm proxy — use safe defaults
        return LLMMetadata(
            context_window=128000,
            num_output=self.max_tokens or -1,
            is_chat_model=True,
            is_function_calling_model=True,
            model_name=self.model,
            system_role=MessageRole.SYSTEM,
        )


LlamaOpenAI.metadata = property(_patched_metadata)

# Initialize the Prysm span handler
span_handler = PrysmSpanHandler(
    api_key=PRYSM_API_KEY,
    base_url=PRYSM_BASE_URL,
    session_id=None,
    user_id=None,
    metadata={"pipeline": "llamaindex", "app": "content-moderator"},
)

# Configure LlamaIndex settings with Prysm handler
# ALL calls (LLM + embeddings) route through the Prysm proxy
callback_manager = CallbackManager([span_handler])
Settings.callback_manager = callback_manager
Settings.llm = LlamaOpenAI(
    model="gpt-4.1-mini",
    temperature=0.1,
    api_key=PRYSM_API_KEY,
    api_base=PRYSM_BASE_URL,
)
Settings.embed_model = OpenAIEmbedding(
    model="text-embedding-3-small",
    api_key=PRYSM_API_KEY,
    api_base=PRYSM_BASE_URL,
)

# Content moderation policy documents
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

# Lazy-initialized index and query engines (deferred to avoid module-load-time API calls)
_indexes = {}
_query_engines = {}


def _get_query_engine(model_name: str = "gpt-4.1-mini"):
    """Build the vector index and query engine on first use, per model."""
    if model_name not in _query_engines:
        llm = LlamaOpenAI(
            model=model_name,
            temperature=0.1,
            api_key=PRYSM_API_KEY,
            api_base=PRYSM_BASE_URL,
        )
        # Build index (embeddings go through Prysm proxy)
        if "default" not in _indexes:
            _indexes["default"] = VectorStoreIndex.from_documents(POLICY_DOCUMENTS)
        _query_engines[model_name] = _indexes["default"].as_query_engine(
            similarity_top_k=2,
            llm=llm,
        )
    return _query_engines[model_name]


async def run_llamaindex_moderation(text: str, user_id: str, model_name: str = "gpt-4.1-mini") -> dict:
    """
    Run the LlamaIndex RAG pipeline with Prysm monitoring.

    All LLM and embedding calls are routed through the Prysm proxy (PRYSM_BASE_URL).
    No separate OPENAI_API_KEY is needed — Prysm injects the provider key.

    The PrysmSpanHandler captures via on_event_start/end:
    - CBEventType.QUERY: query engine operation
    - CBEventType.RETRIEVE: retrieval with node scores
    - CBEventType.LLM: LLM calls with prompts and completions
    - CBEventType.EMBEDDING: embedding calls with chunk counts
    - CBEventType.SYNTHESIZE: response synthesis

    Events are sent to /telemetry/events with source="llamaindex".
    Trace boundaries (start_trace/end_trace) trigger automatic flushes.
    """
    query_engine = _get_query_engine(model_name)

    with prysm_context(user_id=user_id, metadata={"pipeline": "llamaindex", "model": model_name}):
        response = query_engine.query(
            f"Based on our content policies, assess this text: {text}"
        )

    span_handler.flush()

    return {
        "pipeline": "llamaindex",
        "model": model_name,
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
