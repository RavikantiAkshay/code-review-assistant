from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
import zipfile
import os
import tempfile
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from backend.ingestion.git_ingestion import (
    clone_repository,
    scan_repository,
    cleanup_repository,
    validate_git_url,
)
from backend.analysis.python_static import analyze_python_file_normalized
from backend.analysis.javascript_static import analyze_js_file_normalized
from backend.llm.reviewer import review_file_with_llm
from backend.reviews.deduplicator import deduplicate_reviews
from backend.reviews.ranking import rank_reviews
from backend.rulesets.registry import RULESETS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


def get_language_for_file(file_path: str) -> Optional[str]:
    """Get the language for a file based on its extension."""
    ext = os.path.splitext(file_path)[1].lower()
    for lang, exts in LANGUAGE_EXTENSIONS.items():
        if ext in exts:
            return lang
    return None


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


class ReviewRequest(BaseModel):
    temp_dir: str
    files: List[str]
    ruleset: Optional[str] = None


class ReviewIssue(BaseModel):
    line: Optional[int] = None
    severity: str
    message: str
    category: str
    impact: float
    source: str
    rule: Optional[Dict[str, str]] = None
    file: Optional[str] = None


class FileReviewResult(BaseModel):
    file: str
    issues: List[Dict[str, Any]]
    error: Optional[str] = None


class ReviewResponse(BaseModel):
    ranked_issues: List[Dict[str, Any]]
    file_results: List[FileReviewResult]
    summary: Dict[str, int]


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


@app.get("/rulesets")
def list_rulesets():
    """List all available rulesets."""
    rulesets_info = []
    for key, rs in RULESETS.items():
        rulesets_info.append({
            "id": key,
            "name": rs["name"],
            "description": rs["description"],
            "language": rs["language"],
            "categories": rs["categories"],
            "rule_count": len(rs["rules"]),
        })
    return {"rulesets": rulesets_info}


def run_static_analysis(file_path: str, abs_path: str, language: str) -> Dict[str, List[Dict]]:
    """Run static analysis based on file language."""
    static_reviews = {
        "correctness": [],
        "security": [],
        "complexity": [],
        "readability": [],
        "tests": [],
    }
    
    try:
        if language == "python":
            issues = analyze_python_file_normalized(abs_path)
            for issue in issues:
                issue["file"] = file_path
                if issue.get("type") == "complexity":
                    static_reviews["complexity"].append(issue)
                else:
                    static_reviews["readability"].append(issue)
                    
        elif language == "javascript":
            issues = analyze_js_file_normalized(abs_path)
            for issue in issues:
                issue["file"] = file_path
                static_reviews["readability"].append(issue)
                
    except Exception as e:
        logger.warning(f"Static analysis failed for {file_path}: {e}")
    
    return static_reviews


def run_llm_review(file_path: str, abs_path: str, language: str, ruleset: Optional[str]) -> Dict[str, List[Dict]]:
    """Run LLM-based code review."""
    llm_reviews = {
        "correctness": [],
        "security": [],
        "complexity": [],
        "readability": [],
        "tests": [],
    }
    
    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        result = review_file_with_llm(
            file_path=file_path,
            language=language,
            file_content=content,
            ruleset=ruleset,
        )
        
        if "reviews" in result:
            for category in llm_reviews.keys():
                if category in result["reviews"]:
                    for issue in result["reviews"][category]:
                        issue["file"] = file_path
                        llm_reviews[category].append(issue)
                        
    except Exception as e:
        logger.warning(f"LLM review failed for {file_path}: {e}")
    
    return llm_reviews


@app.post("/review", response_model=ReviewResponse)
async def review_files(request: ReviewRequest):
    """
    Run full code review pipeline on selected files.
    
    Pipeline: Static Analysis → LLM Review → Deduplication → Ranking
    """
    if request.ruleset and request.ruleset not in RULESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown ruleset: {request.ruleset}. Use /rulesets to see available options.",
        )
    
    if not os.path.exists(request.temp_dir):
        raise HTTPException(status_code=400, detail="Invalid temp_dir: directory does not exist")
    
    file_results = []
    all_ranked_issues = []
    
    for file_path in request.files:
        abs_path = os.path.join(request.temp_dir, file_path)
        
        if not os.path.exists(abs_path):
            file_results.append(FileReviewResult(
                file=file_path,
                issues=[],
                error=f"File not found: {file_path}",
            ))
            continue
        
        language = get_language_for_file(file_path)
        if not language:
            file_results.append(FileReviewResult(
                file=file_path,
                issues=[],
                error=f"Unsupported file type: {file_path}",
            ))
            continue
        
        # Step 1: Static Analysis
        static_reviews = run_static_analysis(file_path, abs_path, language)
        
        # Step 2: LLM Review (only for Python and JavaScript for now)
        llm_reviews = {cat: [] for cat in static_reviews.keys()}
        if language in ["python", "javascript"]:
            llm_reviews = run_llm_review(file_path, abs_path, language, request.ruleset)
        
        # Step 3: Deduplication
        merged_reviews = deduplicate_reviews(
            file=file_path,
            static_reviews=static_reviews,
            llm_reviews=llm_reviews,
        )
        
        # Step 4: Ranking
        ranked = rank_reviews(merged_reviews)
        
        # Add file info to each issue
        for issue in ranked:
            issue["file"] = file_path
        
        file_results.append(FileReviewResult(
            file=file_path,
            issues=ranked,
        ))
        all_ranked_issues.extend(ranked)
    
    # Sort all issues by impact across all files
    all_ranked_issues.sort(key=lambda x: x.get("impact", 0), reverse=True)
    
    # Generate summary
    summary = {
        "total_issues": len(all_ranked_issues),
        "high_severity": len([i for i in all_ranked_issues if i.get("severity") == "high"]),
        "medium_severity": len([i for i in all_ranked_issues if i.get("severity") == "medium"]),
        "low_severity": len([i for i in all_ranked_issues if i.get("severity") == "low"]),
        "files_reviewed": len(request.files),
        "files_with_issues": len([fr for fr in file_results if fr.issues]),
    }
    
    return ReviewResponse(
        ranked_issues=all_ranked_issues,
        file_results=file_results,
        summary=summary,
    )


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
