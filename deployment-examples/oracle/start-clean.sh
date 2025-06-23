#!/bin/bash

# Clean startup script for PyTorch Issue Agent
# Usage: ./start-clean.sh <issue_number>

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

echo "🚀 Starting PyTorch Issue Agent for issue #$ISSUE_NUMBER"
echo "📍 Server: Oracle Cloud"
echo "🔑 API Key: ${ANTHROPIC_API_KEY:0:10}..."
echo "👤 GitHub User: $GITHUB_USERNAME"
echo ""

# Step 1: Cleanup any existing resources for this issue
echo "🧹 Step 1: Cleaning up existing resources..."
./cleanup.sh "$ISSUE_NUMBER"

# Step 2: Verify API tokens
echo "🔍 Step 2: Verifying API tokens..."

# Test Anthropic API
echo "Testing Anthropic API key..."
if ! curl -s -H "x-api-key: $ANTHROPIC_API_KEY" \
     -H "anthropic-version: 2023-06-01" \
     -H "content-type: application/json" \
     https://api.anthropic.com/v1/messages \
     -d '{"model":"claude-3-haiku-20240307","max_tokens":1,"messages":[{"role":"user","content":"test"}]}' | grep -q "model"; then
    echo "❌ Error: Invalid Anthropic API key"
    exit 1
fi
echo "✅ Anthropic API key valid"

# Test GitHub API
echo "Testing GitHub API token..."
if ! curl -s -H "Authorization: token $GITHUB_TOKEN" \
     https://api.github.com/user | grep -q "login"; then
    echo "❌ Error: Invalid GitHub token"
    exit 1
fi
echo "✅ GitHub token valid"

# Verify GitHub username matches token
ACTUAL_USERNAME=$(curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user | jq -r '.login')
if [ "$ACTUAL_USERNAME" != "$GITHUB_USERNAME" ]; then
    echo "❌ Error: GitHub username mismatch. Token belongs to '$ACTUAL_USERNAME', but GITHUB_USERNAME is set to '$GITHUB_USERNAME'"
    exit 1
fi
echo "✅ GitHub username verified: $GITHUB_USERNAME"

# Check fork exists
echo "Checking if fork exists..."
if curl -s -H "Authorization: token $GITHUB_TOKEN" \
   "https://api.github.com/repos/$GITHUB_USERNAME/pytorch" | grep -q '"name": "pytorch"'; then
    echo "✅ Fork pytorch/$GITHUB_USERNAME exists"
else
    echo "❌ Error: Fork $GITHUB_USERNAME/pytorch does not exist"
    echo "Please create a fork of pytorch/pytorch first: https://github.com/pytorch/pytorch/fork"
    exit 1
fi

# Step 3: Build and start container
echo ""
echo "🔨 Step 3: Building and starting container..."
export ISSUE_NUMBER=$ISSUE_NUMBER

# Build the image
echo "Building PyTorch Issue Agent image..."
docker-compose build --no-cache

# Start the container
echo "Starting container for issue #$ISSUE_NUMBER..."
docker-compose up -d

# Step 4: Monitor startup
echo ""
echo "📋 Step 4: Monitoring startup..."
echo "Container name: pytorch-issue-agent-$ISSUE_NUMBER"
echo ""

# Wait for container to start
sleep 3

# Show logs for 30 seconds to verify startup
echo "Showing startup logs (first 30 seconds):"
echo "----------------------------------------"
timeout 30 docker-compose logs -f || true

echo ""
echo "🎉 PyTorch Issue Agent started successfully!"
echo ""
echo "📊 Status:"
echo "Container: $(docker ps --filter "name=pytorch-issue-agent-$ISSUE_NUMBER" --format "{{.Status}}")"
echo "Volumes: pytorch-repo-$ISSUE_NUMBER, agent-state-$ISSUE_NUMBER"
echo ""
echo "📋 To monitor logs: docker-compose logs -f"
echo "🛑 To stop: docker-compose down"
echo "🧹 To cleanup: ./cleanup.sh $ISSUE_NUMBER"