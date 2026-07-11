FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY scripts ./scripts
COPY alembic.ini .
COPY alembic ./alembic
EXPOSE 8000
# alembic upgrade head is idempotent (no-op if already at head), so this
# is safe to run on every container start, not just the first deploy.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
