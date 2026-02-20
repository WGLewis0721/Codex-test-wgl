# Architecture

This document describes the system architecture of the ITSM Tier 1 Agent, covering each component, data flows, the RAG pipeline, and differences between local and AWS deployments.

---

## Table of Contents

- [System Overview](#system-overview)
- [Component Descriptions](#component-descriptions)
- [Data Flow Diagrams](#data-flow-diagrams)
- [RAG Pipeline](#rag-pipeline)
- [Local vs AWS Deployment](#local-vs-aws-deployment)
- [Security Architecture Overview](#security-architecture-overview)

---

## System Overview

The ITSM Tier 1 Agent is a Retrieval-Augmented Generation (RAG) system designed to answer IT support queries using your organisation's internal knowledge base. Rather than relying solely on an LLM's training data, every response is grounded in documents you provide — runbooks, procedures, FAQs, and policy guides stored in S3.

The system is built from five core components:

```
┌───────────────────────────────────────────────────────────────────────┐
│                                                                       │
│   ┌──────────────┐                                                    │
│   │   End User   │                                                    │
│   └──────┬───────┘                                                    │
│          │ HTTP :8080                                                  │
│          ▼                                                             │
│   ┌──────────────────┐   /api/chat    ┌──────────────────────────┐    │
│   │   OpenWebUI      │──────────────▶│   RAG Backend (FastAPI)  │    │
│   │   (chat UI)      │               │   :8000                  │    │
│   └──────────────────┘               └──────┬──────────┬─────────┘    │
│                                             │          │              │
│                              embed / chat   │          │  list/get    │
│                                             ▼          ▼              │
│                              ┌──────────────┐   ┌──────────────────┐  │
│                              │    Ollama    │   │    ChromaDB      │  │
│                              │  (LLM + emb) │   │  (vector store)  │  │
│                              │   :11434     │   │  (on-disk)       │  │
│                              └──────────────┘   └──────────────────┘  │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
                                         ▲
                           AWS S3 ───────┘  (knowledge-base/ documents)
```

---

## Component Descriptions

### OpenWebUI

- **Image:** `ghcr.io/open-webui/open-webui:main`
- **Port:** 8080
- **Purpose:** Provides a fully-featured chat interface for end users. Connects to Ollama for direct model conversations and can be extended with custom tools/pipelines.
- **Data persistence:** User accounts, conversation history, and settings are stored in `/app/backend/data` (Docker volume: `openwebui_data`).
- **Configuration:** `OLLAMA_BASE_URL` points to the Ollama service. In Docker Compose this is `http://ollama:11434`; on EC2 it uses the host gateway.

### Ollama

- **Image:** `ollama/ollama:latest`
- **Port:** 11434
- **Purpose:** Serves two types of models:
  - **Embedding model** (`nomic-embed-text`): Converts text chunks and queries into high-dimensional vectors.
  - **Chat model** (`llama3.2:3b` or configurable): Generates natural-language responses given a context-enriched prompt.
- **Data persistence:** Model weights are stored in `/root/.ollama` (Docker volume: `ollama_data`). On EC2, models are stored on the secondary data volume at `/data/ollama`.
- **Health check:** `GET /api/tags` — returns a list of available models.

### RAG Backend (FastAPI)

- **Build context:** `./backend`
- **Port:** 8000
- **Purpose:** The central orchestration service. It:
  1. Ingests documents from S3 (chunking, embedding, storing in ChromaDB)
  2. Accepts chat requests from OpenWebUI or direct API consumers
  3. Embeds the user query, retrieves relevant chunks, builds a context-enriched system prompt, and delegates to Ollama for the final response
  4. Maintains per-session conversation history (in-memory, up to 1,000 sessions × 20 turns)
- **Key libraries:** FastAPI, ChromaDB, httpx, tenacity, pydantic-settings
- **Health check:** `GET /health` — checks Ollama, ChromaDB, and S3 connectivity.

### ChromaDB

- **Mode:** Embedded (runs inside the RAG backend process)
- **Persistence:** Docker volume `chroma_data` mounted at `/app/chroma_data`
- **Collection:** `itsm_docs`
- **Purpose:** Stores document chunk embeddings as vectors alongside metadata (doc ID, chunk ID, S3 source key, chunk index). Provides approximate nearest-neighbour search for retrieval.

### AWS S3

- **Purpose:** Durable storage for raw knowledge-base documents (PDFs, Markdown, plain text).
- **Prefix convention:** `knowledge-base/` — documents placed here are synced and ingested.
- **Access:** On EC2, the instance IAM role grants scoped read/write access. For local development, credentials are provided via `.env`.
- **Lifecycle:** Configured via Terraform — objects transition to STANDARD_IA after 90 days, GLACIER after 365 days, and non-current versions are deleted after 730 days.

---

## Data Flow Diagrams

### Document Ingestion Flow

```
  S3 Bucket (knowledge-base/)
         │
         │  1. ListObjectsV2
         ▼
  RAG Backend
  IngestionService
         │
         │  2. GetObject (download file bytes)
         ▼
  Text Extraction
  (plain text / PDF parsing)
         │
         │  3. Chunk text
         │     chunk_size=512, chunk_overlap=64
         ▼
  For each chunk:
         │
         │  4. POST /api/embeddings → Ollama (nomic-embed-text)
         │     Returns: [float, ...] (768-dim vector)
         ▼
  ChromaDB upsert
  (vector + metadata: doc_id, chunk_id, source_key)
         │
         ▼
  Ingestion summary logged
```

### Chat / Query Flow

```
  User types message in OpenWebUI
         │
         │  POST /chat  {session_id, message}
         ▼
  RAG Backend – /chat endpoint
         │
         │  1. POST /api/embeddings → Ollama
         │     Embed user query → query_vector
         ▼
  ChromaDB similarity search
  (cosine distance, top_k=5)
         │
         │  Returns: [(chunk_text, metadata, score), ...]
         ▼
  Build system prompt:
  ┌──────────────────────────────────────────┐
  │ You are an ITSM Tier 1 support agent.    │
  │                                          │
  │ --- CONTEXT START ---                    │
  │ [Source: runbook.pdf]                    │
  │ <chunk text from ChromaDB>               │
  │ [Source: faq.md]                         │
  │ <chunk text from ChromaDB>               │
  │ --- CONTEXT END ---                      │
  └──────────────────────────────────────────┘
         │
         │  2. POST /api/chat → Ollama (llama3.2:3b)
         │     Messages: [system, ...history, user]
         ▼
  Ollama generates response
         │
         │  3. Store turn in session history (deque, max 20)
         ▼
  Return {response, sources, session_id}
         │
         ▼
  OpenWebUI displays response + source citations
```

---

## RAG Pipeline

Retrieval-Augmented Generation (RAG) enhances an LLM's answers by injecting relevant, up-to-date context from a private knowledge base into the prompt at inference time.

### Step 1 — Embed the Query

The user's message is sent to Ollama's `/api/embeddings` endpoint with the `nomic-embed-text` model. This produces a dense vector representation of the query's semantic meaning.

### Step 2 — Vector Search

ChromaDB performs an approximate nearest-neighbour search across all stored chunk embeddings using cosine similarity. The `TOP_K_RESULTS` (default: 5) most similar chunks are returned.

### Step 3 — Context Injection

The retrieved chunk texts are assembled into a structured block and injected into a system prompt. The prompt instructs the model to use only this context when answering, avoiding hallucination of facts not present in the knowledge base.

### Step 4 — LLM Response

The full conversation (system prompt with context + history + user message) is sent to Ollama's `/api/chat` endpoint. The LLM synthesises an answer grounded in the retrieved context.

### Step 5 — Source Attribution

The API response includes a `sources` array listing which documents and chunks were used, allowing the UI to display citations alongside the answer.

---

## Local vs AWS Deployment

| Aspect | Local (Docker Compose) | AWS (Terraform) |
|--------|----------------------|-----------------|
| **Infrastructure** | Single machine, Docker Compose | VPC + EC2 + S3 + IAM + CloudWatch |
| **Ollama** | Docker container | Native install via `ollama.com/install.sh` |
| **OpenWebUI** | Docker container | Docker container on EC2 |
| **RAG Backend** | Docker container (built locally) | Docker container on EC2 |
| **ChromaDB** | Docker volume on local disk | Secondary EBS volume (`/data`) |
| **S3 access** | AWS credentials in `.env` | EC2 IAM instance role (no stored keys) |
| **Networking** | `localhost` / Docker bridge network | VPC with public subnet, Elastic IP, security groups |
| **TLS / HTTPS** | None (development only) | Not included; add ALB + ACM or nginx for production |
| **Scaling** | Single machine | Single EC2 instance (horizontal scaling not included) |
| **Monitoring** | Container logs (`docker compose logs`) | CloudWatch Logs + Metrics + Alarms + Dashboard |
| **Model storage** | Docker volume | `/data/ollama` on 100 GiB gp3 EBS volume |
| **Bootstrap** | `scripts/local_setup.sh` | EC2 user-data (`terraform/scripts/user_data.sh`) |

### AWS Infrastructure Components

```
┌──────────────── AWS Account ─────────────────────────────────────────┐
│                                                                      │
│  ┌──────────────── VPC (10.0.0.0/16) ──────────────────────────────┐ │
│  │                                                                  │ │
│  │  ┌── Public Subnet (10.0.1.0/24) ──────────────────────────┐    │ │
│  │  │                                                          │    │ │
│  │  │  ┌─────────────────────────────────────────────────┐    │    │ │
│  │  │  │  EC2 Instance (t3.large or g4dn.xlarge)         │    │    │ │
│  │  │  │  + Elastic IP                                   │    │    │ │
│  │  │  │  + 50 GiB root EBS (encrypted)                  │    │    │ │
│  │  │  │  + 100 GiB data EBS (encrypted, persistent)     │    │    │ │
│  │  │  │  + IAM Instance Profile                         │    │    │ │
│  │  │  └─────────────────────────────────────────────────┘    │    │ │
│  │  │                                                          │    │ │
│  │  │  Security Group                                          │    │ │
│  │  │  ├─ Ingress: 8080 (OpenWebUI)  from 0.0.0.0/0           │    │ │
│  │  │  ├─ Ingress: 8000 (RAG API)    from 0.0.0.0/0           │    │ │
│  │  │  ├─ Ingress:   22 (SSH)        from admin_cidr           │    │ │
│  │  │  └─ Egress:  all               to   0.0.0.0/0           │    │ │
│  │  └──────────────────────────────────────────────────────────┘    │ │
│  │                                                                  │ │
│  │  ┌── Private Subnets (10.0.101.0/24, 10.0.102.0/24) ───────┐    │ │
│  │  │  (reserved for future database / cache tier)             │    │ │
│  │  └──────────────────────────────────────────────────────────┘    │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  S3 Bucket (itsm-agent-docs-<account_id>)                           │
│  CloudWatch Log Group (/itsm-agent)                                 │
│  CloudWatch Dashboard + Alarms                                      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Security Architecture Overview

See [docs/security.md](security.md) for the full security guide. Key points:

- **IAM least privilege:** The EC2 instance role grants access only to the specific S3 bucket and scoped CloudWatch log groups. No `*` resource wildcards on sensitive actions.
- **IMDSv2 enforced:** The EC2 instance requires token-based Instance Metadata Service access (`http_tokens = required`), mitigating SSRF-based credential theft.
- **Encrypted storage:** Both EBS volumes (root and data) use AES-256 encryption at rest. S3 uses SSE-S3 by default.
- **Network isolation:** The VPC separates the instance from other AWS resources. SSH access is restricted to `admin_cidr` in `terraform.tfvars`. OpenWebUI and the RAG API are accessible from the internet by default — restrict via security group rules for production.
- **No secrets in code:** AWS credentials are never stored in source code. Locally they live in `.env` (git-ignored). On EC2, the instance profile provides temporary credentials via the metadata service.
- **Session Manager:** The IAM role includes `AmazonSSMManagedInstanceCore`, enabling SSH-free access via AWS Systems Manager Session Manager with a full audit trail.
