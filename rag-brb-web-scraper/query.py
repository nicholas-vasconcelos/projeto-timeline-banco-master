import json
import re
from pathlib import Path
from langchain_chroma import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama

CHROMA_PATH = Path(__file__).parent / "chroma_db"

# ── Prompt ──────────────────────────────────────────────────────────────────
# Structured extraction prompt. The JSON schema is enforced here.
# The model is instructed never to hallucinate prices.
SYSTEM_PROMPT = """You are a financial event extraction engine specialized in the
Banco Master / BRB (Banco de Brasília) crisis of 2025–2026.

You will receive excerpts from news articles and analysis documents.
Extract ONLY events that had a measurable or notable impact on BRB's stock
(BSLI3 / BSLI4) or its market position.

Respond ONLY with a valid JSON object. No prose, no markdown fences, no explanation.
The JSON must exactly follow this schema:

{
  "events": [
    {
      "date": "YYYY-MM-DD",
      "title_en": "Short English title, max 8 words",
      "title_pt": "Título curto em português, máx 8 palavras",
      "description_en": "1–2 sentence factual description in English.",
      "description_pt": "Descrição factual de 1–2 frases em português.",
      "bsli3_change_pct": null,
      "bsli4_change_pct": null,
      "price_bsli4": null,
      "sentiment": "bullish|bearish|neutral|crisis",
      "category": "regulatory|legal|market|fraud|governance|arrest",
      "sources": ["source_file_1.md"]
    }
  ]
}

Rules:
- title_en and description_en must be in English.
- title_pt and description_pt must be in Brazilian Portuguese.
- Only populate bsli3_change_pct / bsli4_change_pct / price_bsli4 if the number
  appears explicitly in the provided context. Otherwise use null.
- If multiple chunks describe the same event, merge them into one event object.
- Do not invent events not supported by the provided context.
- dates must be ISO 8601 (YYYY-MM-DD). If only a month is known, use the 1st.
- sentiment must be one of the four enum values exactly.
"""

RETRIEVAL_QUERIES = [
    "BRB BSLI3 BSLI4 stock price drop surge percentage change",
    "Banco Master BRB acquisition announcement March 2025",
    "BACEN Central Bank rejection BRB acquisition September 2025",
    "Operation Compliance Zero Vorcaro arrested November 2025",
    "BRB capital increase provision R$8 billion March 2026",
    "Banco Master liquidation extrajudicial November 2025",
    "BRB BSLI4 queda ações fevereiro 2026 plano recapitalização",
    "Vorcaro arrested again STF March 2026 third phase",
    "CADE approval BRB Master acquisition June 2025",
    "CLDF legislative approval August 2025 BRB Master",
]

def get_vectorstore():
    return Chroma(
        collection_name="brb_master_crisis",
        embedding_function=OllamaEmbeddings(
            model="nomic-embed-text",
            base_url="http://localhost:11434",
        ),
        persist_directory=str(CHROMA_PATH),
    )

def retrieve_chunks(vectorstore, queries: list[str], k_per_query: int = 4) -> list:
    """Multi-query retrieval: run each query, deduplicate by content hash."""
    seen   = set()
    chunks = []
    for query in queries:
        results = vectorstore.similarity_search(query, k=k_per_query)
        for doc in results:
            key = hash(doc.page_content[:120])
            if key not in seen:
                seen.add(key)
                chunks.append(doc)
    return chunks

def build_context(chunks: list) -> str:
    parts = []
    for i, chunk in enumerate(chunks):
        src = chunk.metadata.get("source_file", "unknown")
        parts.append(f"[CHUNK {i+1} | source: {src}]\n{chunk.page_content}\n")
    return "\n---\n".join(parts)

def extract_json(raw: str) -> dict:
    """Robustly extract JSON from LLM output even if it adds prose around it."""
    # Strip markdown fences if present
    raw = re.sub(r"```json|```", "", raw).strip()
    # Find the first { ... } block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON found in LLM output:\n{raw[:500]}")

def query_rag(custom_queries: list[str] | None = None) -> dict:
    queries = custom_queries or RETRIEVAL_QUERIES

    print("Loading vector store...")
    vs = get_vectorstore()
    total = vs._collection.count()
    if total == 0:
        raise RuntimeError("ChromaDB is empty. Run ingest.py first.")
    print(f"  {total} chunks in store.")

    print(f"Retrieving chunks across {len(queries)} queries...")
    chunks = retrieve_chunks(vs, queries, k_per_query=4)
    print(f"  {len(chunks)} unique chunks retrieved.")

    context = build_context(chunks)

    # Trim context to ~8000 chars to stay within Mistral 7B context window
    if len(context) > 8000:
        context = context[:8000] + "\n\n[context truncated]"

    llm = Ollama(
        model="mistral",
        base_url="http://localhost:11434",
        temperature=0.0,   # deterministic for structured extraction
        num_predict=4096,
    )

    full_prompt = f"{SYSTEM_PROMPT}\n\n=== CONTEXT ===\n{context}\n\n=== OUTPUT JSON ==="
    print("Querying Mistral 7B... (may take 20–60s on your hardware)")
    raw_output = llm.invoke(full_prompt)

    events = extract_json(raw_output)
    print(f"  Extracted {len(events.get('events', []))} events.")
    return events

if __name__ == "__main__":
    result = query_rag()
    print(json.dumps(result, indent=2, ensure_ascii=False))