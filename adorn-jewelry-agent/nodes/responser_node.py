from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate

load_dotenv()


main_llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
models = ["gemini-3-flash", "gemini-2.5-flash", "gemini-3.5-flash"]
llms = [ChatGoogleGenerativeAI(model=name) for name in models]

llm = main_llm.with_fallbacks(llms)


def extract_text(response):
    """Gemini sometimes returns .content as a plain string, sometimes as a
    list of content blocks (e.g. [{"type": "text", "text": "..."}]).
    This handles both safely so we never crash on the format."""
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
- If product links are provided, always include them (as markdown links).
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

    return {
        "response": response,
        "conversation_history": [f"User: {State['query']}\nAssistant: {answer_text}"]
    }
