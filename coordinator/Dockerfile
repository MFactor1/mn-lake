# syntax=docker/dockerfile:1
#
# Lake coordinator — the Python process (FastAPI coordinator/API layer).
#
# Deps and venv management use astral uv, resident in THIS image: developers
# do not install Python or uv on their host — `docker compose build coordinator`
# does everything for them (root justfile: just build-coordinator).
#
# Build context: ./coordinator (docker-compose.yml and the justfile both set
# this up). WIP: the uv sync layer and CMD are TODO until code lands; the
# `if` guard keeps the image building while coordinator/pyproject.toml is
# still an empty placeholder.

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# uv itself is a single self-contained binary; the uv docs endorse pip as the
# bootstrap path when no uv exists yet, which is the case in this base image.
RUN pip install --no-cache-dir uv

# The uv-managed venv lives at /venv, OUTSIDE the /app bind mount in
# docker-compose.yml, so a dev's host-side coordinator/ directory stays
# source-only. Baking the env into the image means uv run at runtime
# inherits the same venv.
ENV UV_PROJECT_ENVIRONMENT=/venv \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Manifest first: uv only re-resolves dependencies when pyproject.toml changes.
COPY pyproject.toml .

# uv sync resolves [project.dependencies] into /venv (no local venv or pip
# chore anywhere). Guarded while the manifest is an empty placeholder.
RUN if [ -s pyproject.toml ]; then \
        uv sync ; \
    else \
        echo "TODO: coordinator/pyproject.toml is empty — dependency layer skipped" ; \
    fi

# Sources layer. In dev compose the same tree is bind-mounted at /app, so
# host-side Python edits are live inside uv run without a rebuild.
COPY . .

# TODO: once the coordinator exists, uv run resolves the entrypoint from
# /venv's environment — likely:
#   CMD ["uv", "run", "uvicorn", "coordinator.main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["sh", "-c", "echo 'Lake coordinator placeholder: set the real CMD in coordinator/Dockerfile (uv run <entrypoint> once sources exist)'"]
