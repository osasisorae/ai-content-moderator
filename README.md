# Prysm AI Security Showcase

A reference application that exercises every feature in Prysm AI v0.4.0.

## Features Demonstrated

- **3 Framework Integrations**: LangChain, CrewAI, LlamaIndex
- **Off-Topic Detection**: Keyword-based (free) + LLM-based (paid)
- **ML Toxicity Scoring**: 6-dimension analysis (hate, harassment, self-harm, sexual, violence, dangerous)
- **NER PII Detection**: Person names, organizations, locations, medical data, credentials
- **Output Policy Compliance**: Custom rules with keyword, regex, and topic matching
- **Alert Channels**: PagerDuty Events API v2, Slack webhooks, custom webhooks
- **Tiered Security**: Rule-based (free) vs deep LLM scanning (paid)

## Quick Start

1. `pip install "prysmai[all]==0.4.0" fastapi uvicorn python-dotenv httpx langchain-openai llama-index-llms-openai llama-index-embeddings-openai`
2. Copy `.env.example` to `.env` and fill in your keys
3. `uvicorn main:app --reload`
4. Hit `POST /run-all-scenarios` to exercise all 12 features
5. Open the Prysm dashboard to see everything light up

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/moderate` | POST | Run moderation through any pipeline |
| `/run-all-scenarios` | POST | Execute all test scenarios at once |
| `/scan-tier-demo` | POST | Demonstrate tiered scanning headers |
| `/health` | GET | Health check |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│                                                             │
│  POST /moderate                                             │
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
│              │  (OpenAI / Anthropic / etc)│                 │
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
