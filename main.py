#!/usr/bin/env python3
"""Main entry point for the PyTorch Issue Agent."""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from agent.controller import IssueFixingAgent
from utils.config import Config
from utils.logging import setup_logging


async def main():
    """Main entry point for the PyTorch Issue Agent."""
    parser = argparse.ArgumentParser(
        description="PyTorch Issue Fixing Agent",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "issue_number",
        type=int,
        help="GitHub issue number to fix"
    )
    
    parser.add_argument(
        "--local-repo-path",
        type=Path,
        default=Path("/pytorch"),
        help="Path to local PyTorch repository"
    )
    
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/agent.yaml"),
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(level=args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = Config.load(args.config)
        
        # Create and run agent
        agent = IssueFixingAgent(
            issue_number=args.issue_number,
            repo="pytorch/pytorch",
            config=config,
            local_repo_path=str(args.local_repo_path)
        )
        
        logger.info(f"Starting agent for issue #{args.issue_number}")
        await agent.run()
        
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())