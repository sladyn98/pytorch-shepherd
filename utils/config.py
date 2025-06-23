"""Configuration management for the PyTorch Issue Fixing Agent."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


@dataclass
class MCPConfig:
    """Configuration for MCP servers."""
    github_server_command: list = field(default_factory=lambda: ["npx", "@modelcontextprotocol/server-github"])
    pytorch_hud_server_command: list = field(default_factory=lambda: ["python3", "pytorch_hud_mcp_server.py"])
    startup_timeout: int = 30
    health_check_interval: int = 60


@dataclass
class ClaudeConfig:
    """Configuration for Claude API."""
    api_key: Optional[str] = None
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 8192  # Increased to handle complex file changes
    temperature: float = 0.1
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""
    max_attempts: int = 10
    monitoring_interval: int = 7200  # 2 hours in seconds
    state_file: str = "agent_state.json"
    backup_interval: int = 300  # 5 minutes
    max_errors_per_batch: int = 3  # Limit errors processed at once to avoid context overflow


@dataclass
class Config:
    """Main configuration class."""
    mcp: MCPConfig = field(default_factory=MCPConfig)
    claude: ClaudeConfig = field(default_factory=ClaudeConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    github_token: Optional[str] = None
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        """Load configuration from file and environment variables."""
        config = cls()
        
        # Load from file if provided
        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                data = json.load(f)
                config = cls.from_dict(data)
        
        # Override with environment variables
        config.claude.api_key = os.getenv("ANTHROPIC_API_KEY", config.claude.api_key)
        config.github_token = os.getenv("GITHUB_TOKEN", config.github_token)
        
        # Validate required settings
        if not config.claude.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        if not config.github_token:
            raise ValueError("GITHUB_TOKEN environment variable is required")
        
        return config
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Config":
        """Create config from dictionary."""
        return cls(
            mcp=MCPConfig(**data.get("mcp", {})),
            claude=ClaudeConfig(**data.get("claude", {})),
            agent=AgentConfig(**data.get("agent", {})),
            github_token=data.get("github_token"),
        )
    
    def to_dict(self) -> Dict:
        """Convert config to dictionary."""
        return {
            "mcp": {
                "github_server_command": self.mcp.github_server_command,
                "pytorch_hud_server_command": self.mcp.pytorch_hud_server_command,
                "startup_timeout": self.mcp.startup_timeout,
                "health_check_interval": self.mcp.health_check_interval
            },
            "claude": {
                "model": self.claude.model,
                "max_tokens": self.claude.max_tokens,
                "temperature": self.claude.temperature,
                "max_retries": self.claude.max_retries,
                "retry_delay": self.claude.retry_delay
            },
            "agent": {
                "max_attempts": self.agent.max_attempts,
                "monitoring_interval": self.agent.monitoring_interval,
                "state_file": self.agent.state_file,
                "backup_interval": self.agent.backup_interval,
                "max_errors_per_batch": self.agent.max_errors_per_batch
            }
        }