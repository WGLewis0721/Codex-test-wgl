# Troubleshooting Guide

This document covers common issues encountered when running the ITSM Tier 1 Agent locally or on AWS, with diagnostic commands and resolution steps.

---

## Table of Contents

- [Log Locations](#log-locations)
- [Diagnostic Commands](#diagnostic-commands)
- [Common Issues](#common-issues)
  - [Ollama Not Responding](#ollama-not-responding)
  - [Models Not Found](#models-not-found)
  - [S3 Access Denied](#s3-access-denied)
  - [ChromaDB Out of Memory](#chromadb-out-of-memory)
  - [OpenWebUI Cannot Connect to Ollama](#openwebui-cannot-connect-to-ollama)
  - [EC2 Instance Not Bootstrapping](#ec2-instance-not-bootstrapping)
  - [High Latency Responses](#high-latency-responses)
  - [Ingestion Returns No Documents](#ingestion-returns-no-documents)
  - [RAG Backend Returns 502](#rag-backend-returns-502)

---

## Log Locations

### Local (Docker Compose)

| Service | Command |
|---------|---------|
| All services | `docker compose logs -f` |
| Ollama only | `docker compose logs -f ollama` |
| RAG backend only | `docker compose logs -f rag-backend` |
| OpenWebUI only | `docker compose logs -f openwebui` |

### AWS (EC2)

| Log | Location | How to access |
|-----|----------|---------------|
| Bootstrap script | `/var/log/itsm-bootstrap.log` | SSH + `sudo cat` or CloudWatch |
| System messages | `/var/log/messages` | SSH + `sudo tail -f` or CloudWatch |
| CloudWatch agent | `/var/log/amazon-cloudwatch-agent.log` | SSH |
| Ollama service | `journalctl -u ollama -f` | SSH |
| Docker containers | `docker logs open-webui -f` | SSH |
| All app logs | `aws logs tail /itsm-agent --follow` | AWS CLI |

---

## Diagnostic Commands

### Quick system health check

```bash
curl http://localhost:8000/health | python3 -m json.tool
```

### Check all Docker containers are running

```bash
docker compose ps
```

### Check resource usage

```bash
# Memory and CPU per container
docker stats --no-stream

# Disk usage
df -h
```

### Check Ollama models are available

```bash
curl http://localhost:11434/api/tags | python3 -m json.tool
```

### Test embedding directly

```bash
curl -X POST http://localhost:11434/api/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model":"nomic-embed-text","prompt":"test query"}'
```

### Test chat directly

```bash
curl -X POST http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2:3b","messages":[{"role":"user","content":"hello"}],"stream":false}'
```

### Check ChromaDB chunk count

```bash
curl http://localhost:8000/health | python3 -c "
import sys, json
h = json.load(sys.stdin)
print('Chunks:', h['components']['chromadb'].get('chunk_count', 'N/A'))
"
```

---

## Common Issues

---

### Ollama Not Responding

**Symptom:** `curl http://localhost:11434/api/tags` times out or returns `Connection refused`. The health endpoint shows `"ollama": {"status": "error"}`.

**Causes and fixes:**

**1. Ollama container not started**

```bash
docker compose ps ollama
# If not running:
docker compose up -d ollama
docker compose logs ollama
```

**2. Ollama container is still initialising**

```bash
# Wait for healthy status
docker compose ps ollama
# STATUS column should show "(healthy)" — may take 30–60 seconds on first start
```

**3. Port conflict on 11434**

```bash
# Check if another process is using the port
lsof -i :11434
# Kill the conflicting process or change the host port mapping in docker-compose.yml
```

**4. Insufficient memory**

Ollama requires free RAM proportional to the model size. `llama3.2:3b` requires approximately 4 GB of RAM.

```bash
docker stats --no-stream
# If memory is at or near the system limit, close other applications or use a smaller model
```

---

### Models Not Found

**Symptom:** Ollama responds but chat requests fail with `"model not found"` or embedding calls return errors. `GET /api/tags` returns an empty `models` array.

**Fix — Pull models manually:**

```bash
# Using the pull script
OLLAMA_BASE_URL=http://localhost:11434 bash scripts/pull_models.sh

# Or manually via the Ollama API
curl -X POST http://localhost:11434/api/pull \
  -H "Content-Type: application/json" \
  -d '{"name":"nomic-embed-text"}'

curl -X POST http://localhost:11434/api/pull \
  -H "Content-Type: application/json" \
  -d '{"name":"llama3.2:3b"}'
```

Model downloads may take several minutes. Monitor progress:

```bash
docker compose logs -f ollama
```

**On EC2:** If the model specified in `terraform.tfvars` (`ollama_model`) failed to pull during bootstrap, SSH into the instance and run:

```bash
ollama pull llama3.2:3b
```

---

### S3 Access Denied

**Symptom:** The health endpoint shows `"s3": {"status": "error"}`. Ingestion fails with `AccessDenied` or `NoCredentialsError` in the logs.

**Diagnosis:**

```bash
# Check the error detail
curl http://localhost:8000/health | python3 -m json.tool

# Check backend logs for the specific error
docker compose logs rag-backend | grep -i "s3\|access\|credential\|denied"
```

**Fix — Local development:**

1. Ensure `.env` contains valid credentials:

```bash
cat .env | grep AWS
# AWS_ACCESS_KEY_ID=AKIA...
# AWS_SECRET_ACCESS_KEY=...
# AWS_REGION=us-east-1
# S3_BUCKET=your-itsm-docs-bucket
```

2. Verify the credentials work:

```bash
AWS_ACCESS_KEY_ID=$(grep AWS_ACCESS_KEY_ID .env | cut -d= -f2) \
AWS_SECRET_ACCESS_KEY=$(grep AWS_SECRET_ACCESS_KEY .env | cut -d= -f2) \
aws s3 ls s3://your-itsm-docs-bucket/
```

3. Restart the RAG backend to pick up the new credentials:

```bash
docker compose restart rag-backend
```

**Fix — AWS EC2:**

The EC2 instance uses an IAM instance role — no credentials should be in `.env`. Verify the role is attached:

```bash
# From the instance
curl -sf http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

If the bucket name is wrong, update the `S3_BUCKET` environment variable in the container and restart.

Verify the IAM role has the correct S3 permissions — see [docs/security.md](security.md) for the required policy.

---

### ChromaDB Out of Memory

**Symptom:** The RAG backend crashes or becomes unresponsive during ingestion. `docker stats` shows the container using near the full memory limit.

**Causes and fixes:**

**1. Large batch ingestion**

ChromaDB loads the collection into memory. For large knowledge bases (>10,000 chunks), consider:

- Increasing the Docker memory limit in `docker-compose.yml`:

```yaml
services:
  rag-backend:
    mem_limit: 4g
```

- Ingesting documents in smaller batches — add files to S3 incrementally and trigger `/documents/ingest` between batches.

**2. Collection size**

Check total chunk count:

```bash
curl http://localhost:8000/health | python3 -m json.tool
# "chunk_count": <n>
```

If the count is unexpectedly high (e.g., duplicate ingestion runs), delete and re-ingest:

```bash
# List documents
curl http://localhost:8000/documents | python3 -m json.tool

# Delete a specific document
curl -X DELETE http://localhost:8000/documents/<doc_id>

# Or restart the backend with a fresh ChromaDB volume
docker compose down
docker volume rm <project>_chroma_data
docker compose up -d
```

---

### OpenWebUI Cannot Connect to Ollama

**Symptom:** OpenWebUI shows a banner like "Ollama: Connection failed" or model selection is empty.

**Fix — Local:**

The OpenWebUI container uses `OLLAMA_BASE_URL=http://ollama:11434` to reach Ollama via the Docker Compose internal network. Verify Ollama is healthy:

```bash
docker compose ps ollama
# Should be "(healthy)"
```

If Ollama is healthy but OpenWebUI still fails, restart OpenWebUI:

```bash
docker compose restart openwebui
```

**Fix — AWS EC2:**

OpenWebUI on EC2 is configured with `--add-host=host-gateway:host-gateway` and `OLLAMA_BASE_URL=http://host-gateway:11434`. Verify Ollama is running on the host:

```bash
# On the EC2 instance
systemctl status ollama
curl http://localhost:11434/api/tags
```

If Ollama is stopped:

```bash
sudo systemctl start ollama
```

---

### EC2 Instance Not Bootstrapping

**Symptom:** The EC2 instance is running but OpenWebUI/Ollama are not reachable after 20+ minutes. Bootstrap log shows errors.

**Diagnosis:**

```bash
# SSH into the instance
ssh -i ~/.ssh/itsm-agent-key.pem ec2-user@<public_ip>

# Check bootstrap log
sudo cat /var/log/itsm-bootstrap.log

# Check for failed services
systemctl --failed
```

**Common causes:**

**1. Docker installation failed**

```bash
sudo systemctl status docker
# If not running:
sudo dnf install -y docker
sudo systemctl enable --now docker
```

**2. Ollama install script failed (network issue)**

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
```

**3. Model pull timed out**

```bash
ollama pull llama3.2:3b
```

**4. Data volume not mounted**

```bash
lsblk
# /dev/sdf or /dev/nvme1n1 should be mounted at /data
sudo mount -a
```

**5. Security group blocking connectivity**

From your local machine, confirm ports are reachable:

```bash
nc -zv <public_ip> 8080
nc -zv <public_ip> 8000
```

If not reachable, check the security group in the AWS Console or via Terraform to ensure ingress rules for ports 8080 and 8000 are in place.

---

### High Latency Responses

**Symptom:** Chat responses take more than 30–60 seconds.

**Causes and fixes:**

**1. CPU-only inference (no GPU)**

CPU inference with `llama3.2:3b` typically takes 15–60 seconds per response on a `t3.large`. Options:

- Switch to a smaller model (e.g., `llama3.2:1b`):

```bash
# Update .env
CHAT_MODEL=llama3.2:1b
docker compose restart rag-backend
ollama pull llama3.2:1b
```

- Deploy with GPU (`use_gpu = true` in `terraform.tfvars`, uses `g4dn.xlarge`)

**2. Model not cached in memory**

Ollama keeps the model loaded in RAM for a few minutes after the last request. If Ollama has unloaded the model, the first request will be slow while it reloads.

**3. Large document collection**

Increasing `TOP_K_RESULTS` beyond 5 increases retrieval overhead. Keep it at 3–5 for most use cases.

**4. Insufficient instance resources**

Monitor during a request:

```bash
# On the EC2 instance or locally
docker stats --no-stream
top
```

If CPU is at 100% and memory is exhausted, upgrade to a larger instance type.

---

### Ingestion Returns No Documents

**Symptom:** `POST /documents/ingest` returns success but `GET /documents` shows zero documents. `chunk_count` in health stays at 0.

**Diagnosis:**

```bash
docker compose logs rag-backend | grep -i "ingest\|s3\|error"
```

**Common causes:**

1. **Wrong S3 prefix** — Documents must be in the `knowledge-base/` prefix. Verify:

```bash
aws s3 ls s3://<bucket>/knowledge-base/
```

2. **Empty bucket** — No documents have been uploaded yet.

3. **Unsupported file format** — The ingestion service processes plain text, Markdown, and PDF. Binary formats (`.docx`, `.xlsx`) are not currently supported.

4. **S3 credentials invalid** — See [S3 Access Denied](#s3-access-denied).

5. **Ollama not available for embedding** — Ingestion requires Ollama to generate embeddings. If Ollama is down during ingestion, it will fail silently in the background. Check logs after triggering ingest.

---

### RAG Backend Returns 502

**Symptom:** `POST /chat` returns HTTP 502 with `"Chat service unavailable."` or `"Embedding service unavailable."`.

The backend uses exponential back-off retry (up to 4 attempts) before returning 502. This means the underlying service has been unreachable for up to ~30 seconds.

**Fix:**

1. Check Ollama status: `docker compose ps ollama`
2. Restart Ollama if needed: `docker compose restart ollama`
3. Verify the `OLLAMA_BASE_URL` env var matches the actual Ollama endpoint
4. On EC2: `sudo systemctl restart ollama`
