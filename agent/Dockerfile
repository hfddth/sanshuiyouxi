FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY agent/requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY agent/ .

RUN python -c "from rag import build_vectorstore; build_vectorstore()"

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
