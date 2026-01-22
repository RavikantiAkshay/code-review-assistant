from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict
import zipfile
import os
import tempfile

from backend.ingestion.git_ingestion import (
    clone_repository,
    scan_repository,
    cleanup_repository,
    validate_git_url,
)

# Define file size limit
MAX_FILE_SIZE = 200 * 1024

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


def index_files_by_language(file_list: List[str]) -> Dict[str, List[str]]:
    """Group files by language based on extension."""
    indexed = {lang: [] for lang in LANGUAGE_EXTENSIONS}

    for f in file_list:
        ext = os.path.splitext(f)[1].lower()
        for lang, exts in LANGUAGE_EXTENSIONS.items():
            if ext in exts:
                indexed[lang].append(f)
                break
    return indexed


# Pydantic models
class CloneRepoRequest(BaseModel):
    repo_url: str
    branch: Optional[str] = None


class CloneRepoResponse(BaseModel):
    temp_dir: str
    files: List[str]
    indexed_files: Dict[str, List[str]]
    metadata: Dict


class UploadResponse(BaseModel):
    temp_dir: str
    files: List[str]
    indexed_files: Dict[str, List[str]]


# Initialize FastAPI app
app = FastAPI(
    title="Code Review Assistant",
    description="AI-powered code review with static analysis and LLM insights",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/clone-repo/", response_model=CloneRepoResponse)
async def clone_repo(request: CloneRepoRequest):
    """
    Clone a Git repository from URL and index its files.

    Supports GitHub, GitLab, and Bitbucket HTTPS URLs.
    """
    if not validate_git_url(request.repo_url):
        raise HTTPException(
            status_code=400,
            detail="Invalid Git URL. Supported: GitHub, GitLab, Bitbucket HTTPS URLs",
        )

    try:
        temp_dir, metadata = clone_repository(
            repo_url=request.repo_url,
            branch=request.branch,
        )

        all_files, indexed_files = scan_repository(temp_dir)

        return CloneRepoResponse(
            temp_dir=temp_dir,
            files=all_files,
            indexed_files=indexed_files,
            metadata=metadata,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload-zip/", response_model=UploadResponse)
async def upload_zip(file: UploadFile = File(...)):
    """
    Upload a ZIP file and index its contents.
    """
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are allowed")

    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, file.filename)

    # Save uploaded ZIP
    with open(zip_path, "wb") as f:
        f.write(await file.read())

    # Extract ZIP
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file")

    # List all files, ignoring unwanted folders
    ignore_dirs = {".git", "node_modules", "venv", "__pycache__"}

    all_files = []
    for root, dirs, files in os.walk(temp_dir):
        # Remove ignored directories from traversal
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for name in files:
            file_path = os.path.join(root, name)
            if os.path.getsize(file_path) > MAX_FILE_SIZE:
                continue  # Skip large files

            # Full path relative to temp_dir
            rel_path = os.path.relpath(os.path.join(root, name), temp_dir)
            # Normalize path to use forward slashes
            rel_path = rel_path.replace("\\", "/")
            all_files.append(rel_path)

    # Index files by language
    indexed_files = index_files_by_language(all_files)

    return UploadResponse(
        temp_dir=temp_dir,
        files=all_files,
        indexed_files=indexed_files,
    )
