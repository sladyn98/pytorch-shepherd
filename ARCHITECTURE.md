# PyTorch Issue Agent - Clean Architecture

## Overview

The PyTorch Issue Agent is a autonomous system designed to monitor and fix GitHub issues in the PyTorch repository. This document describes the clean architecture after refactoring.

## Architecture Principles

1. **Separation of Concerns**: Each module has a single, well-defined responsibility
2. **Configuration-Driven**: No hardcoded values; everything configurable via files and environment variables
3. **Dependency Injection**: Components are loosely coupled and easily testable
4. **Error Handling**: Comprehensive error handling with retry mechanisms
5. **Security**: No secrets in code; all sensitive data via environment variables

## Directory Structure

```
pytorch_issue_agent/
├── agent/                  # Core agent logic
│   ├── controller.py      # Main agent controller (refactored)
│   ├── state_manager.py   # State persistence
│   ├── types.py          # Type definitions
│   └── workflow.py       # Workflow engine
├── claude/               # Claude API integration
│   ├── client.py         # Clean Claude API client
│   └── prompts.py        # Prompt templates
├── config/               # Configuration files
│   ├── agent.yaml        # Main agent configuration
│   └── prompts.yaml      # Claude prompts configuration
├── mcp/                  # MCP server integrations
│   ├── client_manager.py # MCP client management
│   ├── github_client.py  # GitHub MCP integration
│   └── pytorch_hud_client.py # PyTorch HUD integration
├── utils/                # Utility modules
│   ├── config.py         # Configuration loading
│   ├── git_ops.py        # Git operations
│   ├── logging.py        # Logging utilities
│   ├── prompt_manager.py # Prompt management
│   └── sanitizer.py      # Content sanitization
├── scripts/              # Deployment scripts
│   └── init_pytorch_repo.sh # Repository initialization
├── main.py               # Entry point
├── monitor_daemon.py     # Main daemon
└── requirements.txt      # Dependencies
```

## Key Components

### 1. Main Entry Point (`main.py`)
- Clean CLI interface with argparse
- Configurable parameters
- Proper error handling and graceful shutdown

### 2. Configuration System
- **`config/agent.yaml`**: Main configuration file
- **`config/prompts.yaml`**: Prompt templates
- **Environment variables**: Secrets and environment-specific settings
- **`utils/prompt_manager.py`**: Centralized prompt management

### 3. Agent Controller (`agent/controller.py`)
- **Responsibilities**: Orchestrates the issue fixing process
- **Cleaned up**: Removed hardcoded values and duplicate methods
- **Configurable**: Uses prompt manager and configuration files

### 4. MCP Integration (`mcp/`)
- **Modular design**: Each MCP server has its own client
- **Generic**: No hardcoded issue-specific logic
- **Configurable**: Mock mode for development

### 5. Utilities (`utils/`)
- **Single responsibility**: Each utility has one job
- **Reusable**: Generic utilities not tied to specific issues
- **Testable**: Pure functions where possible

## Configuration

### Environment Variables
```bash
# Required
ANTHROPIC_API_KEY=your_api_key
GITHUB_TOKEN=your_github_token

# Optional
GIT_USER_NAME="Your Name"
GIT_USER_EMAIL="your.email@domain.com"
PYTORCH_HUD_MOCK_MODE=false
LOG_LEVEL=INFO
```

### Configuration Files
- **`config/agent.yaml`**: Timeouts, retry logic, branch patterns
- **`config/prompts.yaml`**: All Claude CLI prompts
- **`.env`**: Environment-specific settings (not in git)

## Security Improvements

1. **No hardcoded secrets**: All credentials via environment variables
2. **Environment file support**: `.env` files for local development
3. **Example configurations**: `.env.example` shows required variables
4. **Systemd integration**: Uses `EnvironmentFile` for production

## Development Workflow

### Local Development
1. Copy `.env.example` to `.env`
2. Fill in your API keys
3. Set `PYTORCH_HUD_MOCK_MODE=true` for testing
4. Run: `python main.py --help` to see options

### Production Deployment
1. Set environment variables in your deployment system
2. Use configuration files for non-sensitive settings
3. Deploy with Docker or systemd service

## Future Enhancements

1. **Plugin Architecture**: Allow custom MCP servers
2. **Issue Type Detection**: Automatic categorization of issues
3. **Multi-Repository Support**: Support for other repositories
4. **Advanced Retry Logic**: Exponential backoff with jitter
5. **Metrics and Monitoring**: Prometheus metrics integration

## Testing

The clean architecture enables:
- **Unit tests**: Each component can be tested in isolation
- **Integration tests**: Mock MCP servers for end-to-end testing
- **Configuration tests**: Validate configuration loading
- **CLI tests**: Test the main entry point

## Migration Guide

If upgrading from the old codebase:
1. Update environment variables (remove hardcoded secrets)
2. Create configuration files from templates
3. Update deployment scripts to use new environment variables
4. Test with mock mode before production deployment