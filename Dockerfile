# NeuralMind container image.
#
# Two stages: `builder` produces a wheel, `runtime` is a slim image that
# only carries the installed package + its runtime deps. The `neuralmind`
# and `neuralmind-mcp` entry points are on PATH inside the image.
#
# Build locally:
#   docker build -t neuralmind:dev .
#
# Run the MCP server against a host project (read-only mount):
#   docker run --rm -i \
#     -v "$PWD:/project:ro" \
#     neuralmind:dev neuralmind-mcp /project
#
# Run the graph view, exposed on the host:
#   docker run --rm -p 8765:8765 \
#     -v "$PWD:/project:ro" \
#     neuralmind:dev neuralmind serve /project --host 0.0.0.0 --no-auth

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS builder

WORKDIR /src

# Build tools for hatchling + any wheels that need a compiler (chromadb
# pulls in a few). Removed from the runtime stage.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip build

COPY pyproject.toml README.md LICENSE ./
COPY neuralmind ./neuralmind

RUN python -m build --wheel --outdir /wheels

FROM python:${PYTHON_VERSION}-slim AS runtime

# Drop root for runtime. Mounted project dirs stay read-only by default;
# .neuralmind/ state belongs in the host filesystem, not the image.
RUN useradd --create-home --shell /bin/bash neuralmind

WORKDIR /home/neuralmind

COPY --from=builder /wheels /wheels

RUN pip install --no-cache-dir /wheels/*.whl \
 && rm -rf /wheels

USER neuralmind

EXPOSE 8765

# Default to printing help — overriding with `docker run ... neuralmind <cmd>`
# is the expected usage and matches the README examples.
ENTRYPOINT []
CMD ["neuralmind", "--help"]
