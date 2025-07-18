"""Configuration management for the PyTorch Issue Fixing Agent."""

import json
import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Any


@dataclass
class MCPConfig:
    """Configuration for MCP servers."""
    github_server_command: list = field(default_factory=lambda: ["npx", "@modelcontextprotocol/server-github"])
    pytorch_hud_server_command: list = field(default_factory=lambda: ["python3", "pytorch_hud_mcp_server.py"])
    startup_timeout: int = 30
    health_check_interval: int = 60
    servers: Optional[Dict] = None  # Allow servers dict from YAML for compatibility


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
                if str(config_path).endswith(('.yaml', '.yml')):
                    data = yaml.safe_load(f)
                else:
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
    def from_file(cls, config_path: str) -> "Config":
        """Load configuration from file only (no environment variables)."""
        if not Path(config_path).exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path) as f:
            if str(config_path).endswith(('.yaml', '.yml')):
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Config":
        """Create config from dictionary."""
        # Handle MCP config safely
        mcp_data = data.get("mcp", {})
        if "servers" in mcp_data and "github_server_command" not in mcp_data:
            # Convert YAML servers format to expected format
            mcp_config = MCPConfig(servers=mcp_data.get("servers"))
        else:
            # Use existing format
            mcp_config = MCPConfig(**{k: v for k, v in mcp_data.items() if k != "servers"})
        
        # Handle agent config with field name mapping
        agent_data = data.get("agent", {})
        # Map YAML field names to class field names
        if "max_fix_attempts" in agent_data:
            agent_data["max_attempts"] = agent_data.pop("max_fix_attempts")
        # Filter out unknown fields for agent config
        agent_fields = {"max_attempts", "monitoring_interval", "state_file", "backup_interval", "max_errors_per_batch"}
        agent_config_data = {k: v for k, v in agent_data.items() if k in agent_fields}
            
        return cls(
            mcp=mcp_config,
            claude=ClaudeConfig(**data.get("claude", {})),
            agent=AgentConfig(**agent_config_data),
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