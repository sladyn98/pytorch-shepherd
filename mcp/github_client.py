"""GitHub MCP client wrapper."""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .client_manager import MCPClientManager


@dataclass
class GitHubIssue:
    """GitHub issue data."""
    number: int
    title: str
    body: str
    state: str
    labels: List[str]
    assignees: List[str]
    author: str
    created_at: str
    updated_at: str
    comments_count: int
    url: str


@dataclass
class GitHubPR:
    """GitHub pull request data."""
    number: int
    title: str
    body: str
    state: str
    head_ref: str
    base_ref: str
    author: str
    created_at: str
    updated_at: str
    mergeable: bool
    url: str


@dataclass
class GitHubComment:
    """GitHub comment data."""
    id: int
    body: str
    author: str
    created_at: str
    updated_at: str


class GitHubMCPClient:
    """High-level GitHub operations using MCP."""
    
    def __init__(self, client_manager: MCPClientManager, repo: str):
        self.client_manager = client_manager
        self.repo = repo
        self.logger = logging.getLogger(__name__)
    
    async def get_issue(self, issue_number: int) -> Optional[GitHubIssue]:
        """Get issue details."""
        try:
            self.logger.debug(f"Fetching issue {issue_number} from {self.repo}")
            result = await self.client_manager.call_tool(
                "github",
                "get_issue",
                {
                    "owner": self.repo.split("/")[0],
                    "repo": self.repo.split("/")[1],
                    "issue_number": issue_number
                }
            )
            self.logger.debug(f"GitHub API result: {result}")
            
            # Handle different response formats from GitHub MCP server
            issue_data = None
            if result and "issue" in result:
                issue_data = result["issue"]
            elif result and "content" in result and isinstance(result["content"], list):
                # Parse JSON from content array
                import json
                content_text = result["content"][0]["text"]
                issue_data = json.loads(content_text)
            
            if issue_data:
                return GitHubIssue(
                    number=issue_data["number"],
                    title=issue_data["title"],
                    body=issue_data.get("body", ""),
                    state=issue_data["state"],
                    labels=[label["name"] for label in issue_data.get("labels", [])],
                    assignees=[assignee["login"] for assignee in issue_data.get("assignees", [])],
                    author=issue_data["user"]["login"],
                    created_at=issue_data["created_at"],
                    updated_at=issue_data["updated_at"],
                    comments_count=issue_data.get("comments", 0),
                    url=issue_data["html_url"]
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get issue {issue_number}: {e}")
            self.logger.error(f"Exception type: {type(e)}")
            self.logger.error(f"Result was: {result if 'result' in locals() else 'No result'}")
            return None
    
    async def get_issue_comments(self, issue_number: int) -> List[GitHubComment]:
        """Get issue comments."""
        try:
            result = await self.client_manager.call_tool(
                "github",
                "list_issue_comments",
                {
                    "owner": self.repo.split("/")[0],
                    "repo": self.repo.split("/")[1],
                    "issue_number": issue_number
                }
            )
            
            comments = []
            if result and "comments" in result:
                for comment_data in result["comments"]:
                    comments.append(GitHubComment(
                        id=comment_data["id"],
                        body=comment_data["body"],
                        author=comment_data["user"]["login"],
                        created_at=comment_data["created_at"],
                        updated_at=comment_data["updated_at"]
                    ))
            
            return comments
            
        except Exception as e:
            self.logger.error(f"Failed to get issue comments {issue_number}: {e}")
            return []
    
    async def get_file_content(self, file_path: str, ref: str = "main") -> Optional[str]:
        """Get file content from repository."""
        try:
            result = await self.client_manager.call_tool(
                "github",
                "get_file",
                {
                    "owner": self.repo.split("/")[0],
                    "repo": self.repo.split("/")[1],
                    "path": file_path,
                    "ref": ref
                }
            )
            
            if result and "content" in result:
                return result["content"]
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get file {file_path}: {e}")
            return None
    
    async def search_code(self, query: str, file_extension: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search code in repository."""
        try:
            search_query = f"repo:{self.repo} {query}"
            if file_extension:
                search_query += f" extension:{file_extension}"
            
            result = await self.client_manager.call_tool(
                "github",
                "search_code",
                {
                    "q": search_query
                }
            )
            
            if result and "items" in result:
                return result["items"]
            
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to search code: {e}")
            return []
    
    async def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
        fork_owner: str = None
    ) -> Optional[GitHubPR]:
        """Create a pull request from fork to main repository."""
        try:
            # If fork_owner is provided, create PR from fork to main repo
            if fork_owner:
                head_ref = f"{fork_owner}:{head_branch}"
            else:
                head_ref = head_branch
                
            result = await self.client_manager.call_tool(
                "github",
                "create_pull_request",
                {
                    "owner": self.repo.split("/")[0],
                    "repo": self.repo.split("/")[1],
                    "title": title,
                    "body": body,
                    "head": head_ref,
                    "base": base_branch
                }
            )
            
            if result and "pull_request" in result:
                pr_data = result["pull_request"]
                return GitHubPR(
                    number=pr_data["number"],
                    title=pr_data["title"],
                    body=pr_data.get("body", ""),
                    state=pr_data["state"],
                    head_ref=pr_data["head"]["ref"],
                    base_ref=pr_data["base"]["ref"],
                    author=pr_data["user"]["login"],
                    created_at=pr_data["created_at"],
                    updated_at=pr_data["updated_at"],
                    mergeable=pr_data.get("mergeable", False),
                    url=pr_data["html_url"]
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to create PR: {e}")
            return None
    
    async def get_pull_request(self, pr_number: int) -> Optional[GitHubPR]:
        """Get pull request details."""
        try:
            result = await self.client_manager.call_tool(
                "github",
                "get_pull_request",
                {
                    "owner": self.repo.split("/")[0],
                    "repo": self.repo.split("/")[1],
                    "pull_number": pr_number
                }
            )
            
            if result and "pull_request" in result:
                pr_data = result["pull_request"]
                return GitHubPR(
                    number=pr_data["number"],
                    title=pr_data["title"],
                    body=pr_data.get("body", ""),
                    state=pr_data["state"],
                    head_ref=pr_data["head"]["ref"],
                    base_ref=pr_data["base"]["ref"],
                    author=pr_data["user"]["login"],
                    created_at=pr_data["created_at"],
                    updated_at=pr_data["updated_at"],
                    mergeable=pr_data.get("mergeable", False),
                    url=pr_data["html_url"]
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get PR {pr_number}: {e}")
            return None
    
    async def get_pr_comments(self, pr_number: int) -> List[GitHubComment]:
        """Get pull request review comments."""
        try:
            result = await self.client_manager.call_tool(
                "github",
                "get_pull_request_comments",
                {
                    "owner": self.repo.split("/")[0],
                    "repo": self.repo.split("/")[1],
                    "pull_number": pr_number
                }
            )
            
            comments = []
            if result and "comments" in result:
                for comment_data in result["comments"]:
                    comments.append(GitHubComment(
                        id=comment_data["id"],
                        body=comment_data["body"],
                        author=comment_data["user"]["login"],
                        created_at=comment_data["created_at"],
                        updated_at=comment_data["updated_at"]
                    ))
            
            return comments
            
        except Exception as e:
            self.logger.error(f"Failed to get PR comments {pr_number}: {e}")
            return []
    
    async def create_branch(self, branch_name: str, base_ref: str = "main") -> bool:
        """Create a new branch."""
        try:
            # Use create_branch tool
            result = await self.client_manager.call_tool(
                "github",
                "create_branch",
                {
                    "owner": self.repo.split("/")[0],
                    "repo": self.repo.split("/")[1],
                    "branch": branch_name,
                    "from_branch": base_ref
                }
            )
            
            if result is not None:
                self.logger.info(f"Successfully created branch {branch_name}")
                return True
            else:
                self.logger.error(f"Failed to create branch {branch_name}: No result returned")
                return False
            
        except Exception as e:
            self.logger.error(f"Failed to create branch {branch_name}: {e}")
            return False
    
    async def fork_repository(self) -> Optional[str]:
        """Fork the repository and return the fork URL."""
        try:
            result = await self.client_manager.call_tool(
                "github",
                "fork_repository",
                {
                    "owner": self.repo.split("/")[0],
                    "repo": self.repo.split("/")[1]
                }
            )
            
            if result and "fork" in result:
                fork_data = result["fork"]
                fork_url = fork_data["clone_url"]
                self.logger.info(f"Forked repository: {fork_url}")
                return fork_url
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to fork repository: {e}")
            return None
    
    async def check_fork_exists(self, username: str) -> Dict[str, Any]:
        """Check if a fork exists for the given username."""
        try:
            result = await self.client_manager.call_tool(
                "github",
                "get_repository",
                {
                    "owner": username,
                    "repo": self.repo.split("/")[1]
                }
            )
            
            if result and "repository" in result:
                repo_data = result["repository"]
                # Check if it's actually a fork
                is_fork = repo_data.get("fork", False)
                if is_fork:
                    self.logger.info(f"Fork exists for user {username}")
                    return {"exists": True, "fork_data": repo_data}
                else:
                    self.logger.info(f"Repository exists for user {username} but is not a fork")
                    return {"exists": False, "reason": "not_a_fork"}
            else:
                self.logger.info(f"No fork found for user {username}")
                return {"exists": False, "reason": "not_found"}
                
        except Exception as e:
            self.logger.debug(f"Fork check failed for user {username}: {e}")
            # Assume fork doesn't exist if we can't check
            return {"exists": False, "reason": "check_failed", "error": str(e)}
    
    async def create_fork(self) -> Dict[str, Any]:
        """Create a fork of the repository."""
        try:
            fork_url = await self.fork_repository()
            if fork_url:
                return {"success": True, "fork_url": fork_url}
            else:
                return {"success": False, "reason": "fork_failed"}
        except Exception as e:
            self.logger.error(f"Failed to create fork: {e}")
            return {"success": False, "reason": "exception", "error": str(e)}
    
    async def update_file(
        self,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str,
        sha: Optional[str] = None
    ) -> bool:
        """Update a file in the repository."""
        try:
            params = {
                "owner": self.repo.split("/")[0],
                "repo": self.repo.split("/")[1],
                "path": file_path,
                "message": commit_message,
                "content": content,
                "branch": branch
            }
            
            if sha:
                params["sha"] = sha
            
            result = await self.client_manager.call_tool(
                "github",
                "update_file",
                params
            )
            
            return result is not None
            
        except Exception as e:
            self.logger.error(f"Failed to update file {file_path}: {e}")
            return False
    
    async def get_current_user(self) -> Optional[str]:
        """Get the current authenticated user's username."""
        try:
            # Use direct GitHub API call to get current user
            import aiohttp
            import os
            
            github_token = os.getenv("GITHUB_TOKEN")
            if not github_token:
                self.logger.error("GITHUB_TOKEN not found in environment")
                return None
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "PyTorch-Issue-Agent"
                }
                
                async with session.get("https://api.github.com/user", headers=headers) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        username = user_data.get("login")
                        if username:
                            self.logger.info(f"Authenticated as GitHub user: {username}")
                            return username
                    else:
                        self.logger.error(f"GitHub API returned status {response.status}: {await response.text()}")
            
            # Fallback: try to get from git configuration
            import subprocess
            try:
                result = subprocess.run(
                    ["git", "config", "user.name"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    username = result.stdout.strip()
                    self.logger.info(f"Using git config username: {username}")
                    return username
            except Exception as git_error:
                self.logger.debug(f"Failed to get git username: {git_error}")
            
            # Final fallback: return None to skip fork creation
            self.logger.warning("Could not determine current user, will skip fork creation")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get current user: {e}")
            return None
    
    async def get_pr_ci_status(self, pr_number: int) -> Dict[str, Any]:
        """Get CI status information for a pull request."""
        # First try GitHub CLI for complete status (includes GitHub Actions)
        github_cli_result = await self._get_ci_status_with_gh_cli(pr_number)
        if github_cli_result["total_checks"] > 1:  # If we got meaningful data
            return github_cli_result
        
        # Fallback to MCP API
        try:
            self.logger.info(f"Fallback: Getting CI status for PR {pr_number} using MCP")
            result = await self.client_manager.call_tool(
                "github",
                "get_pull_request_status",
                {
                    "owner": self.repo.split("/")[0],
                    "repo": self.repo.split("/")[1],
                    "pull_number": pr_number
                }
            )
            
            # Parse the nested MCP response format
            if result and "content" in result and result["content"]:
                import json
                content_text = result["content"][0]["text"]
                status_data = json.loads(content_text)
            else:
                status_data = result
            
            if status_data and "statuses" in status_data:
                failing_checks = []
                pending_checks = []
                passing_checks = []
                
                # Process status checks
                for status in status_data["statuses"]:
                    check_info = {
                        "name": status.get("context", "unknown"),
                        "state": status.get("state", "unknown"),
                        "description": status.get("description", ""),
                        "target_url": status.get("target_url"),
                        "updated_at": status.get("updated_at")
                    }
                    
                    if status.get("state") == "failure":
                        failing_checks.append(check_info)
                    elif status.get("state") == "pending":
                        pending_checks.append(check_info)
                    elif status.get("state") == "success":
                        passing_checks.append(check_info)
                
                # Also check check runs if available
                if "check_runs" in status_data:
                    for check_run in status_data["check_runs"]:
                        check_info = {
                            "name": check_run.get("name", "unknown"),
                            "state": check_run.get("conclusion", check_run.get("status", "unknown")),
                            "description": check_run.get("summary", ""),
                            "target_url": check_run.get("html_url"),
                            "updated_at": check_run.get("completed_at", check_run.get("started_at"))
                        }
                        
                        conclusion = check_run.get("conclusion")
                        if conclusion in ["failure", "timed_out", "cancelled"]:
                            failing_checks.append(check_info)
                        elif conclusion == "success":
                            passing_checks.append(check_info)
                        else:
                            pending_checks.append(check_info)
                
                return {
                    "overall_state": "failure" if failing_checks else ("pending" if pending_checks else "success"),
                    "failing_checks": failing_checks,
                    "pending_checks": pending_checks, 
                    "passing_checks": passing_checks,
                    "total_checks": len(failing_checks) + len(pending_checks) + len(passing_checks)
                }
            
            # Fallback if no status data
            return {
                "overall_state": "unknown",
                "failing_checks": [],
                "pending_checks": [],
                "passing_checks": [],
                "total_checks": 0
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get CI status for PR {pr_number}: {e}")
            # Return GitHub CLI result if MCP fails
            return github_cli_result
    
    async def _get_ci_status_with_gh_cli(self, pr_number: int) -> Dict[str, Any]:
        """Get complete CI status using GitHub CLI as fallback."""
        try:
            import subprocess
            import json
            
            self.logger.info(f"Fallback: Getting CI status for PR {pr_number} using GitHub CLI")
            
            # Use GitHub CLI to get complete status check rollup
            result = subprocess.run([
                "gh", "pr", "view", str(pr_number),
                "--repo", self.repo,
                "--json", "statusCheckRollup"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                self.logger.error(f"GitHub CLI failed: {result.stderr}")
                return {
                    "overall_state": "error",
                    "failing_checks": [],
                    "pending_checks": [],
                    "passing_checks": [],
                    "total_checks": 0
                }
            
            data = json.loads(result.stdout)
            status_checks = data.get("statusCheckRollup", [])
            
            failing_checks = []
            pending_checks = []
            passing_checks = []
            
            for check in status_checks:
                check_info = {
                    "name": check.get("name", "unknown"),
                    "state": check.get("conclusion", check.get("state", "unknown")),
                    "description": check.get("name", ""),  # Use name as description
                    "target_url": check.get("detailsUrl"),
                    "updated_at": check.get("completedAt", check.get("startedAt"))
                }
                
                conclusion = check.get("conclusion", "").upper()
                status = check.get("status", "").upper()
                
                if conclusion == "FAILURE" or conclusion == "TIMED_OUT" or conclusion == "CANCELLED":
                    failing_checks.append(check_info)
                elif conclusion == "SUCCESS":
                    passing_checks.append(check_info)
                elif status == "IN_PROGRESS" or status == "QUEUED" or conclusion == "":
                    pending_checks.append(check_info)
                else:
                    # Handle other states
                    if conclusion in ["SKIPPED", "NEUTRAL"]:
                        passing_checks.append(check_info)
                    else:
                        pending_checks.append(check_info)
            
            overall_state = "failure" if failing_checks else ("pending" if pending_checks else "success")
            
            self.logger.info(f"GitHub CLI found {len(failing_checks)} failing, {len(pending_checks)} pending, {len(passing_checks)} passing checks")
            
            return {
                "overall_state": overall_state,
                "failing_checks": failing_checks,
                "pending_checks": pending_checks,
                "passing_checks": passing_checks,
                "total_checks": len(failing_checks) + len(pending_checks) + len(passing_checks)
            }
            
        except Exception as e:
            self.logger.error(f"GitHub CLI fallback failed: {e}")
            return {
                "overall_state": "error",
                "failing_checks": [],
                "pending_checks": [],
                "passing_checks": [],
                "total_checks": 0
            }
    
    async def get_check_failure_details(self, check_details_url: str) -> Dict[str, Any]:
        """Get detailed failure information from a GitHub Actions check run."""
        try:
            import subprocess
            import re
            
            # Extract job ID from the details URL
            # URL format: https://github.com/pytorch/pytorch/actions/runs/15660714559/job/44117993387
            job_match = re.search(r'/job/(\d+)', check_details_url)
            if not job_match:
                return {"error": "Could not extract job ID from URL", "summary": "Unknown failure"}
            
            job_id = job_match.group(1)
            self.logger.info(f"Getting failure details for job {job_id}")
            
            # Use GitHub CLI to get job logs
            result = subprocess.run([
                "gh", "run", "view", job_id,
                "--repo", self.repo,
                "--log-failed"
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                # Fallback: try to get basic job info
                result = subprocess.run([
                    "gh", "api", f"repos/{self.repo}/actions/jobs/{job_id}"
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    import json
                    job_data = json.loads(result.stdout)
                    return {
                        "summary": job_data.get("name", "Unknown job"),
                        "conclusion": job_data.get("conclusion", "unknown"),
                        "logs": "Log details not available",
                        "error": None
                    }
                else:
                    return {"error": f"Failed to get job details: {result.stderr}", "summary": "API call failed"}
            
            # Parse the log output for key error information
            log_output = result.stdout
            
            # Extract key failure information (first 2000 chars to avoid overwhelming Claude)
            summary_lines = []
            error_lines = []
            
            for line in log_output.split('\n')[:100]:  # First 100 lines
                line = line.strip()
                if any(keyword in line.lower() for keyword in ['error:', 'failed:', 'exception:', 'traceback']):
                    error_lines.append(line)
                elif any(keyword in line.lower() for keyword in ['test', 'build', 'compile']):
                    summary_lines.append(line)
            
            failure_summary = '\n'.join(error_lines[:10])  # Top 10 error lines
            context_summary = '\n'.join(summary_lines[:5])   # Top 5 context lines
            
            return {
                "summary": context_summary or "Build/test failure",
                "failure_details": failure_summary or "Error details not found in logs",
                "logs_preview": log_output[:1500],  # First 1500 chars of logs
                "conclusion": "failure",
                "error": None
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get check failure details: {e}")
            return {
                "error": str(e),
                "summary": "Failed to retrieve failure details",
                "failure_details": "Could not access GitHub Actions logs",
                "logs_preview": "",
                "conclusion": "unknown"
            }