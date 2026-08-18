# Bước 7 — LLM Generation trong Contract RAG

## 1. LLM Generation là gì?

Sau Retrieval, hệ thống đã có những chunks có khả năng chứa câu trả lời.

LLM Generation là bước:

```text
Question
+
Retrieved Chunks
+
Prompt
    ↓
LLM
    ↓
Answer + Sources
```

Retrieval quyết định:

```text
LLM được nhìn thấy thông tin gì?
```

Generation quyết định:

```text
Từ context đó, trả lời user như thế nào?
```

---

## 2. Flow đầy đủ

```text
User Question
    ↓
Retriever
    ↓
Top-K Chunks
    ↓
Prompt Builder
    ↓
LLM
    ↓
Answer
    +
Sources
```

Ví dụ:

```text
Question:
How can either party terminate the agreement?
```

Retriever trả:

```text
[Source 1]
Section 8 - TERM AND TERMINATION
...
```

LLM dựa vào context để tạo câu trả lời.

---

## 3. Input của Generation

Interface baseline:

```python
generate_answer(
    query: str,
    retrieved_chunks: list[RetrievalResult]
) -> RAGAnswer
```

Generation không cần tự search DB.

Nó chỉ nhận:

```text
query
+
retrieved_chunks
```

Retriever và Generator nên tách riêng.

---

## 4. System Prompt baseline

Contract RAG cần ép LLM chỉ trả lời dựa trên context.

Baseline:

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

Mục tiêu chính:

```text
Grounded Answer
```

Không phải:

```text
LLM dùng kiến thức pháp lý bên ngoài để đoán.
```

---

## 5. Format Context

Không nên chỉ nối raw text:

```python
context = "\n".join(chunk.text for chunk in chunks)
```

Nên giữ identifier của source.

Ví dụ:

```text
[Source 1]
chunk_id: contract_0001_chunk_0008
section: 8 TERM AND TERMINATION

Either party may terminate this Agreement...


[Source 2]
chunk_id: contract_0001_chunk_0010
section: 12 GENERAL PROVISIONS

...
```

Sau đó:

```text
QUESTION:
How can either party terminate the agreement?
```

Nhờ vậy model có thể reference:

```text
[Source 1]
```

thay vì tự bịa source.

---

## 6. Citation phải trace được

Một nguyên tắc rất quan trọng:

> Metadata source phải lấy từ RetrievalResult, không để LLM tự tạo metadata.

Ví dụ Retriever có:

```json
{
  "chunk_id": "contract_0001_chunk_0008",
  "contract_id": "contract_0001",
  "section": "8 TERM AND TERMINATION",
  "source_pdf": "contract.pdf"
}
```

LLM chỉ cần nói:

```text
[Source 1]
```

Backend sẽ map:

```text
Source 1
   ↓
contract_0001_chunk_0008
   ↓
source_pdf
```

Không nên yêu cầu LLM tự bịa:

```text
page 12
section 8.2
filename abc.pdf
```

nếu những field đó không có chắc chắn trong metadata.

---

## 7. Output Schema

Không nên chỉ return một string nếu muốn debug và evaluation tốt.

Ví dụ:

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

Output:

```json
{
  "answer": "Either party may terminate the agreement if ...",
  "sources": [
    {
      "chunk_id": "contract_0001_chunk_0008",
      "contract_id": "contract_0001",
      "section": "8 TERM AND TERMINATION",
      "source_pdf": "..."
    }
  ]
}
```

---

## 8. Abstention — khi context không đủ

LLM không được cố trả lời mọi câu hỏi.

Ví dụ:

```text
Question:
What is the CEO's home address?
```

Nếu retrieved context không có thông tin đó:

```text
The provided contract context does not contain enough information to answer this question.
```

Đây là behavior đúng.

Không được:

```text
LLM đoán từ kiến thức ngoài contract.
```

---

## 9. Preserve Legal Details

Contract QA rất nhạy với các chi tiết như:

```text
60 days
30 days
written notice
material breach
exceptions
survival clauses
conditions
```

Prompt phải yêu cầu model giữ:

- điều kiện;
- ngoại lệ;
- thời hạn;
- nghĩa vụ;
- trigger;
- quyền và trách nhiệm của các bên.

Ví dụ không nên rút gọn:

```text
A party may terminate for breach.
```

nếu context thực tế nói:

```text
material breach
+
written notice
+
60-day cure period
```

Generation phải giữ những điều kiện này.

---

## 10. Không đưa toàn bộ contract cho LLM

Không cần:

```text
Question
+
50,000-word contract
    ↓
LLM
```

Bạn đã làm Retrieval để có:

```text
Question
    ↓
Top 5 relevant chunks
    ↓
LLM
```

Lợi ích:

- ít token hơn;
- nhanh hơn;
- ít noise hơn;
- dễ trace;
- dễ debug;
- dễ evaluate.

---

## 11. RAG Service

Sau khi Retrieval và Generation tách riêng, có thể tạo service tổng:

```python
def answer_question(
    query: str,
    contract_id: str | None = None,
    top_k: int = 5,
):
    filters = None

    if contract_id:
        filters = {
            "contract_id": contract_id
        }

    chunks = retriever.retrieve(
        query=query,
        filters=filters,
        top_k=top_k,
    )

    return generator.generate_answer(
        query=query,
        retrieved_chunks=chunks,
    )
```

Flow:

```text
answer_question()
    ↓
Retriever
    ↓
Generator
    ↓
RAGAnswer
```

---

## 12. Kiến trúc code đề xuất

```text
rag/
├── retrieval/
│   ├── retriever.py
│   ├── vector_store.py
│   └── schemas.py
│
├── generation/
│   ├── generator.py
│   ├── prompts.py
│   └── schemas.py
│
└── rag_service.py
```

Không cần thêm:

```text
agent
reranker
hybrid search
query rewriting
CUAD evaluation
```

ở bước này.

---

## 13. Test Generation

Dùng cùng query đã test Retrieval:

```text
How can either party terminate the agreement?
```

Flow:

```text
query
  ↓
retrieve top 5
  ↓
build context
  ↓
LLM
  ↓
answer + sources
```

Kiểm tra:

```text
✅ Answer dựa trên retrieved context

✅ Không thêm kiến thức ngoài contract

✅ Giữ đúng thời hạn và điều kiện

✅ Citation map được về chunk

✅ Nếu context không đủ thì model biết từ chối
```

---

## 14. Debug theo từng tầng

Nếu answer sai, cần tách lỗi:

### Case 1 — Retrieval sai

```text
Retriever không lấy được clause đúng
```

→ sửa Retrieval / Embedding / Chunking.

### Case 2 — Retrieval đúng nhưng LLM trả lời sai

```text
Correct chunk
    ↓
Wrong answer
```

→ sửa Prompt / Generation.

Đây là lý do Retrieval và Generation phải được tách riêng.

---

## 15. Generation chưa được dùng CUAD Ground Truth

Ở bước này:

```text
LLM chỉ nhìn:
question
+
retrieved chunks
```

Không được nhìn:

```text
CUAD answer
CUAD clause label
expected answer
master_clauses ground truth
```

Nếu đưa ground truth vào prompt thì Evaluation sau này không còn công bằng.

---

## 16. Contract RAG V1 sau bước này

Sau Generation, pipeline trở thành:

```text
OFFLINE / INGESTION

Raw Contracts
    ↓
Normalize
    ↓
Chunk + Metadata
    ↓
Embedding
    ↓
Vector DB


ONLINE / QUERY

User Question
    ↓
Retriever
    ↓
Top-K Chunks
    ↓
Prompt Builder
    ↓
LLM
    ↓
Answer + Sources
```

Đây là phiên bản Contract RAG end-to-end đầu tiên.

---

## 17. Definition of Done

Generation hoàn thành khi hệ thống có thể:

```text
Question
    ↓
Retrieve Top-K
    ↓
Build Context
    ↓
LLM
    ↓
Grounded Answer
    +
Traceable Sources
```

và đảm bảo:

```text
✅ chỉ trả lời từ retrieved context
✅ không tự bịa thông tin
✅ không đủ context thì abstain
✅ giữ chi tiết pháp lý quan trọng
✅ source trace được về chunk gốc
```

Sau bước này, bước tiếp theo là:

```text
8. Evaluation
```

Lúc đó mới bắt đầu sử dụng:

```text
CUAD_v1.json
master_clauses.csv
```

để đo Retrieval và Generation thực sự tốt đến đâu.
