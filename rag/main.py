from notion_ingest import get_note_text
from retriever import build_inmemory_from_texts, ask_pipeline
import os
import warnings

# Disable HuggingFace tokenizer fork warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Hide deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)  # optional, extra quiet

if __name__ == "__main__":
    # Replace this with your actual Notion text extraction:
    # e.g. texts = [page_to_text(page_id) for page_id in my_list_of_page_ids]
    texts = get_note_text()

    vs = build_inmemory_from_texts(texts)
    query = "What does my notes say about microeconomics?"
    out = ask_pipeline(vs, query)
    print(out.get('answer'))