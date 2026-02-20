#!/bin/bash
set -euo pipefail

OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
EMBED_MODEL="${EMBED_MODEL:-nomic-embed-text}"
CHAT_MODEL="${CHAT_MODEL:-llama3.2:3b}"

echo "Waiting for Ollama to be healthy..."
until curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; do
  echo "  Ollama not ready yet — retrying in 5s..."
  sleep 5
done
echo "Ollama is healthy."

echo "Pulling embedding model: ${EMBED_MODEL}"
curl -sf -X POST "${OLLAMA_URL}/api/pull" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"${EMBED_MODEL}\"}" | tail -1

echo "Pulling chat model: ${CHAT_MODEL}"
curl -sf -X POST "${OLLAMA_URL}/api/pull" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"${CHAT_MODEL}\"}" | tail -1

echo ""
echo "Models pulled successfully:"
echo "  Embedding : ${EMBED_MODEL}"
echo "  Chat      : ${CHAT_MODEL}"
