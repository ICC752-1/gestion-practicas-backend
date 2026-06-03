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

COPY --from=builder /app /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]