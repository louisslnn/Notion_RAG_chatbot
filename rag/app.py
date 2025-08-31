# app.py
from flask import Flask, render_template, request, jsonify
from notion_ingest import get_note_text
from retriever import build_inmemory_from_texts, ask_pipeline

app = Flask(__name__)

# --- replace with your actual RAG function ---
def rag_response(user_message: str) -> str:
    texts = get_note_text()
    vs = build_inmemory_from_texts(texts)
    response = ask_pipeline(vs, user_message).get("answer")
    return response

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    response = rag_response(user_message)
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(debug=True)
