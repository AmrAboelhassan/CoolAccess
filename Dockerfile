# =============================================================================
# Stage 1: Build Static Frontend Distribution
# =============================================================================

FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# =============================================================================
# Stage 2: Python Runtime & FastAPI Server
# =============================================================================

FROM python:3.11-slim AS runner

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    COOLACCESS_DATA_DIR=/app/data/locked_dc_scenario \
    COOLACCESS_FRONTEND_DIST=/app/frontend/dist

# Copy Python package metadata and source BEFORE pip install.
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install CoolAccess and its runtime dependencies.
RUN pip install --no-cache-dir .

# Copy prepared historical benchmark data.
COPY data/locked_dc_scenario/ ./data/locked_dc_scenario/

# Copy built frontend assets from Stage 1.
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8000

CMD ["uvicorn", "coolaccess.server:app", "--host", "0.0.0.0", "--port", "8000"]
