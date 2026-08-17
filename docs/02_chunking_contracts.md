# Bước 2 — Chunking Contract Documents

## 1. Mục tiêu của Chunking

Một contract có thể dài từ vài trăm từ đến hàng chục nghìn từ.

Không thể đưa toàn bộ contract vào retrieval như một unit duy nhất.

Chunking nghĩa là:

> Chia một document lớn thành các đoạn nhỏ đủ độc lập để retrieval tìm thấy đúng phần liên quan.

Pipeline:

```text
contracts.jsonl
       ↓
     chunk
       ↓
chunks.jsonl
```

---

# 2. Tại sao phải chunk?

Giả sử một contract có:

```text
45,000 words
```

User hỏi:

```text
What are the termination conditions?
```

Bạn không muốn retrieval trả về toàn bộ 45,000 words.

Bạn muốn:

```text
Termination section
        ↓
1–3 chunks liên quan
```

rồi mới đưa chúng cho LLM.

Đây là mục đích cốt lõi của RAG.

---

# 3. Không chunk theo số lượng file

Sai:

```text
mỗi contract chia thành 10 chunks
```

Vì:

```text
Contract A = 600 words
Contract B = 5,000 words
Contract C = 47,000 words
```

Không thể dùng cùng số chunk.

Đúng hơn:

```text
Contract ngắn
→ ít chunk

Contract dài
→ nhiều chunk
```

---

# 4. Không chunk theo character một cách mù quáng

Ví dụ:

```python
text[0:5000]
text[5000:10000]
text[10000:15000]
```

Có thể cắt giữa câu:

```text
Either party may terminate this Agreement
if the other party fails to...

---------------- CHUNK ----------------

...cure such breach within thirty days.
```

Kết quả là cả hai chunk đều mất context.

---

# 5. Không nên dùng word count làm đơn vị chính

LLM và embedding model làm việc theo token.

```text
word != token
```

Do đó:

```text
1000 words
```

không phải lúc nào cũng tương đương cùng một lượng input.

Nên chunk theo token count của tokenizer phù hợp với embedding model.

---

# 6. Kiểu chunking phù hợp cho dataset contract

Baseline nên dùng:

> **Structure-aware recursive token chunking**

Ba ý trong tên này:

## Structure-aware

Ưu tiên tôn trọng cấu trúc contract:

```text
ARTICLE
SECTION
SUBSECTION
PARAGRAPH
SENTENCE
```

## Recursive

Nếu một section quá dài:

```text
section
  ↓
paragraph
  ↓
sentence
```

Tức chia nhỏ dần cho đến khi đạt giới hạn.

## Token-based

Mỗi chunk vẫn phải có giới hạn token rõ ràng.

---

# 7. Baseline nên bắt đầu

Đề xuất ban đầu:

```text
target_chunk_size = 1000 tokens
max_chunk_size    = 1200 tokens
overlap           = 100–150 tokens
```

Một cấu hình cụ thể:

```text
target = 1000
max    = 1200
overlap = 120
```

Đây là baseline để đánh giá.

Không phải con số tối ưu tuyệt đối.

Sau này Eval mới quyết định:

```text
500
800
1000
1200
1500
```

cái nào tốt nhất.

---

# 8. Document ngắn xử lý thế nào?

Ví dụ Joint Filing Agreement chỉ khoảng 109 words.

Nếu:

```text
document <= max_chunk_size
```

thì:

```text
1 document = 1 chunk
```

Không cần ép chia nhỏ.

Ví dụ:

```json
{
  "chunk_id": "contract_0183_chunk_0000",
  "contract_id": "contract_0183",
  "chunk_index": 0,
  "text": "Exhibit 99.1 JOINT FILING AGREEMENT...",
  "token_count": 160
}
```

---

# 9. Document dài xử lý thế nào?

Ví dụ:

```text
47,000 words
```

Có thể tạo hàng chục chunks.

Điều này hoàn toàn bình thường.

Ví dụ:

```text
contract_0042
├── chunk_000
├── chunk_001
├── chunk_002
├── ...
└── chunk_067
```

Không cần cố để mọi contract có số chunk giống nhau.

---

# 10. Section-aware chunking

Contract thường có dạng:

```text
1. DEFINITIONS

2. TERM

3. TERMINATION

3.1 Termination for Cause

3.2 Termination for Convenience

4. CONFIDENTIALITY
```

Nếu section nhỏ hơn max token:

```text
Termination section = 700 tokens
```

thì giữ cả section:

```text
chunk = toàn bộ Termination
```

Đây là trường hợp tốt.

---

# 11. Section quá dài

Ví dụ:

```text
Termination = 3000 tokens
```

Không thể giữ nguyên.

Ta làm:

```text
Termination
    ↓
split paragraphs
    ↓
gom paragraphs ~1000 tokens
```

Nếu một paragraph vẫn quá dài:

```text
paragraph
   ↓
split sentences
   ↓
gom sentences ~1000 tokens
```

Flow:

```text
Section
   ↓
<=1200 tokens?
 ├─ yes → giữ nguyên
 └─ no
      ↓
   Paragraph
      ↓
   <=1200?
    ├─ yes
    └─ no
         ↓
      Sentence
```

---

# 12. Overlap là gì?

Overlap là phần nội dung được lặp giữa hai chunk liền nhau.

Ví dụ:

```text
chunk 1:
token 0 → 1000

chunk 2:
token 880 → 1880
```

Overlap:

```text
120 tokens
```

Mục đích:

> Tránh mất ý khi clause nằm đúng ở ranh giới giữa hai chunk.

---

# 13. Ví dụ không có overlap

```text
Chunk 1:
Either party may terminate this Agreement if...

Chunk 2:
...the other party materially breaches and fails to cure...
```

Retriever có thể gặp khó vì ý bị chia.

---

# 14. Ví dụ có overlap

```text
Chunk 1:
Either party may terminate this Agreement if...

Chunk 2:
terminate this Agreement if the other party materially breaches...
```

Chunk 2 giữ lại context đầu câu.

---

# 15. Overlap không nên phá cấu trúc

Không nên vì muốn đủ 120 tokens overlap mà kéo:

```text
cuối Termination
+
đầu Confidentiality
```

vào cùng chunk nếu không cần thiết.

Ưu tiên:

```text
overlap trong cùng section
```

Nếu qua section boundary thì có thể reset overlap.

---

# 16. Chunk quá nhỏ

Ví dụ sau split còn chunk cuối:

```text
83 tokens
```

Có thể merge vào chunk trước nếu:

```text
merged_size <= max_chunk_size
```

Một rule đơn giản:

```text
if final_chunk < 150–200 tokens:
    merge_with_previous_if_safe()
```

Nhưng không được merge nếu làm lẫn hai section không liên quan.

---

# 17. Chunk không nên cắt giữa câu

Thứ tự boundary ưu tiên:

```text
1. section
2. subsection
3. paragraph
4. sentence
5. token hard split — fallback cuối cùng
```

Hard split chỉ nên là phương án cuối.

---

# 18. Không cần semantic chunking ở version đầu

Semantic chunking thường dùng embedding hoặc model để tìm điểm chuyển ngữ nghĩa.

Nó có thể tốt, nhưng:

- pipeline phức tạp hơn;
- chậm hơn;
- khó debug hơn;
- chưa chắc tốt hơn trên dataset của bạn;
- bạn chưa có baseline để so sánh.

Do đó:

```text
V1 = deterministic chunker
```

Sau khi có Eval mới thử semantic chunking.

---

# 19. Output của chunk nên có gì?

Tối thiểu:

```json
{
  "chunk_id": "contract_0001_chunk_0007",
  "contract_id": "contract_0001",
  "chunk_index": 7,
  "text": "Either party may terminate...",
  "token_count": 984
}
```

Ở bước 3 sẽ bổ sung metadata phong phú hơn.

---

# 20. `chunk_id`

Nên deterministic và dễ trace:

```text
contract_0001_chunk_0000
contract_0001_chunk_0001
contract_0001_chunk_0002
```

Sau này khi retrieval trả:

```text
contract_0001_chunk_0017
```

bạn biết chính xác nó đến từ đâu.

---

# 21. `chunk_index`

Là vị trí chunk trong document:

```text
0
1
2
3
...
```

Giúp:

- sắp xếp lại context;
- lấy chunk trước/sau;
- debug retrieval;
- mở rộng context window.

Ví dụ retrieval tìm chunk 17, bạn có thể sau này lấy:

```text
16 + 17 + 18
```

nếu cần neighboring context.

---

# 22. Không nên cố nhận diện clause bằng LLM ngay ở chunking

Ví dụ chưa nên:

```text
Gemini đọc mỗi chunk
↓
đoán clause_type
↓
Termination / Confidentiality / ...
```

Điều này:

- tốn token;
- chậm;
- khó tái lập;
- dễ leak ground truth;
- chưa cần thiết.

Chunker nên càng deterministic càng tốt.

---

# 23. Script nên có

```text
scripts/
└── chunk_contracts.py
```

Input:

```text
data/processed/contracts.jsonl
```

Output:

```text
data/processed/chunks.jsonl
```

---

# 24. Pseudocode tư duy

```text
for contract in contracts:

    text = contract.text

    detect structure

    for section in sections:

        if tokens(section) <= max:
            emit(section)

        else:
            split section into paragraphs

            group paragraphs near target size

            if paragraph too large:
                split by sentence

    add overlap where appropriate

    merge tiny trailing chunk if safe
```

---

# 25. Sau khi chunk xong phải thống kê lại

Không được tạo `chunks.jsonl` xong rồi nhảy ngay sang embedding.

Hãy đo:

```text
Total chunks
Average chunks per contract
Median chunks per contract
Min token/chunk
Max token/chunk
Average token/chunk
P90 token/chunk
Number of tiny chunks
Number of oversized chunks
```

---

# 26. Manual inspection

Đọc ngẫu nhiên khoảng 20–50 chunks.

Hỏi:

```text
Chunk có bị cắt giữa câu không?
Chunk đọc riêng có hiểu được không?
Clause có bị chia quá vụn không?
Header/footer có lặp không?
Chunk quá nhỏ không?
Chunk có trộn hai section không liên quan không?
```

Nếu bạn không đọc mẫu thì không biết chunker đang làm gì.

---

# 27. Baseline evaluation nhỏ trước embedding

Bạn có thể chọn vài queries bằng tay:

```text
termination
governing law
confidentiality
renewal
exclusivity
```

Rồi nhìn chunk bằng mắt xem:

```text
nếu search đúng section thì chunk này có đủ context để trả lời không?
```

Đây chưa phải retrieval eval chính thức, nhưng rất hữu ích.

---

# 28. Bước 2 hoàn thành khi nào?

Khi bạn có:

```text
contracts.jsonl
       ↓
chunk_contracts.py
       ↓
chunks.jsonl
```

và mỗi chunk:

- có ID;
- trace được về contract;
- không cắt câu bừa;
- có token count;
- nằm quanh target size;
- document ngắn được giữ nguyên;
- document dài sinh nhiều chunks;
- không có số lượng lớn tiny chunks hoặc giant chunks.

---

# 29. Checklist bước 2

- [ ] Chọn tokenizer
- [ ] Chọn target chunk size
- [ ] Chọn max chunk size
- [ ] Chọn overlap
- [ ] Ưu tiên section boundary
- [ ] Fallback paragraph
- [ ] Fallback sentence
- [ ] Không cắt giữa câu nếu tránh được
- [ ] Document ngắn → 1 chunk
- [ ] Merge tiny tail nếu hợp lý
- [ ] Tạo `chunk_id`
- [ ] Tạo `chunk_index`
- [ ] Ghi `token_count`
- [ ] Thống kê output
- [ ] Manual inspect ít nhất 20 chunks

---

# 30. Tư duy quan trọng nhất

Chunking không phải:

> “Cắt văn bản thành những miếng bằng nhau.”

Chunking là:

> “Tạo các đơn vị retrieval nhỏ nhưng vẫn giữ đủ ý nghĩa.”

Với legal contract, cấu trúc section và clause quan trọng hơn việc ép chunk đúng chính xác 1000 token.

---

# 31. Input và Output của bước 2

## Input

```text
contracts.jsonl
```

## Processing

```text
detect structure
split
group
token limit
overlap
```

## Output

```text
chunks.jsonl
```

Đây là dữ liệu sẽ được enrich ở bước 3 — Metadata — trước khi đưa sang Embedding.
