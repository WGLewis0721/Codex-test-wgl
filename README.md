# ITSM Tier 1 Agent

An AI-powered IT Service Management (ITSM) Tier 1 support agent that uses Retrieval-Augmented Generation (RAG) to answer helpdesk queries from your own internal knowledge base. The system combines **Ollama** for local LLM inference, **OpenWebUI** for a chat interface, and a **FastAPI RAG backend** backed by **ChromaDB** and **AWS S3**.

> Deploy locally with Docker Compose in minutes, or to AWS with the included Terraform configuration.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Quick Start — Local with Docker](#quick-start--local-with-docker)
- [Usage](#usage)
- [AWS Deployment](#aws-deployment)
- [API Reference](#api-reference)
- [Configuration Reference](#configuration-reference)
- [Documentation](#documentation)
- [Contributing](#contributing)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         LOCAL / AWS EC2                         │
│                                                                 │
│   Browser                                                       │
│      │                                                          │
│      ▼                                                          │
│  ┌──────────────┐     REST     ┌──────────────────────────────┐ │
│  │  OpenWebUI   │─────────────▶│   RAG Backend (FastAPI)      │ │
│  │  :8080       │              │   :8000                      │ │
│  └──────┬───────┘              │                              │ │
│         │ Ollama API           │  1. Embed query              │ │
│         ▼                      │  2. Vector search (ChromaDB) │ │
│  ┌──────────────┐              │  3. Build context prompt     │ │
│  │    Ollama    │◀─────────────│  4. LLM response             │ │
│  │    :11434    │  Embeddings  └──────────────┬───────────────┘ │
│  └──────────────┘  & Chat                     │                 │
│                                               │ S3 GetObject    │
│                                ┌──────────────▼───────────────┐ │
│                                │   ChromaDB (vector store)    │ │
│                                │   persisted on disk          │ │
│                                └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                        ▲
                              AWS S3 ───┘  (knowledge-base docs)
```

| Component | Role | Default Port |
|-----------|------|-------------|
| **OpenWebUI** | Chat interface for end users | 8080 |
| **Ollama** | Local LLM & embedding inference | 11434 |
| **RAG Backend** | FastAPI service: ingestion, retrieval, chat | 8000 |
| **ChromaDB** | Persistent vector store (embedded in backend) | — |
| **AWS S3** | Document storage for the knowledge base | — |

For a detailed breakdown see [docs/architecture.md](docs/architecture.md).

---

## Prerequisites

### Local Development

| Requirement | Version | Notes |
|-------------|---------|-------|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | ≥ 24 | Docker Engine also works |
| Docker Compose v2 | ≥ 2.20 | Bundled with Docker Desktop |
| **RAM** | ≥ 8 GB free | 16 GB recommended for larger models |
| **Disk** | ≥ 20 GB free | Ollama model weights are large |

### AWS Deployment (optional)

| Requirement | Notes |
|-------------|-------|
| [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) | Configured with `aws configure` |
| [Terraform](https://developer.hashicorp.com/terraform/install) | ≥ 1.6 |
| EC2 Key Pair | Created in the target AWS region |
| IAM permissions | EC2, S3, VPC, IAM, CloudWatch |

---

## Quick Start — Local with Docker

### 1 — Clone the repository

```bash
git clone https://github.com/your-org/itsm-agent.git
cd itsm-agent
```

### 2 — Run the setup script

The script checks dependencies, copies `.env.example` → `.env`, starts all containers, and pulls the required Ollama models.

```bash
bash scripts/local_setup.sh
```

> **First run:** Ollama model downloads (`llama3.2:3b` ≈ 2 GB, `nomic-embed-text` ≈ 270 MB) will take a few minutes depending on your connection.

### 3 — Open the chat interface

Navigate to **http://localhost:8080** in your browser to start chatting.

### 4 — (Optional) Configure AWS credentials for S3 document ingestion

Edit `.env` and add your AWS credentials, then trigger ingestion:

```bash
# .env
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=your-itsm-docs-bucket
```

```bash
curl -X POST http://localhost:8000/documents/ingest
```

---

## Usage

### Uploading Documents to S3

Place documents (PDF, TXT, Markdown) in your S3 bucket under the `knowledge-base/` prefix:

```bash
aws s3 cp runbook.pdf     s3://your-itsm-docs-bucket/knowledge-base/
aws s3 cp procedures.md   s3://your-itsm-docs-bucket/knowledge-base/
aws s3 sync ./docs/        s3://your-itsm-docs-bucket/knowledge-base/
```

Then trigger re-ingestion via the RAG backend API:

```bash
curl -X POST http://localhost:8000/documents/ingest
```

### Using the Chat Interface

1. Open **http://localhost:8080**
2. Create an account (local OpenWebUI — data stays on your machine)
3. Select a model from the dropdown (e.g., `llama3.2:3b`)
4. Ask IT support questions — the agent retrieves relevant context from your knowledge base before answering

### Checking System Health

```bash
curl http://localhost:8000/health | python3 -m json.tool
```

Expected response when all services are healthy:

```json
{
  "status": "ok",
  "components": {
    "ollama":   { "status": "ok" },
    "chromadb": { "status": "ok", "chunk_count": 142 },
    "s3":       { "status": "ok", "bucket": "your-itsm-docs-bucket" }
  }
}
```

### Stopping the Stack

```bash
docker compose down          # stop containers, keep volumes
docker compose down -v       # stop containers AND delete all data volumes
```

---

## AWS Deployment

A full Terraform configuration is provided to deploy the agent to AWS on a single EC2 instance. The infrastructure includes a VPC, public/private subnets, security groups, S3 bucket, IAM roles, an Elastic IP, and CloudWatch monitoring.

**Brief steps:**

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set key_name, admin_cidr, etc.
terraform init
terraform plan
terraform apply
```

After `apply` completes, Terraform outputs the `openwebui_url` and `fastapi_url`.

> For the complete step-by-step guide including post-deployment configuration, see **[docs/deployment.md](docs/deployment.md)**.

---

## API Reference

The RAG backend exposes a REST API at `http://localhost:8000`. Interactive Swagger docs are available at **http://localhost:8000/docs**.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Component health check |
| `POST` | `/chat` | RAG-powered chat with session history |
| `GET` | `/documents` | List all ingested documents |
| `POST` | `/documents/ingest` | Trigger S3 sync and re-ingestion |
| `GET` | `/documents/{doc_id}/download` | Pre-signed S3 download URL |
| `DELETE` | `/documents/{doc_id}` | Remove document from vector store |

**Minimal chat example:**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user-123",
    "message": "How do I reset my VPN password?"
  }'
```

Full request/response schemas are documented in **[docs/api.md](docs/api.md)**.

---

## Configuration Reference

### Key Environment Variables (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_ACCESS_KEY_ID` | — | AWS credential (leave blank to use instance role on EC2) |
| `AWS_SECRET_ACCESS_KEY` | — | AWS credential |
| `AWS_REGION` | `us-east-1` | AWS region for S3 access |
| `S3_BUCKET` | `itsm-documents` | S3 bucket containing knowledge-base docs |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama API base URL |
| `EMBED_MODEL` | `nomic-embed-text` | Ollama model used for embeddings |
| `CHAT_MODEL` | `llama3.2:3b` | Ollama model used for chat responses |
| `CHROMA_PERSIST_DIR` | `/app/chroma_data` | ChromaDB persistence directory |
| `TOP_K_RESULTS` | `5` | Number of document chunks to retrieve per query |
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins (restrict in production) |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

For the full configuration reference including Terraform variables, Docker Compose options, and ChromaDB tuning parameters see **[docs/configuration.md](docs/configuration.md)**.

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/architecture.md](docs/architecture.md) | Detailed architecture, data flow, and RAG pipeline |
| [docs/deployment.md](docs/deployment.md) | Step-by-step AWS deployment guide |
| [docs/api.md](docs/api.md) | Full API documentation with request/response examples |
| [docs/configuration.md](docs/configuration.md) | All configuration variables with defaults |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Common issues and diagnostic commands |
| [docs/security.md](docs/security.md) | Security best practices and architecture |

---

## Contributing

1. Fork the repository and create a feature branch: `git checkout -b feat/my-feature`
2. Make your changes and ensure the stack starts cleanly: `bash scripts/local_setup.sh`
3. Test the API: `curl http://localhost:8000/health`
4. Commit your changes with a descriptive message and open a pull request

Please keep secrets out of source control — `.env` and `terraform.tfvars` are git-ignored for this reason.