# API Reference

The ITSM Tier 1 RAG Backend exposes a REST API built with FastAPI. Interactive Swagger UI is available at `/docs` and ReDoc at `/redoc`.

---

## Table of Contents

- [Base URL](#base-url)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [GET /health](#get-health)
  - [POST /chat](#post-chat)
  - [GET /documents](#get-documents)
  - [POST /documents/ingest](#post-documentsingest)
  - [GET /documents/{doc_id}/download](#get-documentsdoc_iddownload)
  - [DELETE /documents/{doc_id}](#delete-documentsdoc_id)
- [Error Responses](#error-responses)
- [Session Management](#session-management)

---

## Base URL

| Environment | Base URL |
|-------------|----------|
| Local development | `http://localhost:8000` |
| AWS (from terraform output) | `http://<public_ip>:8000` |

---

## Authentication

The RAG backend does not implement application-level authentication. Access control is enforced at the network layer:

- **Local:** Only accessible on `localhost` by default (Docker bridge network).
- **AWS:** Accessible on the EC2 Elastic IP. Restrict access by tightening the security group inbound rule for port 8000 to trusted CIDR ranges in `terraform.tfvars`.

For production workloads, place the RAG backend behind an Application Load Balancer with AWS WAF or an API Gateway with IAM/Cognito authentication.

---

## Endpoints

### GET /health

Returns the health status of all system components (Ollama, ChromaDB, S3).

**Request**

```http
GET /health HTTP/1.1
```

**Response — all healthy (200)**

```json
{
  "status": "ok",
  "components": {
    "ollama": {
      "status": "ok"
    },
    "chromadb": {
      "status": "ok",
      "chunk_count": 284
    },
    "s3": {
      "status": "ok",
      "bucket": "itsm-agent-docs-123456789012"
    }
  }
}
```

**Response — degraded (200)**

When one or more components are unavailable the top-level `status` becomes `"degraded"` and the affected component shows its error:

```json
{
  "status": "degraded",
  "components": {
    "ollama": {
      "status": "error",
      "detail": "Connection refused"
    },
    "chromadb": {
      "status": "ok",
      "chunk_count": 284
    },
    "s3": {
      "status": "ok",
      "bucket": "itsm-agent-docs-123456789012"
    }
  }
}
```

**Example**

```bash
curl http://localhost:8000/health | python3 -m json.tool
```

---

### POST /chat

Send a user message and receive a RAG-enhanced response from the ITSM agent.

The endpoint:
1. Embeds the message with the configured embedding model
2. Retrieves the top-K most relevant document chunks from ChromaDB
3. Injects the retrieved context into the system prompt
4. Sends the full conversation history to Ollama for response generation
5. Stores the exchange in the in-memory session history

**Request**

```http
POST /chat HTTP/1.1
Content-Type: application/json

{
  "session_id": "user-abc123",
  "message": "How do I reset my VPN password?",
  "model": "llama3.2:3b"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | ✅ | Caller-supplied session identifier. Use a stable ID (e.g., user UUID) to maintain conversation history across requests. |
| `message` | string | ✅ | The user's message or question. |
| `model` | string | ❌ | Override the Ollama chat model. Defaults to `CHAT_MODEL` env var (`llama3.2:3b`). |

**Response (200)**

```json
{
  "session_id": "user-abc123",
  "response": "To reset your VPN password, follow these steps:\n\n1. Navigate to the self-service portal at https://myaccess.company.com\n2. Click **Forgot Password** under the VPN section\n3. Enter your employee ID and corporate email address\n4. Check your email for a reset link (valid for 30 minutes)\n5. Follow the link to set a new password meeting the complexity requirements\n\nIf you do not receive the email within 5 minutes, check your spam folder or contact the help desk at ext. 4357.",
  "sources": [
    {
      "doc_id": "a1b2c3d4",
      "chunk_id": "a1b2c3d4_chunk_002",
      "score": 0.9231,
      "preview": "VPN Password Reset Procedure\n\nUsers can reset their VPN password via the self-service portal. Navigate to https://myaccess.company.com..."
    },
    {
      "doc_id": "e5f6g7h8",
      "chunk_id": "e5f6g7h8_chunk_001",
      "score": 0.8147,
      "preview": "Remote Access Policy\n\nAll VPN passwords must be rotated every 90 days and meet the following complexity requirements..."
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Echoed back from the request. |
| `response` | string | The assistant's generated response. |
| `sources` | array | Retrieved document chunks used to ground the response. |
| `sources[].doc_id` | string | Stable document identifier (SHA-256 prefix of the S3 key). |
| `sources[].chunk_id` | string | Unique chunk identifier within the document. |
| `sources[].score` | float | Cosine similarity score (0–1, higher = more relevant). |
| `sources[].preview` | string | First 300 characters of the chunk text. |

**Error Responses**

| Status | Condition |
|--------|-----------|
| `502` | Ollama embedding service is unreachable |
| `502` | Ollama chat service is unreachable |

**Example — multi-turn session**

```bash
# Turn 1
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"sess-001","message":"My laptop cannot connect to the corporate WiFi."}' \
  | python3 -m json.tool

# Turn 2 — the session history is retained
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"sess-001","message":"I already tried forgetting the network. What next?"}' \
  | python3 -m json.tool
```

---

### GET /documents

List all unique documents currently indexed in ChromaDB.

**Request**

```http
GET /documents HTTP/1.1
```

**Response (200)**

```json
{
  "total": 3,
  "documents": [
    {
      "doc_id": "a1b2c3d4",
      "source_key": "knowledge-base/vpn-reset-procedure.pdf",
      "chunk_count": 8
    },
    {
      "doc_id": "e5f6g7h8",
      "source_key": "knowledge-base/remote-access-policy.pdf",
      "chunk_count": 12
    },
    {
      "doc_id": "i9j0k1l2",
      "source_key": "knowledge-base/software-installation-guide.md",
      "chunk_count": 5
    }
  ]
}
```

**Example**

```bash
curl http://localhost:8000/documents | python3 -m json.tool
```

---

### POST /documents/ingest

Trigger the S3 ingestion pipeline. The endpoint returns immediately — ingestion runs in the background.

The pipeline:
1. Lists all objects under the `knowledge-base/` prefix in the configured S3 bucket
2. Downloads each document
3. Chunks the text (512 tokens, 64-token overlap)
4. Embeds each chunk via Ollama
5. Upserts embeddings and metadata into ChromaDB

Re-ingesting a document that already exists in ChromaDB will upsert (update) its chunks.

**Request**

```http
POST /documents/ingest HTTP/1.1
```

**Response (200)**

```json
{
  "message": "Ingestion started in the background."
}
```

**Example**

```bash
curl -X POST http://localhost:8000/documents/ingest
```

Monitor ingestion progress via the health endpoint (watch `chunk_count` increase) or application logs:

```bash
# Docker Compose
docker compose logs -f rag-backend

# AWS CloudWatch
aws logs tail /itsm-agent --follow
```

---

### GET /documents/{doc_id}/download

Generate a pre-signed S3 URL to download the original document. The URL is valid for 1 hour.

**Request**

```http
GET /documents/a1b2c3d4/download HTTP/1.1
```

| Parameter | Location | Description |
|-----------|----------|-------------|
| `doc_id` | Path | Document identifier from `GET /documents` |

**Response (200)**

```json
{
  "doc_id": "a1b2c3d4",
  "url": "https://itsm-agent-docs-123456789012.s3.amazonaws.com/knowledge-base/vpn-reset-procedure.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=..."
}
```

**Error Responses**

| Status | Condition |
|--------|-----------|
| `404` | `doc_id` not found in ChromaDB |
| `502` | Pre-signed URL generation failed (S3 connectivity issue) |

**Example**

```bash
DOC_ID="a1b2c3d4"
curl http://localhost:8000/documents/${DOC_ID}/download | python3 -m json.tool
```

---

### DELETE /documents/{doc_id}

Remove all indexed chunks for a document from ChromaDB. The original document in S3 is **not** deleted.

**Request**

```http
DELETE /documents/a1b2c3d4 HTTP/1.1
```

| Parameter | Location | Description |
|-----------|----------|-------------|
| `doc_id` | Path | Document identifier from `GET /documents` |

**Response (200)**

```json
{
  "message": "Document 'a1b2c3d4' deleted successfully."
}
```

**Error Responses**

| Status | Condition |
|--------|-----------|
| `404` | `doc_id` not found in ChromaDB |

**Example**

```bash
curl -X DELETE http://localhost:8000/documents/a1b2c3d4
```

To remove the document from S3 as well:

```bash
aws s3 rm s3://<bucket>/knowledge-base/vpn-reset-procedure.pdf
```

---

## Error Responses

The API returns standard HTTP error responses in the following format:

```json
{
  "detail": "Human-readable error message."
}
```

| HTTP Status | Meaning |
|------------|---------|
| `404 Not Found` | The requested resource (e.g., document) does not exist |
| `422 Unprocessable Entity` | Request body validation failed (missing or invalid fields) |
| `502 Bad Gateway` | An upstream service (Ollama, S3) is unreachable or returned an error |

---

## Session Management

The RAG backend maintains conversation history in memory to support multi-turn dialogue:

- Each `session_id` maps to a conversation history deque capped at **20 messages** (10 turns)
- A maximum of **1,000 concurrent sessions** are tracked; the oldest session is evicted when the cap is reached
- Session state is **not persisted** — restarting the backend clears all session history
- Use stable, unique session IDs (e.g., authenticated user UUID + conversation UUID) to maintain context across requests

For production deployments requiring persistent sessions, replace the in-memory `_sessions` dict in `backend/app/routers/chat.py` with a Redis-backed store.
