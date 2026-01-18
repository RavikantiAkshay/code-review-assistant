from fastapi import FastAPI, UploadFile, File
import zipfile
import os
import tempfile

# define file size limit
MAX_FILE_SIZE = 200 * 1024  

# supported languages by extension
LANGUAGE_EXTENSIONS = {
    "python": [".py"],
    "javascript": [".js", ".jsx"],
    "typescript": [".ts", ".tsx"],
    "java": [".java"],
    "c_cpp": [".c", ".cpp", ".h", ".hpp"],
    "html": [".html", ".htm"],
    "css": [".css"],
}

def index_files_by_language(file_list):
    # takes a list of normalized file paths and returns a dict grouped by language. 
    indexed = {lang: [] for lang in LANGUAGE_EXTENSIONS}

    for f in file_list:
        ext = os.path.splitext(f)[1].lower()
        for lang, exts in LANGUAGE_EXTENSIONS.items():
            if ext in exts:
                indexed[lang].append(f)
                break
    return indexed

app = FastAPI(title="Code Review Assistant")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/upload-zip/")
async def upload_zip(file: UploadFile = File(...)):
    if not file.filename.endswith(".zip"):
        return {"error": "Only ZIP files are allowed"}

    # create a temporary directory
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, file.filename)

    # save uploaded ZIP
    with open(zip_path, "wb") as f:
        f.write(await file.read())

    # extract ZIP
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
        
    # list all files, ignoring unwanted folders
    ignore_dirs = {".git", "node_modules", "venv"}

    all_files = []
    for root, dirs, files in os.walk(temp_dir):
        # remove ignored directories from traversal
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for name in files:
            
            file_path = os.path.join(root, name)
            if os.path.getsize(file_path) > MAX_FILE_SIZE: 
                continue # skip large files
            
            # full path relative to temp_dir
            rel_path = os.path.relpath(os.path.join(root, name), temp_dir)
            # normalize path to use forward slashes
            rel_path = rel_path.replace("\\", "/")
            all_files.append(rel_path)
            # index files by language
            indexed_files = index_files_by_language(all_files)

    return {"temp_dir": temp_dir, "files": all_files, "indexed_files": indexed_files}

