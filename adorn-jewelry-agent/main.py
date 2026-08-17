from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
from typing import TypedDict, Optional, Literal
from nodes.product_data_node import product_node
from nodes.router_llm_node import router_node
from nodes.responser_node import responser_llm_node


#State 
class AdronState(TypedDict):
    query : str
    responser_prompt : str
    response : str
    product_data : Optional[list[dict]]
    product_view : Literal['yes', 'no']

#graph 
graph = StateGraph(AdronState)


#Nodes 
graph.add_node("router", router_node)
graph.add_node("product", product_node)
graph.add_node("responser", responser_llm_node)

#edge
graph.add_edge(START, "router")

def router_decision(State: AdronState) -> AdronState:
    if State["product_view"] == "yes":
        return "product_data"
    else: 
        return "responser"

graph.add_conditional_edges("router", router_decision, {
    "product_data" : "product",
    "responser": "responser"})

graph.add_edge("product", "router")
graph.add_edge("responser", END)

#workflow
workflow = graph.compile()

if __name__ == "__main__":
    query = input("query => ").strip()
    initial_state : AdronState = {
        "query" : query,
        "response": "",
        "product_data": None,
        "product_view": None,
        "responser_prompt": None
    }

    response = workflow.invoke(initial_state)
    print("Response = ", response)