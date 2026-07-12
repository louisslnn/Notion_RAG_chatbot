import hashlib
import io
import os
from collections.abc import Iterable

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from pypdf import PdfReader

CHUNK_SIZE = 600
CHUNK_OVERLAP = 80

# Markdown sections larger than this are sub-split (~800 tokens at ~4 chars/token).
MAX_SECTION_CHARS = 3200
SECTION_CHUNK_OVERLAP = 200

HEADERS_TO_SPLIT_ON = [("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4")]
_HEADER_KEYS = [key for _, key in HEADERS_TO_SPLIT_ON]

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "text/markdown",
    "text/plain",
}

MARKDOWN_EXTENSIONS = (".md", ".markdown")


def extract_text(file_bytes: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages).strip()
    if content_type in ("text/markdown", "text/plain"):
        # Markdown is kept raw so heading-aware chunking can use its structure.
        return file_bytes.decode("utf-8")
    raise ValueError(f"Unsupported content type: {content_type}")


def chunk_text(content: str, metadata: dict | None = None) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    docs = splitter.create_documents([content], metadatas=[metadata or {}])
    return docs


def chunk_markdown(content: str, metadata: dict | None = None) -> list[Document]:
    """Split markdown along its heading structure.

    Each chunk belongs to a heading path ("Architecture > Backend", stored in
    metadata.heading_path). Sections larger than MAX_SECTION_CHARS are
    sub-split while inheriting their heading_path.
    """
    base_metadata = metadata or {}
    header_splitter = MarkdownHeaderTextSplitter(HEADERS_TO_SPLIT_ON)
    sub_splitter = RecursiveCharacterTextSplitter(
        chunk_size=MAX_SECTION_CHARS, chunk_overlap=SECTION_CHUNK_OVERLAP
    )

    docs: list[Document] = []
    for section in header_splitter.split_text(content):
        heading_path = " > ".join(
            section.metadata[key] for key in _HEADER_KEYS if key in section.metadata
        )
        section_metadata = dict(base_metadata)
        if heading_path:
            section_metadata["heading_path"] = heading_path

        if len(section.page_content) <= MAX_SECTION_CHARS:
            docs.append(Document(page_content=section.page_content, metadata=section_metadata))
        else:
            docs.extend(
                sub_splitter.create_documents([section.page_content], metadatas=[section_metadata])
            )
    return docs


def chunk_content(
    content: str, metadata: dict | None = None, content_type: str | None = None
) -> list[Document]:
    """Chunk content, using heading-aware splitting for any markdown input."""
    source = str((metadata or {}).get("source", ""))
    if content_type == "text/markdown" or source.lower().endswith(MARKDOWN_EXTENSIONS):
        return chunk_markdown(content, metadata)
    return chunk_text(content, metadata)


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def save_upload_to_disk(upload_folder: str, filename: str, content: bytes) -> str:
    os.makedirs(upload_folder, exist_ok=True)
    path = os.path.join(upload_folder, filename)
    with open(path, "wb") as fh:
        fh.write(content)
    return path


def documents_from_texts(texts: Iterable[str], base_metadata: dict | None = None) -> list[Document]:
    docs: list[Document] = []
    for idx, text in enumerate(texts):
        metadata = base_metadata.copy() if base_metadata else {}
        metadata.setdefault("source", f"notion_page_{idx}")
        docs.extend(chunk_text(text, metadata=metadata))
    return docs
