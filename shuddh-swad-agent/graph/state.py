"""
graph/state.py
--------------
LangGraph state schema. The state is the single source of truth that
flows through every node.

We use TypedDict (not a Pydantic model) because LangGraph's add_messages
reducer + TypedDict gives us the most predictable behavior with
multiple nodes writing to `messages`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict

# Literal type used to validate the query_type field at runtime if needed.
QueryType = Literal[
    "product_info",
    "pricing",
    "faq_policy",
    "order_tracking",
    "greeting_smalltalk",
    "out_of_scope",
]

LanguageStyle = Literal["english", "hinglish", "hindi"]


class AgentState(TypedDict, total=False):
    """
    The full agent state. Every node reads what it needs and writes
    back the fields it owns.

    Fields:
        messages              : full chat history (LangChain-style: [{role, content}])
        user_query            : the latest user message (string, copy of last user turn)
        detected_language_style : english | hinglish | hindi — from classify_and_route
        query_type            : one of QueryType — from classify_and_route
        retrieved_data        : dict of helper-name -> results (from retrieve_data)
        final_response        : the assistant message that will be returned to UI
        llm_provider_used     : which model in the chain served the final response
        error                 : populated if something blew up so the UI can show a friendly fallback
    """
    messages: List[Dict[str, str]]
    user_query: str
    detected_language_style: LanguageStyle
    query_type: QueryType
    retrieved_data: Dict[str, Any]
    final_response: str
    llm_provider_used: str
    error: Optional[str]
