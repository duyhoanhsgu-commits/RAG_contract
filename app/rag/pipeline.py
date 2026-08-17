from app.rag.generator import Generator
from app.rag.retriever import Retriever


class RAGPipeline:
    def __init__(self, retriever: Retriever, generator: Generator) -> None:
        self.retriever = retriever
        self.generator = generator

    def answer(self, question: str, limit: int = 5) -> tuple[str, list[str]]:
        context = self.retriever.retrieve(question, limit=limit)
        return self.generator.generate(question, context), context
