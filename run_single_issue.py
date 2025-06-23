#!/usr/bin/env python3
"""Entry point for running the agent on a single issue."""

import argparse
import asyncio
import logging
import sys
import os
from pathlib import Path

from agent.controller import IssueFixingAgent
from utils.config import Config


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s'
    )


def load_config(config_file: str = None) -> Config:
    """Load configuration from file or environment."""
    if config_file and os.path.exists(config_file):
        return Config.from_file(config_file)
    
    # Create config from environment variables
    config_dict = {
        "claude": {
            "api_key": os.getenv("ANTHROPIC_API_KEY"),
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 4000,
            "temperature": 0.1
        },
        "mcp": {
            "github_server_command": ["npx", "@modelcontextprotocol/server-github"],
            "pytorch_hud_server_command": ["python", "/app/pytorch_hud_mcp_server.py"]
        },
        "github_token": os.getenv("GITHUB_TOKEN"),
        "agent": {
            "max_attempts": 3,
            "monitoring_interval": 7200,
            "state_file": "./state/agent_state.json",
            "backup_interval": 3600,
            "max_errors_per_batch": 10
        }
    }
    
    return Config.from_dict(config_dict)


async def run_agent_for_issue(issue_number: int, repo: str, local_repo_path: str, 
                             config: Config, dry_run: bool = False):
    """Run the agent for a specific issue."""
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting PyTorch Issue Agent for issue #{issue_number}")
    logger.info(f"Repository: {repo}")
    logger.info(f"Local repo path: {local_repo_path}")
    logger.info(f"Dry run: {dry_run}")
    
    try:
        # Create and run the agent
        agent = IssueFixingAgent(
            issue_number=issue_number,
            repo=repo,
            config=config,
            dry_run=dry_run,
            local_repo_path=local_repo_path
        )
        
        # Run the agent
        await agent.run()
        
        logger.info(f"Agent completed successfully for issue #{issue_number}")
        
        # Check if PR was created
        if agent.context and agent.context.pr_number:
            if dry_run:
                logger.info(f"DRY RUN: Would have created PR #{agent.context.pr_number}")
            else:
                logger.info(f"🎉 PR created successfully: #{agent.context.pr_number}")
                logger.info(f"🔗 URL: https://github.com/{repo}/pull/{agent.context.pr_number}")
        else:
            logger.warning("No PR was created")
            
    except Exception as e:
        logger.error(f"Agent failed: {e}", exc_info=True)
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run PyTorch Issue Agent for a specific issue",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "issue_number",
        type=int,
        help="GitHub issue number to process"
    )
    
    parser.add_argument(
        "--repo",
        default="pytorch/pytorch",
        help="GitHub repository (owner/name)"
    )
    
    parser.add_argument(
        "--local-repo-path",
        type=Path,
        default="./pytorch",
        help="Path to local PyTorch repository"
    )
    
    parser.add_argument(
        "--config",
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no actual changes)"
    )
    
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Validate environment
    if not config.claude.api_key:
        logger.error("ANTHROPIC_API_KEY is required")
        sys.exit(1)
    
    # Run the agent
    try:
        asyncio.run(run_agent_for_issue(
            args.issue_number,
            args.repo,
            str(args.local_repo_path),
            config,
            args.dry_run
        ))
    except KeyboardInterrupt:
        logger.info("Agent interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()