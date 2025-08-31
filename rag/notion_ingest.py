from notion_client import Client
from dotenv import load_dotenv
import os

load_dotenv()
notion = Client(auth=os.environ["NOTION_TOKEN"])

def fetch_children(block_id: str):
    """Fetch all children of a block with pagination."""
    results = []
    start_cursor = None
    while True:
        resp = notion.blocks.children.list(block_id=block_id, start_cursor=start_cursor)
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        start_cursor = resp.get("next_cursor")
    return results

def rich_text_to_plain(rich_text_array):
    return "".join(rt.get("plain_text", "") for rt in rich_text_array)

def block_to_text(block):
    btype = block.get("type")
    content = block.get(btype, {})
    text = rich_text_to_plain(content.get("rich_text", [])) if "rich_text" in content else ""

    if btype == "image":
        text = "[IMAGE]"

    # Recursive processing for children
    if block.get("has_children"):
        children = fetch_children(block["id"])
        child_texts = [block_to_text(ch) for ch in children]
        if child_texts:
            text += "\n" + "\n".join(child_texts)

    return text.strip()

def page_to_text(page_id: str):
    blocks = fetch_children(page_id)
    pieces = [text for b in blocks if (text := block_to_text(b)).strip()]
    return "\n\n".join(pieces)

def read_and_save_ids(file='pages_id.txt'):
    with open(file, encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def get_note_text():
    return [page_to_text(id) for id in read_and_save_ids()]