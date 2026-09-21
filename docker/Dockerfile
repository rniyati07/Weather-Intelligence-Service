FROM python:3.11-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
COPY app/ ./app/
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim AS runtime
RUN useradd -m -u 1000 appuser
COPY --from=builder /install /usr/local
WORKDIR /app
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini ./
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import httpx;httpx.get('http://localhost:8000/health',timeout=2)"
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
