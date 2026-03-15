"""LLM Service — wraps the Claude API for Q&A over retrieved document chunks."""

import logging
from typing import Optional

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    return _client


# ── System Prompt ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert Indian property lawyer specialising in Karnataka land law and Bangalore real estate due diligence.

You assist users in verifying land title documents such as:
- EC (Encumbrance Certificate / ಭಾರ ರಹಿತ ಪ್ರಮಾಣ ಪತ್ರ)
- RTC/Pahani (ಆರ್‌ಟಿಸಿ) — ownership, crop, land classification
- Sale Deed (ಮಾರಾಟ ಪತ್ರ)
- Khata Certificate & Extract (ಖಾತಾ)
- Mutation Register (ಮ್ಯುಟೇಷನ್ ರಿಜಿಸ್ಟರ್)
- Survey Sketch / FMB
- BBMP / BDA approval documents

Rules:
1. Answer ONLY from the provided document excerpts (context). Do not fabricate or guess facts.
2. If the context is insufficient, say so clearly and suggest what document to check.
3. When you quote specific details (names, dates, numbers), cite the document type and page.
4. You can respond in the language the user writes in (English or Kannada).
5. Flag potential red flags or discrepancies you notice in the documents.
6. Always remind users that this is an AI-assisted review and should be confirmed by a licensed lawyer before any transaction."""


def answer_question(
    question: str,
    context_chunks: list[dict],
    property_metadata: dict | None = None,
    kg_context: str | None = None,
) -> tuple[str, int]:
    """Ask Claude a question grounded in retrieved document chunks.

    Args:
        kg_context: Optional knowledge graph summary to prepend for richer context.

    Returns:
        (answer: str, tokens_used: int)
    """
    client = _get_client()
    s = get_settings()

    # Build context string
    context_parts = []
    for chunk in context_chunks:
        doc_type = chunk.get("metadata", {}).get("doc_type", "UNKNOWN")
        context_parts.append(
            f"[{doc_type}]\n{chunk['chunk_text']}"
        )
    context_str = "\n\n---\n\n".join(context_parts)

    property_str = ""
    if property_metadata:
        property_str = (
            f"\nProperty details: Survey No. {property_metadata.get('survey_number', 'N/A')}, "
            f"Taluk: {property_metadata.get('taluk', 'N/A')}, "
            f"Village: {property_metadata.get('village', 'N/A')}\n"
        )

    kg_str = f"\n{kg_context}\n" if kg_context else ""

    user_message = f"""{property_str}{kg_str}
Document excerpts:
{context_str}

Question: {question}"""

    response = client.messages.create(
        model=s.claude_model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    answer = response.content[0].text
    tokens_used = response.usage.input_tokens + response.usage.output_tokens

    return answer, tokens_used


def run_due_diligence_check(
    check_name: str,
    check_prompt: str,
    context_chunks: list[dict],
    property_metadata: dict | None = None,
    kg_context: str | None = None,
) -> dict:
    """Run a single structured due diligence check.

    Args:
        kg_context: Optional knowledge graph summary for additional entity context.

    Returns a dict with status, summary, findings, sources.
    """
    client = _get_client()
    s = get_settings()

    context_parts = []
    for chunk in context_chunks:
        doc_type = chunk.get("metadata", {}).get("doc_type", "UNKNOWN")
        context_parts.append(f"[{doc_type}]\n{chunk['chunk_text']}")
    context_str = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant documents found."

    property_str = ""
    if property_metadata:
        property_str = (
            f"Property: Survey No. {property_metadata.get('survey_number', 'N/A')}, "
            f"Taluk: {property_metadata.get('taluk', 'N/A')}\n\n"
        )

    kg_str = f"{kg_context}\n\n" if kg_context else ""

    prompt = f"""{property_str}{kg_str}Document excerpts:
{context_str}

Check: {check_name}
{check_prompt}

Respond ONLY with a JSON object (no markdown fences) with this exact schema:
{{
  "status": "PASS" | "FAIL" | "WARN" | "MISSING",
  "summary": "one-sentence summary",
  "findings": ["finding 1", "finding 2"],
  "sources": ["document type/name referenced"]
}}"""

    response = client.messages.create(
        model=s.claude_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    import json
    raw = response.content[0].text.strip()
    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse check JSON for {check_name}: {raw}")
        return {
            "status": "WARN",
            "summary": "Could not parse structured response.",
            "findings": [raw[:500]],
            "sources": [],
        }
