CONDENSE_PROMPT = """
Given the conversation history and a follow-up question, rewrite the follow-up
into ONE self-contained question, in the same language as the question, that
can be understood without the history. Resolve pronouns and references
("it", "il", "ça", "and for X?") using the history. Do not answer it.

Conversation history:
{history}

Follow-up question:
{question}

Self-contained question:
"""

REWRITE_PROMPT = """
Rewrite the following user query into a clearer, more specific question that would help an assistant
answer using notes. Keep it short and on-point.

Original query:
{question}

Rewritten question:
"""

ANSWER_PROMPT = """
You are an assistant that MUST use only the provided context to answer the user's question.
If the context does not contain the answer, say "I don't know based on the provided notes."

User question:
{question}

Context (retrieved notes):
{context}

Answer concisely and prefer structured bullet points or tables when it improves clarity.
"""
