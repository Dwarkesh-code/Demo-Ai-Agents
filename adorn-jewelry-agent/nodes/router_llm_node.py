from pydantic import BaseModel, Field     
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from typing import Literal
from langchain_core.prompts import PromptTemplate


load_dotenv()


main_llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
models = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]
llms = [ChatGoogleGenerativeAI(model=name) for name in models]

router_llm = main_llm.with_fallbacks(llms)


class RouterStr(BaseModel):
    prompt : str | None = Field(description="generate prompt for response llm")
    product_view : Literal['yes', 'no']


str_router_llm = router_llm.with_structured_output(RouterStr)

def router_node(State) -> dict : 
    prompt = PromptTemplate.from_template("""You are the router for Hello Adorn's shopping assistant. You will receive the user's query, the conversation history so far, and sometimes product data (only when a previous step already fetched it for you).

Conversation history so far:
{conversation_history}

Use this history to understand context — e.g. if the user says "the cheaper one", "rings are best", or refers to something mentioned earlier, use the history to understand what they mean.

Your output must follow the RouterStr schema (prompt, product_view).

CASE 1 — No product data is given below:
Read the user's query (along with the conversation history). Decide if it is asking about, or expects an answer involving, any actual product in the shop — this includes:
- Specific product types, categories, materials, or price ranges (e.g. "gold rings under $50")
- Vague or general product recommendations (e.g. "what's the best product", "what should I buy", "what do you recommend", "what's popular")
- Availability or stock questions (e.g. "do you have necklaces")
- Follow-up questions that refer back to products already discussed in the conversation history (e.g. "the cheaper one", "show me more like that")

Only treat a query as NOT product-related if it is truly unrelated to the shop's products — e.g. greetings, shipping/policy questions, general chit-chat, or questions about the brand itself.

- If the query is NOT product-related:
  Set product_view = "no".
  Write a complete prompt in the `prompt` field for the response LLM. This prompt should instruct the response LLM to answer the user directly and conversationally, using the conversation history for context where relevant, without needing any product data.

- If the query IS product-related (including vague recommendations or follow-ups referring to earlier products):
  Set product_view = "yes".
  Set `prompt` to null. Do not write a response prompt yet — product data will be fetched and given back to you next.

CASE 2 — Product data is given below (this means product_view was "yes" last time, and the data has now been fetched for you):
Set product_view = "no" (the data has already been fetched — do not request it again, this stops the loop).
Using the user's original query, the conversation history, and the given product data, write a detailed prompt in the `prompt` field for the response LLM. This prompt must:
- Include the specific relevant products from the data (name, price, material, availability, link)
- If the query was vague (e.g. "best product"), pick a few good candidates yourself from the data (e.g. best-sellers, popular categories, well-priced items) and present them as suggestions
- If the query is a follow-up referring to earlier conversation (e.g. "the cheaper one"), use the conversation history to identify exactly which earlier product(s) it refers to
- For EVERY product you mention, you MUST include its exact URL from the product data — do not omit it
- Tell the response LLM to answer only using this data, not to invent or assume any product detail not present
- Tell the response LLM to keep the tone friendly and concise, and mention product name + price clearly

User query: {query}
Product data (if provided): {product_data}""")

    chain = prompt | str_router_llm
    result = chain.invoke({"conversation_history":State["conversation_history"], "query":State["query"], "product_data" : State.get("product_data")})

    return {"responser_prompt": result.prompt, "product_view" : result.product_view}

