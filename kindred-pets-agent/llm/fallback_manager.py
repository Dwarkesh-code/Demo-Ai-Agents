"""
llm/fallback_manager.py
LLMFallbackManager — tries Groq models, then Gemini models, in order.
On rate-limit / auth / timeout error, moves to the next model automatically.
Logs which provider/model actually served the request.
"""

import os
import time
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass

# ─── Model ordering (edit these lists to change priority) ───────────────────

# Provider order: "groq_first" or "gemini_first"
PROVIDER_ORDER = "groq_first"

GROQ_MODELS = [
    "llama-3.3-70b-versatile",     # primary  — best quality | 1K RPD, 12K TPM
    "llama-3.1-8b-instant",        # fast     — highest RPD  | 14.4K RPD, 6K TPM
    "openai/gpt-oss-120b",         # backup   — strong model | 1K RPD, 8K TPM
    "qwen/qwen3.6-27b",            # backup   — 1K RPD, 8K TPM
    "openai/gpt-oss-20b",          # fallback — 1K RPD, 8K TPM
]

GEMINI_MODELS = [
    "gemini-3.5-flash-lite",       # primary  — highest quota | 15 RPM, 500 RPD
    "gemini-3.1-flash-lite",       # secondary             | 15 RPM, 500 RPD
    "gemini-2.5-flash-lite",       # tertiary              | 10 RPM,  20 RPD
    "gemini-3.5-flash",            # further backup        |  5 RPM,  20 RPD
    "gemini-3.7-flash",            # last resort           |  5 RPM,  20 RPD
]

# ─── Internal model entry type ───────────────────────────────────────────────

@dataclass
class ModelEntry:
    provider: str   # "groq" or "gemini"
    model: str
    client: object  # groq.Groq or google.generativeai client


# ─── Manager class ───────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)


class LLMFallbackManager:
    """
    Tries an ordered list of LLM (provider, model) pairs.
    Falls through on HTTP 429, auth errors, or timeouts.
    Exposes a single generate(system_prompt, messages) -> str interface.
    """

    def __init__(self):
        self._entries: List[ModelEntry] = []
        self._last_used_label: str = "none"
        self._build_entries()

    def _build_entries(self):
        """Initialise client objects and build the ordered fallback list."""
        groq_key    = os.environ.get("GROQ_API_KEY", "")
        gemini_key  = os.environ.get("GEMINI_API_KEY", "")

        groq_entries: List[ModelEntry] = []
        gemini_entries: List[ModelEntry] = []

        # ── Groq ──────────────────────────────────────────────────────────────
        if groq_key:
            try:
                from groq import Groq
                groq_client = Groq(api_key=groq_key)
                for model in GROQ_MODELS:
                    groq_entries.append(
                        ModelEntry(provider="groq", model=model, client=groq_client)
                    )
            except ImportError:
                logger.warning("groq package not installed — skipping Groq models.")
        else:
            logger.warning("GROQ_API_KEY not set — skipping Groq models.")

        # ── Gemini (new google-genai SDK) ─────────────────────────────────────
        if gemini_key:
            try:
                from google import genai as google_genai
                gemini_client = google_genai.Client(api_key=gemini_key)
                for model in GEMINI_MODELS:
                    gemini_entries.append(
                        ModelEntry(provider="gemini", model=model, client=gemini_client)
                    )
            except ImportError:
                logger.warning("google-genai package not installed — skipping Gemini models.")
        else:
            logger.warning("GEMINI_API_KEY not set — skipping Gemini models.")

        # ── Assemble in configured order ──────────────────────────────────────
        if PROVIDER_ORDER == "gemini_first":
            self._entries = gemini_entries + groq_entries
        else:
            self._entries = groq_entries + gemini_entries

        if not self._entries:
            raise RuntimeError(
                "No LLM providers available. Set GROQ_API_KEY and/or GEMINI_API_KEY."
            )

    @property
    def last_used(self) -> str:
        """Human-readable label for which model answered last (for UI display)."""
        return self._last_used_label

    # ─── Core generation method ────────────────────────────────────────────

    def generate(
        self,
        system_prompt: str,
        messages: List[dict],   # [{"role": "user"|"assistant", "content": str}, …]
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """
        Try each model in order. Return the first successful response.
        Raises RuntimeError only if ALL models fail.
        """
        last_error: Optional[Exception] = None

        for entry in self._entries:
            try:
                logger.info(f"Trying {entry.provider}/{entry.model} …")
                if entry.provider == "groq":
                    response = self._call_groq(
                        entry, system_prompt, messages, max_tokens, temperature
                    )
                else:
                    response = self._call_gemini(
                        entry, system_prompt, messages, max_tokens, temperature
                    )
                self._last_used_label = f"{entry.provider} · {entry.model}"
                logger.info(f"✅ Served by: {self._last_used_label}")
                return response

            except Exception as e:
                err_str = str(e)
                logger.warning(
                    f"❌ {entry.provider}/{entry.model} failed: {err_str[:120]}"
                )
                last_error = e

                # Only retry on recoverable errors; hard-fail immediately otherwise
                if self._is_recoverable(err_str):
                    time.sleep(0.3)   # tiny back-off before next attempt
                    continue
                else:
                    # Non-recoverable (e.g. bad request) — skip this model
                    continue

        raise RuntimeError(
            f"All LLM models exhausted. Last error: {last_error}"
        )

    # ─── Provider-specific callers ─────────────────────────────────────────

    def _call_groq(
        self,
        entry: ModelEntry,
        system_prompt: str,
        messages: List[dict],
        max_tokens: int,
        temperature: float,
    ) -> str:
        all_messages = [{"role": "system", "content": system_prompt}] + messages
        completion = entry.client.chat.completions.create(
            model=entry.model,
            messages=all_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=20,
        )
        return completion.choices[0].message.content.strip()

    def _call_gemini(
        self,
        entry: ModelEntry,
        system_prompt: str,
        messages: List[dict],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Uses the new google-genai SDK (google.genai.Client)."""
        from google.genai import types as genai_types

        client = entry.client

        # Build the conversation contents in the new SDK format
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                genai_types.Content(
                    role=role,
                    parts=[genai_types.Part(text=msg["content"])],
                )
            )

        config = genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=temperature,
        )

        response = client.models.generate_content(
            model=entry.model,
            contents=contents,
            config=config,
        )
        # Safely extract text — response.text raises if content was blocked
        try:
            text = response.text
        except (AttributeError, ValueError) as exc:
            raise RuntimeError(f"Gemini response blocked or empty: {exc}") from exc
        if not text or not text.strip():
            raise RuntimeError("Gemini returned an empty response.")
        return text.strip()

    # ─── Error classification ──────────────────────────────────────────────

    @staticmethod
    def _is_recoverable(error_str: str) -> bool:
        """
        Rate-limit, auth, quota, and timeout errors are worth retrying on
        the next model. Bad-request / invalid-argument errors are not.
        """
        recoverable_keywords = [
            "429", "rate_limit", "rate limit",
            "quota", "exceeded",
            "timeout", "timed out",
            "503", "502", "500",
            "auth", "authentication", "401", "403",
            "unavailable", "overloaded",
        ]
        low = error_str.lower()
        return any(kw in low for kw in recoverable_keywords)
