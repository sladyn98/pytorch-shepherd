"""Prompt management for Claude CLI interactions."""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml


class PromptManager:
    """Manages prompts for Claude CLI interactions."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the prompt manager.
        
        Args:
            config_path: Path to prompts configuration file
        """
        if config_path is None:
            # Default to config/prompts.yaml in the package directory
            package_dir = Path(__file__).parent.parent
            config_path = package_dir / "config" / "prompts.yaml"
        
        self.config_path = config_path
        self.prompts = self._load_prompts()
    
    def _load_prompts(self) -> Dict[str, Any]:
        """Load prompts from configuration file."""
        if not self.config_path.exists():
            # Return default prompts if config file doesn't exist
            return self._get_default_prompts()
        
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            # Fall back to defaults on error
            print(f"Warning: Failed to load prompts from {self.config_path}: {e}")
            return self._get_default_prompts()
    
    def _get_default_prompts(self) -> Dict[str, Any]:
        """Get default prompts if config file is not available."""
        return {
            "fix_issue": {
                "template": "Fix the following issue:\n{error_details}\n\nWhen done, respond with: CHANGES_COMPLETE"
            },
            "fix_failing_tests": {
                "template": "Fix these failing tests:\n{failing_tests}\n\nWhen done, respond with: CHANGES_COMPLETE"
            },
            "address_review": {
                "template": "Address these review comments:\n{review_comments}\n\nWhen done, respond with: CHANGES_COMPLETE"
            },
            "git": {
                "default_user_name": "PyTorch Issue Agent",
                "default_user_email": "agent@pytorch.dev",
                "commit_message_template": "{title}\n\nFixes #{issue_number}"
            }
        }
    
    def get_prompt(self, prompt_type: str, **kwargs) -> str:
        """Get a formatted prompt.
        
        Args:
            prompt_type: Type of prompt (e.g., 'fix_issue', 'fix_failing_tests')
            **kwargs: Variables to format into the prompt template
            
        Returns:
            Formatted prompt string
        """
        prompt_config = self.prompts.get(prompt_type, {})
        template = prompt_config.get("template", "")
        
        # Format the template with provided variables
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required variable for prompt '{prompt_type}': {e}")
    
    def get_git_config(self) -> Dict[str, str]:
        """Get git configuration."""
        return self.prompts.get("git", {})
    
    def get_commit_message(self, title: str, changes_summary: str, issue_number: int) -> str:
        """Generate a commit message.
        
        Args:
            title: Commit title
            changes_summary: Summary of changes
            issue_number: Issue number being fixed
            
        Returns:
            Formatted commit message
        """
        git_config = self.get_git_config()
        template = git_config.get("commit_message_template", "{title}")
        
        return template.format(
            title=title,
            changes_summary=changes_summary,
            issue_number=issue_number
        )