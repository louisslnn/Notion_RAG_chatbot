from datetime import datetime

from flask import current_app, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from flask_cors import cross_origin

from ..extensions import db, limiter
from ..models import User
from ..security import hash_password, verify_password
from . import auth_bp


@auth_bp.route("/register", methods=["POST", "OPTIONS"])
@cross_origin()
@limiter.limit(lambda: current_app.config.get("RATE_LIMIT"), methods=["POST"])
def register():
    if request.method == "OPTIONS":
        return ("", 204, {})
    payload = request.get_json() or {}
    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email already registered"}), 409

    user = User(email=email, password_hash=hash_password(password))
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=user.id)
    return jsonify({"access_token": access_token, "user": {"id": user.id, "email": user.email}})


@auth_bp.route("/login", methods=["POST", "OPTIONS"])
@cross_origin()
@limiter.limit(lambda: current_app.config.get("RATE_LIMIT"), methods=["POST"])
def login():
    if request.method == "OPTIONS":
        return ("", 204, {})
    payload = request.get_json() or {}
    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")

    user = User.query.filter_by(email=email).first()
    if not user or not verify_password(password, user.password_hash):
        return jsonify({"error": "invalid credentials"}), 401

    user.last_login_at = datetime.utcnow()
    db.session.commit()

    access_token = create_access_token(identity=user.id)
    return jsonify({"access_token": access_token, "user": {"id": user.id, "email": user.email}})


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404
    return jsonify({"user": {"id": user.id, "email": user.email}})

