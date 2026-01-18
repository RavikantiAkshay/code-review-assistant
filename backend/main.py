from fastapi import FastAPI

app = FastAPI(title="Code Review Assistant")

@app.get("/health")
def health_check():
    return {"status": "ok"}
