"""LLM prompts for Knowledge Copilot."""

RAG_SYSTEM = """You are a helpful knowledge assistant. Answer questions ONLY using the provided context.
If the context does not contain enough information, say exactly: "I don't have enough information to answer that."
Always cite your sources using [Doc: filename] notation."""

RAG_PROMPT = """Context from knowledge base:
{context}

Question: {query}

Answer based only on the context above. Include citations."""
