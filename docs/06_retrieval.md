# Bước 6 — Retrieval trong Contract RAG

## 1. Retrieval là gì?

Retrieval là bước nhận câu hỏi của người dùng và tìm ra những chunk trong Vector Database có khả năng chứa câu trả lời nhất.

Retrieval **không trả lời câu hỏi**.  
Nó chỉ tìm context phù hợp để đưa cho LLM ở bước sau.

Flow:

```text
User Question
    ↓
Normalize Query
    ↓
Embedding Query
    ↓
Metadata Filter (nếu có)
    ↓
Vector Search
    ↓
Top-K Chunks
```

Ví dụ:

```text
Question:
How can either party terminate the agreement?
```

Retriever có thể trả:

```text
1. Section 8 - TERM AND TERMINATION
2. Section 12.4 - FORCE MAJEURE
3. Section 2.2 - INITIAL INFORMATION TRANSFER
...
```

---

## 2. Input của Retrieval

Interface baseline:

```python
retrieve(
    query: str,
    filters: dict | None = None,
    top_k: int = 5
)
```

Ví dụ search toàn bộ corpus:

```python
results = retrieve(
    query="Can either party terminate the agreement?",
    top_k=5
)
```

Ví dụ chỉ search trong một contract:

```python
results = retrieve(
    query="Can either party terminate the agreement?",
    filters={
        "contract_id": "contract_0001"
    },
    top_k=5
)
```

---

## 3. Query phải được embed bằng cùng model

Rule quan trọng:

```text
chunks → embedding model A
query  → embedding model A
```

Không được:

```text
chunks → model A
query  → model B
```

Vì vector của query và vector của chunks phải nằm trong cùng embedding space.

Flow:

```text
query
  ↓
embedding model
  ↓
query_vector
```

Sau đó `query_vector` được dùng để search trong Vector DB.

---

## 4. Metadata Filter

Metadata filter đặc biệt quan trọng trong Contract RAG.

Nếu user đang hỏi một contract cụ thể:

```text
contract_0001
```

thì không nên search trên toàn bộ 510 contracts.

Đúng:

```python
filters = {
    "contract_id": "contract_0001"
}
```

Flow:

```text
All chunks
    ↓
Filter contract_id = contract_0001
    ↓
Vector similarity search
    ↓
Top-K chunks
```

Không nên:

```text
Search toàn DB
    ↓
Lấy Top 100
    ↓
Sau đó mới lọc contract_id
```

Vì các chunk của contract cần tìm có thể đã không lọt vào Top 100.

---

## 5. Hai mode Retrieval nên hỗ trợ

### Mode 1 — Single Contract Retrieval

Dùng cho Contract QA.

Ví dụ:

```text
What does this agreement say about termination?
```

Call:

```python
retrieve(
    query=query,
    filters={"contract_id": contract_id},
    top_k=5
)
```

### Mode 2 — Corpus Retrieval

Dùng khi muốn tìm clause trên toàn bộ dataset.

Ví dụ:

```text
Find contracts containing non-compete provisions.
```

Call:

```python
retrieve(
    query=query,
    filters=None,
    top_k=5
)
```

---

## 6. Top-K

Baseline:

```python
top_k = 5
```

Không phải `top_k` càng lớn càng tốt.

Ví dụ:

```text
Top 5:
- 3 chunks liên quan
- 2 chunks noise
```

Nếu lấy:

```text
Top 20:
- 3 chunks liên quan
- 17 chunks noise
```

thì LLM ở bước sau có thể bị context nhiễu.

Ở MVP, giữ:

```python
top_k = 5
```

Sau này dùng Evaluation để thử:

```text
k = 3
k = 5
k = 10
```

---

## 7. Retrieval Result Schema

Không nên chỉ trả text.

Nên trả đầy đủ metadata để:

- trace source;
- citation;
- debug;
- evaluation;
- đưa context cho LLM.

Ví dụ:

```python
class RetrievalResult:
    chunk_id: str
    contract_id: str
    chunk_index: int

    section: str | None
    section_number: str | None

    text: str

    score: float

    source_txt: str
    source_pdf: str
```

Output logic:

```json
{
  "chunk_id": "contract_0001_chunk_0008",
  "contract_id": "contract_0001",
  "chunk_index": 8,
  "section": "8 TERM AND TERMINATION",
  "section_number": "8",
  "text": "Either party may terminate...",
  "score": 0.478302,
  "source_txt": "...",
  "source_pdf": "..."
}
```

---

## 8. Hiểu đúng về score

Vector DB có thể trả:

```text
similarity
```

hoặc:

```text
distance
```

Nếu là similarity:

```text
cao hơn → gần hơn
```

Nếu là distance:

```text
thấp hơn → gần hơn
```

Không nên tự đặt rule kiểu:

```python
if score > 0.8:
    accept
```

khi chưa biết score của Vector DB mang ý nghĩa gì.

Threshold phụ thuộc vào:

- embedding model;
- distance metric;
- dataset;
- query style;
- Vector DB.

Ở baseline chỉ cần lấy Top-K và inspect kết quả.

---

## 9. Không dùng CUAD Ground Truth trong Retrieval

Retrieval được phép dùng:

```text
query
contract_id
chunks
metadata bình thường
embeddings
```

Retrieval không được biết:

```text
CUAD answer span
CUAD clause label
expected answer
ground truth clause type
```

Ví dụ sai:

```python
filters = {
    "clause_type": "Termination"
}
```

nếu `Termination` đến từ CUAD ground truth.

Đây là data leakage.

Ground truth phải để riêng cho Evaluation.

---

## 10. Kiến trúc code đề xuất

```text
retrieval/
├── retriever.py
├── schemas.py
└── vector_store.py
```

Concept:

```text
Retriever
   ↓
Embedding Service
   ↓
Vector Store
```

Pseudo-code:

```python
class Retriever:
    def retrieve(
        self,
        query: str,
        filters: dict | None = None,
        top_k: int = 5,
    ) -> list[RetrievalResult]:

        query_vector = self.embedder.embed_query(query)

        results = self.vector_store.search(
            vector=query_vector,
            filters=filters,
            top_k=top_k,
        )

        return results
```

Không cần đưa LLM vào Retriever.

---

## 11. Test Retrieval

Nên test retrieval riêng trước khi nối LLM.

Ví dụ:

```text
Query:
How can either party terminate the agreement?

Contract:
contract_0001

Top 1:
Section 8 - TERM AND TERMINATION
```

Manual test nên có các query tự nhiên:

```text
Can either party end the agreement early?

Is confidential information protected?

Can this agreement be assigned to another company?

What happens if control of the company changes?

Which law governs this agreement?
```

Không chỉ test bằng clause name như:

```text
Termination
Confidentiality
Assignment
```

vì user thực tế thường hỏi bằng natural language.

---

## 12. Kết quả test hiện tại

Với query:

```text
How can either party terminate the agreement?
```

và filter:

```text
contract_0001
```

Retriever đã đưa:

```text
Section 8 - TERM AND TERMINATION
```

lên Top 1.

Đây là dấu hiệu baseline semantic retrieval đang hoạt động đúng.

Tuy nhiên cần chú ý:

- metadata `section` có thể bị lệch ở một số chunk;
- một số chunk chứa nhiều section khác nhau;
- raw text có các dòng `Source:` chen giữa nội dung.

Các vấn đề này thuộc Normalize / Chunking / Metadata nhiều hơn là lỗi Retrieval.

---

## 13. Neighbor Expansion — chưa cần ở V1

Contract có thể bị cắt clause giữa hai chunks.

Ví dụ:

```text
chunk 7
chunk 8
chunk 9
```

Retriever lấy được:

```text
chunk 8
```

Sau này có thể mở rộng:

```text
chunk 7 + chunk 8 + chunk 9
```

dựa trên:

```text
contract_id
chunk_index
```

Nhưng chưa cần ở V1.

Flow hiện tại cứ giữ đơn giản:

```text
query
  ↓
Top-K vector search
```

---

## 14. Definition of Done

Retrieval hoàn thành khi hệ thống chạy được:

```text
Question
    ↓
Embed Query
    ↓
Metadata Filter
    ↓
Vector DB Search
    ↓
Top-K Chunks
```

và mỗi result có:

```text
chunk_id
contract_id
chunk_index
section
text
score
source_txt
source_pdf
```

Khi Retrieval ổn, bước tiếp theo là:

```text
Top-K Chunks
    ↓
LLM Generation
```
