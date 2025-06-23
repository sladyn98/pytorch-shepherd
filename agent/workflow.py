"""Workflow state machine for the PyTorch Issue Fixing Agent."""

import logging
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta


class IssueState(Enum):
    """States in the issue fixing workflow."""
    FETCHING = "fetching"
    ANALYZING = "analyzing"
    FIXING = "fixing"
    CREATING_PR = "creating_pr"
    MONITORING = "monitoring"
    ADDRESSING_REVIEWS = "addressing_reviews"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class WorkflowContext:
    """Context data for workflow execution."""
    issue_number: int
    repo: str
    issue_data: Optional[Dict[str, Any]] = None
    pr_number: Optional[int] = None
    branch_name: Optional[str] = None
    fix_attempt_count: int = 0
    last_check_time: Optional[datetime] = None
    failing_tests: List[Dict[str, Any]] = field(default_factory=list)
    review_comments: List[Dict[str, Any]] = field(default_factory=list)
    generated_files: List[str] = field(default_factory=list)
    error_history: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowTransition:
    """Represents a state transition in the workflow."""
    
    def __init__(self, from_state: IssueState, to_state: IssueState, condition_fn=None):
        self.from_state = from_state
        self.to_state = to_state
        self.condition_fn = condition_fn or (lambda ctx: True)
    
    def can_transition(self, context: WorkflowContext) -> bool:
        """Check if transition is allowed."""
        return self.condition_fn(context)


class WorkflowEngine:
    """State machine engine for issue fixing workflow."""
    
    def __init__(self, max_attempts: int = 3, monitoring_interval: int = 18000):
        self.max_attempts = max_attempts
        self.monitoring_interval = monitoring_interval  # 5 hours in seconds
        self.logger = logging.getLogger(__name__)
        
        # Define state transitions
        self.transitions = {
            IssueState.FETCHING: [
                WorkflowTransition(IssueState.FETCHING, IssueState.ANALYZING),
                WorkflowTransition(IssueState.FETCHING, IssueState.FAILED)
            ],
            IssueState.ANALYZING: [
                WorkflowTransition(IssueState.ANALYZING, IssueState.FIXING),
                WorkflowTransition(IssueState.ANALYZING, IssueState.FAILED)
            ],
            IssueState.FIXING: [
                WorkflowTransition(IssueState.FIXING, IssueState.CREATING_PR),
                WorkflowTransition(
                    IssueState.FIXING,
                    IssueState.FAILED,
                    lambda ctx: ctx.fix_attempt_count >= self.max_attempts
                ),
                WorkflowTransition(IssueState.FIXING, IssueState.FIXING)  # Retry
            ],
            IssueState.CREATING_PR: [
                WorkflowTransition(IssueState.CREATING_PR, IssueState.MONITORING),
                WorkflowTransition(IssueState.CREATING_PR, IssueState.FAILED)
            ],
            IssueState.MONITORING: [
                WorkflowTransition(
                    IssueState.MONITORING,
                    IssueState.ADDRESSING_REVIEWS,
                    self._has_review_comments
                ),
                WorkflowTransition(
                    IssueState.MONITORING,
                    IssueState.ADDRESSING_REVIEWS,
                    self._has_failing_tests
                ),
                WorkflowTransition(
                    IssueState.MONITORING,
                    IssueState.COMPLETED,
                    self._is_ready_for_completion
                ),
                WorkflowTransition(IssueState.MONITORING, IssueState.MONITORING)  # Continue monitoring
            ],
            IssueState.ADDRESSING_REVIEWS: [
                WorkflowTransition(IssueState.ADDRESSING_REVIEWS, IssueState.MONITORING),
                WorkflowTransition(
                    IssueState.ADDRESSING_REVIEWS,
                    IssueState.FAILED,
                    lambda ctx: ctx.fix_attempt_count >= self.max_attempts
                )
            ],
            IssueState.COMPLETED: [],  # Terminal state
            IssueState.FAILED: [],     # Terminal state
            IssueState.PAUSED: [       # Can resume from pause
                WorkflowTransition(IssueState.PAUSED, IssueState.FETCHING),
                WorkflowTransition(IssueState.PAUSED, IssueState.ANALYZING),
                WorkflowTransition(IssueState.PAUSED, IssueState.FIXING),
                WorkflowTransition(IssueState.PAUSED, IssueState.MONITORING),
                WorkflowTransition(IssueState.PAUSED, IssueState.ADDRESSING_REVIEWS)
            ]
        }
    
    def get_valid_transitions(self, current_state: IssueState, context: WorkflowContext) -> List[IssueState]:
        """Get valid next states from current state."""
        valid_states = []
        
        if current_state in self.transitions:
            for transition in self.transitions[current_state]:
                if transition.can_transition(context):
                    valid_states.append(transition.to_state)
        
        return valid_states
    
    def can_transition_to(self, current_state: IssueState, target_state: IssueState, context: WorkflowContext) -> bool:
        """Check if we can transition from current to target state."""
        return target_state in self.get_valid_transitions(current_state, context)
    
    def get_next_state(self, current_state: IssueState, context: WorkflowContext) -> Optional[IssueState]:
        """Get the next state based on current state and context."""
        valid_transitions = self.get_valid_transitions(current_state, context)
        
        if not valid_transitions:
            return None
        
        # State-specific logic for choosing next state
        if current_state == IssueState.MONITORING:
            # Check if we should address reviews/tests or complete
            if self._has_review_comments(context) or self._has_failing_tests(context):
                return IssueState.ADDRESSING_REVIEWS
            elif self._is_ready_for_completion(context):
                return IssueState.COMPLETED
            else:
                # Continue monitoring if not enough time has passed
                if self._should_continue_monitoring(context):
                    return IssueState.MONITORING
                else:
                    return IssueState.COMPLETED
        
        elif current_state == IssueState.FIXING:
            if context.fix_attempt_count >= self.max_attempts:
                return IssueState.FAILED
            elif context.pr_number is None:
                return IssueState.CREATING_PR  # Only create PR if none exists
            else:
                return IssueState.MONITORING   # Go back to monitoring existing PR
        
        elif current_state == IssueState.ADDRESSING_REVIEWS:
            if context.fix_attempt_count >= self.max_attempts:
                return IssueState.FAILED
            else:
                return IssueState.MONITORING
        
        # Default to first valid transition
        return valid_transitions[0]
    
    def should_wait_before_next_check(self, context: WorkflowContext) -> bool:
        """Check if we should wait before next monitoring check."""
        if not context.last_check_time:
            return False
        
        next_check_time = context.last_check_time + timedelta(seconds=self.monitoring_interval)
        return datetime.now() < next_check_time
    
    def get_time_until_next_check(self, context: WorkflowContext) -> Optional[int]:
        """Get seconds until next monitoring check."""
        if not context.last_check_time:
            return 0
        
        next_check_time = context.last_check_time + timedelta(seconds=self.monitoring_interval)
        time_remaining = (next_check_time - datetime.now()).total_seconds()
        
        return max(0, int(time_remaining))
    
    def is_terminal_state(self, state: IssueState) -> bool:
        """Check if state is terminal (no more transitions)."""
        return state in [IssueState.COMPLETED, IssueState.FAILED]
    
    def _has_review_comments(self, context: WorkflowContext) -> bool:
        """Check if there are unaddressed review comments."""
        return len(context.review_comments) > 0
    
    def _has_failing_tests(self, context: WorkflowContext) -> bool:
        """Check if there are failing tests."""
        return len(context.failing_tests) > 0
    
    def _is_ready_for_completion(self, context: WorkflowContext) -> bool:
        """Check if issue is ready for completion."""
        # Ready if no failing tests and no review comments
        return (
            len(context.failing_tests) == 0 and
            len(context.review_comments) == 0 and
            context.pr_number is not None
        )
    
    def _should_continue_monitoring(self, context: WorkflowContext) -> bool:
        """Check if we should continue monitoring."""
        if not context.last_check_time:
            return True
        
        # Continue monitoring if not enough time has passed
        time_since_last_check = datetime.now() - context.last_check_time
        return time_since_last_check.total_seconds() < self.monitoring_interval
    
    def log_state_transition(self, old_state: IssueState, new_state: IssueState, context: WorkflowContext):
        """Log state transition for debugging."""
        self.logger.info(
            f"State transition: {old_state.value} -> {new_state.value} "
            f"(issue #{context.issue_number}, attempt {context.fix_attempt_count})"
        )
        
        # Log relevant context
        if new_state == IssueState.ADDRESSING_REVIEWS:
            self.logger.info(f"Review comments: {len(context.review_comments)}, "
                           f"Failing tests: {len(context.failing_tests)}")
        elif new_state == IssueState.FAILED:
            self.logger.warning(f"Issue failed after {context.fix_attempt_count} attempts")
            if context.error_history:
                self.logger.warning(f"Error history: {context.error_history[-3:]}")  # Last 3 errors