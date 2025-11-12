import os
from typing import List

from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")

notion = Client(auth=NOTION_TOKEN) if NOTION_TOKEN else None


def _fetch_children(block_id: str):
    results = []
    start_cursor = None
    while True:
        resp = notion.blocks.children.list(block_id=block_id, start_cursor=start_cursor)
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        start_cursor = resp.get("next_cursor")
    return results


def _rich_text_to_plain(rich_text_array):
    return "".join(rt.get("plain_text", "") for rt in rich_text_array)


def _block_to_text(block):
    btype = block.get("type")
    content = block.get(btype, {})
    text = _rich_text_to_plain(content.get("rich_text", [])) if "rich_text" in content else ""

    if block.get("has_children"):
        children = _fetch_children(block["id"])
        child_texts = [_block_to_text(ch) for ch in children]
        if child_texts:
            text += "\n" + "\n".join(child_texts)

    return text.strip()


def page_to_text(page_id: str) -> str:
    if not notion:
        raise RuntimeError("NOTION_TOKEN not configured.")
    blocks = _fetch_children(page_id)
    pieces = [text for block in blocks if (text := _block_to_text(block)).strip()]
    return "\n\n".join(pieces)


def get_note_texts(pages: List[str]) -> List[str]:
    return [page_to_text(page_id) for page_id in pages]

