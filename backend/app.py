import os

from flask import Flask, jsonify

from .config import BaseConfig
from .extensions import cors, db, jwt, limiter
from .routes import register_blueprints


def create_app(config_object=BaseConfig):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["VECTOR_STORE_FOLDER"], exist_ok=True)

    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(
        app,
        resources={
            r"/api/*": {
                "origins": app.config["FRONTEND_ORIGINS"],
                "allow_headers": ["Content-Type", "Authorization"],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "supports_credentials": True,
            }
        },
    )
    limiter.init_app(app)

    register_blueprints(app)

    @app.errorhandler(429)
    def rate_limit_handler(error):
        return jsonify({"error": "rate limit exceeded", "details": str(error.description)}), 429

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(debug=True)

