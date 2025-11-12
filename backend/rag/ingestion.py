import hashlib
import io
import os
from dataclasses import dataclass
from typing import Iterable, List, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from markdown import markdown
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

CHUNK_SIZE = 600
CHUNK_OVERLAP = 80


SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "text/markdown",
    "text/plain",
}


@dataclass
class IngestedDocument:
    content: str
    metadata: dict


def _markdown_to_text(value: str) -> str:
    """Render markdown to plain text by stripping HTML tags after markdown conversion."""
    html = markdown(value)
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text("\n")


def extract_text(file_bytes: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages).strip()
    if content_type == "text/markdown":
        return _markdown_to_text(file_bytes.decode("utf-8"))
    if content_type == "text/plain":
        return file_bytes.decode("utf-8")
    raise ValueError(f"Unsupported content type: {content_type}")


def chunk_text(content: str, metadata: Optional[dict] = None) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    docs = splitter.create_documents([content], metadatas=[metadata or {}])
    return docs


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def save_upload_to_disk(upload_folder: str, filename: str, content: bytes) -> str:
    os.makedirs(upload_folder, exist_ok=True)
    path = os.path.join(upload_folder, filename)
    with open(path, "wb") as fh:
        fh.write(content)
    return path


def documents_from_texts(texts: Iterable[str], base_metadata: Optional[dict] = None) -> List[Document]:
    docs: List[Document] = []
    for idx, text in enumerate(texts):
        metadata = base_metadata.copy() if base_metadata else {}
        metadata.setdefault("source", f"notion_page_{idx}")
        docs.extend(chunk_text(text, metadata=metadata))
    return docs

