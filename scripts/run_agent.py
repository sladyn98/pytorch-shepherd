#!/usr/bin/env python3
"""
Run PyTorch Issue Agent for a specific issue.
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.controller import IssueController
from utils.config import Config
from agent.state_manager import StateManager


async def main():
    """Main entry point for running the agent."""
    if len(sys.argv) < 2:
        print("Usage: python run_agent.py <issue_number> [--monitor]")
        sys.exit(1)
    
    issue_number = int(sys.argv[1])
    monitor_mode = "--monitor" in sys.argv
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting PyTorch Issue Agent for issue #{issue_number}")
    
    if monitor_mode:
        logger.info("Running in monitoring mode")
    
    # Load configuration
    config = Config()
    
    # Create state manager
    state_manager = StateManager(
        state_file=f"state/issue_{issue_number}_state.json"
    )
    
    # Create and run controller
    controller = IssueController(
        issue_number=issue_number,
        repo="pytorch/pytorch",
        config=config,
        state_manager=state_manager,
        dry_run=False
    )
    
    try:
        if monitor_mode:
            await controller.monitor_mode()
        else:
            await controller.run()
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
    except Exception as e:
        logger.error(f"Agent failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())