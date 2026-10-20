
from app.llm.base import ChatBlock, ChatMessage

SYSTEM_PROMPT = (
    "You are a precise assistant for this organization. Answer only using the "
    "cached context and retrieved context provided below. If the answer isn't "
    "supported by either, say you don't know rather than guessing."
)


def compose_messages(
    cached_context: str, retrieved_context: str, user_query: str
) -> list[ChatMessage]:
    """Step 5: merge cached (cold) + retrieved (hot) + the user's query into
    the final prompt.

    Ordering matters for prompt caching: the cacheable block must be stable
    byte-for-byte across requests and must come before anything that varies.
    So the cached context gets its own block with `cacheable=True`, placed
    before the retrieved context and query, which differ on every request.
    """

    system = ChatMessage.text("system", SYSTEM_PROMPT, cacheable=False)
    combined = ChatMessage(
        role="user",
        blocks=[
            ChatBlock(
                text=f"## Stable knowledge base (cached, preloaded once)\n{cached_context}",
                cacheable=True,
            ),
            ChatBlock(
                text=(
                    f"## Retrieved context (live, this request)\n{retrieved_context}\n\n"
                    f"## Question\n{user_query}"
                ),
                cacheable=False,
            ),
        ],
    )
    return [system, combined]
