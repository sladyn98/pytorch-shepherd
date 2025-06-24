#!/bin/bash
# Deploy PyTorch Issue Agent updates to Oracle Cloud

set -e

echo "🚀 Deploying PyTorch Issue Agent updates to Oracle Cloud"

# Ensure we're in the right directory
cd /Users/sladynnunes/pytorch-shepherd/pytorch_issue_agent

# Create a tarball of the updated agent
echo "📦 Creating deployment package..."
tar -czf pytorch-issue-agent-update.tar.gz \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='state' \
    --exclude='*.log' \
    .

echo "✅ Deployment package created: pytorch-issue-agent-update.tar.gz"

# Instructions for manual deployment
echo ""
echo "📋 Manual deployment steps:"
echo "1. Transfer the package to Oracle Cloud:"
echo "   scp pytorch-issue-agent-update.tar.gz oracle-cloud:~/"
echo ""
echo "2. SSH to Oracle Cloud and run:"
echo "   ssh oracle-cloud"
echo "   cd /path/to/pytorch-issue-agent"
echo "   docker-compose down"
echo "   tar -xzf ~/pytorch-issue-agent-update.tar.gz"
echo "   docker-compose build --no-cache"
echo "   docker-compose up -d"
echo ""
echo "3. Monitor the logs:"
echo "   docker-compose logs -f"

# Clean up
rm -f test_hud_mcp.py