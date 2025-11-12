from datetime import datetime, timedelta

from flask import jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..models import ChatMessage, ChatSession, UploadedDocument, UsageLog, calculate_usage_summary
from . import analytics_bp


@analytics_bp.route("/summary", methods=["GET"])
@jwt_required()
def summary():
    user_id = get_jwt_identity()
    usage = calculate_usage_summary(user_id)
    total_sessions = ChatSession.query.filter_by(user_id=user_id).count()
    total_messages = (
        ChatMessage.query.join(ChatSession)
        .filter(ChatSession.user_id == user_id, ChatMessage.role == "assistant")
        .count()
    )
    total_docs = UploadedDocument.query.filter_by(user_id=user_id).count()

    last_7_days = datetime.utcnow() - timedelta(days=7)
    last_week_usage = (
        UsageLog.query.filter(UsageLog.user_id == user_id, UsageLog.created_at >= last_7_days)
        .order_by(UsageLog.created_at.desc())
        .all()
    )

    daily_calls = {}
    for entry in last_week_usage:
        day = entry.created_at.strftime("%Y-%m-%d")
        daily_calls.setdefault(day, 0)
        daily_calls[day] += 1

    return jsonify(
        {
            "usage": usage,
            "totals": {
                "sessions": total_sessions,
                "assistant_messages": total_messages,
                "documents": total_docs,
            },
            "last_7_days": daily_calls,
        }
    )

