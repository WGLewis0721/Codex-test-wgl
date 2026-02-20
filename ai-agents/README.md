# CNAP AI Agents

A unified, locally-runnable AI agent platform with 6 production-ready agents built on Ollama, FastAPI, Streamlit, and SQLite.

## Architecture Overview

```
ai-agents/
  shared/           # Shared utilities (config, logging, ollama, storage, etc.)
  agents/
    support-triage/        # Agent 1: Support ticket triage & routing
    knowledge-copilot/     # Agent 2: Document-grounded Q&A (RAG)
    lead-qualification/    # Agent 3: Lead scoring & qualification
    customer-profile/      # Agent 4: Customer technical profile builder
    interview-fit/         # Agent 5: Resume + JD fit analysis
    workbench-gateway/     # Agent 6: OpenAI-compatible LLM gateway
  docker-compose.yml
  Makefile
```

## Agent Index

| Agent | Description | API Port | UI Port | API Docs |
|-------|-------------|----------|---------|----------|
| [Support Triage](agents/support-triage/README.md) | Ticket urgency, sentiment, routing | 8001 | 8501 | http://localhost:8001/docs |
| [Knowledge Copilot](agents/knowledge-copilot/README.md) | RAG Q&A with citations | 8002 | 8502 | http://localhost:8002/docs |
| [Lead Qualification](agents/lead-qualification/README.md) | Deterministic lead scoring | 8003 | 8503 | http://localhost:8003/docs |
| [Customer Profile](agents/customer-profile/README.md) | Versioned technical profiles | 8004 | 8504 | http://localhost:8004/docs |
| [Interview Fit](agents/interview-fit/README.md) | Resume + JD analysis | 8005 | 8505 | http://localhost:8005/docs |
| [Workbench Gateway](agents/workbench-gateway/README.md) | OpenAI-compatible gateway | 8006 | 8506 | http://localhost:8006/docs |

## Quick Start

### Prerequisites
- Docker Desktop (≥ 24) or Docker Engine + Compose v2
- 16 GB RAM recommended (Ollama model weights)
- 20 GB free disk space

### Start All Agents

```bash
cd ai-agents
docker compose up --build
```

On first run, pull the required Ollama models:

```bash
make pull-model
```

### Check Agent Status

```bash
make status
```

### Run Tests

```bash
make test
```

### Stop All Services

```bash
docker compose down        # Keep data volumes
docker compose down -v     # Remove all data
```

## Development Guide

### Project Structure

Each agent follows the same structure:

```
agent-name/
  agent/          # Core logic (prompts, classifier/scorer/analyzer, storage)
  api/main.py     # FastAPI server
  app/ui.py       # Streamlit UI (or dashboard.py for Agent 6)
  tests/          # pytest unit tests
  Dockerfile.api
  Dockerfile.ui
  docker-compose.yml
  requirements.txt
  README.md
```

### Shared Module

The `shared/` directory provides utilities used by all agents:

| File | Purpose |
|------|---------|
| `config.py` | Environment variables & defaults (Pydantic Settings) |
| `logging.py` | Structured JSON logging with PII masking |
| `ollama.py` | Ollama HTTP client (chat, embed, list_models) |
| `opensearch.py` | Optional OpenSearch integration (disabled by default) |
| `storage.py` | SQLite helpers (connection, CRUD, pagination) |
| `schemas.py` | Base Pydantic models (HealthResponse, etc.) |
| `utils.py` | PDF extraction, text chunking, markdown generation |

### Run a Single Agent

```bash
cd agents/support-triage
docker-compose up
```

### Run Tests for One Agent

```bash
make test-agent AGENT=support-triage
```

## Configuration

Key environment variables (set in `.env` or `docker-compose.yml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama API base URL |
| `OLLAMA_MODEL` | `phi3:medium` | Default LLM model |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `SQLITE_DIR` | `/app/data` | SQLite data directory |
| `OPENSEARCH_ENABLED` | `false` | Enable OpenSearch integration |
| `OPENSEARCH_URL` | `http://localhost:9200` | OpenSearch URL |
| `RATE_LIMIT_PER_MINUTE` | `60` | Requests per minute per client |
| `LOG_LEVEL` | `INFO` | Logging level |

## OpenSearch Integration (Optional)

OpenSearch enrichment is disabled by default. To enable:

```yaml
environment:
  OPENSEARCH_ENABLED: "true"
  OPENSEARCH_URL: "http://your-opensearch:9200"
  OPENSEARCH_INDEX: "cnap-events"
```

When enabled, agents query recent OpenSearch events to enrich LLM context.

## Non-Negotiable Rules

- AI is **advisory only** — no automated infrastructure modification
- No direct credential usage in code
- No cross-tenant data access
- All agents run with `docker compose up`
- No cloud dependencies for MVP execution
