"""
graph/build_graph.py
Assembles the LangGraph StateGraph for the Kindred Pets AI Agent.

Graph shape:
  [START]
     │
     ▼
  classify_and_route
     │
     ├── (greeting_smalltalk) ──────────────────────────────┐
     │                                                       │
     └── (all other types) → retrieve_data                  │
                                  │                          │
                                  ▼                          │
                           generate_response ◄───────────────┘
                                  │
                                  ▼
                           format_and_guard
                                  │
                                  ▼
                                [END]
"""

from langgraph.graph import StateGraph, END, START

from graph.state import AgentState
from graph.nodes import (
    classify_and_route,
    retrieve_data,
    generate_response,
    format_and_guard,
)


def route_after_classify(state: AgentState) -> str:
    """
    Conditional edge function: decides whether to retrieve data first
    or skip straight to response generation (for greetings/smalltalk).
    """
    if state.get("query_type") == "greeting_smalltalk":
        return "generate_response"
    return "retrieve_data"


def build_graph():
    """
    Build and compile the Kindred Pets agent StateGraph.
    Returns the compiled runnable.
    """
    graph = StateGraph(AgentState)

    # ── Register nodes ────────────────────────────────────────────────────
    graph.add_node("classify_and_route", classify_and_route)
    graph.add_node("retrieve_data",      retrieve_data)
    graph.add_node("generate_response",  generate_response)
    graph.add_node("format_and_guard",   format_and_guard)

    # ── Edges ─────────────────────────────────────────────────────────────
    graph.add_edge(START, "classify_and_route")

    # Conditional branch after classification
    graph.add_conditional_edges(
        "classify_and_route",
        route_after_classify,
        {
            "retrieve_data":     "retrieve_data",
            "generate_response": "generate_response",
        },
    )

    graph.add_edge("retrieve_data",     "generate_response")
    graph.add_edge("generate_response", "format_and_guard")
    graph.add_edge("format_and_guard",  END)

    return graph.compile()
