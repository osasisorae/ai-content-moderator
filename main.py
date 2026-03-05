"""
Prysm AI Security Showcase — Main Application
Exercises every v0.4.0 feature through a unified FastAPI interface.

All LLM calls route through the Prysm proxy — no separate OPENAI_API_KEY needed.
Prysm injects the upstream provider key automatically.

Supported models (via Prysm proxy):
- gpt-4.1-mini (default)
- gpt-4.1-nano
- gemini-2.5-flash
- claude-sonnet-4-20250514

Endpoints:
- POST /moderate          — Run moderation through any pipeline (with model selection)
- POST /run-all-scenarios — Execute all test scenarios at once
- POST /scan-tier-demo    — Demonstrate tiered scanning headers
- GET  /health            — Health check
- GET  /models            — List supported models
"""
import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
import openai as openai_errors

from prysmai import PrysmClient, prysm_context
from pipelines.langchain_pipeline import run_langchain_moderation
from pipelines.crewai_pipeline import run_crewai_moderation
from pipelines.llamaindex_pipeline import run_llamaindex_moderation

app = FastAPI(
    title="Prysm AI Security Showcase",
    description="Example app exercising every Prysm AI v0.4.0 feature",
    version="1.0.0",
)

# ─── Supported models (extensible — add new models here) ───
SUPPORTED_MODELS = {
    "gpt-4.1-mini": {"provider": "openai", "description": "GPT-4.1 Mini — fast and capable"},
    "gpt-4.1-nano": {"provider": "openai", "description": "GPT-4.1 Nano — fastest, lowest cost"},
    "gemini-2.5-flash": {"provider": "google", "description": "Gemini 2.5 Flash — Google's fast model"},
    "claude-sonnet-4-20250514": {"provider": "anthropic", "description": "Claude Sonnet 4 — Anthropic's balanced model"},
    # Add new models here as they become available on the Prysm proxy:
    # "deepseek-chat": {"provider": "deepseek", "description": "DeepSeek Chat"},
}

DEFAULT_MODEL = "gpt-4.1-mini"

# ─── Core Prysm Client (for direct OpenAI proxy usage) ───
prysm = PrysmClient(
    prysm_key=os.environ["PRYSM_API_KEY"],
    base_url=os.environ.get("PRYSM_BASE_URL", "https://prysmai.io/api/v1"),
)
openai_client = prysm.openai()


class ModerateRequest(BaseModel):
    text: str
    pipeline: Literal["langchain", "crewai", "llamaindex", "direct"] = "langchain"
    model: Optional[str] = DEFAULT_MODEL
    user_id: Optional[str] = "demo-user"


class ModerateResponse(BaseModel):
    pipeline: str
    model: str
    result: str
    features_exercised: list[str]
    events_captured: list[str]


@app.post("/moderate", response_model=ModerateResponse)
async def moderate(req: ModerateRequest):
    """
    Main moderation endpoint. Routes to the specified pipeline and model.
    Each pipeline exercises different v0.4.0 features.
    All LLM calls go through the Prysm proxy — no separate provider keys needed.
    """
    model_name = req.model or DEFAULT_MODEL
    if model_name not in SUPPORTED_MODELS:
        raise HTTPException(
            400,
            f"Unsupported model: {model_name}. "
            f"Supported: {list(SUPPORTED_MODELS.keys())}",
        )

    features = []
    events = []

    try:
        if req.pipeline == "langchain":
            # Feature 1: LangChain integration
            result = await run_langchain_moderation(req.text, req.user_id, model_name)
            features.append("LangChain PrysmCallbackHandler")
            events.extend(result["events_captured"])

        elif req.pipeline == "crewai":
            # Feature 2: CrewAI integration
            result = await run_crewai_moderation(req.text, req.user_id, model_name)
            features.append("CrewAI PrysmCrewMonitor")
            events.extend(result["events_captured"])

        elif req.pipeline == "llamaindex":
            # Feature 3: LlamaIndex integration
            result = await run_llamaindex_moderation(req.text, req.user_id, model_name)
            features.append("LlamaIndex PrysmSpanHandler")
            events.extend(result["events_captured"])

        elif req.pipeline == "direct":
            # Direct proxy usage — exercises tiered scanning (Feature 12)
            with prysm_context(user_id=req.user_id, metadata={"pipeline": "direct", "model": model_name}):
                response = openai_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a content moderation assistant."},
                        {"role": "user", "content": req.text},
                    ],
                )
            result = {"result": response.choices[0].message.content}
            features.append("Direct proxy (tiered scanning)")
            events.append("Proxy request with X-Prysm headers")

        else:
            raise HTTPException(400, f"Unknown pipeline: {req.pipeline}")

    except openai_errors.PermissionDeniedError as e:
        # Prysm security policy blocked the request (403) — this is expected
        # behavior for adversarial inputs. Return the block details as a result.
        error_body = e.body if hasattr(e, 'body') else {}
        if isinstance(error_body, dict):
            err = error_body.get("error", error_body)
        else:
            err = {"message": str(e)}
        features.append(f"BLOCKED by Prysm security ({req.pipeline})")
        events.append("security_block")
        return ModerateResponse(
            pipeline=req.pipeline,
            model=model_name,
            result=f"[BLOCKED] {err.get('message', 'Request blocked by security policy')}. "
                   f"Threat level: {err.get('threat_level', 'unknown')}, "
                   f"Score: {err.get('threat_score', 'N/A')}, "
                   f"Details: {err.get('details', 'N/A')}",
            features_exercised=features + [
                "Tiered security scanning (input)",
                "Injection detection",
            ],
            events_captured=events,
        )
    except Exception as e:
        raise HTTPException(500, f"Pipeline error ({req.pipeline}/{model_name}): {str(e)}")

    # These features trigger automatically on the Prysm server side:
    features.extend([
        "Off-topic detection (input)",         # Features 4, 5
        "Tiered security scanning (input)",    # Feature 12
        "ML toxicity scoring (output)",        # Feature 6
        "NER PII detection (output)",          # Feature 7
        "Output policy compliance (output)",   # Feature 8
    ])

    return ModerateResponse(
        pipeline=req.pipeline,
        model=model_name,
        result=result.get("result", str(result)),
        features_exercised=features,
        events_captured=events,
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "sdk_version": "0.4.0",
        "default_model": DEFAULT_MODEL,
        "supported_models": list(SUPPORTED_MODELS.keys()),
    }


@app.get("/models")
async def list_models():
    """List all supported models available through the Prysm proxy."""
    return {
        "default": DEFAULT_MODEL,
        "models": SUPPORTED_MODELS,
    }


@app.post("/scan-tier-demo")
async def scan_tier_demo(text: str = "Analyze this text for safety concerns.", model: str = DEFAULT_MODEL):
    """
    Send the same prompt through Prysm and return the scan tier headers.
    On Free: X-Prysm-Scan-Tier = "rules"
    On Pro+: X-Prysm-Scan-Tier = "deep"
    """
    if model not in SUPPORTED_MODELS:
        raise HTTPException(400, f"Unsupported model: {model}. Supported: {list(SUPPORTED_MODELS.keys())}")

    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": text}],
    )

    return {
        "model": model,
        "response": response.choices[0].message.content,
        "note": "Check Prysm dashboard → Security Events for scan tier details",
    }


@app.post("/run-all-scenarios")
async def run_all_scenarios(model: str = DEFAULT_MODEL):
    """
    Run every test scenario to exercise all 12 features.
    This is the "one button" demo endpoint for the hackathon.
    Optionally specify a model to run all scenarios with that model.
    """
    from scenarios.test_scenarios import ALL_SCENARIOS

    results = []
    for scenario in ALL_SCENARIOS:
        try:
            result = await moderate(ModerateRequest(
                text=scenario["prompt"],
                pipeline=scenario.get("pipeline", "langchain"),
                model=model,
                user_id=f"demo-{scenario['name'][:20]}",
            ))
            results.append({
                "scenario": scenario["name"],
                "model": model,
                "status": "success",
                "features_hit": scenario["features_hit"],
                "result_preview": result.result[:200],
            })
        except Exception as e:
            results.append({
                "scenario": scenario["name"],
                "model": model,
                "status": "error",
                "error": str(e),
            })

    return {
        "total_scenarios": len(ALL_SCENARIOS),
        "model": model,
        "successful": sum(1 for r in results if r["status"] == "success"),
        "results": results,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
