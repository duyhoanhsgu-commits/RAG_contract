from fastapi import FastAPI

from app.api.rag import router as rag_router

app = FastAPI(title="Contract RAG API")
app.include_router(rag_router, prefix="/api/rag", tags=["rag"])


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
