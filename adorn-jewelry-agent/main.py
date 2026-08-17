from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
from typing import TypedDict, Optional, Literal


#State 
class AdronState(TypedDict):
    query : str
    responser_prompt : str
    response : str
    product_data : Optional[list[dict]]
    product_view : Literal['yes', 'no']