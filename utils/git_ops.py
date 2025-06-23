"""Git operations for local PyTorch repository management."""

import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class GitOperations:
    """Handle git operations for local PyTorch repository."""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_path}")
    
    def _run_git_command(self, cmd: List[str], timeout: int = 60) -> Optional[subprocess.CompletedProcess]:
        """Run a git command and return the result."""
        try:
            full_cmd = ["git", "-C", str(self.repo_path)] + cmd
            logger.debug(f"Running git command: {' '.join(full_cmd)}")
            result = subprocess.run(
                full_cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout
            )
            return result
        except subprocess.TimeoutExpired:
            logger.error(f"Git command timed out: {cmd}")
            return None
        except Exception as e:
            logger.error(f"Git command failed: {cmd} - {e}")
            return None
    
    def get_current_branch(self) -> Optional[str]:
        """Get the current git branch."""
        result = self._run_git_command(["branch", "--show-current"])
        if result and result.returncode == 0:
            return result.stdout.strip()
        return None
    
    def cleanup_repository(self) -> bool:
        """Clean up repository state - reset any uncommitted changes and resolve conflicts."""
        try:
            logger.info("Cleaning up repository state...")
            
            # Reset any uncommitted changes
            result = self._run_git_command(["reset", "--hard", "HEAD"])
            if result and result.returncode != 0:
                logger.warning(f"Failed to reset repository: {result.stderr}")
            
            # Clean untracked files
            result = self._run_git_command(["clean", "-fd"])
            if result and result.returncode != 0:
                logger.warning(f"Failed to clean untracked files: {result.stderr}")
                
            # Abort any ongoing merge/rebase
            result = self._run_git_command(["merge", "--abort"])
            if result and result.returncode != 0:
                logger.debug("No merge to abort (this is normal)")
                
            result = self._run_git_command(["rebase", "--abort"])
            if result and result.returncode != 0:
                logger.debug("No rebase to abort (this is normal)")
            
            logger.info("Repository cleanup completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup repository: {e}")
            return False

    def create_branch(self, branch_name: str, base_branch: str = "main") -> bool:
        """Create a new branch from base branch."""
        try:
            # First, clean up the repository state
            if not self.cleanup_repository():
                logger.warning("Repository cleanup failed, but continuing...")
            
            # Delete existing branch if it exists (ensure we're not on it first)
            if self.branch_exists(branch_name):
                current_branch = self.get_current_branch()
                if current_branch == branch_name:
                    # Switch to base branch before deleting
                    logger.info(f"Switching from {branch_name} to {base_branch} before deletion")
                    if not self.checkout_branch(base_branch):
                        logger.error(f"Failed to checkout {base_branch} before deletion")
                        return False
                logger.info(f"Deleting existing branch: {branch_name}")
                if not self.delete_branch(branch_name, force=True):
                    logger.warning(f"Failed to delete existing branch {branch_name}, will try to continue")
                    # Try to delete remote tracking branch too
                    result = self._run_git_command(["branch", "-Dr", f"origin/{branch_name}"])
                    if result and result.returncode != 0:
                        logger.debug(f"No remote tracking branch to delete for {branch_name}")
                    # Continue anyway, git checkout -B will override existing branch
            
            # First, ensure we're on the base branch and it's up to date
            if not self.checkout_branch(base_branch):
                logger.error(f"Failed to checkout base branch: {base_branch}")
                return False
            
            # Fetch latest changes
            result = self._run_git_command(["fetch", "origin"])
            if result and result.returncode != 0:
                logger.warning(f"Failed to fetch from origin: {result.stderr}")
            
            # Update base branch
            result = self._run_git_command(["pull", "origin", base_branch])
            if result and result.returncode != 0:
                logger.warning(f"Failed to pull latest {base_branch}: {result.stderr}")
            
            # Create new branch (use -B to create or reset if exists)
            result = self._run_git_command(["checkout", "-B", branch_name])
            if result and result.returncode == 0:
                logger.info(f"Created branch: {branch_name}")
                return True
            else:
                logger.error(f"Failed to create branch {branch_name}: {result.stderr if result else 'Unknown error'}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to create branch {branch_name}: {e}")
            return False
    
    def checkout_branch(self, branch_name: str) -> bool:
        """Checkout an existing branch."""
        result = self._run_git_command(["checkout", branch_name])
        if result and result.returncode == 0:
            logger.info(f"Checked out branch: {branch_name}")
            return True
        else:
            logger.error(f"Failed to checkout branch {branch_name}: {result.stderr if result else 'Unknown error'}")
            return False
    
    def commit_changes(self, message: str, files: Optional[List[str]] = None) -> bool:
        """Commit changes to the repository."""
        try:
            # Add files (all if none specified)
            if files:
                for file in files:
                    result = self._run_git_command(["add", file])
                    if result and result.returncode != 0:
                        logger.error(f"Failed to add file {file}: {result.stderr}")
                        return False
            else:
                result = self._run_git_command(["add", "."])
                if result and result.returncode != 0:
                    logger.error(f"Failed to add all files: {result.stderr}")
                    return False
            
            # Check if there are changes to commit
            result = self._run_git_command(["diff", "--cached", "--quiet"])
            if result and result.returncode == 0:
                logger.info("No changes to commit")
                return True
            
            # Commit changes
            result = self._run_git_command(["commit", "-m", message])
            if result and result.returncode == 0:
                logger.info(f"Committed changes: {message}")
                return True
            else:
                logger.error(f"Failed to commit changes: {result.stderr if result else 'Unknown error'}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to commit changes: {e}")
            return False
    
    def push_branch(self, branch_name: str, set_upstream: bool = True) -> bool:
        """Push branch to origin."""
        try:
            cmd = ["push"]
            if set_upstream:
                cmd.extend(["-u", "origin", branch_name])
            else:
                cmd.extend(["origin", branch_name])
            
            result = self._run_git_command(cmd, timeout=120)  # Longer timeout for push
            if result and result.returncode == 0:
                logger.info(f"Pushed branch: {branch_name}")
                return True
            else:
                logger.error(f"Failed to push branch {branch_name}: {result.stderr if result else 'Unknown error'}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to push branch {branch_name}: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get git status information."""
        try:
            result = self._run_git_command(["status", "--porcelain"])
            if not result or result.returncode != 0:
                return {"clean": False, "files": []}
            
            files = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    status = line[:2]
                    filename = line[3:]
                    files.append({"status": status, "file": filename})
            
            return {
                "clean": len(files) == 0,
                "files": files,
                "branch": self.get_current_branch()
            }
            
        except Exception as e:
            logger.error(f"Failed to get git status: {e}")
            return {"clean": False, "files": []}
    
    def get_remote_url(self, remote: str = "origin") -> Optional[str]:
        """Get the URL of a remote."""
        result = self._run_git_command(["remote", "get-url", remote])
        if result and result.returncode == 0:
            return result.stdout.strip()
        return None
    
    def branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists locally."""
        result = self._run_git_command(["branch", "--list", branch_name])
        if result and result.returncode == 0:
            return bool(result.stdout.strip())
        return False
    
    def delete_branch(self, branch_name: str, force: bool = False) -> bool:
        """Delete a local branch."""
        cmd = ["branch", "-D" if force else "-d", branch_name]
        result = self._run_git_command(cmd)
        if result and result.returncode == 0:
            logger.info(f"Deleted branch: {branch_name}")
            return True
        else:
            logger.error(f"Failed to delete branch {branch_name}: {result.stderr if result else 'Unknown error'}")
            return False
    
    def get_diff(self, branch1: str = "HEAD", branch2: str = None) -> Optional[str]:
        """Get diff between branches or commits."""
        cmd = ["diff"]
        if branch2:
            cmd.append(f"{branch1}..{branch2}")
        else:
            cmd.append(branch1)
        
        result = self._run_git_command(cmd)
        if result and result.returncode == 0:
            return result.stdout
        return None
    
    def get_log(self, max_count: int = 10, one_line: bool = True) -> List[str]:
        """Get git log entries."""
        cmd = ["log", f"--max-count={max_count}"]
        if one_line:
            cmd.append("--oneline")
        
        result = self._run_git_command(cmd)
        if result and result.returncode == 0:
            return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        return []