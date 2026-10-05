# NeuralMind container image.
#
# Two stages: `builder` produces a wheel, `runtime` is a slim image that
# only carries the installed package + its runtime deps. The `neuralmind`
# and `neuralmind-mcp` entry points are on PATH inside the image.
#
# Build locally:
#   docker build -t neuralmind:dev .
#
# Mount the project read-write, at the same absolute path the agent uses.
# NeuralMind writes .neuralmind/ into the project, and the MCP server appends
# to its audit log on every tool call, so on a read-only mount every call
# fails. `neuralmind-mcp` takes no arguments: each tool call names its own
# project_path, which the container has to be able to resolve.
#
# Build the index, then run the MCP server over stdio:
#   docker run --rm -v "$PWD:$PWD" neuralmind:dev neuralmind build "$PWD"
#   docker run --rm -i -v "$PWD:$PWD" neuralmind:dev neuralmind-mcp
#
# Run the graph view, published on the host's loopback only, token on:
#   docker run --rm -p 127.0.0.1:8787:8787 \
#     -v "$PWD:$PWD" \
#     neuralmind:dev neuralmind serve "$PWD" --host 0.0.0.0 --no-browser
#
# The image doesn't bundle the embedding model, so each fresh container
# downloads it on its first build. See docs/DEPLOYMENT-GUIDE.md for mounting
# a pre-extracted model with NEURALMIND_ONNX_MODEL_DIR.

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

# Build the project wheel, then pre-download every transitive runtime
# dep as a wheel (including graphifyy, the optional external graph
# builder; `neuralmind build` has its own). Doing it here means the
# runtime stage installs from /wheels only and never reaches PyPI — so no
# sdist can sneak in and need a compiler we don't ship in the runtime image.
RUN python -m build --wheel --outdir /wheels
RUN pip wheel --no-cache-dir --wheel-dir /wheels /wheels/*.whl graphifyy

FROM python:${PYTHON_VERSION}-slim AS runtime

# Drop root for runtime. .neuralmind/ state belongs in the host filesystem,
# not the image, so the `neuralmind` user needs write access to the mounted
# project.
RUN useradd --create-home --shell /bin/bash neuralmind

WORKDIR /home/neuralmind

COPY --from=builder /wheels /wheels

# --no-index + --find-links pins us to the pre-built wheels above. If
# PyPI is unreachable at image build time, this still succeeds.
RUN pip install --no-cache-dir --no-index --find-links /wheels neuralmind graphifyy \
 && rm -rf /wheels

USER neuralmind

EXPOSE 8787

# Default to printing help — overriding with `docker run ... neuralmind <cmd>`
# is the expected usage and matches the README examples.
ENTRYPOINT []
CMD ["neuralmind", "--help"]
