"""
LLM Provider Abstraction
------------------------
Set LLM_PROVIDER in .env to switch between providers.
All other modules import from here — never import openai or google.generativeai directly.

.env options:
    LLM_PROVIDER=openai    (default)  requires OPENAI_API_KEY
    LLM_PROVIDER=gemini               requires GEMINI_API_KEY

Optional model overrides in .env:
    CHAT_MODEL=gpt-4o
    EMBED_MODEL=text-embedding-3-small
"""

import os
from typing import List

PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
if PROVIDER not in ("openai", "gemini"):
    raise ValueError(f"LLM_PROVIDER must be 'openai' or 'gemini', got '{PROVIDER}'")

_DEFAULTS = {
    "openai": {"chat": "gpt-4o",            "embed": "text-embedding-3-small"},
    "gemini": {"chat": "gemini-2.0-flash",  "embed": "models/gemini-embedding-001"},
}

CHAT_MODEL  = os.getenv("CHAT_MODEL",  _DEFAULTS[PROVIDER]["chat"])
EMBED_MODEL = os.getenv("EMBED_MODEL", _DEFAULTS[PROVIDER]["embed"])


# ── Public API ────────────────────────────────────────────────────────────────

def chat(messages: list[dict], json_mode: bool = False) -> str:
    """
    Send messages and return the response as a plain string.

    messages — OpenAI format:
        [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]

    json_mode — hint to the model to return valid JSON (used in karpathy_rag).
    """
    if PROVIDER == "gemini":
        return _gemini_chat(messages, json_mode)
    return _openai_chat(messages, json_mode)


def embed(text: str) -> List[float]:
    """Embed a text string and return a float vector."""
    if PROVIDER == "gemini":
        return _gemini_embed(text)
    return _openai_embed(text)


def get_chroma_embedding_fn():
    """Return a Chroma-compatible embedding function for the active provider."""
    if PROVIDER == "gemini":
        return _gemini_chroma_fn()
    return _openai_chroma_fn()


# ── OpenAI ────────────────────────────────────────────────────────────────────

def _openai_chat(messages: list[dict], json_mode: bool) -> str:
    from openai import OpenAI
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    resp = OpenAI().chat.completions.create(
        model=CHAT_MODEL, messages=messages, **kwargs
    )
    return resp.choices[0].message.content


def _openai_embed(text: str) -> List[float]:
    from openai import OpenAI
    resp = OpenAI().embeddings.create(model=EMBED_MODEL, input=text[:8000])
    return resp.data[0].embedding


def _openai_chroma_fn():
    from chromadb.utils import embedding_functions
    return embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name=EMBED_MODEL,
    )


# ── Gemini (google-genai SDK) ─────────────────────────────────────────────────

def _gemini_client():
    from google import genai
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def _gemini_chat(messages: list[dict], json_mode: bool) -> str:
    from google import genai
    from google.genai import types

    client = _gemini_client()
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    turns  = [m for m in messages if m["role"] != "system"]

    cfg = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json" if json_mode else None,
    )

    if len(turns) == 1:
        return client.models.generate_content(
            model=CHAT_MODEL,
            contents=turns[0]["content"],
            config=cfg,
        ).text

    # Multi-turn
    history = [
        types.Content(
            role="model" if m["role"] == "assistant" else "user",
            parts=[types.Part(text=m["content"])],
        )
        for m in turns[:-1]
    ]
    chat_session = client.chats.create(model=CHAT_MODEL, config=cfg, history=history)
    return chat_session.send_message(turns[-1]["content"]).text


def _gemini_embed(text: str) -> List[float]:
    client = _gemini_client()
    result = client.models.embed_content(model=EMBED_MODEL, contents=text[:8000])
    return result.embeddings[0].values


def _gemini_chroma_fn():
    """Custom Chroma embedding function using the new google-genai SDK."""
    from chromadb import EmbeddingFunction

    api_key = os.getenv("GEMINI_API_KEY")
    model   = EMBED_MODEL

    class _GeminiEmbedFn(EmbeddingFunction):
        def name(self) -> str:
            return "gemini_embedding"

        def __call__(self, input: list[str]) -> list[list[float]]:
            from google import genai
            c = genai.Client(api_key=api_key)
            result = c.models.embed_content(model=model, contents=input)
            return [e.values for e in result.embeddings]

    return _GeminiEmbedFn()
