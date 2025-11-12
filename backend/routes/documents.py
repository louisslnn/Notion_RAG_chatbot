import secrets
import time

from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db, limiter
from ..models import UploadedDocument, UsageLog
from ..rag import get_pipeline
from ..rag.ingestion import (
    SUPPORTED_MIME_TYPES,
    extract_text,
    hash_content,
    save_upload_to_disk,
)
from . import docs_bp


@docs_bp.route("", methods=["GET"])
@jwt_required()
def list_documents():
    user_id = get_jwt_identity()
    docs = (
        UploadedDocument.query.filter_by(user_id=user_id)
        .order_by(UploadedDocument.created_at.desc())
        .all()
    )
    return jsonify(
        {
            "documents": [
                {
                    "id": doc.id,
                    "filename": doc.original_name,
                    "stored_name": doc.filename,
                    "created_at": doc.created_at.isoformat(),
                    "chunk_count": doc.chunk_count,
                    "metadata": doc.metadata,
                }
                for doc in docs
            ]
        }
    )


@docs_bp.route("/upload", methods=["POST"])
@jwt_required()
@limiter.limit(lambda: current_app.config.get("RATE_LIMIT"))
def upload_document():
    user_id = get_jwt_identity()
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "file is required"}), 400

    content_type = file.mimetype or "application/octet-stream"
    if content_type not in SUPPORTED_MIME_TYPES:
        return jsonify({"error": f"Unsupported content type: {content_type}"}), 415

    file_bytes = file.read()
    try:
        text = extract_text(file_bytes, content_type)
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

    if not text.strip():
        return jsonify({"error": "No readable text found in document"}), 400

    content_hash = hash_content(text)
    existing = UploadedDocument.query.filter_by(user_id=user_id, content_hash=content_hash).first()
    if existing:
        return jsonify({"message": "Document already ingested", "document_id": existing.id}), 200

    random_name = f"{secrets.token_hex(8)}_{file.filename}"
    stored_path = save_upload_to_disk(current_app.config["UPLOAD_FOLDER"], random_name, file_bytes)

    pipeline = get_pipeline(
        persist_directory=current_app.config["VECTOR_STORE_FOLDER"],
        top_k=current_app.config["RAG_TOP_K"],
    )
    start = time.perf_counter()
    ingest_result = pipeline.ingest_uploaded_text(
        text,
        metadata={
            "source": file.filename,
            "content_type": content_type,
            "user_id": user_id,
            "path": stored_path,
        },
    )

    document = UploadedDocument(
        user_id=user_id,
        filename=random_name,
        original_name=file.filename,
        content_hash=ingest_result["content_hash"],
        chunk_count=ingest_result["chunks_added"],
        metadata={"content_type": content_type},
    )
    db.session.add(document)

    latency_ms = (time.perf_counter() - start) * 1000
    usage_entry = UsageLog(user_id=user_id, endpoint="documents.upload", latency_ms=latency_ms)
    db.session.add(usage_entry)

    db.session.commit()

    return jsonify(
        {
            "document_id": document.id,
            "chunks_ingested": ingest_result["chunks_added"],
            "latency_ms": round(latency_ms, 2),
        }
    )

