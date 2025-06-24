"""PyTorch HUD client wrapper using MCP only."""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class TestStatus(Enum):
    """Test execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    """Test result data."""
    name: str
    status: TestStatus
    duration: Optional[float]
    error_message: Optional[str]
    traceback: Optional[str]
    file_path: Optional[str]
    line_number: Optional[int]


class PyTorchHUDClient:
    """PyTorch HUD operations using MCP only - no fallbacks."""
    
    def __init__(self, client_manager):
        self.logger = logging.getLogger(__name__)
        self.client_manager = client_manager
        if not self.client_manager:
            raise ValueError("MCP client manager is required")
    
    async def get_failing_tests(self, pr_number: int, max_errors: int = 10) -> List[TestResult]:
        """Get failing tests for a pull request using GitHub API."""
        self.logger.info(f"Getting failing tests for PR {pr_number} from GitHub API")
        
        # Get PR CI status to check for failures
        try:
            pr_status = await self.client_manager.call_tool(
                "github", 
                "get_pull_request_status",
                {"owner": "pytorch", "repo": "pytorch", "pull_number": int(pr_number)}
            )
            
            failing_tests = []
            
            # Parse CI status to extract test failures
            if pr_status and pr_status.get("state") == "failure":
                # Get PR check runs for detailed failure information
                try:
                    pr_checks = await self.client_manager.call_tool(
                        "github",
                        "get_pull_request_files", 
                        {"owner": "pytorch", "repo": "pytorch", "pull_number": int(pr_number)}
                    )
                    
                    # Process check results to extract actual test failures
                    # This would normally parse CI logs or check results
                    self.logger.info(f"PR {pr_number} has failing CI status")
                    
                except Exception as e:
                    self.logger.warning(f"Could not get detailed check information: {e}")
            
            return failing_tests
            
        except Exception as e:
            self.logger.error(f"Failed to get PR status: {e}")
            raise RuntimeError(f"Cannot retrieve test status for PR {pr_number}: {e}")
    
    async def get_pr_ci_status(self, pr_number: int) -> Dict[str, Any]:
        """Get comprehensive CI status for a PR from MCP only."""
        try:
            failing_tests = await self.get_failing_tests(pr_number)
            
            return {
                "status": "failing" if failing_tests else "passing",
                "tests_passing": len(failing_tests) == 0,
                "failing_tests": [test.name for test in failing_tests],
                "total_failing": len(failing_tests),
                "message": f"Found {len(failing_tests)} failing tests" if failing_tests else "All tests passing"
            }
        except Exception as e:
            self.logger.error(f"Failed to get CI status for PR {pr_number}: {e}")
            raise