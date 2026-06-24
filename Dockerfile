FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app


FROM base AS builder

RUN pip install uv

COPY pyproject.toml .
COPY uv.lock* .

RUN uv sync --no-dev

COPY . .


FROM base AS runtime

ENV PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fonts-liberation \
        libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
