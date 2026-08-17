"""
graph/build_graph.py
--------------------
Assembles the LangGraph StateGraph and exposes a `build_agent()` factory.

Edges:
    START
      ↓
    classify_and_route
      ↓
    [conditional] ── greeting_smalltalk / out_of_scope ──→ generate_response
      ↓
    retrieve_data
      ↓
    generate_response
      ↓
    format_and_guard
      ↓
    END
"""

from __future__ import annotations

import os
from typing import Any, Dict

from langgraph.graph import StateGraph, START, END

from graph.state import AgentState, QueryType
from graph.nodes import (
    classify_and_route,
    retrieve_data,
    generate_response,
    format_and_guard,
)


# Query types that don't need a DB round-trip
_NO_RETRIEVE = {"greeting_smalltalk", "out_of_scope"}


def _route_after_classify(state: AgentState) -> str:
    """Conditional edge: skip retrieve_data for smalltalk / out_of_scope."""
    qtype = state.get("query_type", "out_of_scope")
    if qtype in _NO_RETRIEVE:
        return "generate_response"
    return "retrieve_data"


def build_agent():
    """
    Build and compile the StateGraph. Returns a LangChain Runnable that
    takes a dict (initial state) and yields the final state.
    """
    g = StateGraph(AgentState)

    # Nodes
    g.add_node("classify_and_route", classify_and_route)
    g.add_node("retrieve_data", retrieve_data)
    g.add_node("generate_response", generate_response)
    g.add_node("format_and_guard", format_and_guard)

    # Edges
    g.add_edge(START, "classify_and_route")

    g.add_conditional_edges(
        "classify_and_route",
        _route_after_classify,
        {
            "retrieve_data": "retrieve_data",
            "generate_response": "generate_response",
        },
    )

    g.add_edge("retrieve_data", "generate_response")
    g.add_edge("generate_response", "format_and_guard")
    g.add_edge("format_and_guard", END)

    return g.compile()


# --------------------------------------------------------------------------
# Convenience runner: takes a chat history, returns the final response text
# and which provider served it. Used by the Streamlit app.
# --------------------------------------------------------------------------

_agent_singleton = None


def run_agent(user_query: str, history: list) -> Dict[str, Any]:
    """
    Run the agent once.

    Args:
        user_query: the new user message
        history:    list of {"role": "user" | "assistant", "content": ...}
                    representing the conversation BEFORE this turn
                    (this turn's user message should NOT be in here;
                    we'll append it)

    Returns:
        {"final_response": str, "llm_provider_used": str, "error": Optional[str]}
    """
    global _agent_singleton
    if _agent_singleton is None:
        _agent_singleton = build_agent()

    messages = list(history) + [{"role": "user", "content": user_query}]

    initial_state: AgentState = {
        "messages": messages,
        "user_query": user_query,
        # Everything else filled in by nodes
        "detected_language_style": "english",
        "query_type": "product_info",
        "retrieved_data": {},
        "final_response": "",
        "llm_provider_used": "",
        "error": None,
    }

    result = _agent_singleton.invoke(initial_state)
    return {
        "final_response": result.get("final_response", ""),
        "llm_provider_used": result.get("llm_provider_used", "unknown"),
        "query_type": result.get("query_type", ""),
        "language_style": result.get("detected_language_style", "english"),
        "error": result.get("error"),
    }
