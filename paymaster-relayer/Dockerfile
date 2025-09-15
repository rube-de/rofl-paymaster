# Use Python 3.12 slim image (latest stable)
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for Python package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --frozen

# Copy source code
COPY paymaster_relayer/ ./paymaster_relayer/
COPY abis/ ./abis/

# Run the relayer using module execution
ENTRYPOINT ["uv", "run", "python", "-m", "paymaster_relayer"]
