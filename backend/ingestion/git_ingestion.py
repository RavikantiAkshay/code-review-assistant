"""
Git Repository Ingestion Module

Clones repositories from GitHub/GitLab URLs and indexes files by language.
"""

import os
import re
import tempfile
import shutil
from typing import Dict, List, Tuple, Optional
from git import Repo, GitCommandError
from git.exc import InvalidGitRepositoryError


# Supported languages by extension
LANGUAGE_EXTENSIONS = {
    "python": [".py"],
    "javascript": [".js", ".jsx"],
    "typescript": [".ts", ".tsx"],
    "java": [".java"],
    "c_cpp": [".c", ".cpp", ".h", ".hpp"],
    "html": [".html", ".htm"],
    "css": [".css"],
}

# Directories to ignore during file indexing
IGNORE_DIRS = {".git", "node_modules", "venv", "__pycache__", ".venv", "dist", "build"}

# Maximum file size to process (200KB)
MAX_FILE_SIZE = 200 * 1024


def validate_git_url(url: str) -> bool:
    """
    Validate that the URL looks like a valid Git repository URL.
    Supports GitHub, GitLab, and Bitbucket HTTPS URLs.
    """
    patterns = [
        r"^https://github\.com/[\w\-]+/[\w\-\.]+(?:\.git)?$",
        r"^https://gitlab\.com/[\w\-]+/[\w\-\.]+(?:\.git)?$",
        r"^https://bitbucket\.org/[\w\-]+/[\w\-\.]+(?:\.git)?$",
        r"^git@github\.com:[\w\-]+/[\w\-\.]+\.git$",
        r"^git@gitlab\.com:[\w\-]+/[\w\-\.]+\.git$",
    ]
    return any(re.match(pattern, url) for pattern in patterns)


def clone_repository(
    repo_url: str,
    branch: Optional[str] = None,
    depth: int = 1,
) -> Tuple[str, Dict]:
    """
    Clone a Git repository to a temporary directory.

    Args:
        repo_url: HTTPS URL of the repository
        branch: Optional branch name (defaults to default branch)
        depth: Clone depth (shallow clone by default)

    Returns:
        Tuple of (temp_dir_path, metadata_dict)

    Raises:
        ValueError: If URL is invalid
        RuntimeError: If cloning fails
    """
    if not validate_git_url(repo_url):
        raise ValueError(f"Invalid Git URL: {repo_url}")

    temp_dir = tempfile.mkdtemp(prefix="code_review_")

    try:
        clone_kwargs = {
            "depth": depth,
        }
        if branch:
            clone_kwargs["branch"] = branch

        repo = Repo.clone_from(repo_url, temp_dir, **clone_kwargs)

        # Get repository metadata
        metadata = {
            "url": repo_url,
            "branch": repo.active_branch.name if repo.heads else "main",
            "commit": repo.head.commit.hexsha[:8] if repo.head.is_valid() else None,
            "temp_dir": temp_dir,
        }

        return temp_dir, metadata

    except GitCommandError as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"Failed to clone repository: {e}")
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"Unexpected error during cloning: {e}")


def index_files_by_language(file_list: List[str]) -> Dict[str, List[str]]:
    """
    Group files by programming language based on extension.

    Args:
        file_list: List of file paths

    Returns:
        Dictionary mapping language to list of file paths
    """
    indexed = {lang: [] for lang in LANGUAGE_EXTENSIONS}

    for f in file_list:
        ext = os.path.splitext(f)[1].lower()
        for lang, exts in LANGUAGE_EXTENSIONS.items():
            if ext in exts:
                indexed[lang].append(f)
                break

    return indexed


def scan_repository(repo_path: str) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    Scan a repository directory and return all processable files.

    Args:
        repo_path: Path to the repository root

    Returns:
        Tuple of (all_files_list, indexed_by_language_dict)
    """
    all_files = []

    for root, dirs, files in os.walk(repo_path):
        # Remove ignored directories from traversal
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for name in files:
            file_path = os.path.join(root, name)

            # Skip large files
            try:
                if os.path.getsize(file_path) > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue

            # Get path relative to repo root
            rel_path = os.path.relpath(file_path, repo_path)
            # Normalize to forward slashes
            rel_path = rel_path.replace("\\", "/")
            all_files.append(rel_path)

    indexed = index_files_by_language(all_files)

    return all_files, indexed


def cleanup_repository(temp_dir: str) -> None:
    """
    Clean up a cloned repository directory.

    Args:
        temp_dir: Path to the temporary directory to remove
    """
    if temp_dir and os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
