"""Direct GitHub API client to work around MCP authentication issues."""

import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any
import json


class GitHubAPIClient:
    """Direct GitHub API client for operations that don't work via MCP."""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.logger = logging.getLogger(__name__)
        
    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "PyTorch-Issue-Agent/1.0"
        }
    
    async def create_fork(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Create a fork of the repository."""
        url = f"{self.base_url}/repos/{owner}/{repo}/forks"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=self._get_headers()) as response:
                    if response.status == 202:  # Fork created
                        data = await response.json()
                        self.logger.info(f"Fork created: {data['full_name']}")
                        return data
                    elif response.status == 200:  # Fork already exists
                        data = await response.json()
                        self.logger.info(f"Fork already exists: {data['full_name']}")
                        return data
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Fork creation failed: {response.status} - {error_text}")
                        return None
            except Exception as e:
                self.logger.error(f"Fork creation error: {e}")
                return None
    
    async def get_current_user(self) -> Optional[str]:
        """Get the current authenticated user's username."""
        url = f"{self.base_url}/user"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=self._get_headers()) as response:
                    if response.status == 200:
                        data = await response.json()
                        username = data['login']
                        self.logger.info(f"Current user: {username}")
                        return username
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Get user failed: {response.status} - {error_text}")
                        return None
            except Exception as e:
                self.logger.error(f"Get user error: {e}")
                return None
    
    async def check_fork_exists(self, owner: str, repo: str, fork_owner: str) -> bool:
        """Check if a fork exists."""
        url = f"{self.base_url}/repos/{fork_owner}/{repo}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=self._get_headers()) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Check if it's actually a fork of the target repo
                        if data.get('fork') and data.get('parent', {}).get('full_name') == f"{owner}/{repo}":
                            return True
                    return False
            except Exception as e:
                self.logger.debug(f"Fork check error: {e}")
                return False