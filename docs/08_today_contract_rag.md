# Contract RAG — Tổng kết hôm nay

## 1. Trạng thái hiện tại

Pipeline hiện tại:

```text
Raw Contracts
    ↓
1. Understand / Normalize
    ↓
2. Chunk
    ↓
3. Metadata
    ↓
4. Embedding
    ↓
5. Vector DB
    ↓
6. Retrieval
    ↓
7. LLM Generation
    ↓
8. Evaluation
```

Các phần hôm nay đã chốt:

```text
✅ Retrieval
✅ LLM Generation
✅ Retrieval Evaluation V1
✅ Generation Evaluation V1
```

Bước tiếp theo:

```text
9. Hybrid Search
```

---

# 2. Bước 6 — Retrieval

## Mục tiêu

Retrieval không trả lời câu hỏi.

Nó chỉ tìm những chunk có khả năng chứa câu trả lời nhất.

Flow:

```text
User Question
    ↓
Embed Query
    ↓
Metadata Filter
    ↓
Vector Search
    ↓
Top-K Chunks
```

Public interface:

```python
retrieve(
    query: str,
    filters: dict | None = None,
    top_k: int = 5
) -> list[RetrievalResult]
```

Ví dụ:

```python
results = retrieve(
    query="How can either party terminate the agreement?",
    filters={"contract_id": "contract_0001"},
    top_k=5
)
```

## Rule quan trọng

Query phải dùng cùng embedding model và cùng config với chunks đã index.

```text
chunks → embedding model A
query  → embedding model A
```

Không được:

```text
chunks → model A
query  → model B
```

## Metadata Filter

Với Contract QA, `contract_id` là filter chính.

```python
filters = {
    "contract_id": "contract_0001"
}
```

Flow:

```text
All chunks
    ↓
Filter contract_id
    ↓
Vector Search
    ↓
Top-K
```

Không nên search toàn DB rồi mới lọc.

## Hai mode Retrieval

### Single Contract Retrieval

```python
retrieve(
    query=query,
    filters={"contract_id": contract_id},
    top_k=5
)
```

Dùng cho:

```text
What does this contract say about termination?
```

### Corpus Retrieval

```python
retrieve(
    query=query,
    filters=None,
    top_k=5
)
```

Dùng để tìm clause trên toàn bộ dataset.

## Retrieval Result

Nên giữ:

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

Metadata được dùng cho:

```text
citation
debug
evaluation
source tracing
LLM context
```

## Top-K baseline

Baseline:

```python
top_k = 5
```

Không cần tăng quá lớn vì càng nhiều chunk càng dễ tạo noise cho LLM.

## Kết quả test hiện tại

Query:

```text
How can either party terminate the agreement?
```

Filter:

```text
contract_0001
```

Top 1 đã trả đúng:

```text
Section 8 — TERM AND TERMINATION
```

Điều này cho thấy baseline semantic retrieval đang hoạt động đúng.

Một số vấn đề phát hiện ở data:

```text
- section metadata đôi lúc bị lệch
- một chunk có thể chứa nhiều section
- dòng Source: ... chen giữa text
```

Các vấn đề này chủ yếu thuộc Normalize / Chunking / Metadata Parser, không phải lỗi Retrieval.

---

# 3. Bước 7 — LLM Generation

## Mục tiêu

Flow:

```text
Question
+
Top-K Chunks
+
Prompt
    ↓
LLM
    ↓
Answer + Sources
```

Retrieval quyết định:

```text
LLM được nhìn thấy gì?
```

Generation quyết định:

```text
LLM trả lời như thế nào?
```

## Interface

```python
generate_answer(
    query: str,
    retrieved_chunks: list[RetrievalResult]
) -> RAGAnswer
```

Generation không tự search DB.

## Prompt baseline

```text
You are a contract analysis assistant.

Answer the user's question using only the provided contract context.

Rules:
- Do not use outside knowledge.
- Do not invent missing information.
- If the answer cannot be found in the context, say that the provided context is insufficient.
- Preserve important legal conditions, exceptions, time periods, and obligations.
- Cite the supporting source chunks.
```

## Context format

Nên format context có source identifier:

```text
[Source 1]
chunk_id: contract_0001_chunk_0008
section: 8 TERM AND TERMINATION

text...

[Source 2]
chunk_id: ...
section: ...

text...
```

Sau đó:

```text
QUESTION:
How can either party terminate the agreement?
```

## Citation

Source metadata phải lấy từ `RetrievalResult`.

Không để LLM tự bịa:

```text
page
section
filename
contract_id
```

LLM chỉ cần reference:

```text
[Source 1]
```

Backend map lại về metadata thật.

## Output schema

```python
class SourceReference:
    chunk_id: str
    contract_id: str
    section: str | None
    source_pdf: str | None


class RAGAnswer:
    answer: str
    sources: list[SourceReference]
```

## Abstention

Nếu context không đủ, model phải trả:

```text
The provided contract context does not contain enough information to answer this question.
```

Không được đoán bằng kiến thức ngoài contract.

## Preserve Legal Details

Phải giữ các chi tiết:

```text
conditions
exceptions
time periods
written notice
cure periods
obligations
rights
```

Ví dụ context có:

```text
material breach
+
written notice
+
60-day cure period
```

thì không được rút gọn thành:

```text
A party may terminate for breach.
```

---

# 4. Bước 8 — Evaluation

Mục tiêu:

> Đo chất lượng thực tế của RAG bằng CUAD ground truth.

Ground truth:

```text
CUAD_v1.json
master_clauses.csv
```

Rule cực kỳ quan trọng:

> Ground truth chỉ dùng để chấm điểm sau khi hệ thống đã retrieve/generate.

Không được đưa ground truth vào:

```text
Vector DB
Retriever
LLM Prompt
LLM Context
```

Evaluation chia thành:

```text
1. Retrieval Evaluation
2. Generation Evaluation
```

---

# 5. Retrieval Evaluation V1

Flow:

```text
CUAD Evaluation Case
       ↓
Retriever
       ↓
Top-K Chunks
       ↓
Compare với Ground Truth
       ↓
Metrics
```

Evaluation case:

```python
{
    "contract_id": "...",
    "query": "...",
    "ground_truth_text": "..."
}
```

## Metrics

Baseline:

```text
Hit@1
Hit@3
Hit@5
MRR
```

### Hit@K

Ground truth có xuất hiện trong Top-K hay không.

Ví dụ relevant chunk đứng rank 4:

```text
Hit@1 = 0
Hit@3 = 0
Hit@5 = 1
```

### MRR

```text
MRR = Mean Reciprocal Rank
```

Nếu relevant result đầu tiên đứng rank 4:

```text
reciprocal_rank = 1 / 4
```

Sau đó lấy trung bình trên toàn bộ cases.

## Ground Truth Matching

Không nên yêu cầu exact string match tuyệt đối vì:

```text
- ground truth có thể nằm bên trong một chunk lớn hơn
- answer span có thể qua boundary chunk
- whitespace/punctuation có thể khác
```

V1 nên dùng matching deterministic, dễ debug.

Chưa dùng LLM-as-a-judge.

## Output mỗi case

```python
{
    "contract_id": "...",
    "query": "...",
    "ground_truth_text": "...",

    "hit_at_1": True,
    "hit_at_3": True,
    "hit_at_5": True,

    "first_relevant_rank": 1,

    "retrieved": [
        {
            "rank": 1,
            "chunk_id": "...",
            "score": 0.48,
            "text": "..."
        }
    ]
}
```

Report:

```text
Total cases: ...
Hit@1: ...
Hit@3: ...
Hit@5: ...
MRR: ...
```

Nên lưu detailed results ra JSON/JSONL để inspect các case miss.

---

# 6. Generation Evaluation V1

Flow:

```text
CUAD Evaluation Case
       ↓
Retriever
       ↓
Top-K
       ↓
LLM Generation
       ↓
Generated Answer
       ↓
Compare với Ground Truth
```

Baseline chưa dùng:

```text
LLM-as-a-judge
RAGAS
```

Metric:

```text
Exact Match
Token F1
```

## Exact Match

Normalize trước:

```text
lowercase
trim whitespace
collapse multiple spaces
optional punctuation cleanup
```

Sau đó:

```text
normalized_generated == normalized_ground_truth
```

Nếu giống hoàn toàn:

```text
Exact Match = 1
```

Nếu khác:

```text
Exact Match = 0
```

## Token F1

Tính:

```text
precision = common_tokens / generated_tokens

recall = common_tokens / ground_truth_tokens

F1 = 2 * precision * recall / (precision + recall)
```

Nên dùng:

```python
collections.Counter
```

để xử lý duplicate tokens đúng cách.

Không chỉ dùng `set()`.

## Multiple Ground Truth Answers

Nếu một case có nhiều acceptable answers:

```text
generated answer
    ↓
compare với từng ground truth
    ↓
lấy score cao nhất
```

Ví dụ:

```python
best_f1 = max(
    f1(generated, gt)
    for gt in ground_truths
)
```

## Output mỗi case

```python
{
    "contract_id": "...",
    "query": "...",

    "ground_truth_text": "...",
    "generated_answer": "...",

    "exact_match": 0,
    "token_f1": 0.76,

    "sources": [...],
    "retrieved_chunk_ids": [...]
}
```

Report:

```text
Total cases: ...
Exact Match Accuracy: ...
Average Token F1: ...
```

---

# 7. Tại sao phải Evaluation trước Hybrid Search?

Không nên:

```text
Vector Search
    ↓
Hybrid Search
    ↓
Reranker
    ↓
không biết có cải thiện thật hay không
```

Đúng:

```text
Vector-only baseline
    ↓
Evaluation
    ↓
Lưu metrics

Hit@1 = ...
Hit@3 = ...
Hit@5 = ...
MRR = ...
Token F1 = ...

    ↓
Hybrid Search
    ↓
Evaluation lại
    ↓
Compare
```

Như vậy mới biết Hybrid Search có thật sự tốt hơn baseline.

---

# 8. Baseline cần lưu

Sau khi chạy Evaluation V1 nên có report:

```text
BASELINE — VECTOR SEARCH

Retrieval
-----------------
Hit@1 : ...
Hit@3 : ...
Hit@5 : ...
MRR   : ...

Generation
-----------------
Exact Match : ...
Token F1    : ...
```

Đây là mốc để so sánh với:

```text
Hybrid Search
Reranker
```

sau này.

---

# 9. Kiến trúc tổng hiện tại

```text
                OFFLINE / INGESTION

Raw Contracts
      ↓
Normalize
      ↓
contracts.jsonl
      ↓
Chunk + Metadata
      ↓
chunks.jsonl
      ↓
Embedding
      ↓
Vector DB


                ONLINE / QUERY

User Question
      ↓
Retriever
      ↓
Embed Query
      ↓
Metadata Filter
      ↓
Vector Search
      ↓
Top-K Chunks
      ↓
Prompt Builder
      ↓
LLM
      ↓
Answer + Sources


                EVALUATION

CUAD Ground Truth
      ↓
Evaluation Cases
      ↓
Run RAG
      ↓
Compare
      ↓
Metrics
```

---

# 10. Điều cần nhớ

## Retrieval

```text
Question → relevant chunks
```

## Generation

```text
Question + relevant chunks → answer
```

## Evaluation

```text
System output + ground truth → metrics
```

Ba tầng này phải tách nhau để debug.

Nếu Retrieval sai:

```text
→ kiểm tra chunk / embedding / vector search
```

Nếu Retrieval đúng nhưng answer sai:

```text
→ kiểm tra prompt / generation
```

Nếu cả hai chạy được:

```text
→ Evaluation cho biết baseline tốt tới đâu
```

---

# 11. Bước tiếp theo

Sau khi có baseline metrics:

```text
9. Hybrid Search
```

Ý tưởng:

```text
Vector Search
+
Keyword / BM25 Search
    ↓
Combine Results
    ↓
Better Retrieval?
```

Sau đó:

```text
Hybrid Search
    ↓
Evaluation lại
    ↓
Compare với Vector-only baseline
```

Sau Hybrid Search mới tới:

```text
10. Reranker
```

---

# 12. Tóm tắt hôm nay

Hôm nay đã hoàn thiện tư duy cho:

```text
6. Retrieval
7. LLM Generation
8. Evaluation
```

Pipeline hiện tại đã trở thành một Contract RAG V1 end-to-end có khả năng đo lường:

```text
Contract
    ↓
Chunk
    ↓
Embedding
    ↓
Vector DB
    ↓
Retrieve
    ↓
Generate
    ↓
Evaluate
```

Đây là baseline quan trọng trước khi tối ưu bằng Hybrid Search và Reranker.
