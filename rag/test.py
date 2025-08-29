from pydantic import BaseModel, Field
from typing import List
from dotenv import load_dotenv

from notion_ingest import page_to_text
from db_handler import read_and_save_ids

from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.chat_models import init_chat_model

import os
import warnings

# Disable HuggingFace tokenizer fork warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Hide deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)  # optional, extra quiet


load_dotenv()

# ---- VARIABLE CONFIG ----
ANTHROPIC_MODEL = "anthropic:claude-3-5-sonnet-latest"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 4

# ---- LLMs ----
# temperature 0.3 for creativity
llm = init_chat_model(ANTHROPIC_MODEL, temperature=0.3)      # used for rewrite + answer
grader_llm = init_chat_model(ANTHROPIC_MODEL, temperature=0.3)

# ---- structured outputs ----
class GradeDocuments(BaseModel):
    binary_score: str = Field(
        description="Relevance score: 'yes' if relevant, or 'no' if not relevant"
    )

class RewrittenQuestion(BaseModel):
    rewritten: str = Field(description="A clearer, more specific question")

class AnswerOutput(BaseModel):
    answer: str = Field(description="Final natural language answer based on context")

# ---- prompts ----
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

Answer concisely and cite which chunk(s) you used by writing (chunk i) after each supporting sentence,
where i is the 1-based index of the chunk in the `context` list. If multiple chunks are used, list them.
"""


# ---- helpers: build in-memory store from list of page texts ----
def build_inmemory_from_texts(texts: List[str]) -> InMemoryVectorStore:
    # texts = list of full page texts (strings)
    docs = [Document(page_content=t, metadata={"source": f"notion_page_{i}"}) for i, t in enumerate(texts)]
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    doc_splits = splitter.split_documents(docs)
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    vectorstore = InMemoryVectorStore.from_documents(doc_splits, embedding=embeddings)
    # keep the split docs handy in metadata if needed
    vectorstore._local_docs = doc_splits   # hacky but convenient for chunk indexing later
    return vectorstore

# ---- retrieval ----
def retrieve_chunks(vectorstore: InMemoryVectorStore, query: str, k: int = TOP_K):
    # returns list of Documents (langchain docs)
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    docs = retriever.get_relevant_documents(query)
    return docs

# ---- rewrite ----
def rewrite_query(original_query: str) -> str:
    prompt = REWRITE_PROMPT.format(question=original_query)
    resp = llm.with_structured_output(RewrittenQuestion).invoke([{"role":"user","content":prompt}])
    return resp.rewritten

# ---- grade ----
def grade_context(question: str, context_text: str) -> str:
    prompt = GRADE_PROMPT.format(question=question, context=context_text)
    resp = grader_llm.with_structured_output(GradeDocuments).invoke([{"role":"user","content":prompt}])
    return resp.binary_score  # "yes" or "no"

# ---- answer generation ----
def generate_answer(question: str, chunks: List[str]) -> str:
    # build a single context string with numbered chunks to keep track
    numbered_context = "\n\n".join(f"(chunk {i+1}) {c}" for i, c in enumerate(chunks))
    prompt = ANSWER_PROMPT.format(question=question, context=numbered_context)
    resp = llm.with_structured_output(AnswerOutput).invoke([{"role":"user","content":prompt}])
    return resp.answer

# ---- orchestrator ----
def ask_pipeline(vectorstore: InMemoryVectorStore, user_query: str):
    # 1) optional rewrite
    rewritten = rewrite_query(user_query)
    # 2) retrieve using rewritten query
    docs = retrieve_chunks(vectorstore, rewritten)
    # convert docs to plain text chunks for grader & answer
    chunks = [d.page_content for d in docs]
    combined_context_for_grader = "\n\n".join(chunks) if chunks else ""
    # 3) grade context relevance
    if combined_context_for_grader:
        score = grade_context(rewritten, combined_context_for_grader)
    else:
        score = "no"

    if score == "yes":
        answer = generate_answer(rewritten, chunks)
        return {
            "query_original": user_query,
            "query_rewritten": rewritten,
            "decision": "generate_answer",
            "answer": answer,
            "source_chunks": chunks,
        }
    else:
        # if not relevant, return a suggested rewrite + indicate we couldn't find support
        return {
            "query_original": user_query,
            "query_rewritten": rewritten,
            "decision": "rewrite_question",
            "message": "Retrieved notes do not appear relevant. Consider refining the query or adding notes."
        }
    
def get_note_text():
    texts = []
    ids = read_and_save_ids()
    for id in ids:
        texts.append(page_to_text(id))
    return texts

# ---- USAGE EXAMPLE ----
if __name__ == "__main__":
    # Replace this with your actual Notion text extraction:
    # e.g. texts = [page_to_text(page_id) for page_id in my_list_of_page_ids]
    texts = get_note_text()

    vs = build_inmemory_from_texts(texts)
    query = "What does my notes say about microeconomics?"
    out = ask_pipeline(vs, query)
    print(out.get('answer'))
