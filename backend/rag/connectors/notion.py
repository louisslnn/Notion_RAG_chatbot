import os
from collections.abc import Iterator

from dotenv import load_dotenv
from notion_client import Client

from .base import SourceConnector, SourceDocument

load_dotenv()


def _default_client() -> Client | None:
    token = os.getenv("NOTION_TOKEN")
    return Client(auth=token) if token else None


def _fetch_children(client: Client, block_id: str):
    results = []
    start_cursor = None
    while True:
        resp = client.blocks.children.list(block_id=block_id, start_cursor=start_cursor)
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        start_cursor = resp.get("next_cursor")
    return results


def _rich_text_to_plain(rich_text_array):
    return "".join(rt.get("plain_text", "") for rt in rich_text_array)


def _block_to_text(client: Client, block):
    btype = block.get("type")
    content = block.get(btype, {})
    text = _rich_text_to_plain(content.get("rich_text", [])) if "rich_text" in content else ""

    if block.get("has_children"):
        children = _fetch_children(client, block["id"])
        child_texts = [_block_to_text(client, ch) for ch in children]
        if child_texts:
            text += "\n" + "\n".join(child_texts)

    return text.strip()


def page_to_text(client: Client, page_id: str) -> str:
    blocks = _fetch_children(client, page_id)
    pieces = [text for block in blocks if (text := _block_to_text(client, block)).strip()]
    return "\n\n".join(pieces)


class NotionConnector(SourceConnector):
    """Reads a fixed set of Notion pages through the Notion API."""

    def __init__(self, page_ids: list[str], client: Client | None = None):
        self.page_ids = page_ids
        self.client = client or _default_client()
        if self.client is None:
            raise RuntimeError("NOTION_TOKEN not configured.")

    def iter_documents(self) -> Iterator[SourceDocument]:
        for page_id in self.page_ids:
            yield SourceDocument(
                content=page_to_text(self.client, page_id),
                metadata={"source": f"notion_page_{page_id}", "notion_page_id": page_id},
            )
