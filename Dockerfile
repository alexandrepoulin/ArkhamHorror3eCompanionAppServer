# Multi-stage: build wheel + install → production runtime
FROM python:3.14-slim-bookworm AS builder

# Install build tools + uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cargo curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv globally
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# uv handles EVERYTHING (build-system + wheel creation)
RUN uv build --wheel && \
    ls -la dist/

FROM python:3.14-slim-bookworm AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && \
    rm -rf /var/lib/apt/lists/* && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app
COPY --from=builder /build/dist/*.whl .
COPY --from=builder /build/pyproject.toml ./

# Install runtime package + deps with uv (fast)
RUN uv pip install --system --no-cache --only-binary=all *.whl

# Non-root user
RUN useradd --create-home --shell /bin/false appuser
USER appuser
EXPOSE 8000

# Use your CLI entrypoint
ENTRYPOINT ["companion"]
CMD ["--host", "0.0.0.0", "--port", "8000"]