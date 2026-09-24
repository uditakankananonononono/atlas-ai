FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
COPY pyproject.toml ./
COPY backend ./backend
RUN pip wheel --no-cache-dir --wheel-dir /wheels .
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend PORT=8080
RUN addgroup --system atlas && adduser --system --ingroup atlas atlas
# TeX for Module 15 PDF delivery (pdflatex + geometry/graphicx/hyperref from latex-base, T1 Latin Modern fonts).
RUN apt-get update \
 && apt-get install -y --no-install-recommends texlive-latex-base texlive-latex-recommended texlive-fonts-recommended lmodern \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY --chown=atlas:atlas backend ./backend
COPY --chown=atlas:atlas scripts ./scripts
COPY --chown=atlas:atlas migrations ./migrations
COPY --chown=atlas:atlas alembic.ini ./alembic.ini
USER atlas
EXPOSE 8080
CMD ["sh","-c","python scripts/validate_config.py && python scripts/migrate.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers"]
