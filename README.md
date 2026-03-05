# Prysm AI Security Showcase

A reference application that exercises every feature in Prysm AI v0.4.0.

All LLM calls — including LangChain, CrewAI, LlamaIndex, and embeddings — route through the **Prysm proxy**. No separate `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` is needed. Prysm injects the upstream provider key automatically.

## Features Demonstrated

- **3 Framework Integrations**: LangChain, CrewAI, LlamaIndex
- **Multi-Model Support**: GPT-4.1 Mini, GPT-4.1 Nano, Gemini 2.5 Flash, Claude Sonnet 4 (extensible)
- **Off-Topic Detection**: Keyword-based (free) + LLM-based (paid)
- **ML Toxicity Scoring**: 6-dimension analysis (hate, harassment, self-harm, sexual, violence, dangerous)
- **NER PII Detection**: Person names, organizations, locations, medical data, credentials
- **Output Policy Compliance**: Custom rules with keyword, regex, and topic matching
- **Alert Channels**: PagerDuty Events API v2, Slack webhooks, custom webhooks
- **Tiered Security**: Rule-based (free) vs deep LLM scanning (paid)

## Supported Models

All models are accessed through the Prysm proxy. Add new models to `SUPPORTED_MODELS` in `main.py`.

| Model | Provider | Status |
|-------|----------|--------|
| `gpt-4.1-mini` | OpenAI | Default |
| `gpt-4.1-nano` | OpenAI | Available |
| `gemini-2.5-flash` | Google | Available |
| `claude-sonnet-4-20250514` | Anthropic | Available |
| `deepseek-chat` | DeepSeek | Pending proxy support |

## Quick Start

```bash
pip install "prysmai[all]==0.4.0" fastapi uvicorn python-dotenv httpx langchain-openai crewai llama-index llama-index-llms-openai llama-index-embeddings-openai
cp .env.example .env
# Edit .env with your PRYSM_API_KEY — that's all you need
uvicorn main:app --reload
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/moderate` | POST | Run moderation through any pipeline with model selection |
| `/run-all-scenarios` | POST | Execute all 15 test scenarios at once (with optional model param) |
| `/scan-tier-demo` | POST | Demonstrate tiered scanning headers |
| `/models` | GET | List all supported models |
| `/health` | GET | Health check with SDK version and model list |

## Usage Examples

**Basic moderation (default model: gpt-4.1-mini):**
```bash
curl -X POST http://localhost:8000/moderate \
  -H "Content-Type: application/json" \
  -d '{"text": "Check this for safety", "pipeline": "langchain"}'
```

**Moderation with Claude:**
```bash
curl -X POST http://localhost:8000/moderate \
  -H "Content-Type: application/json" \
  -d '{"text": "Check this for safety", "pipeline": "direct", "model": "claude-sonnet-4-20250514"}'
```

**Run all 15 scenarios:**
```bash
curl -X POST http://localhost:8000/run-all-scenarios
```

**Run all scenarios with a specific model:**
```bash
curl -X POST "http://localhost:8000/run-all-scenarios?model=claude-sonnet-4-20250514"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│                                                             │
│  POST /moderate  (model selection: gpt-4.1-mini, claude...) │
│  ┌───────────┐  ┌───────────┐  ┌──────────────┐           │
│  │ LangChain │  │  CrewAI   │  │  LlamaIndex  │           │
│  │  Pipeline  │  │  Pipeline │  │   Pipeline   │           │
│  └─────┬─────┘  └─────┬─────┘  └──────┬───────┘           │
│        │              │               │                     │
│        ▼              ▼               ▼                     │
│  PrysmCallback   PrysmCrewMonitor  PrysmSpanHandler         │
│  Handler              │               │                     │
│        │              │               │                     │
│        └──────────────┼───────────────┘                     │
│                       ▼                                     │
│              Prysm Proxy (prysmai.io/api/v1)               │
│              ┌────────────────────────────┐                 │
│              │  Input Scanning Pipeline   │                 │
│              │  ├─ Injection Detection    │                 │
│              │  ├─ Off-Topic Detection    │                 │
│              │  ├─ PII Detection (regex)  │                 │
│              │  └─ Tiered Deep Scan       │                 │
│              ├────────────────────────────┤                 │
│              │  Upstream LLM Provider     │                 │
│              │  (OpenAI/Anthropic/Google) │                 │
│              ├────────────────────────────┤                 │
│              │  Output Scanning Pipeline  │                 │
│              │  ├─ PII Detection (regex)  │                 │
│              │  ├─ Toxicity (keyword)     │                 │
│              │  ├─ ML Toxicity (6-dim)    │                 │
│              │  ├─ NER Detection          │                 │
│              │  └─ Policy Compliance      │                 │
│              └────────────────────────────┘                 │
│                       │                                     │
│                       ▼                                     │
│              Alert Engine (threshold evaluation)            │
│              ├─ PagerDuty Events API v2                     │
│              ├─ Slack Webhook                               │
│              └─ Custom Webhook                              │
└─────────────────────────────────────────────────────────────┘
```

## Adding New Models

To add a new model (e.g., DeepSeek when proxy support is available):

1. Add the model to `SUPPORTED_MODELS` in `main.py`:
   ```python
   "deepseek-chat": {"provider": "deepseek", "description": "DeepSeek Chat"},
   ```
2. That's it. All pipelines accept a `model_name` parameter and route through the Prysm proxy.

## Feature Matrix

| # | Feature | Category | How to Verify |
|---|---------|----------|---------------|
| 1 | LangChain Integration | SDK | Telemetry events under "langchain" source |
| 2 | CrewAI Integration | SDK | Telemetry events under "crewai" source |
| 3 | LlamaIndex Integration | SDK | Telemetry events under "llamaindex" source |
| 4 | Off-Topic Detection (Keyword) | Security — Input | `off_topic` threat, `method: "keyword"` |
| 5 | Off-Topic Detection (LLM) | Security — Input | `off_topic` threat, `method: "llm"` |
| 6 | ML Toxicity Scoring | Security — Output | `mlToxicityResult` with 6 dimension scores |
| 7 | NER-Based PII Detection | Security — Output | `nerResult` with entity types |
| 8 | Output Policy Compliance | Security — Output | `policyResult` with violations |
| 9 | PagerDuty Alerts | Alerting | PagerDuty incident with `prysm-alert-{id}` |
| 10 | Slack Webhook Alerts | Alerting | Slack message in configured channel |
| 11 | Custom Webhook Alerts | Alerting | POST received at webhook endpoint |
| 12 | Tiered Security Scanning | Security — Input | `X-Prysm-Scan-Tier: deep` vs `rules` |

## Test Scenarios

The app includes 15 pre-built test scenarios in `scenarios/test_scenarios.py` that collectively exercise all 12 features. Run them all at once via `POST /run-all-scenarios`.

## Alert Testing

Configure alerts in the Prysm dashboard, then run the trigger script:

```bash
python -m alerts.setup_alerts
```

This sends traffic patterns designed to breach alert thresholds and trigger PagerDuty, Slack, and webhook notifications.

## Dashboard Configuration

Before testing, configure these in the Prysm dashboard:

1. **Off-Topic Detection** (Settings → Security): Set agent description and keywords
2. **Content Policies** (Settings → Security): Add competitor_mention, pricing_claim, legal_liability rules
3. **Alert Rules** (Settings → Alerts): Create High Threat Rate, High Error Rate, and Latency Spike alerts

## SDK Version

`prysmai==0.4.0` with extras: `[langchain]`, `[crewai]`, `[llamaindex]`, `[all]`
