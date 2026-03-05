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

1. `pip install "prysmai[all]==0.4.0" fastapi uvicorn python-dotenv`
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

## SDK Version

`prysmai==0.4.0` with extras: `[langchain]`, `[crewai]`, `[llamaindex]`, `[all]`
