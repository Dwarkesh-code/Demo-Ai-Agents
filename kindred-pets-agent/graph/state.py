"""
graph/state.py — LangGraph State schema for the Kindred Pets AI Agent.
"""

from typing import Annotated, List, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
import operator


class AgentState(TypedDict):
    """
    The shared state object that flows through every node in the graph.
    Each field is updated by the relevant node; fields are read by downstream nodes.
    """

    # Full conversation history (HumanMessage / AIMessage objects)
    messages: Annotated[List[BaseMessage], operator.add]

    # The raw text of the user's latest message
    user_query: str

    # Detected language/style: "english" | "hindi" | "hinglish"
    detected_language_style: str

    # Query category assigned by classify_and_route:
    # "product_info" | "pricing" | "recommendation" | "faq_policy"
    # | "order_tracking" | "greeting_smalltalk" | "out_of_scope"
    query_type: str

    # Serialized string of data retrieved from the DB by retrieve_data
    retrieved_data: str

    # The final reply text produced by generate_response
    final_response: str

    # Which LLM model actually answered (for debug sidebar in Streamlit)
    llm_provider_used: str
