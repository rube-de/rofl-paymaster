# ROFL Paymaster Application

Oasis ROFL application for paymaster functionality.

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run application
python -m rofl_paymaster

# Run tests
pytest

# Format code
black src/ tests/

# Type checking
mypy src/
```

## Docker

```bash
# Build image
docker build -t rofl-paymaster .

# Run container
docker run -p 8000:8000 rofl-paymaster
```

## Project Structure

```
├── src/rofl_paymaster/    # Main application code
├── tests/                 # Test files
├── pyproject.toml        # Project configuration
├── Dockerfile            # Container configuration
└── README.md             # This file
```