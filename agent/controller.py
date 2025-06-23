"""Main controller for the PyTorch Issue Fixing Agent."""

import asyncio
import logging
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from mcp.client_manager import MCPClientManager
from mcp.github_client import GitHubMCPClient
from mcp.pytorch_hud_client import PyTorchHUDClient
from claude.client import ClaudeClient
from utils.config import Config
from utils.logging import set_correlation_id
from utils.sanitizer import ContentSanitizer
from .workflow import IssueState, WorkflowContext, WorkflowEngine
from .state_manager import StateManager, AgentState


class IssueFixingAgent:
    """Main agent controller that orchestrates the issue fixing process."""
    
    def __init__(self, issue_number: int, repo: str, config: Config, dry_run: bool = False, local_repo_path: Optional[str] = None):
        self.issue_number = issue_number
        self.repo = repo
        self.config = config
        self.dry_run = dry_run
        self.local_repo_path = local_repo_path
        self.logger = logging.getLogger(__name__)
        
        # Set correlation ID for this agent instance
        self.correlation_id = set_correlation_id(f"issue-{issue_number}")
        
        # Initialize components
        self.mcp_manager = MCPClientManager(config.mcp)
        self.github_client = GitHubMCPClient(self.mcp_manager, repo)
        self.pytorch_hud_client = PyTorchHUDClient(self.mcp_manager)
        self.claude_client = ClaudeClient(config.claude)
        self.workflow_engine = WorkflowEngine(
            max_attempts=config.agent.max_attempts,
            monitoring_interval=config.agent.monitoring_interval
        )
        self.state_manager = StateManager(
            state_file=config.agent.state_file,
            backup_interval=config.agent.backup_interval
        )
        
        # Local operations will be initialized later after ensuring repository exists
        self.local_ops = None
        self.git_ops = None
        
        # Runtime state
        self.current_state: Optional[IssueState] = None
        self.context: Optional[WorkflowContext] = None
        self.running = False
    
    async def _ensure_repository_prerequisites(self):
        """Ensure PyTorch repository and fork exist, create them if missing."""
        if not self.local_repo_path:
            return  # Skip if no local repo path specified
        
        self.logger.info("Checking repository prerequisites...")
        
        # Step 1: Ensure PyTorch repository exists locally
        await self._ensure_local_repository()
        
        # Step 2: Ensure user has a fork
        await self._ensure_fork_exists()
        
        # Step 3: Initialize local operations now that repo exists
        await self._initialize_local_operations()
    
    async def _ensure_local_repository(self):
        """Clone PyTorch repository if it doesn't exist with robust error handling."""
        repo_path = Path(self.local_repo_path)
        
        if repo_path.exists() and (repo_path / ".git").exists():
            self.logger.info(f"Repository already exists at: {self.local_repo_path}")
            return
        
        self.logger.info(f"Cloning PyTorch repository to: {self.local_repo_path}")
        
        # Try multiple strategies for initializing repository
        strategies = [
            self._clone_with_cleanup,
            self._clone_without_cleanup,
            self._clone_to_subdirectory
        ]
        
        for i, strategy in enumerate(strategies, 1):
            try:
                self.logger.info(f"Trying repository initialization strategy {i}/3")
                await strategy(repo_path)
                self.logger.info("Successfully cloned PyTorch repository")
                return
            except Exception as e:
                self.logger.warning(f"Strategy {i} failed: {e}")
                if i == len(strategies):
                    # All strategies failed
                    self.logger.error(f"All repository initialization strategies failed")
                    raise RuntimeError(f"Could not initialize PyTorch repository: {e}")
                else:
                    # Try next strategy
                    continue

    async def _clone_with_cleanup(self, repo_path: Path):
        """Strategy 1: Remove existing directory then clone."""
        import subprocess, shutil
        
        if repo_path.exists():
            self.logger.info("Removing existing directory for clean clone")
            shutil.rmtree(repo_path)
        
        cmd = [
            "git", "clone", 
            "--depth", "1",
            "https://github.com/pytorch/pytorch.git",
            str(repo_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")

    async def _clone_without_cleanup(self, repo_path: Path):
        """Strategy 2: Clone directly without removing existing directory."""
        import subprocess
        
        if repo_path.exists():
            self.logger.info("Directory exists, attempting direct clone")
        
        cmd = [
            "git", "clone", 
            "--depth", "1",
            "https://github.com/pytorch/pytorch.git",
            str(repo_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")

    async def _clone_to_subdirectory(self, repo_path: Path):
        """Strategy 3: Clone to temp directory then move."""
        import subprocess, shutil, tempfile
        
        # Create a temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_repo = Path(temp_dir) / "pytorch"
            
            cmd = [
                "git", "clone", 
                "--depth", "1",
                "https://github.com/pytorch/pytorch.git",
                str(temp_repo)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                raise RuntimeError(f"Git clone failed: {result.stderr}")
            
            # Ensure target directory exists and move contents
            repo_path.mkdir(parents=True, exist_ok=True)
            
            # Move contents from temp to target
            for item in temp_repo.iterdir():
                target = repo_path / item.name
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                shutil.move(str(item), str(target))
    
    async def _ensure_fork_exists(self):
        """Ensure user has a fork of PyTorch, create one if missing."""
        try:
            # Get GitHub username from config/environment
            github_username = os.getenv("GITHUB_USERNAME")
            if not github_username:
                self.logger.warning("GITHUB_USERNAME not set, skipping fork check")
                return
            
            # Check if fork already exists
            fork_check_result = await self.github_client.check_fork_exists(github_username)
            
            if fork_check_result.get("exists", False):
                self.logger.info(f"Fork already exists for user: {github_username}")
                return
            
            # Create fork
            self.logger.info(f"Creating fork for user: {github_username}")
            fork_result = await self.github_client.create_fork()
            
            if fork_result.get("success", False):
                self.logger.info("Successfully created fork")
            else:
                self.logger.warning(f"Fork creation result unclear: {fork_result}")
                
        except Exception as e:
            self.logger.error(f"Failed to ensure fork exists: {e}")
            # Don't raise here - fork creation might not be critical for some operations
    
    async def _initialize_local_operations(self):
        """Initialize local operations after ensuring repository exists."""
        try:
            from utils.local_ops import LocalFileOperations
            from utils.git_ops import GitOperations
            
            self.local_ops = LocalFileOperations(self.local_repo_path)
            self.git_ops = GitOperations(self.local_repo_path)
            self.logger.info(f"Successfully initialized local operations for: {self.local_repo_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize local operations: {e}")
            raise
    
    async def run(self):
        """Main execution loop."""
        self.logger.info(f"Starting PyTorch Issue Fixing Agent for issue #{self.issue_number}")
        
        try:
            # Initialize services
            await self._initialize()
            
            # Ensure repository prerequisites (clone repo, create fork if needed)
            await self._ensure_repository_prerequisites()
            
            # Load or create initial state
            await self._load_or_create_state()
            
            # Main execution loop
            self.running = True
            while self.running and not self.workflow_engine.is_terminal_state(self.current_state):
                await self._execute_current_state()
                await self._transition_to_next_state()
                await self._save_state()
                
                # Brief pause between state transitions to avoid overwhelming APIs
                await asyncio.sleep(1)
            
            # Log final state
            if self.current_state == IssueState.COMPLETED:
                self.logger.info(f"Issue #{self.issue_number} completed successfully!")
            elif self.current_state == IssueState.FAILED:
                self.logger.error(f"Issue #{self.issue_number} failed after all attempts")
            
        except KeyboardInterrupt:
            self.logger.info("Agent stopped by user")
            self.running = False
            await self._save_state()
        except Exception as e:
            self.logger.error(f"Agent crashed: {e}", exc_info=True)
            if self.context:
                self.context.error_history.append(f"Agent crash: {str(e)}")
            await self._save_state()
            raise
        finally:
            await self._cleanup()
    
    async def pause(self):
        """Pause the agent execution."""
        self.logger.info("Pausing agent execution")
        self.running = False
        if self.current_state and self.current_state != IssueState.PAUSED:
            old_state = self.current_state
            self.current_state = IssueState.PAUSED
            self.workflow_engine.log_state_transition(old_state, self.current_state, self.context)
            await self._save_state()
    
    async def resume(self):
        """Resume paused agent execution."""
        if self.current_state != IssueState.PAUSED:
            self.logger.warning("Agent is not paused")
            return
        
        self.logger.info("Resuming agent execution")
        # Determine appropriate state to resume from
        if self.context.pr_number:
            self.current_state = IssueState.MONITORING
        elif self.context.issue_data:
            self.current_state = IssueState.FIXING
        else:
            self.current_state = IssueState.FETCHING
        
        await self.run()
    
    async def _initialize(self):
        """Initialize all services."""
        self.logger.info("Initializing MCP servers")
        
        # Start GitHub MCP server
        if not await self.mcp_manager.start_server("github", self.config.mcp.github_server_command):
            raise RuntimeError("Failed to start GitHub MCP server")
        
        github_health = await self.mcp_manager.health_check("github")
        if not github_health:
            raise RuntimeError("GitHub MCP server is not healthy")
        
        # Test GitHub MCP server tools
        try:
            tools = await self.mcp_manager.list_tools("github")
            self.logger.info(f"GitHub MCP tools available: {[t.get('name') for t in tools]}")
        except Exception as e:
            self.logger.error(f"Failed to list GitHub tools: {e}")
        
        # Start PyTorch HUD MCP server
        try:
            # Use our PyTorch HUD MCP server
            import sys
            import os
            venv_python = sys.executable
            server_path = os.path.join(os.path.dirname(__file__), "..", "pytorch_hud_mcp_server.py")
            pytorch_hud_command = [venv_python, server_path]
            if await self.mcp_manager.start_server("pytorch_hud", pytorch_hud_command):
                pytorch_hud_health = await self.mcp_manager.health_check("pytorch_hud")
                if pytorch_hud_health:
                    try:
                        tools = await self.mcp_manager.list_tools("pytorch_hud")
                        self.logger.info(f"PyTorch HUD MCP tools available: {[t.get('name') for t in tools]}")
                        self.logger.info("PyTorch HUD MCP server initialized successfully")
                    except Exception as e:
                        self.logger.warning(f"Failed to list PyTorch HUD tools: {e}")
                else:
                    self.logger.warning("PyTorch HUD MCP server is not healthy")
            else:
                self.logger.warning("Failed to start PyTorch HUD MCP server")
        except Exception as e:
            self.logger.warning(f"PyTorch HUD MCP initialization failed: {e}")
        
        self.logger.info("MCP servers initialization completed")
        
        # Validate GitHub authentication early
        await self._validate_github_authentication()
    
    async def _validate_github_authentication(self):
        """Validate GitHub authentication works before starting workflow."""
        self.logger.info("Validating GitHub authentication...")
        
        try:
            # Test basic GitHub API access through MCP
            current_user = await self.github_client.get_current_user()
            if not current_user:
                raise RuntimeError("Failed to get current user - GitHub token may be invalid")
            
            self.logger.info(f"GitHub authentication successful - User: {current_user}")
            
            # Validate we can access the pytorch/pytorch repository  
            repo_check = await self.mcp_manager.call_tool(
                "github", 
                "get_repository", 
                {"owner": "pytorch", "repo": "pytorch"}
            )
            if not repo_check or "repository" not in repo_check:
                raise RuntimeError("Cannot access pytorch/pytorch repository")
            
            self.logger.info("GitHub repository access validated")
            
            # Check if user has a fork or can create one
            github_username = os.getenv("GITHUB_USERNAME")
            if github_username:
                self.logger.info(f"Checking fork permissions for user: {github_username}")
                # Test fork check (will validate permissions without creating)
                fork_check = await self.github_client.check_fork_exists(github_username)
                self.logger.info(f"Fork check result: {fork_check}")
            
        except Exception as e:
            self.logger.error(f"GitHub authentication validation failed: {e}")
            raise RuntimeError(f"GitHub authentication failed: {e}. Please check your GITHUB_TOKEN.")
    
    async def _load_or_create_state(self):
        """Load existing state or create new one."""
        # Try to load existing state
        existing_state = self.state_manager.load_state()
        
        if existing_state and existing_state.issue_number == self.issue_number:
            self.logger.info(f"Resuming from saved state: {existing_state.current_state.value}")
            self.current_state = existing_state.current_state
            self.context = existing_state.context
        else:
            # No existing state - start fresh
            self.logger.info("Creating new state")
            self.current_state = IssueState.FETCHING
            self.context = WorkflowContext(
                issue_number=self.issue_number,
                repo=self.repo
            )
    
    async def _execute_current_state(self):
        """Execute the current state logic."""
        self.logger.info(f"Executing state: {self.current_state.value}")
        
        try:
            if self.current_state == IssueState.FETCHING:
                await self._fetch_issue()
            elif self.current_state == IssueState.ANALYZING:
                await self._analyze_issue()
            elif self.current_state == IssueState.FIXING:
                await self._fix_issue()
            elif self.current_state == IssueState.CREATING_PR:
                await self._create_pull_request()
            elif self.current_state == IssueState.MONITORING:
                await self._monitor_progress()
            elif self.current_state == IssueState.ADDRESSING_REVIEWS:
                await self._address_reviews()
            else:
                self.logger.warning(f"No handler for state: {self.current_state.value}")
                
        except Exception as e:
            self.logger.error(f"Error in state {self.current_state.value}: {e}", exc_info=True)
            self.context.error_history.append(f"{self.current_state.value}: {str(e)}")
            raise
    
    async def _transition_to_next_state(self):
        """Transition to the next state."""
        old_state = self.current_state
        next_state = self.workflow_engine.get_next_state(self.current_state, self.context)
        
        if next_state and next_state != self.current_state:
            self.current_state = next_state
            self.workflow_engine.log_state_transition(old_state, next_state, self.context)
        elif self.current_state == IssueState.MONITORING:
            # Handle monitoring wait logic
            wait_time = self.workflow_engine.get_time_until_next_check(self.context)
            if wait_time > 0:
                self.logger.info(f"Waiting {wait_time} seconds before next monitoring check")
                await asyncio.sleep(min(wait_time, 300))  # Max 5 minute sleep intervals
    
    async def _save_state(self):
        """Save current state."""
        if self.current_state and self.context:
            state = AgentState(
                issue_number=self.issue_number,
                repo=self.repo,
                current_state=self.current_state,
                context=self.context,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            self.state_manager.save_state(state)
    
    async def _cleanup(self):
        """Cleanup resources."""
        self.logger.info("Cleaning up resources")
        self.state_manager.stop_auto_backup()
        await self.mcp_manager.stop_all()
    
    # State-specific execution methods
    
    async def _fetch_issue(self):
        """Fetch issue details from GitHub."""
        self.logger.info(f"Fetching issue #{self.issue_number}")
        
        issue = await self.github_client.get_issue(self.issue_number)
        if not issue:
            raise RuntimeError(f"Could not fetch issue #{self.issue_number}")
        
        # Get issue comments for additional context
        comments = await self.github_client.get_issue_comments(self.issue_number)
        
        self.context.issue_data = {
            "issue": issue.__dict__,
            "comments": [comment.__dict__ for comment in comments]
        }
        
        self.logger.info(f"Issue fetched: {issue.title}")
    
    async def _analyze_issue(self):
        """Analyze the issue to understand the problem."""
        self.logger.info("Analyzing issue")
        
        # Use Claude to analyze the issue
        analysis = await self.claude_client.analyze_issue(
            self.context.issue_data["issue"],
            self.context.issue_data.get("comments", [])
        )
        
        # Search for related code files
        if analysis.get("search_terms"):
            for term in analysis["search_terms"][:5]:  # Limit searches
                if self.local_ops:
                    # Use local search operations
                    results = self.local_ops.search_code(term, max_results=3)
                    self.context.metadata.setdefault("related_files", []).extend(results)
                else:
                    # Fall back to GitHub API search
                    results = await self.github_client.search_code(term)
                    self.context.metadata.setdefault("related_files", []).extend(results[:3])
        
        self.context.metadata["analysis"] = analysis
        self.logger.info("Issue analysis completed")
    
    async def _fix_issue(self):
        """Generate and apply fix for the issue using Claude CLI."""
        self.logger.info(f"Attempting fix #{self.context.fix_attempt_count + 1}")
        
        self.context.fix_attempt_count += 1
        
        # Create branch for the fix
        self.context.branch_name = f"fix-issue-{self.issue_number}-attempt-{self.context.fix_attempt_count}"
        
        if not self.dry_run:
            if self.git_ops:
                # Use local git operations
                if not self.git_ops.create_branch(self.context.branch_name):
                    raise RuntimeError(f"Failed to create branch {self.context.branch_name}")
            else:
                # Fall back to GitHub API
                branch_created = await self.github_client.create_branch(self.context.branch_name)
                if not branch_created:
                    raise RuntimeError(f"Failed to create branch {self.context.branch_name}")
        
        # Use Claude CLI to make changes directly
        if not self.dry_run and self.local_repo_path:
            success = await self._run_claude_cli_fix()
            if not success:
                raise RuntimeError("Claude CLI fix failed")
        
        # Check what files were changed
        if self.git_ops:
            status = self.git_ops.get_status()
            changed_files = [f["file"] for f in status["files"] if f["status"].strip()]
            
            # Validate and clean up unwanted files
            validated_files = self._validate_and_cleanup_files(changed_files)
            self.context.generated_files = validated_files
            
            # Commit changes if any were made
            if validated_files and not self.dry_run:
                # Generate commit message based on issue title
                issue_title = self.context.issue_data.get("issue", {}).get("title", "Fix issue")
                commit_message = f"Fix issue #{self.issue_number}: {issue_title}"
                sanitized_commit_message = ContentSanitizer.sanitize_commit_message(commit_message)
                
                if not self.git_ops.commit_changes(sanitized_commit_message):
                    self.logger.warning("Failed to commit changes, but continuing")
        
        self.logger.info(f"Fix applied to {len(self.context.generated_files)} files")
    
    async def _run_claude_cli_fix(self):
        """Run Claude CLI to make fixes directly to the codebase."""
        import subprocess
        import tempfile
        import os
        
        try:
            # Create a detailed prompt for Claude CLI
            issue_title = self.context.issue_data["issue"]["title"]
            issue_body = self.context.issue_data["issue"]["body"]
            issue_comments = self.context.issue_data.get("comments", [])
            
            # Summarize and extract key information from issue comments
            comments_summary = ""
            if issue_comments:
                comments_summary = "\n\nKEY INSIGHTS FROM ISSUE COMMENTS:\n"
                
                # Extract and summarize key information
                key_points = []
                suggestions = []
                clarifications = []
                
                for comment in issue_comments:
                    author = comment.get("author", "Unknown")
                    body = comment.get("body", "").lower()
                    original_body = comment.get("body", "")
                    
                    # Identify different types of valuable information
                    if any(word in body for word in ["should", "try", "suggest", "recommend", "instead"]):
                        suggestions.append(f"- {author}: {original_body[:150]}...")
                    elif any(word in body for word in ["because", "reason", "why", "cause", "due to"]):
                        clarifications.append(f"- {author}: {original_body[:150]}...")
                    elif any(word in body for word in ["error", "fail", "problem", "issue", "bug"]):
                        key_points.append(f"- {author}: {original_body[:150]}...")
                
                if key_points:
                    comments_summary += "Key Issues Identified:\n" + "\n".join(key_points[:3]) + "\n\n"
                if suggestions:
                    comments_summary += "Suggested Solutions:\n" + "\n".join(suggestions[:3]) + "\n\n"
                if clarifications:
                    comments_summary += "Additional Context:\n" + "\n".join(clarifications[:3]) + "\n\n"
            
            prompt = f"""You have FULL PERMISSION to modify any files in this PyTorch repository to fix this issue. Please proceed immediately with making the necessary changes.

ISSUE: {issue_title}

DESCRIPTION:
{issue_body}{comments_summary}

AUTHORIZATION:
- You are AUTHORIZED to edit any file in this repository
- You have WRITE PERMISSIONS for all files  
- You should IMMEDIATELY start making file changes
- Do NOT ask for permission - you already have it
- Do NOT wait for approval - proceed with modifications

Please analyze the issue carefully and implement the appropriate solution. Follow the constraints and guidelines provided, and make only the necessary changes to resolve the issue."""

            # Set up environment
            env = os.environ.copy()
            env["ANTHROPIC_API_KEY"] = env.get("ANTHROPIC_API_KEY", "")
            
            # Check if Claude CLI is available
            try:
                subprocess.run(["which", "claude"], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                raise RuntimeError("Claude CLI not found in PATH. Please ensure Claude CLI is installed.")
            
            # Run Claude CLI with dangerous permissions skip to enable automatic editing
            cmd = ["claude", "--dangerously-skip-permissions"]
            
            self.logger.info(f"Running Claude CLI in {self.local_repo_path}")
            result = subprocess.run(
                cmd,
                input=prompt,
                cwd=self.local_repo_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=None  # No timeout - let Claude CLI take as long as needed
            )
            
            if result.returncode == 0:
                self.logger.info("Claude CLI completed successfully")
                if result.stdout:
                    self.logger.info(f"Claude CLI output: {result.stdout}")
                if result.stderr:
                    self.logger.warning(f"Claude CLI stderr: {result.stderr}")
                return True
            else:
                self.logger.error(f"Claude CLI failed with return code {result.returncode}")
                if result.stderr:
                    self.logger.error(f"Claude CLI error: {result.stderr}")
                if result.stdout:
                    self.logger.error(f"Claude CLI stdout: {result.stdout}")
                return False
                
        except subprocess.TimeoutExpired as e:
            self.logger.error(f"Claude CLI timed out after {e.timeout}s")
            # Kill any remaining Claude processes
            try:
                subprocess.run(["pkill", "-f", "claude"], timeout=5)
            except:
                pass
            return False
        except Exception as e:
            self.logger.error(f"Failed to run Claude CLI: {e}")
            return False
    
    async def _create_pull_request(self):
        """Create pull request with the fix."""
        self.logger.info("Creating pull request")
        
        if self.dry_run:
            self.logger.info("DRY RUN: Would create PR")
            self.context.pr_number = 999999  # Mock PR number for dry run
            return
        
        # Get current user and create fork using direct API (workaround for MCP auth issues)
        current_user = None
        fork_owner = None
        
        if hasattr(self.config, 'github_token') and self.config.github_token:
            # Use direct GitHub API to get user and create fork
            from utils.github_api import GitHubAPIClient
            github_api = GitHubAPIClient(self.config.github_token)
            
            current_user = await github_api.get_current_user()
            if current_user:
                self.logger.info(f"Current user: {current_user}")
                
                # Check if fork exists or create it
                fork_exists = await github_api.check_fork_exists("pytorch", "pytorch", current_user)
                if fork_exists:
                    self.logger.info(f"Fork already exists: {current_user}/pytorch")
                    fork_owner = current_user
                else:
                    fork_data = await github_api.create_fork("pytorch", "pytorch")
                    if fork_data:
                        fork_owner = current_user
                        self.logger.info(f"Fork created: {current_user}/pytorch")
                    else:
                        self.logger.warning("Failed to create fork via direct API")
        
        if not fork_owner:
            self.logger.warning("Could not create fork, will try direct push to origin")
        
        # If using local operations, push to origin (which should be the fork)
        if self.git_ops:
            # Check if we're using a fork setup
            github_username = os.getenv("GITHUB_USERNAME")
            if github_username:
                self.logger.info(f"Using fork workflow with username: {github_username}")
                # Origin should already be set to the fork by setup script
                if not self.git_ops.push_branch(self.context.branch_name):
                    raise RuntimeError(f"Failed to push branch {self.context.branch_name}")
                # Set fork_owner for PR creation
                fork_owner = github_username
            else:
                # Legacy flow - try to push to fork remote if it exists
                if fork_owner:
                    # Add fork as remote if not already added
                    fork_remote_url = f"https://github.com/{fork_owner}/{self.repo.split('/')[1]}.git"
                    result = self.git_ops._run_git_command(["remote", "add", "fork", fork_remote_url])
                    if result and result.returncode != 0 and "already exists" not in result.stderr:
                        self.logger.warning(f"Failed to add fork remote: {result.stderr}")
                    
                    # Push to fork
                    result = self.git_ops._run_git_command(["push", "-u", "fork", self.context.branch_name])
                    if not result or result.returncode != 0:
                        self.logger.warning("Failed to push to fork, falling back to origin")
                        if not self.git_ops.push_branch(self.context.branch_name):
                            raise RuntimeError(f"Failed to push branch {self.context.branch_name}")
                else:
                    # Push to origin
                    if not self.git_ops.push_branch(self.context.branch_name):
                        raise RuntimeError(f"Failed to push branch {self.context.branch_name}")
        
        # Generate PR title and description
        pr_data = await self.claude_client.generate_pr_description(
            issue_data=self.context.issue_data,
            fix_summary=self.context.metadata.get("analysis", {}),
            files_changed=self.context.generated_files
        )
        
        # Ensure PR data has required fields
        if "title" not in pr_data:
            pr_data["title"] = f"Fix issue #{self.issue_number}"
        if "body" not in pr_data:
            pr_data["body"] = "Automated fix for PyTorch issue."
            
        # Sanitize PR title and body
        sanitized_title = ContentSanitizer.sanitize_pr_title(pr_data["title"], self.issue_number)
        sanitized_body = ContentSanitizer.sanitize_pr_body(pr_data["body"], self.issue_number)
        
        # Validate sanitization
        title_issues = ContentSanitizer.validate_sanitization(sanitized_title)
        body_issues = ContentSanitizer.validate_sanitization(sanitized_body)
        
        if title_issues:
            self.logger.warning(f"PR title sanitization issues: {title_issues}")
        if body_issues:
            self.logger.warning(f"PR body sanitization issues: {body_issues}")
        
        pr = await self.github_client.create_pull_request(
            title=sanitized_title,
            body=sanitized_body,
            head_branch=self.context.branch_name,
            base_branch="main",
            fork_owner=fork_owner
        )
        
        if not pr:
            raise RuntimeError("Failed to create pull request")
        
        self.context.pr_number = pr.number
        self.logger.info(f"Pull request created: #{pr.number}")
    
    async def _monitor_progress(self):
        """Monitor CI tests and review comments."""
        self.logger.info(f"Monitoring PR #{self.context.pr_number}")
        
        # Update last check time
        self.context.last_check_time = datetime.now()
        
        # Get latest test results (limited to avoid context overflow)
        try:
            failing_tests = await self.pytorch_hud_client.get_failing_tests(
                self.context.pr_number, 
                max_errors=self.config.agent.max_errors_per_batch
            )
            # Convert TestResult objects to serializable dictionaries
            self.context.failing_tests = []
            for test in failing_tests:
                test_dict = test.__dict__.copy()
                # Convert TestStatus enum to string
                if hasattr(test_dict.get('status'), 'value'):
                    test_dict['status'] = test_dict['status'].value
                self.context.failing_tests.append(test_dict)
        except Exception as e:
            self.logger.warning(f"Failed to get failing tests from PyTorch HUD: {e}")
            self.context.failing_tests = []  # Continue without failing tests data
        
        # Get review comments
        comments = await self.github_client.get_pr_comments(self.context.pr_number)
        # Filter for unaddressed comments (this is simplified)
        self.context.review_comments = [comment.__dict__ for comment in comments]
        
        self.logger.info(f"Found {len(self.context.failing_tests)} failing tests, "
                        f"{len(self.context.review_comments)} review comments")
    
    async def _address_reviews(self):
        """Address review comments and failing tests using Claude CLI."""
        self.logger.info("Addressing reviews and failing tests")
        
        self.context.fix_attempt_count += 1
        
        # Ensure we're on the correct branch for the PR
        if self.git_ops and self.context.branch_name:
            current_branch = self.git_ops.get_current_branch()
            if current_branch != self.context.branch_name:
                self.logger.info(f"Switching from {current_branch} to {self.context.branch_name}")
                # Try to fetch the branch from origin first
                self.git_ops._run_git_command(["fetch", "origin", f"{self.context.branch_name}:{self.context.branch_name}"])
                if not self.git_ops.checkout_branch(self.context.branch_name):
                    raise RuntimeError(f"Failed to checkout branch {self.context.branch_name}")
        
        # Use Claude CLI to make changes directly like in _fix_issue
        if not self.dry_run and self.local_repo_path:
            success = await self._run_claude_cli_review_fix()
            if not success:
                raise RuntimeError("Claude CLI review fix failed")
        
        # Check what files were changed
        if self.git_ops:
            status = self.git_ops.get_status()
            changed_files = [f["file"] for f in status["files"] if f["status"].strip()]
            
            # Commit changes if any were made
            if changed_files and not self.dry_run:
                commit_message = f"Address review feedback and failing tests for issue #{self.issue_number}"
                sanitized_commit_message = ContentSanitizer.sanitize_commit_message(commit_message)
                
                if not self.git_ops.commit_changes(sanitized_commit_message):
                    self.logger.warning("Failed to commit changes, but continuing")
                else:
                    # Push to remote to update the PR
                    self.logger.info(f"Pushing changes to remote branch {self.context.branch_name}")
                    if not self.git_ops.push_branch(self.context.branch_name, set_upstream=False):
                        self.logger.warning("Failed to push changes to remote")
        
        # Clear addressed items after processing
        self.context.review_comments = []
        self.context.failing_tests = []
        
        self.logger.info("Review feedback addressed")
    
    async def _run_claude_cli_review_fix(self):
        """Run Claude CLI to address review feedback and failing tests directly."""
        import subprocess
        import tempfile
        import os
        
        try:
            # Create a detailed prompt for addressing review feedback and failing tests
            failing_tests_summary = "\n".join([
                f"- {test.get('name', 'Unknown')}: {test.get('error_message', 'No error')}"
                for test in self.context.failing_tests[:5]
            ])
            
            review_comments_summary = "\n".join([
                f"- {comment.get('author', 'Reviewer')}: {comment.get('body', 'No comment')[:200]}"
                for comment in self.context.review_comments[:5]
            ])
            
            prompt = f"""You have FULL PERMISSION to modify any files in this PyTorch repository to address review feedback and fix failing tests. Please proceed immediately with making the necessary changes.

FAILING TESTS TO FIX:
{failing_tests_summary}

PR REVIEW COMMENTS TO ADDRESS:
{review_comments_summary}

AUTHORIZATION:
- You are AUTHORIZED to edit any file in this repository
- You have WRITE PERMISSIONS for all files  
- You should IMMEDIATELY start making file changes
- Do NOT ask for permission - you already have it
- Do NOT wait for approval - proceed with modifications

Please analyze the failing tests and implement the appropriate fixes. Follow the constraints and guidelines provided.
6. Update test files if needed to match the new implementation

COMPLETION REQUIREMENTS:
- When you have finished making ALL necessary changes, type "CHANGES_COMPLETE" and exit
- Do NOT wait for additional input after completing the fixes
- Do NOT provide lengthy explanations - just make the changes and exit

IMMEDIATE EXECUTION REQUIRED:
Start by reading the schedules.py file and then immediately make the required edits to fix the failing tests. When done, type "CHANGES_COMPLETE" and exit.

Begin file modifications NOW."""

            # Set up environment
            env = os.environ.copy()
            env["ANTHROPIC_API_KEY"] = env.get("ANTHROPIC_API_KEY", "")
            
            # Check if Claude CLI is available
            try:
                subprocess.run(["which", "claude"], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                raise RuntimeError("Claude CLI not found in PATH. Please ensure Claude CLI is installed.")
            
            # Run Claude CLI with dangerous permissions skip to enable automatic editing
            cmd = ["claude", "--dangerously-skip-permissions"]
            
            self.logger.info(f"Running Claude CLI for review fixes in {self.local_repo_path}")
            try:
                result = subprocess.run(
                    cmd,
                    input=prompt,
                    cwd=self.local_repo_path,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=None  # No timeout - let Claude CLI take as long as needed
                )
            except subprocess.TimeoutExpired as e:
                self.logger.warning(f"Claude CLI timed out after {e.timeout}s, killing any remaining processes...")
                # Kill any remaining Claude processes
                try:
                    subprocess.run(["pkill", "-f", "claude"], timeout=5)
                except:
                    pass
                # Check if changes were made even though it timed out
                return True  # Let the calling code check for changes
            
            if result.returncode == 0:
                self.logger.info("Claude CLI review fix completed successfully")
                if result.stdout:
                    self.logger.info(f"Claude CLI output: {result.stdout}")
                if result.stderr:
                    self.logger.warning(f"Claude CLI stderr: {result.stderr}")
                return True
            else:
                self.logger.error(f"Claude CLI review fix failed with return code {result.returncode}")
                if result.stderr:
                    self.logger.error(f"Claude CLI error: {result.stderr}")
                if result.stdout:
                    self.logger.error(f"Claude CLI stdout: {result.stdout}")
                return False
                
        except subprocess.TimeoutExpired as e:
            self.logger.error(f"Claude CLI review fix timed out after {e.timeout}s")
            # Kill any remaining Claude processes
            try:
                subprocess.run(["pkill", "-f", "claude"], timeout=5)
            except:
                pass
            return False
        except Exception as e:
            self.logger.error(f"Failed to run Claude CLI review fix: {e}")
            return False
    
    def _validate_and_cleanup_files(self, changed_files: List[str]) -> List[str]:
        """Validate and clean up files to remove unwanted test files."""
        validated_files = []
        unwanted_patterns = [
            r'test_.*\.py$',
            r'.*_test\.py$', 
            r'.*/test/.*\.py$',
            r'.*test.*\.py$',
            r'.*example.*\.py$',
            r'.*demo.*\.py$',
            r'.*standalone.*\.py$',
            r'.*usage.*\.py$',
            r'.*rope.*\.py$',
            r'.*basic.*\.py$',
            r'.*validation.*\.py$'
        ]
        
        for file_path in changed_files:
            is_unwanted = False
            
            # Check against unwanted patterns
            for pattern in unwanted_patterns:
                if re.match(pattern, file_path, re.IGNORECASE):
                    is_unwanted = True
                    self.logger.warning(f"Removing unwanted file: {file_path}")
                    
                    # Remove the file if it exists and not in dry run
                    if not self.dry_run and self.git_ops:
                        try:
                            file_full_path = os.path.join(self.local_repo_path, file_path)
                            if os.path.exists(file_full_path):
                                os.remove(file_full_path)
                                self.logger.info(f"Deleted unwanted file: {file_path}")
                            
                            # Remove from git tracking
                            self.git_ops._run_git_command(["rm", "--cached", file_path])
                        except Exception as e:
                            self.logger.warning(f"Failed to remove unwanted file {file_path}: {e}")
                    break
            
            if not is_unwanted:
                validated_files.append(file_path)
        
        removed_count = len(changed_files) - len(validated_files)
        if removed_count > 0:
            self.logger.info(f"Removed {removed_count} unwanted files, kept {len(validated_files)} valid files")
        
        return validated_files
