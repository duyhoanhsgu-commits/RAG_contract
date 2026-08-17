# Bước 4 — Embedding trong Contract RAG

## 1. Embedding là gì?

Embedding là quá trình biến một đoạn văn bản thành một vector số.

Ví dụ:

```text
"Either party may terminate this Agreement..."
```

được đưa qua embedding model:

```text
Text
 ↓
Embedding Model
 ↓
[0.021, -0.184, 0.763, 0.091, ...]
```

Dãy số này gọi là **embedding vector**.

Embedding vector không dùng để đọc lại thành text. Nó là một biểu diễn toán học để máy tính có thể so sánh **mức độ tương đồng về ý nghĩa** giữa các đoạn văn bản.

---

## 2. Tại sao RAG cần Embedding?

Giả sử trong contract có:

```text
Either party may terminate this Agreement upon thirty days written notice.
```

Nhưng user hỏi:

```text
Can either party end the agreement?
```

Keyword:

```text
end != terminate
```

Nhưng về nghĩa:

```text
end the agreement ≈ terminate the agreement
```

Embedding model cố gắng đặt hai đoạn này gần nhau trong vector space.

Nhờ vậy hệ thống có thể tìm theo **semantic meaning**, không chỉ theo từ khóa chính xác.

---

## 3. Embedding nằm ở đâu trong pipeline?

Pipeline hiện tại:

```text
Raw contracts
      ↓
Normalize
      ↓
contracts.jsonl
      ↓
Chunk + Metadata
      ↓
chunks.jsonl
      ↓
Embedding          ← BƯỚC 4
      ↓
Vector DB
      ↓
Retrieval
```

Bước 4 chỉ có một nhiệm vụ:

> Chuyển text của mỗi chunk thành vector.

---

## 4. Input của Embedding

Bạn đã có `chunks.jsonl`.

Ví dụ:

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
  "source_pdf": "ABC_SERVICE_AGREEMENT.pdf",
  "text": "Either party may terminate this Agreement..."
}
```

Không nên embed toàn bộ JSON.

---

## 5. Thứ gì nên được embed?

Baseline đơn giản nhất:

```python
embedding_text = chunk["text"]
```

Với Contract RAG, có thể thêm section title:

```python
def build_embedding_text(chunk):
    section = chunk.get("section")
    text = chunk["text"]

    if section:
        return f"Section: {section}\n\n{text}"

    return text
```

Ví dụ embedding input:

```text
Section: Termination for Cause

Either party may terminate this Agreement...
```

Điều này có thể giúp các query như:

```text
termination clause
termination for cause
how can the agreement be terminated
```

match tốt hơn.

---

## 6. Thứ gì không nên được embed?

Không nên trộn các metadata kỹ thuật vào embedding text:

```text
chunk_id
contract_id
chunk_index
source_pdf
source_txt
token_count
dataset_part
```

Ví dụ không nên:

```text
contract_id: contract_0042
chunk_index: 13
source_pdf: /data/foo/abc.pdf
token_count: 987

Either party may terminate...
```

Các field này dùng để:

```text
filter
trace source
citation
debug
```

không phải để biểu diễn semantic meaning.

---

## 7. Text và Metadata có vai trò khác nhau

Một chunk có thể hình dung:

```text
                  CHUNK
                    │
           ┌────────┴────────┐
           │                 │
          TEXT            METADATA
           │                 │
           ▼                 ▼
       EMBEDDING          giữ nguyên
           │                 │
           └────────┬────────┘
                    ▼
                Vector DB
```

Text được biến thành vector.

Metadata được giữ nguyên để search/filter/trace về sau.

---

## 8. Một chunk tạo ra một vector

Baseline:

```text
chunk_001 → vector_001
chunk_002 → vector_002
chunk_003 → vector_003
```

Không nên:

```text
1 contract dài 40,000 từ
        ↓
1 vector duy nhất
```

Vì một contract có thể chứa:

```text
Definitions
Term
Termination
Confidentiality
Governing Law
Renewal
Exclusivity
...
```

Nếu cả contract chỉ có một vector, vector đó quá tổng quát.

Chunk-level embedding giúp retrieval tìm đúng clause hơn.

---

## 9. Query cũng phải được Embedding

Không chỉ document.

Khi user hỏi:

```text
How can either party terminate the agreement?
```

query cũng phải đi qua embedding model:

```text
Query
 ↓
Embedding Model
 ↓
Query Vector
```

Sau đó query vector mới được so sánh với chunk vectors.

---

## 10. Document và Query phải dùng cùng Embedding Model

Đây là rule cực kỳ quan trọng.

Đúng:

```text
Chunks
   ↓
Embedding Model A
   ↓
Vectors


Query
   ↓
Embedding Model A
   ↓
Query Vector
```

Sai:

```text
Chunks → Model A

Query → Model B
```

Hai model có thể tạo vector space hoàn toàn khác nhau.

Vector của Model A không nên được so trực tiếp với vector của Model B.

---

## 11. Vector Space là gì?

Có thể tưởng tượng mỗi embedding là một điểm trong không gian nhiều chiều.

Ví dụ rất đơn giản:

```text
Termination clause     ●
                       ● End agreement

Confidentiality clause                     ●
```

Các đoạn gần nghĩa sẽ có vị trí gần nhau hơn.

Trong thực tế vector có thể có hàng trăm hoặc hàng nghìn chiều, chứ không phải 2 chiều như hình dung trên.

---

## 12. Embedding Dimension

Embedding model trả về vector có số chiều cố định.

Ví dụ:

```text
dimension = 768
```

nghĩa là:

```text
[float_1, float_2, ..., float_768]
```

Một model khác có thể:

```text
dimension = 1024
dimension = 1536
dimension = 3072
```

Dimension lớn hơn **không đồng nghĩa** chắc chắn tốt hơn.

Chất lượng phụ thuộc vào model và dataset.

---

## 13. Similarity là gì?

Sau khi có:

```text
Query Vector
Chunk Vector A
Chunk Vector B
Chunk Vector C
```

ta cần đo vector nào gần query nhất.

Một metric phổ biến là:

```text
Cosine Similarity
```

Về tư duy:

```text
Query:
"Can the agreement be terminated?"
```

Chunk A:

```text
"Either party may terminate this Agreement..."
```

→ similarity cao.

Chunk B:

```text
"The receiving party shall keep information confidential..."
```

→ similarity thấp hơn.

---

## 14. Embedding khác với LLM như thế nào?

Embedding model:

```text
Text
 ↓
Vector
```

Không tạo câu trả lời.

LLM generation:

```text
Question + Retrieved Context
 ↓
LLM
 ↓
Answer
```

Hai nhiệm vụ hoàn toàn khác nhau.

---

## 15. Embedding không phải Retrieval

Embedding:

```text
Text → Vector
```

Retrieval:

```text
Query Vector
 ↓
compare với stored vectors
 ↓
Top-K chunks
```

Do đó:

```text
Embedding ≠ Vector Search
```

Embedding chỉ tạo representation.

Vector DB / Retriever mới tìm kiếm.

---

## 16. Test Embedding trước khi ingest toàn bộ

Trước khi embed toàn dataset, nên test nhỏ.

Ví dụ:

```text
A:
Either party may terminate this Agreement...

B:
This Agreement may be ended by either party...

C:
The receiving party shall keep information confidential...
```

Kỳ vọng:

```text
similarity(A, B) > similarity(A, C)
```

Nếu kết quả này hợp lý, embedding đang biểu diễn semantic meaning theo hướng mong muốn.

---

## 17. Test với Query thật

Ví dụ query:

```text
How can either party terminate the agreement?
```

Embed query và một nhóm chunks.

Sort similarity giảm dần.

Output mong muốn:

```text
1. Termination                0.89
2. Termination for Cause      0.84
3. Term                       0.61
4. Confidentiality            0.31
```

Không cần Vector DB để test bước này.

Có thể tính similarity trực tiếp trong Python.

---

## 18. Batch Embedding

Sau khi test ổn, không nên gọi embedding API từng chunk nếu provider hỗ trợ batch.

Không tốt:

```python
for chunk in chunks:
    embed_text(chunk["text"])
```

Tốt hơn:

```python
texts = [...]
vectors = embed_batch(texts)
```

Ví dụ:

```text
12,000 chunks
```

Nếu 1 request/chunk:

```text
12,000 requests
```

Nếu batch 50 chunks:

```text
~240 requests
```

Batch giúp:

- giảm request overhead;
- nhanh hơn;
- dễ kiểm soát rate limit;
- giảm khả năng lỗi mạng;
- dễ retry.

Batch size thực tế tùy provider/model.

---

## 19. Retry và Rate Limit

Embedding API có thể lỗi:

```text
429 Too Many Requests
timeout
network error
provider temporarily unavailable
```

Pipeline ingestion nên có retry đơn giản.

Ví dụ:

```text
attempt 1
 ↓ fail
wait
 ↓
attempt 2
 ↓ fail
wait lâu hơn
 ↓
attempt 3
```

Không cần hệ thống retry phức tạp ở MVP.

---

## 20. Có cần lưu embeddings thành JSONL không?

Không bắt buộc.

Có thể tưởng tượng:

```text
chunks.jsonl
    ↓
Embedding
    ↓
chunks_with_embeddings.jsonl
```

nhưng thực tế nếu vector cuối cùng được đưa vào Vector DB thì file trung gian này thường không cần.

Pipeline gọn hơn:

```text
chunks.jsonl
    ↓
Embedding Model
    ↓
Vector DB
```

---

## 21. Không embed Ground Truth CUAD vào Knowledge Base

Các file như:

```text
master_clauses.csv
CUAD_v1.json
```

nên được giữ cho Evaluation.

Không nên biến annotation/answer của CUAD thành vector retrieval nếu mục tiêu là benchmark hệ thống một cách công bằng.

Knowledge base:

```text
raw contract chunks
```

Ground truth:

```text
CUAD annotations
```

Hai thứ nên tách biệt.

---

## 22. Embedding Adapter

Nên có một interface đơn giản.

Ví dụ:

```python
class Embedder:
    def embed_text(self, text: str) -> list[float]:
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...
```

Lợi ích:

Nếu sau này đổi:

```text
Gemini Embedding
→ local embedding
→ model khác
```

các tầng phía trên không phải sửa nhiều.

---

## 23. `build_embedding_text()` nên tách riêng

Ví dụ:

```python
def build_embedding_text(chunk: dict) -> str:
    section = chunk.get("section")
    text = chunk["text"]

    if section:
        return f"Section: {section}\n\n{text}"

    return text
```

Sau này bạn có thể làm experiment:

```text
Experiment A:
embed(text)

Experiment B:
embed(section + text)
```

mà không sửa cả pipeline.

---

## 24. Điều cần ghi lại khi dùng Embedding Model

Ít nhất nên biết:

```text
provider
model_name
embedding_dimension
max_input_tokens
batch support
```

Và quan trọng:

> Khi đổi embedding model cho documents, thường phải re-embed toàn bộ collection.

Vì vector space đã thay đổi.

---

## 25. Không chọn Model bằng cảm giác

Một model được quảng cáo tốt chưa chắc tốt nhất cho Contract RAG.

Sau này nên dùng Evaluation:

```text
Model A
Recall@5 = 72%

Model B
Recall@5 = 81%
```

rồi quyết định dựa trên dataset thực tế.

Ở bước 4 chỉ cần một baseline tốt và ổn định.

---

## 26. Bước 4 hoàn thành khi nào?

Bước Embedding hoàn thành về mặt hiểu biết khi bạn chứng minh được:

```text
Text
 ↓
Embedding
 ↓
Vector
```

và:

```text
Query
 ↓
Same Embedding Model
 ↓
Query Vector
 ↓
Similarity
 ↓
Relevant chunks đứng cao hơn irrelevant chunks
```

Sau khi test ổn, bạn có thể đưa toàn bộ vectors vào Vector DB.

---

## 27. Checklist Bước 4

- [ ] Có embedding model hoạt động
- [ ] Có `embed_text()`
- [ ] Có `embed_batch()` nếu provider hỗ trợ
- [ ] Có `build_embedding_text()`
- [ ] Không embed metadata kỹ thuật
- [ ] Document và query dùng cùng model
- [ ] Test semantic similarity trên vài chunks
- [ ] Query termination tìm đúng termination chunks
- [ ] Biết embedding dimension
- [ ] Có retry cơ bản nếu dùng API
- [ ] Không đưa CUAD ground truth vào knowledge base
- [ ] Sẵn sàng ingest vectors vào Vector DB

---

## 28. Tư duy cần nhớ

Embedding chỉ trả lời:

> "Làm sao biểu diễn meaning của text thành numbers?"

Nó **không trả lời user** và cũng **chưa search dữ liệu**.

Toàn bộ bước 4 có thể tóm lại:

```text
chunk text
    ↓
embedding model
    ↓
vector
```

Bước tiếp theo là:

```text
vector
+
text
+
metadata
    ↓
Vector DB
```
