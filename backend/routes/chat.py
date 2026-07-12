import time

from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db, limiter
from ..models import ChatMessage, ChatSession, UsageLog
from ..rag import get_pipeline
from . import chat_bp


def _public_sources(sources: list[dict] | None) -> list[dict]:
    """Sources as exposed over HTTP: full chunk content stays internal."""
    return [{k: v for k, v in src.items() if k != "content"} for src in sources or []]


def _get_or_create_session(
    user_id: int, session_id: int | None, title: str | None = None
) -> ChatSession:
    if session_id:
        session = ChatSession.query.filter_by(id=session_id, user_id=user_id).first()
        if session:
            return session
    session = ChatSession(user_id=user_id, title=title or "New Session")
    db.session.add(session)
    db.session.flush()
    return session


@chat_bp.route("/query", methods=["POST"])
@jwt_required()
@limiter.limit(lambda: current_app.config.get("RATE_LIMIT"))
def query_chat():
    payload = request.get_json() or {}
    message = payload.get("message", "").strip()
    session_id = payload.get("session_id")
    title = payload.get("title")

    if not message:
        return jsonify({"error": "message is required"}), 400

    user_id = int(get_jwt_identity())
    pipeline = get_pipeline(
        persist_directory=current_app.config["VECTOR_STORE_FOLDER"],
        top_k=current_app.config["RAG_TOP_K"],
    )

    session = _get_or_create_session(user_id, session_id, title)

    # Conversation window used to condense anaphoric follow-ups
    # ("et pour X ?") into standalone questions before retrieval.
    window = pipeline.config.history_window
    chat_history = [
        {"role": msg.role, "content": msg.content} for msg in session.messages[-window:]
    ]

    user_msg = ChatMessage(session=session, role="user", content=message)
    db.session.add(user_msg)
    db.session.flush()

    start = time.perf_counter()
    result = pipeline.query(message, user_id=user_id, history=chat_history)
    latency_ms = (time.perf_counter() - start) * 1000

    sources = _public_sources(result.get("sources"))
    assistant_msg = ChatMessage(
        session=session,
        role="assistant",
        content=result.get("answer", ""),
        sources=sources,
        response_time_ms=latency_ms,
    )
    db.session.add(assistant_msg)

    usage_entry = UsageLog(user_id=user_id, endpoint="chat.query", latency_ms=latency_ms)
    db.session.add(usage_entry)

    db.session.commit()

    return jsonify(
        {
            "session_id": session.id,
            "answer": result.get("answer"),
            "sources": sources,
            "query_rewritten": result.get("query_rewritten"),
            "rewrite_reason": result.get("rewrite_reason"),
            "latency_ms": round(latency_ms, 2),
        }
    )


@chat_bp.route("/history", methods=["GET"])
@jwt_required()
def history():
    user_id = int(get_jwt_identity())
    sessions = (
        ChatSession.query.filter_by(user_id=user_id).order_by(ChatSession.created_at.desc()).all()
    )
    serialized = []
    for session in sessions:
        serialized.append(
            {
                "session_id": session.id,
                "title": session.title,
                "created_at": session.created_at.isoformat(),
                "messages": [
                    {
                        "id": msg.id,
                        "role": msg.role,
                        "content": msg.content,
                        "created_at": msg.created_at.isoformat(),
                        "sources": msg.sources,
                        "response_time_ms": msg.response_time_ms,
                    }
                    for msg in session.messages
                ],
            }
        )
    return jsonify({"sessions": serialized})
