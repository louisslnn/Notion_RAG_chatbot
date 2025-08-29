from rag_pipeline.retriever import build_inmemory_from_texts
from rag.app_ui import run_app

# Load Notion pages into texts (or any source)
texts = ["Text from notion page 1", "Text from notion page 2"]
vectorstore = build_inmemory_from_texts(texts)

# run GUI
run_app(vectorstore)
