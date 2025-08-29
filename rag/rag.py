import getpass
import os
import fitz
from typing import List
from dotenv import load_dotenv
from embedding import embedding_function
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document

load_dotenv()

sk_key = os.getenv("ANTHROPIC_API_KEY") 

def _set_env(key):
    if key not in os.environ:
        os.environ[key] = getpass.getpass(f"{key}:")

def load_docs(urls):
    docs = [WebBaseLoader(url).load() for url in urls]
    return docs

def chunk_text(text: str) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = splitter.split_documents([Document(page_content=text, metadata={"source": "notion"})])
    return docs

def read_pdf(file):
    doc = fitz.open(file)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def init_vectorstore(docs: List[str], embeddings) -> InMemoryVectorStore:
    vectorstore = InMemoryVectorStore.from_documents(docs, embedding=embeddings)
    retriever = vectorstore.as_retriever()
    return retriever

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

from notion_ingest import page_to_text
from db_handler import read_and_save_ids
from retriever_tool import Retriever

def get_note_text():
    texts = []
    ids = read_and_save_ids()
    for id in ids:
        texts.append(page_to_text(id))
    return texts

print(get_note_text())




