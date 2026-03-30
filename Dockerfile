FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

# Copy dependency metadata first to maximize Docker cache reuse.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "backup.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
