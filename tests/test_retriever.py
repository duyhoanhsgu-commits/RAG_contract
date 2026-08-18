from app.rag.embedder import Embedder
from app.rag.retriever import Retriever
from app.rag.vector_store import MetadataFilters, SearchResult, VectorStore


class FakeEmbedder(Embedder):
    def embed_text(self, text: str) -> list[float]:
        return [0.1, 0.2]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


class FakeVectorStore(VectorStore):
    def __init__(self) -> None:
        self.filters: MetadataFilters | None = None

    def upsert(self, ids, texts, embeddings, metadatas) -> None:
        raise NotImplementedError

    def search_with_metadata(self, embedding, limit=5, filters=None):
        self.filters = filters
        return [
            SearchResult(
                chunk_id="contract_1_chunk_0003",
                text="Either party may terminate this Agreement.",
                metadata={
                    "contract_id": "contract_1",
                    "chunk_index": 3,
                    "section": "Termination",
                    "section_number": "8.2",
                    "source_txt": "contract_1.txt",
                    "source_pdf": "contract_1.pdf",
                },
                distance=0.15,
            )
        ]


def test_retrieve_returns_structured_result_and_passes_filter() -> None:
    store = FakeVectorStore()
    result = Retriever(FakeEmbedder(), store).retrieve(
        "termination rights",
        filters={"contract_id": "contract_1"},
        top_k=3,
    )[0]

    assert store.filters == {"contract_id": "contract_1"}
    assert result.chunk_id == "contract_1_chunk_0003"
    assert result.contract_id == "contract_1"
    assert result.chunk_index == 3
    assert result.section == "Termination"
    assert result.section_number == "8.2"
    assert result.score == 0.85
    assert result.source_txt == "contract_1.txt"
    assert result.source_pdf == "contract_1.pdf"


def test_retrieve_rejects_invalid_input() -> None:
    retriever = Retriever(FakeEmbedder(), FakeVectorStore())

    for query, top_k in [("", 5), ("   ", 5), ("valid", 0)]:
        try:
            retriever.retrieve(query, top_k=top_k)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError")
