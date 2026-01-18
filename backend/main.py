from fastapi import FastAPI, UploadFile, File
import zipfile
import os
import tempfile

app = FastAPI(title="Code Review Assistant")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/upload-zip/")
async def upload_zip(file: UploadFile = File(...)):
    if not file.filename.endswith(".zip"):
        return {"error": "Only ZIP files are allowed"}

    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, file.filename)

    # Save uploaded ZIP
    with open(zip_path, "wb") as f:
        f.write(await file.read())

    # Extract ZIP
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    # List all files
    # List all files, ignoring unwanted folders
    ignore_dirs = {".git", "node_modules", "venv"}

    all_files = []
    for root, dirs, files in os.walk(temp_dir):
        # Remove ignored directories from traversal
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for name in files:
            # Full path relative to temp_dir
            rel_path = os.path.relpath(os.path.join(root, name), temp_dir)
            # Normalize path to use forward slashes
            rel_path = rel_path.replace("\\", "/")
            all_files.append(rel_path)


    return {"temp_dir": temp_dir, "files": all_files}
