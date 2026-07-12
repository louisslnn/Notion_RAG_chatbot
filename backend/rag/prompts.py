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
