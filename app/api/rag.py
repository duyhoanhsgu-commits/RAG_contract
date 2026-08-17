from fastapi import APIRouter, HTTPException, Request

from app.schemas.rag import RAGRequest, RAGResponse

router = APIRouter()


@router.post("/query", response_model=RAGResponse)
def query_rag(payload: RAGRequest, request: Request) -> RAGResponse:
    pipeline = getattr(request.app.state, "rag_pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline is not configured")

    answer, sources = pipeline.answer(payload.question, limit=payload.limit)
    return RAGResponse(answer=answer, sources=sources)
