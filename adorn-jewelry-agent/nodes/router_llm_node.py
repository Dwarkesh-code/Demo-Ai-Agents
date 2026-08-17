from pydantic import BaseModel, Field     
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from typing import Literal
from langchain_core.prompts import PromptTemplate


load_dotenv()

router_llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")

class RouterStr(BaseModel):
    prompt : str | None = Field(description="generate prompt for response llm")
    product_view : Literal['yes', 'no']


str_router_llm = router_llm.with_structured_output(RouterStr)

def router_node(State) -> dict : 
    prompt = PromptTemplate.from_template("""You are the router for Hello Adorn's shopping assistant. You will receive the user's query, and sometimes product data (only when a previous step already fetched it for you).

Your output must follow the RouterStr schema (prompt, product_view).

CASE 1 — No product data is given below:
Read the user's query. Decide if it is asking about a product, product type, category, material, price, or availability (e.g. "gold rings under $50", "do you have necklaces", "what earrings do you sell").

- If the query does NOT mention anything product-related:
  Set product_view = "no".
  Write a complete prompt in the `prompt` field for the response LLM. This prompt should instruct the response LLM to answer the user directly and conversationally, without needing any product data.

- If the query DOES mention something product-related:
  Set product_view = "yes".
  Set `prompt` to null. Do not write a response prompt yet — product data will be fetched and given back to you next.

CASE 2 — Product data is given below (this means product_view was "yes" last time, and the data has now been fetched for you):
Set product_view = "no" (the data has already been fetched — do not request it again, this stops the loop).
Using the user's original query and the given product data, write a detailed prompt in the `prompt` field for the response LLM. This prompt must:
- Include the specific relevant products from the data (name, price, material, availability, link)
- Tell the response LLM to answer only using this data, not to invent or assume any product detail not present
- Tell the response LLM to keep the tone friendly and concise, and mention product name + price clearly

User query: {query}
Product data (if provided): {product_data}""")

    chain = prompt | str_router_llm
    result = chain.invoke({"query":State["query"], "product_data" : State.get("product_data")})

    return {"responser_prompt": result.prompt, "product_view" : result.product_view}

