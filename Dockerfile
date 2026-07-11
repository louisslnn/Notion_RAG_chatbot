FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Install dependencies first so this layer is cached across code changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend ./backend

ENV PATH="/app/.venv/bin:$PATH" \
    UPLOAD_FOLDER=/data/uploads \
    VECTOR_STORE_FOLDER=/data/vectorstore \
    HF_HOME=/data/hf-cache

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", "backend.app:create_app()"]
