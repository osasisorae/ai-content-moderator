"""
Prysm AI Security Showcase — Main Application
Exercises every v0.4.0 feature through a unified FastAPI interface.
"""
import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal

from prysmai import PrysmClient, prysm_context, monitor
from pipelines.langchain_pipeline import run_langchain_moderation
from pipelines.crewai_pipeline import run_crewai_moderation
from pipelines.llamaindex_pipeline import run_llamaindex_moderation

app = FastAPI(
    title="Prysm AI Security Showcase",
    description="Example app exercising every Prysm AI v0.4.0 feature",
    version="1.0.0",
)

# ─── Core Prysm Client (for direct OpenAI proxy usage) ───
prysm = PrysmClient(
    prysm_key=os.environ["PRYSM_API_KEY"],
    base_url=os.environ.get("PRYSM_BASE_URL", "https://prysmai.io/api/v1"),
)
openai_client = prysm.openai()


class ModerateRequest(BaseModel):
    text: str
    pipeline: Literal["langchain", "crewai", "llamaindex", "direct"] = "langchain"
    user_id: Optional[str] = "demo-user"


class ModerateResponse(BaseModel):
    pipeline: str
    result: str
    features_exercised: list[str]
    events_captured: list[str]


@app.post("/moderate", response_model=ModerateResponse)
async def moderate(req: ModerateRequest):
    """
    Main moderation endpoint. Routes to the specified pipeline.
    Each pipeline exercises different v0.4.0 features.
    """
    features = []
    events = []
    
    if req.pipeline == "langchain":
        # Feature 1: LangChain integration
        result = await run_langchain_moderation(req.text, req.user_id)
        features.append("LangChain PrysmCallbackHandler")
        events.extend(result["events_captured"])
        
    elif req.pipeline == "crewai":
        # Feature 2: CrewAI integration
        result = await run_crewai_moderation(req.text, req.user_id)
        features.append("CrewAI PrysmCrewMonitor")
        events.extend(result["events_captured"])
        
    elif req.pipeline == "llamaindex":
        # Feature 3: LlamaIndex integration
        result = await run_llamaindex_moderation(req.text, req.user_id)
        features.append("LlamaIndex PrysmSpanHandler")
        events.extend(result["events_captured"])
        
    elif req.pipeline == "direct":
        # Direct proxy usage — exercises tiered scanning (Feature 12)
        with prysm_context(user_id=req.user_id, metadata={"pipeline": "direct"}):
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
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
        result=result.get("result", str(result)),
        features_exercised=features,
        events_captured=events,
    )


@app.get("/health")
async def health():
    return {"status": "ok", "sdk_version": "0.4.0"}


@app.post("/run-all-scenarios")
async def run_all_scenarios():
    """
    Run every test scenario to exercise all 12 features.
    This is the "one button" demo endpoint for the hackathon.
    """
    from scenarios.test_scenarios import ALL_SCENARIOS
    
    results = []
    for scenario in ALL_SCENARIOS:
        try:
            result = await moderate(ModerateRequest(
                text=scenario["prompt"],
                pipeline=scenario.get("pipeline", "langchain"),
                user_id=f"demo-{scenario['name'][:20]}",
            ))
            results.append({
                "scenario": scenario["name"],
                "status": "success",
                "features_hit": scenario["features_hit"],
                "result_preview": result.result[:200],
            })
        except Exception as e:
            results.append({
                "scenario": scenario["name"],
                "status": "error",
                "error": str(e),
            })
    
    return {
        "total_scenarios": len(ALL_SCENARIOS),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "results": results,
    }


@app.post("/scan-tier-demo")
async def scan_tier_demo(text: str):
    """
    Send the same prompt through Prysm and return the scan tier headers.
    On Free: X-Prysm-Scan-Tier = "rules"
    On Pro+: X-Prysm-Scan-Tier = "deep"
    """
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": text}],
    )
    
    # The response object itself doesn't expose headers,
    # but the Prysm dashboard will show the scan tier.
    # To see headers directly, use the raw httpx response:
    return {
        "response": response.choices[0].message.content,
        "note": "Check Prysm dashboard → Security Events for scan tier details",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
