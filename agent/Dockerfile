FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py agent.py config.py llm.py prompts.py rag.py schema.py skills.py validator.py ./
COPY data ./data

RUN python -c "from rag import build_vectorstore; build_vectorstore()"

RUN useradd --create-home --uid 10001 appuser
# Chroma opens its SQLite files in read/write mode even for searches, and the
# Agent also persists finished scripts below /app. Give the runtime user
# ownership after all build-time assets have been generated.
RUN chown -R appuser:appuser /app
USER appuser

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
