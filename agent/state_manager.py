"""State management and persistence for the PyTorch Issue Fixing Agent."""

import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from .workflow import IssueState, WorkflowContext


@dataclass
class AgentState:
    """Complete agent state for persistence."""
    issue_number: int
    repo: str
    current_state: IssueState
    context: WorkflowContext
    created_at: datetime
    updated_at: datetime
    version: str = "1.0.0"


class StateManager:
    """Manages agent state persistence and recovery."""
    
    def __init__(self, state_file: str = "agent_state.json", backup_interval: int = 300):
        self.state_file = Path(state_file)
        self.backup_interval = backup_interval
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._current_state: Optional[AgentState] = None
        self._backup_timer: Optional[threading.Timer] = None
        
        # Ensure state directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
    
    def save_state(self, state: AgentState) -> bool:
        """Save agent state to disk."""
        with self._lock:
            try:
                state.updated_at = datetime.now()
                self._current_state = state
                
                # Convert to serializable format
                state_dict = {
                    "issue_number": state.issue_number,
                    "repo": state.repo,
                    "current_state": state.current_state.value,
                    "context": self._serialize_context(state.context),
                    "created_at": state.created_at.isoformat(),
                    "updated_at": state.updated_at.isoformat(),
                    "version": state.version
                }
                
                # Atomic write using temporary file
                temp_file = self.state_file.with_suffix('.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(state_dict, f, indent=2)
                
                # Atomic rename
                temp_file.rename(self.state_file)
                
                self.logger.debug(f"State saved to {self.state_file}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to save state: {e}")
                return False
    
    def load_state(self) -> Optional[AgentState]:
        """Load agent state from disk."""
        with self._lock:
            try:
                if not self.state_file.exists():
                    self.logger.info("No existing state file found")
                    return None
                
                with open(self.state_file, 'r') as f:
                    state_dict = json.load(f)
                
                # Validate version compatibility
                if state_dict.get("version", "1.0.0") != "1.0.0":
                    self.logger.warning("State file version mismatch, may need migration")
                
                # Deserialize state
                context = self._deserialize_context(state_dict["context"])
                
                state = AgentState(
                    issue_number=state_dict["issue_number"],
                    repo=state_dict["repo"],
                    current_state=IssueState(state_dict["current_state"]),
                    context=context,
                    created_at=datetime.fromisoformat(state_dict["created_at"]),
                    updated_at=datetime.fromisoformat(state_dict["updated_at"])
                )
                
                self._current_state = state
                self.logger.info(f"State loaded from {self.state_file}")
                return state
                
            except Exception as e:
                self.logger.error(f"Failed to load state: {e}")
                return None
    
    def get_current_state(self) -> Optional[AgentState]:
        """Get the current in-memory state."""
        with self._lock:
            return self._current_state
    
    def clear_state(self) -> bool:
        """Clear persisted state."""
        with self._lock:
            try:
                if self.state_file.exists():
                    self.state_file.unlink()
                self._current_state = None
                self.logger.info("State cleared")
                return True
            except Exception as e:
                self.logger.error(f"Failed to clear state: {e}")
                return False
    
    def backup_state(self) -> bool:
        """Create a backup of current state."""
        with self._lock:
            try:
                if not self.state_file.exists():
                    return True
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = self.state_file.with_suffix(f'.backup_{timestamp}.json')
                
                # Copy current state file to backup
                backup_file.write_text(self.state_file.read_text())
                
                self.logger.debug(f"State backed up to {backup_file}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to backup state: {e}")
                return False
    
    def start_auto_backup(self):
        """Start automatic backup timer."""
        if self.backup_interval > 0:
            self._schedule_backup()
    
    def stop_auto_backup(self):
        """Stop automatic backup timer."""
        if self._backup_timer:
            self._backup_timer.cancel()
            self._backup_timer = None
    
    def _schedule_backup(self):
        """Schedule next backup."""
        if self._backup_timer:
            self._backup_timer.cancel()
        
        self._backup_timer = threading.Timer(self.backup_interval, self._perform_backup)
        self._backup_timer.daemon = True
        self._backup_timer.start()
    
    def _perform_backup(self):
        """Perform scheduled backup."""
        self.backup_state()
        self._schedule_backup()  # Schedule next backup
    
    def _serialize_context(self, context: WorkflowContext) -> Dict[str, Any]:
        """Serialize workflow context to JSON-compatible format."""
        return {
            "issue_number": context.issue_number,
            "repo": context.repo,
            "issue_data": context.issue_data,
            "pr_number": context.pr_number,
            "branch_name": context.branch_name,
            "fix_attempt_count": context.fix_attempt_count,
            "last_check_time": context.last_check_time.isoformat() if context.last_check_time else None,
            "failing_tests": context.failing_tests,
            "review_comments": context.review_comments,
            "generated_files": context.generated_files,
            "error_history": context.error_history,
            "metadata": context.metadata
        }
    
    def _deserialize_context(self, data: Dict[str, Any]) -> WorkflowContext:
        """Deserialize workflow context from JSON data."""
        return WorkflowContext(
            issue_number=data["issue_number"],
            repo=data["repo"],
            issue_data=data.get("issue_data"),
            pr_number=data.get("pr_number"),
            branch_name=data.get("branch_name"),
            fix_attempt_count=data.get("fix_attempt_count", 0),
            last_check_time=datetime.fromisoformat(data["last_check_time"]) if data.get("last_check_time") else None,
            failing_tests=data.get("failing_tests", []),
            review_comments=data.get("review_comments", []),
            generated_files=data.get("generated_files", []),
            error_history=data.get("error_history", []),
            metadata=data.get("metadata", {})
        )
    
    def __enter__(self):
        """Context manager entry."""
        self.start_auto_backup()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_auto_backup()
        if self._current_state:
            self.backup_state()