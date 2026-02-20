# Configuration Reference

Complete reference for all configuration options across Terraform, environment variables, Docker Compose, ChromaDB, and Ollama model selection.

---

## Table of Contents

- [Environment Variables](#environment-variables)
- [Terraform Variables](#terraform-variables)
- [Docker Compose Configuration](#docker-compose-configuration)
- [ChromaDB Tuning Parameters](#chromadb-tuning-parameters)
- [Ollama Model Selection Guide](#ollama-model-selection-guide)

---

## Environment Variables

The RAG backend is configured via environment variables. For local development, copy `.env.example` to `.env` and edit the values. Docker Compose passes this file to the `rag-backend` service via `env_file: .env`.

On EC2, set these as environment variables in the container run command or via a secrets manager.

### AWS Configuration

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `AWS_ACCESS_KEY_ID` | — | Local only | AWS access key ID. Leave blank on EC2 — the instance role provides credentials automatically. |
| `AWS_SECRET_ACCESS_KEY` | — | Local only | AWS secret access key. Leave blank on EC2. |
| `AWS_REGION` | `us-east-1` | ❌ | AWS region where the S3 bucket resides. |
| `S3_BUCKET` | `itsm-documents` | ✅ | Name of the S3 bucket containing knowledge-base documents. |

### Ollama Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Base URL of the Ollama API server. In Docker Compose this resolves via the internal network. Change to `http://localhost:11434` if running the backend outside Docker. |
| `EMBED_MODEL` | `nomic-embed-text` | Ollama model used to generate embeddings during ingestion and query. Must be pulled before use. |
| `CHAT_MODEL` | `llama3.2:3b` | Default Ollama model for chat responses. Can be overridden per-request via the `model` field in the `/chat` payload. |

### ChromaDB Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMA_PERSIST_DIR` | `/app/chroma_data` | Directory where ChromaDB persists its on-disk storage. Mapped to the `chroma_data` Docker volume locally and to `/data/app` on EC2. |

> The ChromaDB collection name is hardcoded as `itsm_docs` in `backend/app/config.py` (`chroma_collection_name`).

### Chunking Parameters

These control how documents are split into chunks before embedding.

| Variable | Default | Description |
|----------|---------|-------------|
| `CHUNK_SIZE` | `512` | Maximum number of tokens per text chunk. Larger chunks preserve more context per retrieval result but reduce precision. |
| `CHUNK_OVERLAP` | `64` | Number of tokens shared between consecutive chunks. Prevents losing context at chunk boundaries. |

**Tuning guidance:**
- For dense technical documents (runbooks, procedures): `CHUNK_SIZE=512`, `CHUNK_OVERLAP=64` (defaults work well)
- For long-form policy documents: increase to `CHUNK_SIZE=768`, `CHUNK_OVERLAP=128`
- For short FAQ entries: decrease to `CHUNK_SIZE=256`, `CHUNK_OVERLAP=32`

### Retrieval Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TOP_K_RESULTS` | `5` | Number of most similar document chunks to retrieve per query. Higher values provide more context but increase prompt length and latency. |

**Tuning guidance:**
- `3` — Fast, lower context, suitable for simple factual queries
- `5` — Default, balanced (recommended)
- `7–10` — Higher context for complex, multi-part questions; monitor for prompt length limits

### Application Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Python logging level for the FastAPI backend. Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Use `DEBUG` during development to see detailed request/response logs. |
| `CORS_ORIGINS` | `["*"]` | JSON array of allowed CORS origins. Restrict to specific origins in production, e.g., `["http://localhost:8080","https://itsm.company.com"]`. |

### Complete .env Example

```ini
# AWS credentials (local dev only — use IAM role on EC2)
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1
S3_BUCKET=itsm-agent-docs-123456789012

# Ollama
OLLAMA_BASE_URL=http://ollama:11434
EMBED_MODEL=nomic-embed-text
CHAT_MODEL=llama3.2:3b

# ChromaDB
CHROMA_PERSIST_DIR=/app/chroma_data

# Chunking
CHUNK_SIZE=512
CHUNK_OVERLAP=64

# Retrieval
TOP_K_RESULTS=5

# Application
LOG_LEVEL=INFO
CORS_ORIGINS=["http://localhost:8080","http://localhost:3000"]
```

---

## Terraform Variables

All variables are defined in `terraform/variables.tf`. Override them in `terraform/terraform.tfvars`.

### General

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `aws_region` | string | `"us-east-1"` | AWS region where all resources are deployed. |
| `project_name` | string | `"itsm-agent"` | Short name used to prefix all resource names (lowercase, no spaces). |
| `environment` | string | `"dev"` | Deployment environment label. Allowed: `dev`, `staging`, `prod`. |

### Networking

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `vpc_cidr` | string | `"10.0.0.0/16"` | CIDR block for the VPC. |
| `public_subnet_cidrs` | list(string) | `["10.0.1.0/24","10.0.2.0/24"]` | CIDRs for public subnets, one per Availability Zone. |
| `private_subnet_cidrs` | list(string) | `["10.0.101.0/24","10.0.102.0/24"]` | CIDRs for private subnets (reserved for future use). |
| `availability_zones` | list(string) | `["us-east-1a","us-east-1b"]` | AZs to deploy subnets into. Must match subnet CIDR list length. |
| `admin_cidr` | string | `"0.0.0.0/0"` | CIDR allowed to reach the instance on port 22 (SSH). **Always restrict this to your IP in production.** |

### Compute

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `instance_type` | string | `"t3.large"` | EC2 instance type for CPU-only deployments. |
| `gpu_instance_type` | string | `"g4dn.xlarge"` | EC2 instance type when `use_gpu = true`. |
| `use_gpu` | bool | `false` | Set to `true` to deploy a GPU instance. See [Ollama Model Selection Guide](#ollama-model-selection-guide). |
| `key_name` | string | *(required)* | Name of an existing EC2 Key Pair. No default — must be set in `terraform.tfvars`. |
| `root_volume_size_gb` | number | `50` | Size in GiB of the root EBS volume. |
| `data_volume_size_gb` | number | `100` | Size in GiB of the secondary data EBS volume (model weights, app data). |

### Application

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ollama_model` | string | `"llama3.2:3b"` | Ollama model pulled during EC2 bootstrap. |
| `openwebui_port` | number | `8080` | TCP port for the OpenWebUI service. |
| `fastapi_port` | number | `8000` | TCP port for the FastAPI RAG backend. |

### S3

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `s3_bucket_name` | string | `""` | S3 bucket name. Leave empty to auto-generate: `<project_name>-docs-<account_id>`. |
| `s3_lifecycle_ia_days` | number | `90` | Days before objects transition to STANDARD_IA. |
| `s3_lifecycle_glacier_days` | number | `365` | Days before objects transition to GLACIER. |
| `s3_lifecycle_expiry_days` | number | `730` | Days before non-current object versions are permanently deleted. |

### CloudWatch

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `log_retention_days` | number | `90` | Days to retain logs in CloudWatch. |
| `cpu_alarm_threshold` | number | `80` | CPU utilisation % that triggers the high-CPU alarm. |
| `memory_alarm_threshold` | number | `85` | Memory utilisation % that triggers the high-memory alarm. |
| `disk_alarm_threshold` | number | `85` | Disk utilisation % that triggers the high-disk alarm. |
| `alarm_sns_arn` | string | `""` | ARN of an existing SNS topic for alarm notifications. Leave empty to skip. |

### Terraform Outputs

After `terraform apply`, the following outputs are available:

| Output | Description |
|--------|-------------|
| `openwebui_url` | `http://<elastic_ip>:8080` |
| `fastapi_url` | `http://<elastic_ip>:8000` |
| `ssh_command` | Ready-to-use SSH command |
| `s3_bucket_name` | The (possibly auto-generated) bucket name |
| `instance_id` | EC2 instance ID |
| `public_ip` | Elastic IP address |
| `log_group_name` | CloudWatch log group name |
| `dashboard_url` | Direct link to the CloudWatch dashboard |

```bash
# Print all outputs
terraform output

# Get a specific output
terraform output openwebui_url
```

---

## Docker Compose Configuration

The `docker-compose.yml` at the repository root defines three services.

### Service: `ollama`

```yaml
image: ollama/ollama:latest
ports:
  - "11434:11434"
volumes:
  - ollama_data:/root/.ollama
```

**Customisation options:**

- **GPU support (Linux only):** Add the `deploy` block to pass the GPU to the container:

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

Requires the NVIDIA Container Toolkit: `nvidia-ctk runtime configure --runtime=docker`.

- **Custom model directory:** Add an environment variable:

```yaml
environment:
  OLLAMA_MODELS: /custom/path
volumes:
  - /host/path:/custom/path
```

### Service: `openwebui`

```yaml
image: ghcr.io/open-webui/open-webui:main
ports:
  - "8080:8080"
environment:
  OLLAMA_BASE_URL: http://ollama:11434
```

**Customisation options:**

- **Change the host port** (e.g., if 8080 is in use):

```yaml
ports:
  - "3000:8080"
```

- **Disable user registration** (single-user or pre-provisioned accounts):

```yaml
environment:
  WEBUI_AUTH: "false"
```

- **Set a custom title:**

```yaml
environment:
  WEBUI_NAME: "ITSM Support Agent"
```

### Service: `rag-backend`

```yaml
build: ./backend
ports:
  - "8000:8000"
env_file:
  - .env
environment:
  OLLAMA_BASE_URL: http://ollama:11434
  CHROMA_PERSIST_DIR: /app/chroma_data
volumes:
  - chroma_data:/app/chroma_data
```

**Customisation options:**

- **Memory limit** (recommended for large document collections):

```yaml
mem_limit: 4g
```

- **Use a pre-built image** instead of building locally:

```yaml
image: your-registry/itsm-backend:latest
# Remove: build: ./backend
```

- **Mount local source code** for development with live reload:

```yaml
volumes:
  - ./backend:/app
  - chroma_data:/app/chroma_data
command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## ChromaDB Tuning Parameters

ChromaDB is embedded directly into the RAG backend process. The following parameters affect performance and storage.

### Collection Configuration

Configured in `backend/app/config.py`:

| Parameter | Config Key | Default | Notes |
|-----------|-----------|---------|-------|
| Persistence directory | `chroma_persist_dir` | `/app/chroma_data` | Set via `CHROMA_PERSIST_DIR` env var |
| Collection name | `chroma_collection_name` | `itsm_docs` | Hardcoded in config; change and re-ingest if needed |

### Memory and Performance

ChromaDB loads the active collection's index into memory. Approximate memory usage:

| Chunks | Approximate RAM |
|--------|----------------|
| 1,000 | ~50 MB |
| 10,000 | ~200 MB |
| 100,000 | ~1.5 GB |

For large collections, increase the Docker memory limit for the `rag-backend` service.

### Distance Function

ChromaDB defaults to cosine similarity for text embeddings, which is appropriate for the `nomic-embed-text` model. This is set at collection creation time and cannot be changed without recreating the collection.

### Resetting the Vector Store

To clear all indexed documents and start fresh:

```bash
# Stop the stack
docker compose down

# Remove the ChromaDB volume
docker volume rm $(docker volume ls -q | grep chroma)

# Restart and re-ingest
docker compose up -d
curl -X POST http://localhost:8000/documents/ingest
```

---

## Ollama Model Selection Guide

Choosing the right models depends on your hardware, latency requirements, and response quality needs.

### Embedding Models

The embedding model converts text to vectors and runs during every ingestion and query. It must be fast and produce high-quality semantic representations.

| Model | Size | Dimensions | Use Case |
|-------|------|-----------|---------|
| `nomic-embed-text` *(default)* | ~270 MB | 768 | Best general-purpose embedding model for Ollama. Recommended for production. |
| `all-minilm` | ~45 MB | 384 | Smallest/fastest option. Slightly lower quality. Good for resource-constrained environments. |
| `mxbai-embed-large` | ~670 MB | 1024 | Higher-quality embeddings, especially for technical documents. Requires more RAM. |

> After changing the embedding model, you must delete and re-ingest all documents — existing embeddings are incompatible with a different model's vector space.

### Chat Models

| Model | Size | RAM Required | GPU | Quality | Recommended For |
|-------|------|-------------|-----|---------|----------------|
| `llama3.2:1b` | ~1.3 GB | 4 GB | ❌ | Basic | Very low-resource environments |
| `llama3.2:3b` *(default)* | ~2.0 GB | 4–6 GB | ❌ | Good | CPU-only deployments (`t3.large`) |
| `llama3.1:8b` | ~5.0 GB | 10–12 GB | Optional | Very good | `t3.2xlarge` (CPU) or `g4dn.xlarge` (GPU) |
| `llama3.1:70b` | ~40 GB | 48+ GB | Required | Excellent | `g4dn.12xlarge` or `p3.2xlarge` |
| `mistral:7b` | ~4.1 GB | 8–10 GB | Optional | Good | Alternative to Llama for instruction following |
| `phi3:mini` | ~2.3 GB | 4–6 GB | ❌ | Good | CPU-only; strong at reasoning tasks |

### Recommended Configurations by Hardware

**Local development (8–16 GB RAM, no GPU):**
```ini
EMBED_MODEL=nomic-embed-text
CHAT_MODEL=llama3.2:3b
```

**Local development (32 GB RAM, no GPU):**
```ini
EMBED_MODEL=nomic-embed-text
CHAT_MODEL=llama3.1:8b
```

**AWS t3.large (8 GB RAM, CPU-only):**
```ini
EMBED_MODEL=nomic-embed-text
CHAT_MODEL=llama3.2:3b
```

**AWS g4dn.xlarge (16 GB RAM, 1× NVIDIA T4 GPU, 16 GB VRAM):**
```ini
EMBED_MODEL=nomic-embed-text
CHAT_MODEL=llama3.1:8b   # Fits fully in GPU VRAM
```

**AWS g4dn.12xlarge (192 GB RAM, 4× NVIDIA T4 GPU, 64 GB VRAM):**
```ini
EMBED_MODEL=mxbai-embed-large
CHAT_MODEL=llama3.1:70b
```

### Pulling Models

```bash
# Pull locally via the Ollama container
docker compose exec ollama ollama pull llama3.1:8b

# Or via the Ollama API
curl -X POST http://localhost:11434/api/pull \
  -H "Content-Type: application/json" \
  -d '{"name":"llama3.1:8b"}'

# List all available models
curl http://localhost:11434/api/tags | python3 -m json.tool
```

### Switching Models at Runtime

The chat model can be overridden per-request in the `/chat` API without restarting the backend:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user-123",
    "message": "What is the WiFi password policy?",
    "model": "llama3.1:8b"
  }'
```

To change the default permanently, update `CHAT_MODEL` in `.env` and restart the backend:

```bash
# Edit .env: CHAT_MODEL=llama3.1:8b
docker compose restart rag-backend
```
