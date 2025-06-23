#!/usr/bin/env python3
"""
GitHub authentication and fork management utilities.
"""

import os
import logging
import subprocess
from typing import Optional, Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class GitHubAuth:
    """Manages GitHub authentication and fork setup."""
    
    def __init__(self, github_token: str, github_username: Optional[str] = None):
        self.token = github_token
        self.username = github_username or self._get_username()
        
    def _get_username(self) -> str:
        """Get GitHub username from token."""
        try:
            import requests
            headers = {"Authorization": f"token {self.token}"}
            response = requests.get("https://api.github.com/user", headers=headers)
            response.raise_for_status()
            return response.json()["login"]
        except Exception as e:
            logger.error(f"Failed to get GitHub username: {e}")
            raise RuntimeError("Could not determine GitHub username from token")
    
    def setup_fork_remote(self, repo_path: str, upstream_repo: str = "pytorch/pytorch") -> bool:
        """Set up git remotes for fork workflow."""
        try:
            # Parse upstream repo
            owner, repo = upstream_repo.split("/")
            fork_url = f"https://{self.username}:{self.token}@github.com/{self.username}/{repo}.git"
            upstream_url = f"https://github.com/{owner}/{repo}.git"
            
            # Check current remotes
            result = subprocess.run(
                ["git", "remote", "-v"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            
            # Remove existing remotes
            subprocess.run(["git", "remote", "remove", "origin"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "remote", "remove", "upstream"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "remote", "remove", "fork"], cwd=repo_path, capture_output=True)
            
            # Add fork as origin
            subprocess.run(
                ["git", "remote", "add", "origin", fork_url],
                cwd=repo_path,
                check=True
            )
            
            # Add upstream
            subprocess.run(
                ["git", "remote", "add", "upstream", upstream_url],
                cwd=repo_path,
                check=True
            )
            
            logger.info(f"Set up fork remote: origin -> {self.username}/{repo}")
            logger.info(f"Set up upstream remote: upstream -> {owner}/{repo}")
            
            # Fetch from upstream
            subprocess.run(
                ["git", "fetch", "upstream"],
                cwd=repo_path,
                check=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup fork remote: {e}")
            return False
    
    def ensure_fork_exists(self, upstream_repo: str = "pytorch/pytorch") -> bool:
        """Ensure the fork exists on GitHub."""
        try:
            import requests
            
            owner, repo = upstream_repo.split("/")
            
            # Check if fork exists
            headers = {"Authorization": f"token {self.token}"}
            fork_url = f"https://api.github.com/repos/{self.username}/{repo}"
            response = requests.get(fork_url, headers=headers)
            
            if response.status_code == 200:
                logger.info(f"Fork already exists: {self.username}/{repo}")
                return True
            
            # Create fork
            logger.info(f"Creating fork of {upstream_repo}...")
            fork_api_url = f"https://api.github.com/repos/{owner}/{repo}/forks"
            response = requests.post(fork_api_url, headers=headers)
            
            if response.status_code in [202, 201]:
                logger.info(f"Fork created successfully: {self.username}/{repo}")
                return True
            else:
                logger.error(f"Failed to create fork: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to ensure fork exists: {e}")
            return False


def setup_github_auth(repo_path: str, github_token: str, 
                     github_username: Optional[str] = None,
                     upstream_repo: str = "pytorch/pytorch") -> bool:
    """Complete GitHub authentication setup."""
    auth = GitHubAuth(github_token, github_username)
    
    # Ensure fork exists
    if not auth.ensure_fork_exists(upstream_repo):
        return False
    
    # Setup remotes
    if not auth.setup_fork_remote(repo_path, upstream_repo):
        return False
    
    # Configure git user
    try:
        subprocess.run(
            ["git", "config", "user.name", "PyTorch Issue Agent"],
            cwd=repo_path,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.email", f"{auth.username}@users.noreply.github.com"],
            cwd=repo_path,
            check=True
        )
        logger.info("Git user configured")
    except Exception as e:
        logger.error(f"Failed to configure git user: {e}")
        return False
    
    return True