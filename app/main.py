from fastapi import FastAPI

app = FastAPI(
    title="PolicyRAG Studio API",
    version="0.1.0",
    description="A reproducible workbench for policy retrieval experiments.",
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "PolicyRAG Studio",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "policy-rag-studio",
        "mode": "development",
    }
