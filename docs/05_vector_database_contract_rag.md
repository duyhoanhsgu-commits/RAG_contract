# Bước 5 — Vector Database trong Contract RAG

## 1. Vector DB là gì?

Vector Database là nơi lưu embedding vectors và cho phép tìm các vector gần query vector nhất.

Sau bước Embedding:

```text
Chunk Text
    ↓
Embedding Model
    ↓
Vector
```

Bây giờ cần nơi lưu:

```text
vector
+
original text
+
metadata
```

Đó là vai trò của Vector DB.

---

## 2. Vector DB nằm ở đâu trong pipeline?

```text
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
Vector DB          ← BƯỚC 5
      ↓
Retrieval
      ↓
LLM
```

---

## 3. Vector DB không chỉ lưu Vector

Một record nên có tối thiểu:

```text
id
embedding
document/text
metadata
```

Ví dụ logic:

```json
{
  "id": "contract_0042_chunk_0013",
  "embedding": [0.021, -0.184, 0.763, 0.091],
  "text": "Either party may terminate this Agreement...",
  "metadata": {
    "contract_id": "contract_0042",
    "chunk_index": 13,
    "contract_type": "Service",
    "section": "Termination for Cause",
    "source_pdf": "ABC_SERVICE_AGREEMENT.pdf"
  }
}
```

---

## 4. Vai trò của từng thành phần

### `id`

Dùng để định danh chunk.

Nên dùng:

```text
chunk_id
```

Ví dụ:

```text
contract_0042_chunk_0013
```

### `embedding`

Dùng để semantic search.

### `text`

Dùng để:

- đưa context cho LLM;
- hiển thị search result;
- debug retrieval.

### `metadata`

Dùng để:

- filter;
- citation;
- trace source;
- giới hạn search scope.

---

## 5. Vì sao không thể chỉ lưu Vector?

Nếu chỉ có:

```text
[0.021, -0.184, ...]
```

khi search ra bạn không biết:

```text
vector này là đoạn văn nào?
thuộc contract nào?
section nào?
PDF nào?
```

Do đó:

```text
Vector = search
Text = context
Metadata = identity/source/filter
```

Ba thứ đều cần thiết.

---

## 6. Collection là gì?

Trong ChromaDB/Qdrant và nhiều Vector DB, vectors được nhóm vào một collection/index.

Ví dụ:

```text
collection:
contract_chunks
```

Bên trong:

```text
contract_0001_chunk_0000
contract_0001_chunk_0001
contract_0002_chunk_0000
...
```

Ở MVP, một collection cho toàn bộ contract chunks là đủ.

---

## 7. Có cần một Vector DB cho mỗi Contract không?

Không.

Không nên:

```text
contract_1 → DB 1
contract_2 → DB 2
contract_3 → DB 3
```

Thay vào đó:

```text
                 contract_chunks collection
                         │
        ┌────────────────┼─────────────────┐
        │                │                 │
    Contract A       Contract B        Contract C
```

Mỗi record có:

```text
contract_id
```

trong metadata.

Khi cần search một contract cụ thể:

```text
filter contract_id = contract_0042
```

---

## 8. Metadata Filter

Giả sử database có:

```text
15,000 chunks
```

User đang xem:

```text
contract_0042
```

và hỏi:

```text
What are the termination conditions?
```

Không nhất thiết search toàn bộ 15,000 chunks.

Có thể:

```text
Filter:
contract_id = contract_0042
```

rồi semantic search trong các chunks của contract đó.

Flow:

```text
All vectors
    ↓
Metadata Filter
    ↓
Relevant scope
    ↓
Vector Similarity
    ↓
Top-K
```

---

## 9. Một collection cho MVP

Với project hiện tại:

```text
contract_chunks
```

là đủ.

Chưa cần:

```text
termination_collection
service_collection
license_collection
franchise_collection
...
```

`contract_type` đã nằm trong metadata.

Filter metadata tốt hơn việc tạo hàng chục collection không cần thiết.

---

## 10. Ingestion là gì?

Ingestion ở bước này nghĩa là:

> Đưa toàn bộ chunks đã embed vào Vector DB.

Pipeline:

```text
chunks.jsonl
     ↓
build_embedding_text
     ↓
Embedding Model
     ↓
Vector
     ↓
Vector DB upsert
```

---

## 11. Input của bước 5

Input:

```text
data/processed/chunks.jsonl
```

Ví dụ chunk:

```json
{
  "chunk_id": "contract_0042_chunk_0013",
  "contract_id": "contract_0042",
  "chunk_index": 13,
  "contract_type": "Service",
  "dataset_part": "Part_I",
  "section": "Termination for Cause",
  "section_number": "8.2",
  "token_count": 987,
  "source_txt": "...",
  "source_pdf": "...",
  "text": "Either party may terminate..."
}
```

---

## 12. Record đưa vào Vector DB

Logic:

```text
id
=
chunk_id
```

```text
embedding
=
embed(build_embedding_text(chunk))
```

```text
document
=
chunk["text"]
```

```text
metadata
=
contract_id
chunk_index
contract_type
dataset_part
section
section_number
token_count
source_txt
source_pdf
```

---

## 13. Không cần lưu vector vào JSONL trung gian

Không bắt buộc:

```text
chunks.jsonl
    ↓
chunks_with_embeddings.jsonl
    ↓
Vector DB
```

Có thể làm trực tiếp:

```text
chunks.jsonl
    ↓
Embedding
    ↓
Vector DB
```

Điều này đơn giản hơn và tránh file JSON chứa hàng triệu số float.

---

## 14. Upsert là gì?

`upsert` = update nếu ID đã tồn tại, insert nếu chưa tồn tại.

Ví dụ:

```text
chunk_id = contract_0042_chunk_0013
```

Lần đầu:

```text
insert
```

Chạy ingestion lại:

```text
update / replace
```

không tạo duplicate.

Đây là lý do nên dùng `chunk_id` deterministic.

---

## 15. Vì sao ingestion phải idempotent?

Idempotent nghĩa là:

> Chạy một lần hay chạy lại nhiều lần vẫn không tạo dữ liệu duplicate ngoài ý muốn.

Nếu ingestion crash giữa chừng, bạn có thể chạy lại.

Không muốn:

```text
12,000 chunks
↓ chạy lại
24,000 records
```

Đúng hơn:

```text
12,000 chunks
↓ chạy lại
12,000 records
```

---

## 16. Batch Ingestion

Không nên:

```text
chunk
 ↓
embedding API
 ↓
DB
 ↓
chunk tiếp
```

từng cái một nếu provider hỗ trợ batch.

Nên:

```text
Batch 1: 32 chunks
↓
embed_batch
↓
upsert 32

Batch 2: 32 chunks
↓
embed_batch
↓
upsert 32
```

Điều này nhanh và dễ quản lý hơn.

---

## 17. Retry

Nếu embedding API fail:

```text
429
timeout
network issue
```

nên retry batch.

Nếu DB insert fail cũng phải log rõ.

Không nên:

```python
try:
    ...
except:
    pass
```

vì bạn có thể nghĩ đã ingest đủ trong khi thực tế mất hàng trăm chunks.

---

## 18. Verify Count

Sau ingestion phải kiểm tra.

Ví dụ:

```text
Input chunks: 12,482
```

Vector DB:

```text
Collection count: 12,482
```

Kỳ vọng:

```text
input_count == db_count
```

Nếu không khớp, cần tìm:

```text
duplicate IDs?
invalid chunks?
empty text?
failed batches?
```

---

## 19. Smoke Test

Sau khi DB đã có dữ liệu, test một query.

Ví dụ:

```text
How can either party terminate the agreement?
```

Flow:

```text
Query
 ↓
Same Embedding Model
 ↓
Query Vector
 ↓
Vector DB
 ↓
Top 5 nearest chunks
```

Output mong muốn:

```text
#1
section: Termination
score: 0.89

#2
section: Termination for Cause
score: 0.84

#3
section: Term
score: 0.63
```

Nếu kết quả hợp lý thì Vector DB hoạt động.

---

## 20. Top-K là gì?

`Top-K` nghĩa là lấy K kết quả gần nhất.

Ví dụ:

```text
top_k = 5
```

Vector DB trả:

```text
chunk 1
chunk 2
chunk 3
chunk 4
chunk 5
```

Top-K sẽ được bàn kỹ hơn ở bước Retrieval.

Ở bước 5 chỉ cần biết DB có thể trả nearest neighbors.

---

## 21. Score và Distance

Tùy Vector DB, kết quả có thể trả:

```text
similarity score
```

hoặc:

```text
distance
```

Không nên mặc định:

```text
score càng lớn luôn càng tốt
```

mà phải đọc semantics của DB/metric đang dùng.

Ví dụ một DB trả cosine similarity:

```text
cao hơn = gần hơn
```

DB khác có thể trả distance:

```text
thấp hơn = gần hơn
```

Cần hiểu API cụ thể.

---

## 22. Vector Distance Metric

Các metric thường gặp:

```text
cosine
dot product
euclidean / L2
```

Không cần tối ưu metric ngay ở MVP.

Quan trọng là document vectors và query vectors dùng đúng embedding model và metric phù hợp với Vector DB/model.

---

## 23. ChromaDB hay Qdrant?

Cho local MVP, cả hai đều ổn.

### ChromaDB

Phù hợp khi:

- muốn setup nhanh;
- project nhỏ;
- chạy local;
- học RAG;
- chưa cần hệ thống DB phức tạp.

### Qdrant

Phù hợp khi:

- muốn Vector DB rõ ràng hơn;
- filter metadata mạnh;
- có khả năng mở rộng service/server về sau.

Ở giai đoạn học, chọn một cái và giữ baseline.

Không cần đổi DB liên tục.

---

## 24. Vector DB không phải Database thay thế tất cả

Vector DB rất tốt cho:

```text
semantic similarity
nearest neighbor search
```

Nhưng không có nghĩa mọi dữ liệu phải đưa vào Vector DB.

Ví dụ dữ liệu transaction, user, booking, permission... vẫn phù hợp với relational database hơn.

Trong Contract RAG:

```text
Vector DB
→ contract chunks for retrieval
```

Không phải toàn bộ application database.

---

## 25. Vector DB không phải LLM Memory

Vector DB chứa knowledge chunks không đồng nghĩa với chat memory.

Hai khái niệm khác nhau.

```text
Vector DB
→ tìm tài liệu
```

```text
Conversation Memory
→ giữ context hội thoại
```

Không nên trộn hai thứ khi thiết kế hệ thống.

---

## 26. Source Text phải giữ nguyên

Document được lưu trong DB nên là original chunk text:

```python
document = chunk["text"]
```

Không nhất thiết là:

```python
document = build_embedding_text(chunk)
```

Ví dụ:

Embedding input:

```text
Section: Termination

Either party may terminate...
```

Original document:

```text
Either party may terminate...
```

Điều này giúp context đưa cho LLM sạch hơn.

---

## 27. Metadata `None`

Một số Vector DB không thích metadata:

```json
{
  "section": null
}
```

Có thể normalize:

```python
metadata = {
    key: value
    for key, value in metadata.items()
    if value is not None
}
```

Không cần biến tất cả thành string nếu DB hỗ trợ numeric/bool.

---

## 28. Source PDF

Nên giữ:

```text
source_pdf
```

để sau này:

```text
retrieval result
    ↓
answer
    ↓
source
    ↓
open original PDF
```

Không cần page number nếu chưa có mapping chính xác.

Không bịa page.

---

## 29. Ground Truth vẫn không vào Vector DB

Knowledge collection:

```text
contract_chunks
```

chỉ chứa chunks từ raw contracts.

Không đưa:

```text
master_clauses.csv answers
CUAD_v1.json expected answers
```

vào cùng collection nếu bạn muốn dùng chúng để Evaluation.

---

## 30. Script Ingestion

Có thể có:

```text
scripts/
└── ingest_vector_db.py
```

Nhiệm vụ:

```text
read chunks.jsonl
↓
batch
↓
embedding
↓
upsert
↓
verify count
```

Không cần làm:

```text
LLM generation
RAG answer
hybrid search
reranker
agent
```

---

## 31. Vector Store Wrapper

Có thể có abstraction mỏng:

```python
class VectorStore:
    def upsert(self, ...):
        ...

    def search(self, ...):
        ...

    def count(self) -> int:
        ...
```

Không cần 5 tầng class.

Mục tiêu là nếu sau này đổi:

```text
Chroma → Qdrant
```

thì code phía trên ít thay đổi hơn.

---

## 32. Flow hoàn chỉnh của Bước 5

```text
                 chunks.jsonl
                       │
                       ▼
             build_embedding_text
                       │
                       ▼
                embed_batch()
                       │
                       ▼
             ┌──────────────────┐
             │    Vector DB     │
             │                  │
             │ id               │
             │ vector           │
             │ text             │
             │ metadata         │
             └────────┬─────────┘
                      │
                      ▼
                 verify count
                      │
                      ▼
                 smoke search
```

---

## 33. Bước 5 hoàn thành khi nào?

Khi bạn làm được:

```text
chunks.jsonl
    ↓
embedding
    ↓
Vector DB
```

và xác nhận:

1. tất cả chunks đã được lưu;
2. không duplicate khi chạy lại;
3. mỗi vector trace được về original chunk;
4. metadata đúng;
5. query vector search trả được semantic chunks hợp lý.

---

## 34. Checklist Bước 5

- [ ] Tạo Vector DB/collection
- [ ] Collection có tên rõ ràng, ví dụ `contract_chunks`
- [ ] Dùng `chunk_id` làm record ID
- [ ] Lưu vector
- [ ] Lưu original chunk text
- [ ] Lưu metadata
- [ ] Metadata giữ `contract_id`
- [ ] Metadata giữ `contract_type`
- [ ] Metadata giữ `section`
- [ ] Metadata giữ source
- [ ] Embed theo batch
- [ ] Upsert thay vì duplicate insert
- [ ] Retry lỗi cơ bản
- [ ] Verify record count
- [ ] Test một semantic query
- [ ] Không đưa CUAD ground truth vào collection

---

## 35. Tư duy quan trọng nhất

Embedding trả lời:

> Text này được biểu diễn thành vector nào?

Vector DB trả lời:

> Với query vector này, những stored vectors nào gần nhất?

Hai bước khác nhau:

```text
Embedding
=
Text → Vector
```

```text
Vector DB
=
Store Vector + Search Nearest Vectors
```

Sau khi Vector DB hoạt động, bước tiếp theo là **Retrieval**.

Retrieval sẽ biến việc test search thủ công thành một component rõ ràng:

```python
retrieve(query, filters=None, top_k=5)
```

và chịu trách nhiệm lấy context phù hợp cho LLM.
