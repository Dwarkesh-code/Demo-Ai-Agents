from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate

load_dotenv()


main_llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
models = ["gemini-3-flash", "gemini-2.5-flash", "gemini-3.5-flash"]
llms = [ChatGoogleGenerativeAI(model=name) for name in models]

llm = main_llm.with_fallbacks(llms)


def extract_text(response):
    """Handles all shapes: a plain string, a Gemini response with .content
    as a string, or .content as a list of blocks."""
    if isinstance(response, str):
        return response
    content = response.content
    if isinstance(content, str):
        return content
    elif isinstance(content, list) and len(content) > 0:
        first = content[0]
        if isinstance(first, dict) and "text" in first:
            return first["text"]
        return str(first)
    return str(content)


def responser_llm_node(State) -> dict:
    prompt = PromptTemplate.from_template("""You are the customer-facing assistant for Hello Adorn, a handmade jewelry shop.

Conversation history so far:
{conversation_history}

You will be given a prompt/instruction below, written specifically for this response. Follow it exactly — it already contains everything you need (product details, or guidance for a general reply).

Rules:
- Only use the information given in the instruction below. Do not invent product names, prices, materials, or availability that aren't explicitly mentioned.
- Use the conversation history for context if the user refers back to something discussed earlier.
- Keep the tone warm, friendly, and concise — like a helpful shop assistant, not a corporate bot.
- Do NOT write, type, or invent any link or URL anywhere in your response. Links are attached automatically after your text — just talk about the products naturally.
- Do not mention that you are following instructions or that this is a generated prompt — just respond naturally to the user.

Instruction:
{responser_prompt}

User's original query:
{query}""")

    chain = prompt | llm
    response = chain.invoke({
        "conversation_history": State["conversation_history"],
        "responser_prompt": State["responser_prompt"],
        "query": State["query"]
    })

    answer_text = extract_text(response)

    selected_products = State.get("selected_products") or []
    if selected_products:
        links_block = "\n\n".join(
            f"- [{p['name']}]({p['url']}) — ${p['price_usd']:.0f}, {p['material']}"
            for p in selected_products
        )
        answer_text = f"{answer_text}\n\n{links_block}"

    return {
        "response": answer_text,
        "conversation_history": [f"User: {State['query']}\nAssistant: {answer_text}"]
    }