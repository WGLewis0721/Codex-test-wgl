#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Dependency checks ────────────────────────────────────────────────────────
echo "Checking dependencies..."

if ! command -v docker &> /dev/null; then
  echo "ERROR: docker is not installed or not in PATH." >&2
  exit 1
fi

if ! docker compose version &> /dev/null 2>&1; then
  echo "ERROR: docker compose (v2) is not available. Please upgrade Docker Desktop or install the Compose plugin." >&2
  exit 1
fi

echo "  docker        : $(docker --version)"
echo "  docker compose: $(docker compose version)"

# ── Environment file ─────────────────────────────────────────────────────────
if [[ ! -f "${REPO_ROOT}/.env" ]]; then
  echo ""
  echo "No .env found — copying .env.example to .env"
  cp "${REPO_ROOT}/.env.example" "${REPO_ROOT}/.env"
  echo "  Edit ${REPO_ROOT}/.env with your AWS credentials before re-running if needed."
else
  echo ""
  echo ".env already exists — skipping copy."
fi

# ── Start services ───────────────────────────────────────────────────────────
echo ""
echo "Starting services with docker compose..."
docker compose -f "${REPO_ROOT}/docker-compose.yml" up -d

# ── Wait for core services ───────────────────────────────────────────────────
echo ""
echo "Waiting for services to be ready..."

wait_healthy() {
  local name="$1"
  local url="$2"
  local retries=30

  echo -n "  Waiting for ${name}..."
  until curl -sf "${url}" > /dev/null 2>&1; do
    retries=$((retries - 1))
    if [[ $retries -le 0 ]]; then
      echo " TIMEOUT"
      echo "ERROR: ${name} did not become ready in time." >&2
      exit 1
    fi
    echo -n "."
    sleep 5
  done
  echo " ready."
}

wait_healthy "Ollama"       "http://localhost:11434/api/tags"
wait_healthy "RAG backend"  "http://localhost:8000/health"

# ── Pull Ollama models ───────────────────────────────────────────────────────
echo ""
echo "Pulling Ollama models (this may take a while on first run)..."
OLLAMA_BASE_URL="http://localhost:11434" \
  bash "${REPO_ROOT}/scripts/pull_models.sh"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "Setup complete. Services are running:"
echo "  OpenWebUI  : http://localhost:8080"
echo "  RAG API    : http://localhost:8000"
echo "  Ollama API : http://localhost:11434"
