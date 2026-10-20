# LexBridge API and page, as a Hugging Face Docker Space (or any container host).
#
# The bundle is copied in, not rebuilt: the statute PDFs come from government sites that
# intermittently fail (data/sources.json pins their hashes), and the bundle's own manifest
# hashes prove it is the one the evaluation measured. The embedder's pinned weights are
# downloaded at build time, so a container starts without the network.
FROM python:3.11-slim

# Spaces run the container as uid 1000.
RUN useradd --create-home --uid 1000 user
WORKDIR /home/user/app
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface

# CPU torch first, from PyTorch's own index: the default Linux wheel bundles CUDA.
RUN pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

USER user
RUN python -c "from lexbridge.retrieve.embed import SentenceTransformerEmbedder; \
SentenceTransformerEmbedder('bge-m3')"
COPY --chown=user artifacts/ ./artifacts/

ENV HF_HUB_OFFLINE=1 \
    LEXBRIDGE_BUNDLE=artifacts/v2026-10-18 \
    LEXBRIDGE_PIPELINE=v3-references \
    LEXBRIDGE_TRACES=/tmp/traces.sqlite3 \
    LEXBRIDGE_PROXY_HOPS=1
EXPOSE 7860
# No --proxy-headers: the app reads X-Forwarded-For itself, trusting LEXBRIDGE_PROXY_HOPS.
CMD ["uvicorn", "--factory", "lexbridge.api.main:build", "--host", "0.0.0.0", "--port", "7860"]
