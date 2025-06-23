# Oracle Cloud Deployment

This directory contains deployment files for running the PyTorch Issue Agent on Oracle Cloud.

## Prerequisites

1. Oracle Cloud instance with Docker and Docker Compose installed
2. Required environment variables:
   - `ANTHROPIC_API_KEY`: Your Anthropic API key
   - `GITHUB_TOKEN`: GitHub personal access token with repo permissions
   - `GITHUB_USERNAME`: Your GitHub username

## Quick Start

1. Set environment variables:
```bash
export ANTHROPIC_API_KEY="your-api-key"
export GITHUB_TOKEN="your-github-token"
export GITHUB_USERNAME="your-username"
```

2. Deploy for a specific issue:
```bash
./deploy.sh 149534
```

## Files

- `docker-compose.yml`: Docker Compose configuration
- `deploy.sh`: Deployment script with cleanup and logging
- `README.md`: This file

## Monitoring

To check logs:
```bash
docker-compose logs -f
```

To check container status:
```bash
docker-compose ps
```

## Cleanup

To stop and remove all containers:
```bash
docker-compose down --volumes
```