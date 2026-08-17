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
    prompt: str | None = Field(
        description="Instruction for the response LLM. Must NEVER contain any URL/link text — links are attached separately in code."
    )
    product_view: Literal['yes', 'no']
    selected_indices: list[int] | None = Field(
        default=None,
        description="0-based indices into product_data['products'] for items relevant to the query. Only set this when product_data was provided below."
    )


str_router_llm = router_llm.with_structured_output(RouterStr)

def router_node(State) -> dict:
    prompt = PromptTemplate.from_template("""You are the router for Hello Adorn's shopping assistant. You will receive the user's query, the conversation history so far, and sometimes product data (only when a previous step already fetched it for you).

Conversation history so far:
{conversation_history}

Use this history to understand context — e.g. if the user says "the cheaper one", "rings are best", or refers to something mentioned earlier, use the history to understand what they mean.

Your output must follow the RouterStr schema (prompt, product_view, selected_indices).

CASE 1 — No product data is given below:
Read the user's query (along with the conversation history). Decide if it is asking about, or expects an answer involving, any actual product in the shop — this includes:
- Specific product types, categories, materials, or price ranges (e.g. "gold rings under $50")
- Vague or general product recommendations (e.g. "what's the best product", "what should I buy", "what do you recommend", "what's popular")
- Availability or stock questions (e.g. "do you have necklaces")
- Follow-up questions that refer back to products already discussed in the conversation history (e.g. "the cheaper one", "show me more like that")

Only treat a query as NOT product-related if it is truly unrelated to the shop's products — e.g. greetings, shipping/policy questions, general chit-chat, or questions about the brand itself.

- If the query is NOT product-related:
  Set product_view = "no". Set selected_indices = null.
  Write a complete prompt in the `prompt` field for the response LLM. This prompt should instruct the response LLM to answer the user directly and conversationally, using the conversation history for context where relevant, without needing any product data.

- If the query IS product-related (including vague recommendations or follow-ups referring to earlier products):
  Set product_view = "yes". Set `prompt` to null. Set selected_indices = null.
  Do not write a response prompt yet — product data will be fetched and given back to you next.

CASE 2 — Product data is given below (this means product_view was "yes" last time, and the data has now been fetched for you):
Set product_view = "no" (the data has already been fetched — do not request it again, this stops the loop).

Look at product_data['products'], which is a list. Pick the 0-based indices of the items relevant to the user's query and put them in `selected_indices`.
- If the query was vague (e.g. "best product"), pick a few good candidates yourself (best-sellers, popular categories, well-priced items).
- If the query is a follow-up referring to earlier conversation (e.g. "the cheaper one"), use the conversation history to identify exactly which earlier product(s) it refers to, and pick their indices.

Then write a `prompt` field for the response LLM that:
- Mentions the relevant products by name, price, and material (you may type these — they're short and safe)
- Tells the response LLM to keep tone friendly and concise
- Explicitly tells the response LLM to NOT write any links or URLs itself — the correct links will be attached automatically in code after its response
- Tells the response LLM to answer only using this data, not to invent or assume any product detail not present

CRITICAL: Never type out, copy, or reference any URL/link anywhere in your output. Only use selected_indices for that.

User query: {query}
Product data (if provided): {product_data}""")

    chain = prompt | str_router_llm
    result = chain.invoke({"conversation_history": State["conversation_history"], "query": State["query"], "product_data": State.get("product_data")})

    selected_products = []
    product_data = State.get("product_data")
    if result.selected_indices and product_data and product_data.get("products"):
        products_list = product_data["products"]
        for i in result.selected_indices:
            if isinstance(i, int) and 0 <= i < len(products_list):
                selected_products.append(products_list[i])

    return {
        "responser_prompt": result.prompt,
        "product_view": result.product_view,
        "selected_products": selected_products,
    }