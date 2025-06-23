#!/bin/bash
set -e

PYTORCH_REPO_PATH="/pytorch"
PYTORCH_REPO_URL="https://github.com/pytorch/pytorch.git"

echo "Initializing PyTorch repository at $PYTORCH_REPO_PATH..."

# Check if the directory exists and is a git repository
if [ -d "$PYTORCH_REPO_PATH/.git" ]; then
    echo "PyTorch repository already exists, fetching latest changes..."
    cd "$PYTORCH_REPO_PATH"
    git fetch origin
    git checkout main
    git pull origin main
else
    echo "Cloning PyTorch repository..."
    if [ -d "$PYTORCH_REPO_PATH" ] && [ "$(ls -A $PYTORCH_REPO_PATH)" ]; then
        echo "Directory $PYTORCH_REPO_PATH exists but is not empty and not a git repo. Removing contents..."
        rm -rf "$PYTORCH_REPO_PATH"/*
        rm -rf "$PYTORCH_REPO_PATH"/.*  2>/dev/null || true
    fi
    
    # Clone the repository
    git clone "$PYTORCH_REPO_URL" "$PYTORCH_REPO_PATH"
    cd "$PYTORCH_REPO_PATH"
    
    # Set up git config for commits (use environment variables if available)
    git config user.name "${GIT_USER_NAME:-PyTorch Issue Agent}"
    git config user.email "${GIT_USER_EMAIL:-agent@pytorch.dev}"
fi

# Set up GitHub authentication if token is provided
if [ -n "$GITHUB_TOKEN" ] && [ -n "$GITHUB_USERNAME" ]; then
    echo "Setting up GitHub authentication for user: $GITHUB_USERNAME"
    # Create Git credentials file for HTTPS authentication
    echo "https://$GITHUB_USERNAME:$GITHUB_TOKEN@github.com" > ~/.git-credentials
    git config --global credential.helper store
    echo "GitHub authentication configured successfully!"
else
    echo "Warning: GITHUB_TOKEN or GITHUB_USERNAME not provided - Git pushes may fail"
fi

echo "PyTorch repository initialized successfully!"
echo "Repository is at commit: $(git rev-parse HEAD)"
echo "Current branch: $(git branch --show-current)"