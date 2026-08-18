"""Context-grounded answer generation for Contract RAG V1."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

from openai import OpenAI

from app.core.config import get_settings
from app.core.prompts import RAG_PROMPT, SYSTEM_PROMPT
from app.rag.retriever import RetrievalResult

INSUFFICIENT_CONTEXT_ANSWER = (
    "The provided context is insufficient to answer the question."
)
SOURCE_CITATION_PATTERN = re.compile(r"\[Source\s+(\d+)\]", re.IGNORECASE)


@dataclass(frozen=True)
class AnswerSource:
    chunk_id: str
    contract_id: str
    section: str
    source_pdf: str


@dataclass(frozen=True)
class RAGAnswer:
    answer: str
    sources: list[AnswerSource]


class Generator:
    """Answer generation interface."""

    def generate_answer(
        self,
        query: str,
        retrieved_chunks: list[RetrievalResult],
    ) -> RAGAnswer:
        raise NotImplementedError

    def generate(self, question: str, context: Sequence[str]) -> str:
        """Compatibility method used by the original pipeline."""
        raise NotImplementedError


class OpenAIGenerator(Generator):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY is required")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate_answer(
        self,
        query: str,
        retrieved_chunks: list[RetrievalResult],
    ) -> RAGAnswer:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not retrieved_chunks:
            return RAGAnswer(answer=INSUFFICIENT_CONTEXT_ANSWER, sources=[])

        answer = self._complete(
            query,
            format_context(retrieved_chunks),
        )
        return RAGAnswer(
            answer=answer,
            sources=select_sources(answer, retrieved_chunks),
        )

    def generate(self, question: str, context: Sequence[str]) -> str:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        if not context:
            return INSUFFICIENT_CONTEXT_ANSWER
        return self._complete(question, "\n\n".join(context))

    def _complete(self, query: str, context: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": RAG_PROMPT.format(context=context, question=query),
                },
            ],
        )
        answer = response.choices[0].message.content
        if not answer or not answer.strip():
            raise RuntimeError("LLM returned an empty answer")
        return answer.strip()


def format_context(chunks: Sequence[RetrievalResult]) -> str:
    sections: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        section = " ".join(
            part for part in (chunk.section_number, chunk.section) if part
        )
        sections.append(
            f"[Source {index}]\n"
            f"chunk_id: {chunk.chunk_id}\n"
            f"section: {section}\n"
            f"text: {chunk.text}"
        )
    return "\n\n".join(sections)


def select_sources(
    answer: str,
    chunks: Sequence[RetrievalResult],
) -> list[AnswerSource]:
    """Resolve LLM citation labels to trusted retrieval metadata."""
    cited_indexes = {
        int(match) - 1 for match in SOURCE_CITATION_PATTERN.findall(answer)
    }
    valid_indexes = sorted(index for index in cited_indexes if 0 <= index < len(chunks))
    return [
        AnswerSource(
            chunk_id=chunks[index].chunk_id,
            contract_id=chunks[index].contract_id,
            section=chunks[index].section,
            source_pdf=chunks[index].source_pdf,
        )
        for index in valid_indexes
    ]


@lru_cache
def get_generator() -> OpenAIGenerator:
    settings = get_settings()
    return OpenAIGenerator(
        api_key=settings.openai_api_key,
        model=settings.model_name,
    )


def generate_answer(
    query: str,
    retrieved_chunks: list[RetrievalResult],
) -> RAGAnswer:
    return get_generator().generate_answer(query, retrieved_chunks)
