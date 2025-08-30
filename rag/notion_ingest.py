from notion_client import Client
from dotenv import load_dotenv
import os

load_dotenv()

notion = Client(auth=os.environ["NOTION_TOKEN"])

def fetch_children(block_id: str):
    """Recursively fetch all children of a block (handles pagination)."""
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
    text = ""

    if btype in ["paragraph","heading_1","heading_2","heading_3",
                 "bulleted_list_item","numbered_list_item","quote","callout"]:
        text = rich_text_to_plain(content.get("rich_text", []))
    elif btype == "code":
        text = rich_text_to_plain(content.get("rich_text", []))
    elif btype == "image":
        text = "[IMAGE]"
    else:
        # fallback if it has rich_text
        if "rich_text" in content:
            text = rich_text_to_plain(content["rich_text"])

    # recursive: if the block has children
    if block.get("has_children"):
        children = fetch_children(block["id"])
        child_texts = [block_to_text(ch) for ch in children]
        if child_texts:
            text += "\n" + "\n".join(child_texts)

    return text.strip()

def page_to_text(page_id: str):
    blocks = fetch_children(page_id)
    pieces = [block_to_text(b) for b in blocks if block_to_text(b).strip()]
    return "\n\n".join(pieces)

def read_and_save_ids(file='pages_id.txt'):
    ids = []

    with open(file=file, encoding='utf-8') as f:
        text = f.read()

    for line in text.split("\n"):
        if line.strip():   # skip empty lines
            ids.append(line.strip())

    return ids

def get_note_text():
    texts = []
    ids = read_and_save_ids()
    for id in ids:
        texts.append(page_to_text(id))
    return texts


