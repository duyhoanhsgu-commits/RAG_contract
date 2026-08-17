from pydantic import BaseModel, Field


class RAGRequest(BaseModel):
    question: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class RAGResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
