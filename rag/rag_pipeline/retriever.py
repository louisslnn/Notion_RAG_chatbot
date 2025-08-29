from typing import List
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_community.embeddings import HuggingFaceEmbeddings
from grader import grade_context
from rewriter import rewrite_query
from answerer import generate_answer
from rag.db_handler import read_and_save_ids
from rag.notion_ingest import page_to_text

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 4

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

def retrieve_chunks(vectorstore: InMemoryVectorStore, query: str, k: int = TOP_K):
    # returns list of Documents (langchain docs)
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    docs = retriever.get_relevant_documents(query)
    return docs

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