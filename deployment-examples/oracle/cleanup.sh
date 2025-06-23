#!/bin/bash

# Complete cleanup script for PyTorch Issue Agent
# Usage: ./cleanup.sh [issue_number]

set -e

ISSUE_NUMBER=${1:-"all"}

echo "🧹 Starting PyTorch Issue Agent cleanup..."

if [ "$ISSUE_NUMBER" = "all" ]; then
    echo "🚨 Cleaning up ALL containers and volumes"
    
    # Stop and remove all pytorch-issue-agent containers
    echo "Stopping all pytorch-issue-agent containers..."
    docker ps -a --filter "name=pytorch-issue-agent" --format "{{.Names}}" | xargs -r docker stop
    docker ps -a --filter "name=pytorch-issue-agent" --format "{{.Names}}" | xargs -r docker rm
    
    # Remove all pytorch-related volumes
    echo "Removing all pytorch-related volumes..."
    docker volume ls --filter "name=pytorch-repo" --format "{{.Name}}" | xargs -r docker volume rm
    docker volume ls --filter "name=agent-state" --format "{{.Name}}" | xargs -r docker volume rm
    
    # Remove any orphaned volumes
    echo "Removing orphaned volumes..."
    docker volume prune -f
    
    # Remove pytorch-issue-agent images
    echo "Removing pytorch-issue-agent images..."
    docker images --filter "reference=*pytorch-issue-agent*" --format "{{.Repository}}:{{.Tag}}" | xargs -r docker rmi || true
    
    echo "✅ Complete cleanup finished!"
    
else
    echo "🎯 Cleaning up issue #$ISSUE_NUMBER"
    
    # Stop and remove specific container
    CONTAINER_NAME="pytorch-issue-agent-$ISSUE_NUMBER"
    echo "Stopping container: $CONTAINER_NAME"
    docker stop "$CONTAINER_NAME" 2>/dev/null || echo "Container $CONTAINER_NAME not running"
    docker rm "$CONTAINER_NAME" 2>/dev/null || echo "Container $CONTAINER_NAME not found"
    
    # Remove specific volumes
    REPO_VOLUME="pytorch-repo-$ISSUE_NUMBER"
    STATE_VOLUME="agent-state-$ISSUE_NUMBER"
    
    echo "Removing volumes: $REPO_VOLUME, $STATE_VOLUME"
    docker volume rm "$REPO_VOLUME" 2>/dev/null || echo "Volume $REPO_VOLUME not found"
    docker volume rm "$STATE_VOLUME" 2>/dev/null || echo "Volume $STATE_VOLUME not found"
    
    echo "✅ Cleanup for issue #$ISSUE_NUMBER finished!"
fi

# Show remaining containers and volumes
echo ""
echo "📊 Remaining pytorch-related resources:"
echo "Containers:"
docker ps -a --filter "name=pytorch-issue-agent" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || echo "None"
echo ""
echo "Volumes:"
docker volume ls --filter "name=pytorch" --format "table {{.Name}}\t{{.Driver}}" || echo "None"
docker volume ls --filter "name=agent-state" --format "table {{.Name}}\t{{.Driver}}" || echo "None"

echo ""
echo "🚀 Ready for fresh deployment!"