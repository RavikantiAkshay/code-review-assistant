"""
Export module for Code Review Assistant

Provides functionality to export review results in various formats:
- GitHub PR comment JSON format
- Unified diff patch files for autofix
"""

import json
from typing import List, Dict, Any
from datetime import datetime


def export_github_pr_comments(
    ranked_issues: List[Dict[str, Any]],
    repo_owner: str = "owner",
    repo_name: str = "repo",
    pull_number: int = 1,
    commit_sha: str = "HEAD"
) -> Dict[str, Any]:
    """
    Export review results as GitHub PR review comments format.
    
    This generates JSON compatible with GitHub's Pull Request Review API:
    https://docs.github.com/en/rest/pulls/reviews
    
    Args:
        ranked_issues: List of issues from the review
        repo_owner: GitHub repository owner
        repo_name: GitHub repository name
        pull_number: Pull request number
        commit_sha: Commit SHA to attach comments to
        
    Returns:
        Dict with GitHub PR review format
    """
    comments = []
    
    for issue in ranked_issues:
        # Build the comment body
        severity_emoji = {
            "high": "🔴",
            "medium": "🟡",
            "low": "🟢"
        }.get(issue.get("severity", "low"), "⚪")
        
        body_parts = [
            f"{severity_emoji} **{issue.get('severity', 'unknown').upper()}** - {issue.get('category', 'unknown').capitalize()}",
            "",
            issue.get("message", "No description"),
        ]
        
        # Add snippet if available
        if issue.get("snippet"):
            body_parts.extend([
                "",
                "**Problematic code:**",
                "```",
                issue.get("snippet", ""),
                "```"
            ])
        
        # Add fix suggestion if available
        if issue.get("fix"):
            body_parts.extend([
                "",
                "**Suggested fix:**",
                "```",
                issue.get("fix", ""),
                "```"
            ])
        
        # Add rule link if available
        if issue.get("rule") and issue["rule"].get("link"):
            body_parts.extend([
                "",
                f"📖 [Rule Documentation]({issue['rule']['link']})"
            ])
        
        comment = {
            "path": issue.get("file", "unknown"),
            "line": issue.get("line", 1),
            "body": "\n".join(body_parts)
        }
        
        # Add side for diff view (RIGHT = new code)
        comment["side"] = "RIGHT"
        
        comments.append(comment)
    
    # Build the full PR review payload
    review_payload = {
        "owner": repo_owner,
        "repo": repo_name,
        "pull_number": pull_number,
        "commit_id": commit_sha,
        "event": "COMMENT",  # or "REQUEST_CHANGES" for blocking review
        "body": f"## Code Review Assistant Report\n\nFound **{len(ranked_issues)}** issues.\n\nGenerated at {datetime.now().isoformat()}",
        "comments": comments
    }
    
    return review_payload


def export_github_pr_comments_json(
    ranked_issues: List[Dict[str, Any]],
    output_path: str = None,
    **kwargs
) -> str:
    """
    Export review results as GitHub PR comments JSON file.
    
    Args:
        ranked_issues: List of issues from the review
        output_path: Optional path to save JSON file
        **kwargs: Additional arguments for export_github_pr_comments
        
    Returns:
        JSON string
    """
    payload = export_github_pr_comments(ranked_issues, **kwargs)
    json_str = json.dumps(payload, indent=2)
    
    if output_path:
        with open(output_path, "w") as f:
            f.write(json_str)
    
    return json_str


def generate_unified_diff(
    file_path: str,
    original_content: str,
    issue: Dict[str, Any]
) -> str:
    """
    Generate a unified diff patch for a single issue fix.
    
    Args:
        file_path: Path to the file
        original_content: Original file content
        issue: Issue dict with 'line', 'snippet', and 'fix'
        
    Returns:
        Unified diff string
    """
    if not issue.get("fix") or not issue.get("snippet"):
        return ""
    
    line_num = issue.get("line", 1)
    snippet = issue.get("snippet", "").strip()
    fix = issue.get("fix", "").strip()
    
    # Build unified diff header
    lines = [
        f"--- a/{file_path}",
        f"+++ b/{file_path}",
        f"@@ -{line_num},1 +{line_num},1 @@"
    ]
    
    # Add the change
    for old_line in snippet.split("\n"):
        lines.append(f"-{old_line}")
    for new_line in fix.split("\n"):
        lines.append(f"+{new_line}")
    
    return "\n".join(lines)


def generate_patch_file(
    ranked_issues: List[Dict[str, Any]],
    file_contents: Dict[str, str] = None
) -> str:
    """
    Generate a unified diff patch file for all fixable issues.
    
    Args:
        ranked_issues: List of issues from the review
        file_contents: Optional dict mapping file paths to their content
        
    Returns:
        Combined unified diff string
    """
    patches = []
    
    # Group issues by file
    issues_by_file: Dict[str, List[Dict]] = {}
    for issue in ranked_issues:
        if issue.get("fix") and issue.get("snippet"):
            file_path = issue.get("file", "unknown")
            if file_path not in issues_by_file:
                issues_by_file[file_path] = []
            issues_by_file[file_path].append(issue)
    
    # Sort issues by line number (descending to avoid offset issues)
    for file_path, file_issues in issues_by_file.items():
        file_issues.sort(key=lambda x: x.get("line", 0), reverse=True)
        
        # Generate header for this file
        patches.append(f"diff --git a/{file_path} b/{file_path}")
        patches.append(f"--- a/{file_path}")
        patches.append(f"+++ b/{file_path}")
        
        for issue in file_issues:
            line_num = issue.get("line", 1)
            snippet = issue.get("snippet", "").strip()
            fix = issue.get("fix", "").strip()
            
            snippet_lines = snippet.split("\n")
            fix_lines = fix.split("\n")
            
            # Hunk header
            patches.append(f"@@ -{line_num},{len(snippet_lines)} +{line_num},{len(fix_lines)} @@ {issue.get('message', '')[:50]}")
            
            # Old lines
            for line in snippet_lines:
                patches.append(f"-{line}")
            
            # New lines
            for line in fix_lines:
                patches.append(f"+{line}")
        
        patches.append("")  # Empty line between files
    
    return "\n".join(patches)


def save_patch_file(
    ranked_issues: List[Dict[str, Any]],
    output_path: str = "autofix.patch"
) -> str:
    """
    Generate and save a patch file for autofix.
    
    Args:
        ranked_issues: List of issues from the review
        output_path: Path to save the patch file
        
    Returns:
        Path to the saved file
    """
    patch_content = generate_patch_file(ranked_issues)
    
    if patch_content.strip():
        with open(output_path, "w") as f:
            f.write(patch_content)
        return output_path
    
    return ""
