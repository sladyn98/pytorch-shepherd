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
        """Get failing tests for a pull request using PyTorch HUD MCP server."""
        self.logger.info(f"Getting failing tests for PR {pr_number} from PyTorch HUD MCP")
        
        try:
            # First, get recent commits with jobs to find failures for this PR
            recent_commits = await self.client_manager.call_tool(
                "pytorch_hud",
                "get_recent_commits_with_jobs_resource",
                {
                    "repo_owner": "pytorch",
                    "repo_name": "pytorch", 
                    "branch_or_commit_sha": "main",
                    "include_failures": True,
                    "per_page": 50  # Check more commits to find the PR
                }
            )
            
            failing_tests = []
            
            # Parse the response to find jobs related to this PR
            if recent_commits and "commits" in recent_commits:
                for commit in recent_commits["commits"]:
                    # Check if this commit is associated with our PR
                    if commit.get("pr_number") == pr_number:
                        self.logger.info(f"Found commit {commit.get('sha', '')[:8]} for PR {pr_number}")
                        
                        # Look for failing jobs in this commit
                        for job in commit.get("jobs", []):
                            if job.get("conclusion") == "failure":
                                # Download log and extract test failures
                                try:
                                    job_id = job.get("id")
                                    if job_id:
                                        log_info = await self.client_manager.call_tool(
                                            "pytorch_hud",
                                            "download_log_to_file_resource",
                                            {"job_id": int(job_id)}
                                        )
                                        
                                        if log_info and "file_path" in log_info:
                                            # Extract test results from the log
                                            test_results = await self.client_manager.call_tool(
                                                "pytorch_hud",
                                                "extract_test_results_resource",
                                                {"file_path": log_info["file_path"]}
                                            )
                                            
                                            # Convert test results to our format
                                            if test_results and "test_results" in test_results:
                                                for test in test_results["test_results"]:
                                                    if test.get("status") == "failed":
                                                        failing_tests.append(TestResult(
                                                            name=test.get("name", "Unknown Test"),
                                                            status=TestStatus.FAILED,
                                                            duration=test.get("duration"),
                                                            error_message=test.get("error_message", "Test failed"),
                                                            traceback=test.get("traceback"),
                                                            file_path=test.get("file_path"),
                                                            line_number=test.get("line_number")
                                                        ))
                                                        
                                                        # Limit results to avoid context overflow
                                                        if len(failing_tests) >= max_errors:
                                                            break
                                except Exception as e:
                                    self.logger.warning(f"Could not analyze job {job_id}: {e}")
                                
                                if len(failing_tests) >= max_errors:
                                    break
                        
                        break  # Found the PR commit, stop searching
            
            self.logger.info(f"Found {len(failing_tests)} failing tests for PR {pr_number} from PyTorch HUD MCP")
            return failing_tests
            
        except Exception as e:
            self.logger.error(f"PyTorch HUD MCP call failed: {e}")
            raise RuntimeError(f"Cannot retrieve test failures from PyTorch HUD for PR {pr_number}: {e}")
    
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