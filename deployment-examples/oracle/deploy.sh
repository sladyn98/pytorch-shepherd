#!/bin/bash

# Oracle Cloud Deployment Script for PyTorch Issue Agent
# Usage: ./deploy.sh <issue_number>

set -e

# Check required arguments
if [ $# -ne 1 ]; then
    echo "Usage: $0 <issue_number>"
    echo "Example: $0 149534"
    exit 1
fi

ISSUE_NUMBER=$1

# Check required environment variables
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: ANTHROPIC_API_KEY environment variable is required"
    exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable is required"
    exit 1
fi

if [ -z "$GITHUB_USERNAME" ]; then
    echo "Error: GITHUB_USERNAME environment variable is required"
    exit 1
fi

echo "🚀 Deploying PyTorch Issue Agent for issue #$ISSUE_NUMBER"
echo "📍 Server: Oracle Cloud"
echo "🔑 API Key: ${ANTHROPIC_API_KEY:0:10}..."
echo "👤 GitHub User: $GITHUB_USERNAME"

# Export issue number for docker-compose
export ISSUE_NUMBER=$ISSUE_NUMBER

# Clean up any existing containers
echo "🧹 Cleaning up existing containers..."
docker-compose down --volumes --remove-orphans || true

# Build and start the agent
echo "🔨 Building and starting agent..."
docker-compose up --build -d

# Show logs
echo "📋 Following logs (Ctrl+C to stop watching)..."
docker-compose logs -f