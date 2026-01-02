# Use a specific version of the uv image for reproducibility
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

# Enable bytecode compilation for faster startups
ENV UV_COMPILE_BYTECODE=1

# Use a non-root directory for the app
WORKDIR /app

# Install dependencies first to leverage Docker layer caching
# We only copy the lock and pyproject files initially
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy the rest of the source code
COPY . .

# Sync the project (this installs the current project as a package)
RUN uv sync --frozen --no-dev


# Final runtime stage
FROM python:3.14-slim-bookworm

WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Ensure the app uses the virtualenv's python and site-packages
ENV PATH="/app/.venv/bin:$PATH"

# Copy the source code (needed for execution)
COPY src ./src
# Copy configuration templates if they aren't provided via volumes
COPY logger.conf.default.yaml /app

# Set the entrypoint to your run script
# Using the -u flag for unbuffered logs (essential for Docker logs)
CMD ["python", "-u", "src/run.py"]
