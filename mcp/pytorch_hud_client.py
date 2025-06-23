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
    
    async def get_failing_tests(self, pr_number: int, max_errors: int = 3) -> List[TestResult]:
        """Get failing tests for a pull request using PyTorch HUD MCP only."""
        try:
            self.logger.info(f"Getting failing tests for PR {pr_number} from PyTorch HUD MCP")
            
            # Call PyTorch HUD MCP - no fallbacks
            result = await self.client_manager.call_tool(
                "pytorch_hud",
                "get_failing_tests",
                {"pr_number": pr_number}
            )
            
            if not result:
                raise RuntimeError(f"PyTorch HUD MCP returned no result for PR {pr_number}")
            
            if "failing_tests" not in result:
                raise RuntimeError(f"PyTorch HUD MCP response missing 'failing_tests' for PR {pr_number}")
            
            failing_tests = []
            # Limit to max_errors to avoid context overflow
            limited_tests = result["failing_tests"][:max_errors]
            self.logger.info(f"Processing {len(limited_tests)} of {len(result['failing_tests'])} failing tests (limited by max_errors={max_errors})")
            
            for test_data in limited_tests:
                failing_tests.append(TestResult(
                    name=test_data.get("name", "Unknown Test"),
                    status=TestStatus.FAILED,
                    duration=test_data.get("duration"),
                    error_message=test_data.get("error_message", "Test failed"),
                    traceback=test_data.get("traceback"),
                    file_path=test_data.get("file_path"),
                    line_number=test_data.get("line_number")
                ))
            
            self.logger.info(f"Found {len(failing_tests)} failing tests for PR {pr_number} from PyTorch HUD MCP")
            return failing_tests
                
        except Exception as e:
            self.logger.error(f"PyTorch HUD MCP call failed: {e}")
            raise RuntimeError(f"Failed to get failing tests from PyTorch HUD MCP: {e}")
    
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