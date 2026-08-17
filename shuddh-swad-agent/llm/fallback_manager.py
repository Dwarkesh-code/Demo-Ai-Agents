"""
llm/fallback_manager.py
-----------------------
LLMFallbackManager — a thin wrapper that tries multiple (provider, model)
pairs in order, falling back on rate-limit (HTTP 429), auth errors, or
timeouts, and never failing the user's request unless every option is
exhausted.

Why this exists:
- The demo will be shown to a real business. "Sorry, I'm down right now"
  is a deal-breaker.
- Groq has generous token limits but per-model rate limits; Gemini has
  per-day quotas. We want a single uniform call site.

Design notes:
- We import the SDKs lazily inside the call so that if you only have one
  provider's key configured, the other one never breaks import time.
- The exact models the user specified are hard-coded below. Update them
  there if Groq / Gemini retire a name.
- The full ordered chain is built in `build_default_chain()`.
- Last refreshed: 2026-08-11 (latest available models on both providers).
"""

from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger("shuddh_swad.llm")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


# --------------------------------------------------------------------------
# Provider-order switch.
# Flip PROVIDER_ORDER to ["gemini", "groq"] if you want Gemini first.
# --------------------------------------------------------------------------
PROVIDER_ORDER = ["groq", "gemini"]


@dataclass
class ModelSpec:
    provider: str       # "groq" | "gemini"
    model: str          # model id / name
    label: str          # human-readable caption for the UI ("Groq · llama-3.3-70b")


# --------------------------------------------------------------------------
# Latest model chain — refreshed 2026-08-11
#
# Groq: https://console.groq.com/docs/models
#   - llama-3.3-70b-versatile  → workhorse, best quality
#   - openai/gpt-oss-120b      → strong open-source, 500 t/s
#   - qwen/qwen3.6-27b         → newest Qwen (released 2026-07-04)
#   - llama-3.1-8b-instant     → 840 t/s, very cheap, great fallback
#   - openai/gpt-oss-20b       → 1000 t/s, ultra-cheap last-resort
#
# Gemini: https://ai.google.dev/gemini-api/docs/models
#   - gemini-3.5-flash         → GA, smartest Flash for agentic work
#   - gemini-3.6-flash         → latest stable Flash (newest)
#   - gemini-3.5-flash-lite    → ultra-cheap, lowest latency
#   - gemini-3.1-flash-lite    → stable Flash-Lite
#
# NOTE: gemini-2.5-flash-lite was retired on 2026-06-01 — do NOT use it.
# --------------------------------------------------------------------------

GROQ_CHAIN: List[ModelSpec] = [
    ModelSpec("groq", "llama-3.3-70b-versatile",  "Groq · llama-3.3-70b-versatile"),
    ModelSpec("groq", "openai/gpt-oss-120b",     "Groq · gpt-oss-120b"),
    ModelSpec("groq", "qwen/qwen3.6-27b",        "Groq · qwen3.6-27b"),
    ModelSpec("groq", "llama-3.1-8b-instant",    "Groq · llama-3.1-8b-instant"),
    ModelSpec("groq", "openai/gpt-oss-20b",      "Groq · gpt-oss-20b"),
]

GEMINI_CHAIN: List[ModelSpec] = [
    ModelSpec("gemini", "gemini-3.5-flash",      "Gemini · 3.5-flash"),
    ModelSpec("gemini", "gemini-3.6-flash",      "Gemini · 3.6-flash"),
    ModelSpec("gemini", "gemini-3.5-flash-lite", "Gemini · 3.5-flash-lite"),
    ModelSpec("gemini", "gemini-3.1-flash-lite", "Gemini · 3.1-flash-lite"),
]


def build_default_chain() -> List[ModelSpec]:
    """
    Returns the full ordered list of models to try, expanding PROVIDER_ORDER.
    """
    chains = {"groq": GROQ_CHAIN, "gemini": GEMINI_CHAIN}
    out: List[ModelSpec] = []
    for prov in PROVIDER_ORDER:
        out.extend(chains.get(prov, []))
    return out


# --------------------------------------------------------------------------
# Exception classification
# --------------------------------------------------------------------------

# A loose set of substrings that indicate a "try the next model" situation.
# We treat all of these as recoverable: the next model might still work.
_RETRIABLE_HINTS = (
    "429", "rate limit", "rate_limit", "quota", "exhausted",
    "503", "service unavailable", "timeout", "timed out",
    "connection", "reset by peer", "temporarily", "unavailable",
    "internal error", "500", "502", "504",
    "unauthorized", "401", "invalid api key", "auth", "permission",
)


class AllProvidersExhausted(RuntimeError):
    """Raised when no model in the chain could serve the request."""


def _is_retriable(exc: Exception) -> bool:
    msg = (str(exc) or "").lower()
    return any(h in msg for h in _RETRIABLE_HINTS)


# --------------------------------------------------------------------------
# Provider-specific callers. Each returns a string reply or raises.
# --------------------------------------------------------------------------

def _call_groq(spec: ModelSpec, system_prompt: str, messages: list, timeout: float = 30.0) -> str:
    """Call Groq with the given model. Lazy import so missing key doesn't break import."""
    from groq import Groq  # type: ignore

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set in the environment")

    client = Groq(api_key=api_key, timeout=timeout)
    full_messages = [{"role": "system", "content": system_prompt}] + list(messages)
    resp = client.chat.completions.create(
        model=spec.model,
        messages=full_messages,
        temperature=0.4,
        max_tokens=800,
    )
    return resp.choices[0].message.content or ""


def _call_gemini(spec: ModelSpec, system_prompt: str, messages: list, timeout: float = 30.0) -> str:
    """Call Gemini via the new google-genai SDK. Lazy import."""
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment")

    client = genai.Client(api_key=api_key)

    # Convert openai-style messages to Gemini contents
    contents = []
    if system_prompt:
        contents.append(types.Content(
            role="user",
            parts=[types.Part(text=f"[SYSTEM INSTRUCTION]\n{system_prompt}\n[END SYSTEM INSTRUCTION]")],
        ))
    for m in messages:
        role = m.get("role", "user")
        text = m.get("content", "")
        # Gemini alternates user/model. We collapse all non-system to user
        # except the last one which we keep as 'model' to keep the turn-taking
        # natural; the SDK is forgiving either way.
        contents.append(types.Content(
            role="user" if role in ("user", "system") else "model",
            parts=[types.Part(text=text)],
        ))

    resp = client.models.generate_content(
        model=spec.model,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.4,
            max_output_tokens=800,
        ),
    )
    return resp.text or ""


_DISPATCH = {
    "groq":   _call_groq,
    "gemini": _call_gemini,
}


# --------------------------------------------------------------------------
# The main class
# --------------------------------------------------------------------------

class LLMFallbackManager:
    """
    Try each (provider, model) in order. On retriable error, move to the next.
    Returns (text, used_label). Raises AllProvidersExhausted if none work.
    """

    def __init__(
        self,
        chain: Optional[List[ModelSpec]] = None,
        sleep_between: float = 0.4,
        max_retries_per_model: int = 1,
    ):
        self.chain = chain or build_default_chain()
        self.sleep_between = sleep_between
        self.max_retries_per_model = max_retries_per_model
        self.last_used: Optional[str] = None  # for UI / debug

    def generate(
        self,
        system_prompt: str,
        messages: list,
        temperature: Optional[float] = None,  # accepted for API symmetry; SDK uses its own default
    ) -> str:
        """
        Run the full fallback chain. Returns the text reply.
        Records the actually-used provider/model in self.last_used.
        """
        if not self.chain:
            raise AllProvidersExhausted("Empty LLM chain — check PROVIDER_ORDER and model lists.")

        last_exc: Optional[Exception] = None
        for spec in self.chain:
            caller = _DISPATCH.get(spec.provider)
            if caller is None:
                logger.warning("Unknown provider in chain: %s", spec.provider)
                continue

            for attempt in range(self.max_retries_per_model + 1):
                try:
                    logger.info("LLM call → %s (%s)", spec.label, spec.model)
                    text = caller(spec, system_prompt, messages)
                    self.last_used = spec.label
                    if text is None:
                        raise RuntimeError("Empty response from model")
                    return text
                except Exception as e:  # noqa: BLE001
                    last_exc = e
                    if _is_retriable(e):
                        logger.warning("Model %s failed (retriable): %s", spec.label, e)
                        # fall through to next attempt or next model
                        if attempt < self.max_retries_per_model:
                            time.sleep(self.sleep_between)
                            continue
                        else:
                            break  # next model
                    else:
                        # Non-retriable (e.g. malformed input). Still try next model
                        # in case it's a quirk of one provider, but log clearly.
                        logger.warning("Model %s failed (non-retriable): %s", spec.label, e)
                        break

            time.sleep(self.sleep_between)

        raise AllProvidersExhausted(
            f"All {len(self.chain)} models failed. Last error: {last_exc}"
        )

    # Convenience for the Streamlit sidebar
    def describe_chain(self) -> List[str]:
        return [f"{s.label} ({s.provider})" for s in self.chain]


# --------------------------------------------------------------------------
# Read keys from Streamlit secrets if available (so this file works in both
# `streamlit run` and plain python).
# --------------------------------------------------------------------------

def load_keys_into_env() -> None:
    """If running under Streamlit, copy st.secrets into os.environ once."""
    try:
        import streamlit as st  # type: ignore
        if hasattr(st, "secrets"):
            for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
                if k in st.secrets and k not in os.environ:
                    os.environ[k] = str(st.secrets[k])
    except Exception:
        # Not running under streamlit, or secrets not configured — fine.
        pass
