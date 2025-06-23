# Use Python 3.11 slim image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    procps \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for MCP servers and Claude CLI
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g @anthropic-ai/claude-code

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for PyTorch repo (will be mounted as volume)
RUN mkdir -p /pytorch && chmod 777 /pytorch

# Set environment variables
ENV PYTORCH_REPO_PATH=/pytorch
ENV PYTHONUNBUFFERED=1

# Copy scripts
COPY scripts/ /app/scripts/
RUN chmod +x /app/scripts/*.sh

# Create non-root user for future use
RUN useradd -m -s /bin/bash -u 1000 agent && \
    chown -R agent:agent /app && \
    mkdir -p /app/state && \
    chmod -R 777 /pytorch /app/state && \
    chown -R agent:agent /pytorch

# Configure Git for the agent user
RUN git config --global user.name "PyTorch Issue Agent" && \
    git config --global user.email "pytorch-agent@example.com" && \
    git config --global init.defaultBranch main && \
    git config --global credential.helper store

# Switch to non-root user for Claude CLI security requirements
USER agent

# Default command - initialize repo first, then start agent
CMD ["/bin/bash", "-c", "/app/scripts/init_pytorch_repo.sh && python main.py 149534 --local-repo-path /pytorch"]