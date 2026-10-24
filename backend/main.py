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
from backend.analysis.ast_engine import (
    analyze_code_ast,
    extract_ast_symbols,
    build_repository_symbol_graph,
)
from backend.llm.reviewer import review_file_with_llm
from backend.reviews.deduplicator import deduplicate_reviews, resolve_rule_category
from backend.reviews.ranking import rank_reviews
from backend.rulesets.registry import RULESETS
from backend.reviews.cache import review_cache
from backend.exports import (
    export_github_pr_comments_json,
    generate_patch_file,
)
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Concurrency limiter to protect API rate limits and resources
MAX_CONCURRENT_REVIEWS = 5
CONCURRENCY_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REVIEWS)

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
    """Run static analysis and AST anti-pattern checks."""
    static_reviews = {
        "correctness": [],
        "security": [],
        "complexity": [],
        "readability": [],
        "tests": [],
    }
    
    try:
        # Read file content for AST analysis
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Step 1: Run deterministic AST anti-pattern rule engine
        ast_issues = analyze_code_ast(file_path, content, language)
        for issue in ast_issues:
            issue["file"] = file_path
            cat = issue.get("category", "correctness").lower()
            if cat in static_reviews:
                static_reviews[cat].append(issue)
            else:
                static_reviews["correctness"].append(issue)

        # Step 2: Run traditional linters (Flake8 / Radon / ESLint)
        linter_issues = []
        if language == "python":
            linter_issues = analyze_python_file_normalized(abs_path)
        elif language in ["javascript", "jsx", "typescript", "ts", "tsx"]:
            linter_issues = analyze_js_file_normalized(abs_path)

        for issue in linter_issues:
            issue["file"] = file_path
            # Dynamically resolve category from rule code or issue type
            rule_code = issue.get("code")
            mapped_cat = resolve_rule_category(rule_code)
            if mapped_cat and mapped_cat in static_reviews:
                static_reviews[mapped_cat].append(issue)
            elif issue.get("type") == "complexity":
                static_reviews["complexity"].append(issue)
            else:
                static_reviews["readability"].append(issue)

    except Exception as e:
        logger.warning(f"Static/AST analysis failed for {file_path}: {e}")
    
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


async def review_single_file_async(
    file_path: str,
    temp_dir: str,
    ruleset: Optional[str],
    semaphore: asyncio.Semaphore,
) -> FileReviewResult:
    """
    Process a single file through the review pipeline:
    Cache Check -> Static/AST Analysis -> LLM Review -> Deduplication -> Ranking -> Cache Save.
    Runs inside a concurrency semaphore to prevent rate-limit throttling.
    """
    abs_path = os.path.join(temp_dir, file_path)

    if not os.path.exists(abs_path):
        return FileReviewResult(
            file=file_path,
            issues=[],
            error=f"File not found: {file_path}",
        )

    language = get_language_for_file(file_path)
    if not language:
        return FileReviewResult(
            file=file_path,
            issues=[],
            error=f"Unsupported file type: {file_path}",
        )

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        return FileReviewResult(
            file=file_path,
            issues=[],
            error=f"Failed to read file: {e}",
        )

    # Check in-memory content cache for instant sub-millisecond retrieval
    cached_issues = review_cache.get(file_path, content, ruleset)
    if cached_issues is not None:
        logger.info("Review cache hit for %s", file_path)
        return FileReviewResult(
            file=file_path,
            issues=cached_issues,
        )

    async with semaphore:
        # Step 1: Static Analysis & AST rules (executed in thread pool)
        static_reviews = await asyncio.to_thread(
            run_static_analysis, file_path, abs_path, language
        )

        # Step 2: LLM Review (executed concurrently in thread pool)
        llm_reviews = {cat: [] for cat in static_reviews.keys()}
        if language in ["python", "javascript"]:
            llm_reviews = await asyncio.to_thread(
                run_llm_review, file_path, abs_path, language, ruleset
            )

        # Step 3: Deduplication with fuzzy intervals & dynamic categories
        merged_reviews = deduplicate_reviews(
            file=file_path,
            static_reviews=static_reviews,
            llm_reviews=llm_reviews,
        )

        # Step 4: Impact ranking & metadata preservation
        ranked = rank_reviews(merged_reviews)
        for issue in ranked:
            issue["file"] = file_path

        # Cache the result for subsequent instant hits
        review_cache.set(file_path, content, ruleset, ranked)

        return FileReviewResult(
            file=file_path,
            issues=ranked,
        )


@app.post("/review", response_model=ReviewResponse)
async def review_files(request: ReviewRequest):
    """
    Run full code review pipeline concurrently across all selected files.
    
    Pipeline: Cache Check → Concurrent Static/AST & LLM → Deduplication → Ranking
    """
    if request.ruleset and request.ruleset not in RULESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown ruleset: {request.ruleset}. Use /rulesets to see available options.",
        )

    if not os.path.exists(request.temp_dir):
        raise HTTPException(status_code=400, detail="Invalid temp_dir: directory does not exist")

    # Run all file reviews concurrently
    tasks = [
        review_single_file_async(
            file_path=file_path,
            temp_dir=request.temp_dir,
            ruleset=request.ruleset,
            semaphore=CONCURRENCY_SEMAPHORE,
        )
        for file_path in request.files
    ]
    file_results = await asyncio.gather(*tasks)

    all_ranked_issues = []
    for fr in file_results:
        all_ranked_issues.extend(fr.issues)

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


# ====================
# Export Endpoints
# ====================

class ExportRequest(BaseModel):
    ranked_issues: List[Dict[str, Any]]
    repo_owner: Optional[str] = "owner"
    repo_name: Optional[str] = "repo"
    pull_number: Optional[int] = 1
    commit_sha: Optional[str] = "HEAD"


@app.post("/export/github-pr-comments")
def export_pr_comments(request: ExportRequest):
    """
    Export review results as GitHub PR comment JSON format.
    
    This generates JSON compatible with GitHub's Pull Request Review API.
    Can be used to post comments via the GitHub API.
    """
    try:
        json_output = export_github_pr_comments_json(
            ranked_issues=request.ranked_issues,
            repo_owner=request.repo_owner,
            repo_name=request.repo_name,
            pull_number=request.pull_number,
            commit_sha=request.commit_sha
        )
        return {"format": "github_pr_review", "content": json.loads(json_output)}
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/export/patch")
def export_patch(request: ExportRequest):
    """
    Generate a unified diff patch file for autofix.
    
    This creates a patch that can be applied with `git apply`.
    Only includes issues that have both 'snippet' and 'fix' fields.
    """
    try:
        patch_content = generate_patch_file(request.ranked_issues)
        
        if not patch_content.strip():
            return {
                "format": "unified_diff",
                "content": "",
                "message": "No fixable issues found (issues need both 'snippet' and 'fix' fields)"
            }
        
        return {
            "format": "unified_diff",
            "content": patch_content,
            "fixable_issues": len([i for i in request.ranked_issues if i.get("fix") and i.get("snippet")])
        }
    except Exception as e:
        logger.error(f"Patch generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Need to import json for the export endpoint
import json


class AstSymbolsRequest(BaseModel):
    temp_dir: str
    file_path: str


class BlastRadiusRequest(BaseModel):
    temp_dir: str
    files: List[str]
    symbol_name: str
    file_path: Optional[str] = None
    max_depth: Optional[int] = 3


@app.post("/ast-symbols")
def get_ast_symbols(request: AstSymbolsRequest):
    """Extract AST symbols, complexity, and imports for a file."""
    abs_path = os.path.join(request.temp_dir, request.file_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")

    language = get_language_for_file(request.file_path)
    if not language:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {request.file_path}")

    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    return extract_ast_symbols(request.file_path, content, language)


@app.post("/blast-radius")
def get_blast_radius(request: BlastRadiusRequest):
    """Find all upstream callers dependent on a symbol across the repository."""
    graph = build_repository_symbol_graph(request.files, request.temp_dir)
    blast = graph.find_blast_radius(
        symbol_name=request.symbol_name,
        file_path=request.file_path,
        max_depth=request.max_depth or 3,
    )
    return {
        "symbol": request.symbol_name,
        "file_path": request.file_path,
        "blast_radius": blast,
        "affected_callers_count": len(blast),
    }


@app.get("/cache/stats")
def get_cache_stats():
    """Get review cache statistics."""
    return {"cached_files_count": review_cache.size(), "max_size": review_cache.max_size}


@app.post("/cache/clear")
def clear_review_cache():
    """Flush the in-memory review cache."""
    review_cache.clear()
    return {"status": "cleared", "cached_files_count": 0}


