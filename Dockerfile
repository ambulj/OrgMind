FROM falkordb/falkordb:latest

# Install system dependencies & Python 3
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    git \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set up virtual environment
ENV VIRTUAL_ENV=/app/.venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy package dependencies and core library first for layer caching
COPY requirements.txt pyproject.toml ./
COPY packages/ ./packages/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -e packages/core

# Copy remaining codebase
COPY . .

# Convert entrypoint line endings and make executable
RUN dos2unix /app/scripts/entrypoint_hf.sh && \
    chmod +x /app/scripts/entrypoint_hf.sh

ENV FALKORDB_HOST=127.0.0.1
ENV FALKORDB_PORT=6379
ENV FALKORDB_PASSWORD=""
ENV FALKORDB_GRAPH_NAME=northwind_labs
ENV STREAMLIT_SERVER_PORT=7860
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

EXPOSE 7860

ENTRYPOINT ["/app/scripts/entrypoint_hf.sh"]
