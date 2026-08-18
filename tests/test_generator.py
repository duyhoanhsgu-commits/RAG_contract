from types import SimpleNamespace

from app.rag.generator import (
    INSUFFICIENT_CONTEXT_ANSWER,
    OpenAIGenerator,
    format_context,
)
from app.rag.retriever import RetrievalResult


def make_chunk(index: int) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=f"contract_1_chunk_{index:04d}",
        contract_id="contract_1",
        chunk_index=index,
        section="Termination",
        section_number="8.2",
        text=f"Contract text {index}",
        score=0.9,
        source_txt="contract_1.txt",
        source_pdf="contract_1.pdf",
    )


class FakeCompletions:
    def __init__(self) -> None:
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Answer supported by [Source 2].")
                )
            ]
        )


def make_generator() -> tuple[OpenAIGenerator, FakeCompletions]:
    generator = OpenAIGenerator.__new__(OpenAIGenerator)
    completions = FakeCompletions()
    generator.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    generator.model = "test-model"
    return generator, completions


def test_generate_answer_formats_context_and_maps_trusted_source() -> None:
    generator, completions = make_generator()
    chunks = [make_chunk(1), make_chunk(2)]

    result = generator.generate_answer("When can it terminate?", chunks)

    prompt = completions.request["messages"][1]["content"]
    assert format_context(chunks) in prompt
    assert result.answer == "Answer supported by [Source 2]."
    assert len(result.sources) == 1
    assert result.sources[0].chunk_id == chunks[1].chunk_id
    assert result.sources[0].source_pdf == chunks[1].source_pdf


def test_generate_answer_skips_llm_when_context_is_empty() -> None:
    generator, completions = make_generator()

    result = generator.generate_answer("What is the term?", [])

    assert result.answer == INSUFFICIENT_CONTEXT_ANSWER
    assert result.sources == []
    assert completions.request is None
