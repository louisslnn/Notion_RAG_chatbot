from flask import Blueprint

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")
docs_bp = Blueprint("documents", __name__, url_prefix="/api/documents")
analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


def register_blueprints(app):
    from . import auth, chat, documents, analytics  # noqa: F401

    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(analytics_bp)

