# AI Workbench Gateway

OpenAI-compatible local LLM gateway for IDE integration.

## Features
- OpenAI-compatible `/v1/chat/completions` endpoint
- Model allowlist enforcement
- Rate limiting
- Request metadata logging (no raw prompts)
- Streamlit dashboard with metrics

## Usage
```bash
docker-compose up
```
- Dashboard: http://localhost:8506
- API: http://localhost:8006
- API Docs: http://localhost:8006/docs
- OpenAI-compatible: http://localhost:8006/v1/chat/completions

## IDE Integration
Configure your IDE's OpenAI extension to use:
- Base URL: http://localhost:8006/v1
- API Key: (any value, not required)
