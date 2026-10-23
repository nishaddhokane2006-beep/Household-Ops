# Dockerfile for Household Ops
# Builds a minimal Python image serving the MCP server on port 8000.
# The demo backend (backend.py) can be started separately or composed with docker-compose.

FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Seed the database on build so the container is demo-ready
RUN python seed.py

EXPOSE 8000

# Default: run MCP server. Override CMD to run backend.py instead.
CMD ["python", "server.py"]
