FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project configuration
COPY pyproject.toml .
COPY README.md .

# Copy source code
COPY src/ src/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create non-root user
RUN useradd --create-home --shell /bin/bash rofl
USER rofl

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "rofl_paymaster"]