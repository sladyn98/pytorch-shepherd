"""Prompt templates for Claude interactions."""

ISSUE_ANALYSIS_PROMPT = """
You are an expert PyTorch contributor analyzing a GitHub issue. Analyze this issue thoroughly and provide structured insights.

ISSUE DATA:
Title: {title}
Body: {body}
Labels: {labels}
Author: {author}
Comments: {comments_summary}

ANALYSIS TASKS:
1. Identify the core problem and root cause
2. Determine issue category (bug, feature request, performance, documentation, etc.)
3. Assess complexity and estimated effort
4. Identify relevant PyTorch components/modules
5. Generate search terms for finding related code
6. Suggest initial approach for fixing

Provide your analysis in this JSON format:
{{
    "problem_summary": "Brief description of the core issue",
    "category": "bug|feature|performance|docs|other",
    "complexity": "low|medium|high",
    "estimated_effort": "1-2 hours|half day|1-2 days|1+ weeks",
    "components": ["list", "of", "pytorch", "components"],
    "search_terms": ["code", "search", "terms"],
    "approach": "High-level approach for fixing",
    "prerequisites": ["any", "prerequisites", "or", "dependencies"],
    "risks": ["potential", "risks", "or", "challenges"]
}}
"""

PR_DESCRIPTION_PROMPT = """
Generate a comprehensive pull request description for a PyTorch issue fix.

ISSUE CONTEXT:
Title: {issue_title}
Number: #{issue_number}
Problem: {problem_summary}

FIX SUMMARY:
{fix_summary}

FILES CHANGED:
{files_changed}

Generate a pull request with:
1. Clear, descriptive title (NO AI/Claude references)
2. Comprehensive description explaining the fix (NO AI/Claude references)
3. Testing approach and coverage
4. Any breaking changes or migration notes
5. Performance implications if any
6. Must include "Fixes #{issue_number}" in the description

IMPORTANT: Do NOT include any references to AI, Claude, Anthropic, LLM, or AI assistance in the title or description. Write as if a human developer created this fix.

Provide response in this JSON format:
{{
    "title": "PR title following PyTorch conventions (no AI references)",
    "body": "Comprehensive PR description in markdown format with 'Fixes #{issue_number}'"
}}

The PR description should include:
- ## Summary section
- ## Changes section  
- ## Testing section
- ## Checklist section
- "Fixes #{issue_number}" reference
- Links to related issues/PRs if applicable
"""


def format_issue_analysis_prompt(issue_data: dict, comments: list = None) -> str:
    """Format the issue analysis prompt."""
    comments_summary = ""
    if comments:
        comments_summary = "\n".join([
            f"- {comment.get('author', 'Unknown')}: {comment.get('body', '')[:200]}..."
            for comment in comments[:5]  # Limit to first 5 comments
        ])
    
    # Handle both nested issue data and direct issue data
    if "issue" in issue_data:
        actual_issue = issue_data["issue"]
    else:
        actual_issue = issue_data
    
    # Extract labels properly
    labels = actual_issue.get("labels", [])
    if isinstance(labels, list) and labels and isinstance(labels[0], dict):
        label_names = [label.get("name", "") for label in labels]
    else:
        label_names = labels if isinstance(labels, list) else []
    
    return ISSUE_ANALYSIS_PROMPT.format(
        title=actual_issue.get("title", "No title"),
        body=actual_issue.get("body", "No description")[:1000],  # Limit body length
        labels=", ".join(label_names),
        author=actual_issue.get("author", "Unknown"),
        comments_summary=comments_summary
    )


def format_pr_description_prompt(issue_data: dict, fix_summary: dict, files_changed: list) -> str:
    """Format the PR description prompt."""
    # Handle both nested issue data and direct issue data
    if "issue" in issue_data:
        actual_issue = issue_data["issue"]
    else:
        actual_issue = issue_data
    
    files_list = "\n".join([f"- {file}" for file in files_changed]) if files_changed else "- No files specified"
    
    return PR_DESCRIPTION_PROMPT.format(
        issue_title=actual_issue.get("title", "Unknown issue"),
        issue_number=actual_issue.get("number", "unknown"),
        problem_summary=fix_summary.get("problem_summary", "Fix for PyTorch issue"),
        fix_summary=fix_summary.get("approach", "Automated fix applied"),
        files_changed=files_list
    )