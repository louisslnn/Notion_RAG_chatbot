GRADE_PROMPT = """
You are a grader. Decide whether the retrieved document content is relevant to the user question.

User question:
{question}

Retrieved document content:
{context}

If the document contains keywords or semantic meaning related to the user question, respond with exactly 'yes'. Otherwise respond with exactly 'no'.
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

